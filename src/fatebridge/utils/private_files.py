"""User-private artifact files and kernel locks on POSIX and Windows."""

import os
import stat
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


def default_result_directory() -> Path:
    if sys.platform == "win32":
        # A SID distinguishes users even if TEMP points at a shared directory.
        import win32security

        identity = win32security.ConvertSidToStringSid(_windows_user())
    else:
        identity = str(os.getuid())
    return Path(tempfile.gettempdir()) / f"fatebridge-results-{identity}"


def _windows_user() -> Any:
    import win32api
    import win32con
    import win32security

    token = win32security.OpenProcessToken(
        win32api.GetCurrentProcess(), win32con.TOKEN_QUERY
    )
    try:
        return win32security.GetTokenInformation(token, win32security.TokenUser)[0]
    finally:
        token.Close()


def _windows_security() -> Any:
    import ntsecuritycon
    import pywintypes
    import win32con
    import win32security

    user = _windows_user()
    acl = win32security.ACL()
    acl.AddAccessAllowedAceEx(
        win32security.ACL_REVISION,
        win32con.OBJECT_INHERIT_ACE | win32con.CONTAINER_INHERIT_ACE,
        ntsecuritycon.FILE_ALL_ACCESS,
        user,
    )
    descriptor = win32security.SECURITY_DESCRIPTOR()
    descriptor.SetSecurityDescriptorOwner(user, False)
    descriptor.SetSecurityDescriptorDacl(True, acl, False)
    descriptor.SetSecurityDescriptorControl(
        win32security.SE_DACL_PROTECTED, win32security.SE_DACL_PROTECTED
    )
    attributes = pywintypes.SECURITY_ATTRIBUTES()
    attributes.SECURITY_DESCRIPTOR = descriptor
    return attributes


def _validate_windows_handle(handle: Any) -> None:
    import win32con
    import win32file
    import win32security

    if (
        win32file.GetFileInformationByHandle(handle)[0]
        & win32con.FILE_ATTRIBUTE_REPARSE_POINT
    ):
        raise OSError("Result artifacts cannot be reparse points")
    descriptor = win32security.GetSecurityInfo(
        handle,
        win32security.SE_FILE_OBJECT,
        win32security.OWNER_SECURITY_INFORMATION
        | win32security.DACL_SECURITY_INFORMATION,
    )
    user = _windows_user()
    acl = descriptor.GetSecurityDescriptorDacl()
    if (
        descriptor.GetSecurityDescriptorOwner() != user
        or acl is None
        or not acl.GetAceCount()
    ):
        raise RuntimeError("Result artifacts must be owned by and private to this user")
    for index in range(acl.GetAceCount()):
        ace = acl.GetAce(index)
        if ace[0][0] != win32security.ACCESS_ALLOWED_ACE_TYPE or ace[2] != user:
            raise RuntimeError("Result artifacts must be private to this user")


def ensure_private_directory(path: Path) -> Path:
    if sys.platform == "win32":
        import ntsecuritycon
        import pywintypes
        import win32con
        import win32file

        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            win32file.CreateDirectory(str(path), _windows_security())
        except pywintypes.error as exc:
            if exc.winerror != 183:  # ERROR_ALREADY_EXISTS
                raise
        handle = win32file.CreateFile(
            str(path),
            win32con.READ_CONTROL | ntsecuritycon.FILE_READ_ATTRIBUTES,
            win32con.FILE_SHARE_READ
            | win32con.FILE_SHARE_WRITE
            | win32con.FILE_SHARE_DELETE,
            None,
            win32con.OPEN_EXISTING,
            win32file.FILE_FLAG_OPEN_REPARSE_POINT
            | win32con.FILE_FLAG_BACKUP_SEMANTICS,
            None,
        )
        try:
            _validate_windows_handle(handle)
        finally:
            handle.Close()
        if not path.is_dir():
            raise RuntimeError("Result artifact directory is not a directory")
    else:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
            raise RuntimeError("Result artifact directory is not owned by this user")
        if info.st_mode & 0o077:
            raise RuntimeError("Result artifact directory must be private")
    return path


def open_private_file(path: Path, flags: int) -> int:
    """Open a regular file without following links; validate the opened object."""
    if sys.platform == "win32":
        import msvcrt

        import pywintypes
        import win32con
        import win32file

        access = win32con.GENERIC_READ | win32con.READ_CONTROL
        if flags & (os.O_WRONLY | os.O_RDWR):
            access |= win32con.GENERIC_WRITE
        creation = (
            win32con.CREATE_NEW
            if flags & os.O_EXCL
            else win32con.OPEN_ALWAYS if flags & os.O_CREAT else win32con.OPEN_EXISTING
        )
        try:
            handle = win32file.CreateFile(
                str(path),
                access,
                win32con.FILE_SHARE_READ
                | win32con.FILE_SHARE_WRITE
                | win32con.FILE_SHARE_DELETE,
                _windows_security() if flags & os.O_CREAT else None,
                creation,
                win32file.FILE_FLAG_OPEN_REPARSE_POINT,
                None,
            )
        except pywintypes.error as exc:
            raise OSError(exc.winerror, "Cannot open result artifact") from exc
        try:
            _validate_windows_handle(handle)
            mode = flags & (os.O_WRONLY | os.O_RDWR) | os.O_BINARY
            fd = int(msvcrt.open_osfhandle(int(handle), mode))
            handle.Detach()  # the CRT descriptor now owns the native handle
            return fd
        finally:
            handle.Close()
    fd = os.open(path, flags | os.O_NOFOLLOW, 0o600)
    info = os.fstat(fd)
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or info.st_mode & 0o077
    ):
        os.close(fd)
        raise RuntimeError("Result artifact files must be private regular files")
    return fd


@contextmanager
def locked_private_file(path: Path) -> Iterator[None]:
    fd = open_private_file(path, os.O_RDWR | os.O_CREAT)
    try:
        if sys.platform == "win32":
            import msvcrt

            import pywintypes
            import win32con
            import win32file

            handle = msvcrt.get_osfhandle(fd)
            overlapped = pywintypes.OVERLAPPED()
            win32file.LockFileEx(
                handle, win32con.LOCKFILE_EXCLUSIVE_LOCK, 1, 0, overlapped
            )
            try:
                yield
            finally:
                win32file.UnlockFileEx(handle, 1, 0, overlapped)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)

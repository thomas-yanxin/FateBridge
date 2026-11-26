"""Windows ownership, protected ACLs and locks for private result artifacts."""

from __future__ import annotations

import sys

if sys.platform != "win32":
    raise ImportError("private_files_windows requires Windows")

import msvcrt
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import ntsecuritycon
import pywintypes
import win32api
import win32con
import win32file
import win32security

ERROR_ALREADY_EXISTS = 183
FILE_SHARE_MODE = (
    win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE | win32con.FILE_SHARE_DELETE
)


def user_identity() -> str:
    sid_text: str = win32security.ConvertSidToStringSid(windows_user())
    return sid_text


def result_temp_roots() -> list[str]:
    return [
        os.path.expanduser(r"~\AppData\Local\Temp"),
        os.path.expandvars(r"%SYSTEMROOT%\Temp"),
        r"c:\temp",
        r"c:\tmp",
        r"\temp",
        r"\tmp",
    ]


def windows_user() -> pywintypes.SIDType:
    token = win32security.OpenProcessToken(
        win32api.GetCurrentProcess(), win32con.TOKEN_QUERY
    )
    try:
        user_sid: pywintypes.SIDType = win32security.GetTokenInformation(
            token, win32security.TokenUser
        )[0]
        return user_sid
    finally:
        token.Close()


def private_security_attributes() -> pywintypes.SECURITY_ATTRIBUTESType:
    user_sid = windows_user()
    acl = win32security.ACL()
    acl.AddAccessAllowedAceEx(
        win32security.ACL_REVISION,
        win32con.OBJECT_INHERIT_ACE | win32con.CONTAINER_INHERIT_ACE,
        ntsecuritycon.FILE_ALL_ACCESS,
        user_sid,
    )
    descriptor = win32security.SECURITY_DESCRIPTOR()
    descriptor.SetSecurityDescriptorOwner(user_sid, False)
    descriptor.SetSecurityDescriptorDacl(True, acl, False)
    descriptor.SetSecurityDescriptorControl(
        win32security.SE_DACL_PROTECTED, win32security.SE_DACL_PROTECTED
    )
    attributes: pywintypes.SECURITY_ATTRIBUTESType = pywintypes.SECURITY_ATTRIBUTES()
    attributes.SECURITY_DESCRIPTOR = descriptor
    return attributes


def validate_private_handle(handle: pywintypes.HANDLEType) -> None:
    file_attributes = win32file.GetFileInformationByHandle(handle)[0]
    if file_attributes & win32con.FILE_ATTRIBUTE_REPARSE_POINT:
        raise OSError("Result artifacts cannot be reparse points")
    descriptor = win32security.GetSecurityInfo(
        handle,
        win32security.SE_FILE_OBJECT,
        win32security.OWNER_SECURITY_INFORMATION
        | win32security.DACL_SECURITY_INFORMATION,
    )
    user_sid = windows_user()
    acl = descriptor.GetSecurityDescriptorDacl()
    if (
        descriptor.GetSecurityDescriptorOwner() != user_sid
        or acl is None
        or not acl.GetAceCount()
    ):
        raise RuntimeError("Result artifacts must be owned by and private to this user")
    for index in range(acl.GetAceCount()):
        ace = acl.GetAce(index)
        if ace[0][0] != win32security.ACCESS_ALLOWED_ACE_TYPE or ace[2] != user_sid:
            raise RuntimeError("Result artifacts must be private to this user")


def ensure_private_directory(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        win32file.CreateDirectory(str(path), private_security_attributes())
    except pywintypes.error as exc:
        if exc.winerror != ERROR_ALREADY_EXISTS:
            raise
    return validate_private_directory(path)


def validate_private_directory(path: Path) -> Path:
    handle = win32file.CreateFile(
        str(path),
        win32con.READ_CONTROL | ntsecuritycon.FILE_READ_ATTRIBUTES,
        FILE_SHARE_MODE,
        None,
        win32con.OPEN_EXISTING,
        win32file.FILE_FLAG_OPEN_REPARSE_POINT | win32con.FILE_FLAG_BACKUP_SEMANTICS,
        None,
    )
    try:
        validate_private_handle(handle)
    finally:
        handle.Close()
    if not path.is_dir():
        raise RuntimeError("Result artifact directory is not a directory")
    else:
        return path


def open_private_file(path: Path, flags: int) -> int:
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
            FILE_SHARE_MODE,
            private_security_attributes() if flags & os.O_CREAT else None,
            creation,
            win32file.FILE_FLAG_OPEN_REPARSE_POINT,
            None,
        )
    except pywintypes.error as exc:
        raise OSError(exc.winerror, "Cannot open result artifact") from exc
    try:
        validate_private_handle(handle)
        mode = flags & (os.O_WRONLY | os.O_RDWR) | os.O_BINARY
        descriptor = msvcrt.open_osfhandle(int(handle), mode)
        # note (ownership): The CRT descriptor now owns the native handle.
        handle.Detach()
        return descriptor
    finally:
        handle.Close()


@contextmanager
def locked_private_file(path: Path) -> Iterator[None]:
    descriptor = open_private_file(path, os.O_RDWR | os.O_CREAT)
    try:
        handle = msvcrt.get_osfhandle(descriptor)
        overlapped = pywintypes.OVERLAPPED()
        win32file.LockFileEx(handle, win32con.LOCKFILE_EXCLUSIVE_LOCK, 1, 0, overlapped)
        try:
            yield
        finally:
            win32file.UnlockFileEx(handle, 1, 0, overlapped)
    finally:
        os.close(descriptor)

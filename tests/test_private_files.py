"""Result storage permission boundaries, link rejection and same-process locks."""

import os
import subprocess
import sys
import threading

import pytest

from fatebridge.utils.private_files import (
    ensure_private_directory,
    locked_private_file,
    open_private_file,
)


def test_threads_cannot_enter_the_same_artifact_lock_together(tmp_path):
    directory = ensure_private_directory(tmp_path / "private")
    started, acquired = threading.Event(), threading.Event()
    errors = []

    def read():
        started.set()
        try:
            with locked_private_file(directory / ".lock"):
                acquired.set()
        except Exception as exc:
            errors.append(exc)

    with locked_private_file(directory / ".lock"):
        thread = threading.Thread(target=read)
        thread.start()
        assert started.wait(5)
        assert not acquired.wait(0.1)
    thread.join(timeout=5)
    assert not thread.is_alive() and not errors
    assert acquired.is_set()


def test_new_files_are_private_and_exclusive_creation_never_replaces_them(tmp_path):
    directory = ensure_private_directory(tmp_path / "private")
    path = directory / "result"
    fd = open_private_file(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(fd, "wb") as handle:
        handle.write(b"private result")
    with pytest.raises(OSError):
        open_private_file(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    assert path.read_bytes() == b"private result"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX mode bits")
def test_world_readable_directory_and_file_are_rejected(tmp_path):
    directory = ensure_private_directory(tmp_path / "private")
    path = directory / "result"
    path.write_bytes(b"secret")
    path.chmod(0o644)
    with pytest.raises(RuntimeError, match="private"):
        open_private_file(path, os.O_RDONLY)
    directory.chmod(0o755)
    with pytest.raises(RuntimeError, match="private"):
        ensure_private_directory(directory)


@pytest.mark.skipif(sys.platform != "win32", reason="native Windows ACL")
def test_windows_rejects_directory_with_an_everyone_read_ace(tmp_path):
    import win32con
    import win32security

    directory = ensure_private_directory(tmp_path / "private")
    descriptor = win32security.GetFileSecurity(
        str(directory), win32security.DACL_SECURITY_INFORMATION
    )
    acl = descriptor.GetSecurityDescriptorDacl()
    acl.AddAccessAllowedAce(
        win32security.ACL_REVISION,
        win32con.GENERIC_READ,
        win32security.CreateWellKnownSid(win32security.WinWorldSid, None),
    )
    win32security.SetNamedSecurityInfo(
        str(directory),
        win32security.SE_FILE_OBJECT,
        win32security.DACL_SECURITY_INFORMATION,
        None,
        None,
        acl,
        None,
    )
    with pytest.raises(RuntimeError, match="private"):
        ensure_private_directory(directory)


@pytest.mark.skipif(sys.platform != "win32", reason="native Windows junction")
def test_windows_never_uses_a_junction_as_the_result_directory(tmp_path):
    outside = ensure_private_directory(tmp_path / "outside")
    junction = tmp_path / "junction"
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
        check=True,
        capture_output=True,
    )
    try:
        with pytest.raises(OSError, match="reparse"):
            ensure_private_directory(junction)
    finally:
        junction.rmdir()

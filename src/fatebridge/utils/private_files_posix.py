"""POSIX ownership, permissions and locks for private result artifacts."""

import sys

if sys.platform == "win32":
    raise ImportError("private_files_posix requires POSIX")

import fcntl
import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def user_identity() -> str:
    return str(os.getuid())


def result_temp_roots() -> list[str]:
    return ["/tmp", "/var/tmp", "/usr/tmp"]


def ensure_private_directory(path: Path) -> Path:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return validate_private_directory(path)


def validate_private_directory(path: Path) -> Path:
    directory_stat = path.lstat()
    if not stat.S_ISDIR(directory_stat.st_mode) or directory_stat.st_uid != os.getuid():
        raise RuntimeError("Result artifact directory is not owned by this user")
    elif directory_stat.st_mode & 0o077:
        raise RuntimeError("Result artifact directory must be private")
    else:
        return path


def open_private_file(path: Path, flags: int) -> int:
    descriptor = os.open(path, flags | os.O_NOFOLLOW, 0o600)
    try:
        file_stat = os.fstat(descriptor)
        if (
            not stat.S_ISREG(file_stat.st_mode)
            or file_stat.st_uid != os.getuid()
            or file_stat.st_mode & 0o077
        ):
            raise RuntimeError("Result artifact files must be private regular files")
        else:
            return descriptor
    except (OSError, RuntimeError):
        os.close(descriptor)
        raise


@contextmanager
def locked_private_file(path: Path) -> Iterator[None]:
    descriptor = open_private_file(path, os.O_RDWR | os.O_CREAT)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)

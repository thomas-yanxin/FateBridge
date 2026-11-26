"""Select native private-file operations and locate result directories."""

import os
import sys
import tempfile
from pathlib import Path

if sys.platform == "win32":
    from fatebridge.utils.private_files_windows import (
        ensure_private_directory,
        locked_private_file,
        open_private_file,
        result_temp_roots,
        user_identity,
        validate_private_directory,
    )
else:
    from fatebridge.utils.private_files_posix import (
        ensure_private_directory,
        locked_private_file,
        open_private_file,
        result_temp_roots,
        user_identity,
        validate_private_directory,
    )

__all__ = [
    "default_result_directory",
    "ensure_private_directory",
    "locked_private_file",
    "open_private_file",
    "result_directory_candidates",
    "validate_private_directory",
]


def result_directory_name() -> str:
    # note (ownership): The UID or SID distinguishes users in a shared temp directory.
    return f"fatebridge-json-results-{user_identity()}"


def default_result_directory() -> Path:
    return Path(tempfile.gettempdir()) / result_directory_name()


def result_directory_candidates() -> list[Path]:
    """Locate existing artifacts without probing whether temp dirs are writable."""
    roots = [os.fsdecode(tempfile.tempdir)] if tempfile.tempdir is not None else []
    roots.extend(
        configured_root
        for name in ("TMPDIR", "TEMP", "TMP")
        if (configured_root := os.getenv(name))
    )
    roots.extend(result_temp_roots())
    try:
        roots.append(os.getcwd())
    except OSError:
        pass
    name = result_directory_name()
    return list(dict.fromkeys(Path(root).absolute() / name for root in roots))

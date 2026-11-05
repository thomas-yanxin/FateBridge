"""Read current source/reference fixtures without loading archived producers."""

import gzip
import hashlib
import json
from pathlib import Path


def read(path: Path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_source_files(directory: Path) -> None:
    """Bind current independent data bytes; no implementation or archived output files."""
    for name, expected in read(directory / "source-files.json")["files"].items():
        assert sha(directory / name) == expected, name

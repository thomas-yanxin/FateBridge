"""Verify a pinned Guolao evidence ZIP without extracting or executing it."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

SCHEMA = "guolao_replay_v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("manifest contains a duplicate key")
        result[key] = value
    return result


def _path(name: str) -> None:
    if (
        not name
        or "\\" in name
        or PurePosixPath(name).is_absolute()
        or ".." in PurePosixPath(name).parts
        or PurePosixPath(name).as_posix() != name
        or name.endswith("/")
    ):
        raise ValueError("archive path is not a canonical relative file")


def verify_bundle(path: Path, *, expected_sha256: str) -> dict[str, Any]:
    """The external digest binds identity; the inner manifest checks every file.

    This verifies bytes, not source authority, numerical correctness or efficacy.
    No archive path is extracted and no bundled program is run.
    """
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("expected SHA256 must be an explicit lowercase digest")
    if _sha256(path) != expected_sha256:
        raise ValueError("archive SHA256 differs from the pinned digest")
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if len(names) != len(set(names)):
            raise ValueError("archive contains duplicate paths")
        for entry in entries:
            _path(entry.filename)
            if stat.S_ISLNK(entry.external_attr >> 16):
                raise ValueError("archive contains a symbolic link")
            if entry.flag_bits & 1:
                raise ValueError("encrypted archive entries are not supported")
        if "manifest.json" not in names:
            raise ValueError("manifest.json is missing")
        if archive.getinfo("manifest.json").file_size > 8 * 1024 * 1024:
            raise ValueError("manifest exceeds the declared 8MiB reader limit")
        manifest = json.loads(
            archive.read("manifest.json"), object_pairs_hook=_unique_object
        )
        if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
            raise ValueError("unsupported evidence manifest")
        files = manifest.get("files")
        if not isinstance(files, dict) or not files:
            raise ValueError("manifest must declare a nonempty file set")
        if set(names) != set(files) | {"manifest.json"}:
            raise ValueError("archive and declared file set differ")
        total = 0
        for name, record in files.items():
            _path(name)
            if (
                name == "manifest.json"
                or not isinstance(record, dict)
                or type(record.get("bytes")) is not int
                or record["bytes"] < 0
                or not isinstance(record.get("sha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", record["sha256"])
            ):
                raise ValueError("invalid file digest or byte count")
            if archive.getinfo(name).file_size != record["bytes"]:
                raise ValueError("file length differs from manifest: " + name)
            digest = hashlib.sha256()
            count = 0
            with archive.open(name) as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
                    count += len(chunk)
            if count != record["bytes"] or digest.hexdigest() != record["sha256"]:
                raise ValueError("file bytes differ from manifest: " + name)
            total += count
    return dict(
        schema=SCHEMA,
        archive_sha256=expected_sha256,
        verified_files=len(files),
        verified_uncompressed_bytes=total,
        extracted_files=0,
        executed_programs=0,
        integrity_only=True,
        real_world_efficacy_established=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    try:
        result = verify_bundle(args.bundle, expected_sha256=args.sha256)
    except (OSError, ValueError, TypeError, zipfile.BadZipFile) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

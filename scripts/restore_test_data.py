"""Restore pinned regression inputs from the separate GitHub data release."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOTS = ("tests/fixtures", "tests/golden/snapshots", "docs/validation")


class DataPart(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    asset_id: int = Field(gt=0)
    name: str = Field(pattern=r"^[A-Za-z0-9_.-]+\.tar\.gz$")
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size: int = Field(gt=0)
    group: Literal["core", "fixtures", "validation", "golden"]


class DataManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal[1]
    repository: Literal["thomas-yanxin/FateBridge"]
    source_revision: str = Field(pattern=r"^[a-f0-9]{40}$")
    parts: list[DataPart] = Field(min_length=1)


def restore(
    manifest: DataManifest,
    root: Path,
    *,
    core_only: bool = False,
    archive_directory: Path | None = None,
) -> int:
    restored = 0
    with tempfile.TemporaryDirectory(prefix="fatebridge-test-data-") as directory:
        for part in manifest.parts:
            if core_only and part.group != "core":
                continue
            archive = (
                archive_directory / part.name
                if archive_directory is not None
                else Path(directory) / part.name
            )
            if archive_directory is None:
                with archive.open("wb") as output:
                    subprocess.run(
                        [
                            "gh",
                            "api",
                            f"repos/{manifest.repository}/releases/assets/{part.asset_id}",
                            "--header",
                            "Accept: application/octet-stream",
                        ],
                        stdout=output,
                        check=True,
                    )
            digest = hashlib.sha256()
            with archive.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            if archive.stat().st_size != part.size or digest.hexdigest() != part.sha256:
                raise ValueError(f"Pinned test-data archive changed: {part.name}")
            with tarfile.open(archive, "r:gz") as bundle:
                for member in bundle:
                    relative = PurePosixPath(member.name)
                    if (
                        not member.isfile()
                        or relative.is_absolute()
                        or ".." in relative.parts
                        or "\\" in member.name
                        or not any(relative.is_relative_to(base) for base in DATA_ROOTS)
                    ):
                        raise ValueError(f"Invalid test-data member: {member.name}")
                    destination = root.joinpath(*relative.parts)
                    if not destination.resolve().is_relative_to(root.resolve()):
                        raise ValueError(
                            f"Test-data path escapes checkout: {member.name}"
                        )
                    source = bundle.extractfile(member)
                    assert source is not None
                    with source:
                        if destination.exists():
                            current = hashlib.sha256()
                            with destination.open("rb") as stream:
                                for block in iter(
                                    lambda: stream.read(1024 * 1024), b""
                                ):
                                    current.update(block)
                            incoming = hashlib.sha256()
                            for block in iter(lambda: source.read(1024 * 1024), b""):
                                incoming.update(block)
                            if current.digest() != incoming.digest():
                                raise ValueError(
                                    f"Existing test data differs: {member.name}"
                                )
                            continue
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        with destination.open("wb") as output:
                            shutil.copyfileobj(source, output)
                        destination.chmod(member.mode & 0o777)
                        restored += 1
            print(f"Verified {part.name}", flush=True)
            if archive_directory is None:
                archive.unlink()
    return restored


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-only", action="store_true")
    parser.add_argument("--archive-directory", type=Path)
    options = parser.parse_args()
    manifest = DataManifest.model_validate_json(
        (ROOT / "tests/fixture-data.json").read_text(encoding="utf-8")
    )
    count = restore(
        manifest,
        ROOT,
        core_only=options.core_only,
        archive_directory=options.archive_directory,
    )
    print(f"Restored {count} frozen test-data files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

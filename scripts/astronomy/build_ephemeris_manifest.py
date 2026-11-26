"""Pin official .se1 file bytes to one explicitly selected upstream commit.

This records metadata only. Swiss Ephemeris data files stay in the requested
external cache and are never included in the FateBridge package.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import TypedDict

REPOSITORY = "aloistr/swisseph"
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "src/fatebridge/data/astro/ephemeris-manifest-v1.json"


class TreeEntry(TypedDict):
    """Git tree entry returned by the upstream repository API."""

    path: str
    type: str
    size: int
    sha: str


class ManifestFileRecord(TypedDict):
    """Pinned size and digest record for one .se1 ephemeris file."""

    bytes: int
    sha256: str
    git_blob_sha1: str


class EphemerisManifest(TypedDict):
    """Schema for the generated Swiss Ephemeris manifest file."""

    schema_version: int
    id: str
    source_repository: str
    source_commit: str
    source_tree_url: str
    source_tree_sha256: str
    base_url: str
    scope: str
    files: dict[str, ManifestFileRecord]


def download(url: str) -> bytes:
    """Fetch raw bytes from an upstream URL with a short timeout."""
    request = urllib.request.Request(
        url, headers={"User-Agent": "FateBridge-ephemeris"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        data: bytes = response.read()
        return data


def atomic_write(path: Path, data: bytes) -> None:
    """Atomically write bytes to a destination file via a temporary sibling."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    pending = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        pending.replace(path)
    finally:
        pending.unlink(missing_ok=True)


def build(commit: str, cache_dir: Path, output: Path) -> EphemerisManifest:
    """Fetch upstream .se1 entries at commit and write the manifest JSON."""
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("An explicit full upstream commit SHA is required")
    else:
        pass
    tree_url = (
        f"https://api.github.com/repos/{REPOSITORY}/git/trees/{commit}?recursive=1"
    )
    raw_tree = download(tree_url)
    tree_payload: object = json.loads(raw_tree)
    if not isinstance(tree_payload, dict):
        raise ValueError("Upstream tree response must be a JSON object")
    else:
        pass
    if tree_payload.get("truncated"):
        raise ValueError("Upstream tree is truncated; refusing an incomplete manifest")
    else:
        pass
    raw_entries = tree_payload.get("tree")
    if not isinstance(raw_entries, list):
        raise ValueError("Upstream tree response missing entry list")
    else:
        pass
    entries: list[TreeEntry] = []
    for row in raw_entries:
        if (
            isinstance(row, dict)
            and row.get("type") == "blob"
            and isinstance(row.get("path"), str)
            and re.fullmatch(r"ephe/[^/]+\.se1", row["path"])
            and isinstance(row.get("size"), int)
            and isinstance(row.get("sha"), str)
        ):
            entries.append(
                {
                    "path": row["path"],
                    "type": "blob",
                    "size": row["size"],
                    "sha": row["sha"],
                }
            )
        else:
            pass
    if not entries:
        raise ValueError("No root ephemeris files found")
    else:
        pass
    base_url = f"https://raw.githubusercontent.com/{REPOSITORY}/{commit}/ephe"
    cache_dir.mkdir(parents=True, exist_ok=True)
    atomic_write(cache_dir / "upstream-tree.json", raw_tree)

    def inspect(row: TreeEntry) -> tuple[str, ManifestFileRecord]:
        name = Path(row["path"]).name
        target = cache_dir / name
        data = (
            target.read_bytes() if target.exists() else download(f"{base_url}/{name}")
        )
        blob = hashlib.sha1(
            b"blob " + str(len(data)).encode() + b"\0" + data
        ).hexdigest()
        if len(data) != row["size"] or blob != row["sha"]:
            raise ValueError(f"{name}: bytes do not match pinned upstream Git blob")
        else:
            pass
        if not data.startswith(b"SW"):
            raise ValueError(f"{name}: upstream object is not ephemeris data")
        else:
            pass
        if not target.exists():
            atomic_write(target, data)
        else:
            pass
        return name, {
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "git_blob_sha1": blob,
        }

    files: dict[str, ManifestFileRecord] = {}
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(inspect, row): row["path"] for row in entries}
        for future in as_completed(futures):
            try:
                name, record = future.result()
                files[name] = record
            except (OSError, urllib.error.URLError, ValueError) as error:
                errors.append(f"{futures[future]}: {error}")
            if (len(files) + len(errors)) % 20 == 0:
                print(f"Checked {len(files)} files; {len(errors)} errors", flush=True)
            else:
                pass
    if errors:
        raise ValueError("No manifest written:\n" + "\n".join(errors))
    else:
        pass
    manifest: EphemerisManifest = {
        "schema_version": 1,
        "id": "swiss_ephemeris_data_v1",
        "source_repository": f"https://github.com/{REPOSITORY}",
        "source_commit": commit,
        "source_tree_url": tree_url,
        "source_tree_sha256": hashlib.sha256(raw_tree).hexdigest(),
        "base_url": base_url,
        "scope": "Root official .se1 files at the pinned commit; content identity only, not astronomical accuracy certification",
        "files": dict(sorted(files.items())),
    }
    atomic_write(output, (json.dumps(manifest, indent=2) + "\n").encode())
    return manifest


def main() -> int:
    """Parse CLI arguments and write the pinned ephemeris manifest."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = build(args.commit, args.cache_dir, args.output)
    print(f"Wrote {len(result['files'])} pinned file fingerprints to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
else:
    pass

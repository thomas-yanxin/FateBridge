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
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict

REPOSITORY = "aloistr/swisseph"
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "src/fatebridge/data/astro/ephemeris-manifest-v1.json"


def download(url: str) -> bytes:
    request = urllib.request.Request(
        url, headers={"User-Agent": "FateBridge-ephemeris"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        data: bytes = response.read()
        return data


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    pending = Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        pending.replace(path)
    finally:
        pending.unlink(missing_ok=True)


def build(commit: str, cache_dir: Path, output: Path) -> Dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("An explicit full upstream commit SHA is required")
    tree_url = (
        f"https://api.github.com/repos/{REPOSITORY}/git/trees/{commit}?recursive=1"
    )
    raw_tree = download(tree_url)
    tree = json.loads(raw_tree)
    if tree.get("truncated"):
        raise ValueError("Upstream tree is truncated; refusing an incomplete manifest")
    entries = [
        row
        for row in tree["tree"]
        if row["type"] == "blob" and re.fullmatch(r"ephe/[^/]+\.se1", row["path"])
    ]
    if not entries:
        raise ValueError("No root ephemeris files found")
    base_url = f"https://raw.githubusercontent.com/{REPOSITORY}/{commit}/ephe"
    cache_dir.mkdir(parents=True, exist_ok=True)
    atomic_write(cache_dir / "upstream-tree.json", raw_tree)

    def inspect(row: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
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
        if not data.startswith(b"SW"):
            raise ValueError(f"{name}: upstream object is not ephemeris data")
        if not target.exists():
            atomic_write(target, data)
        return name, {
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "git_blob_sha1": blob,
        }

    files: Dict[str, Any] = {}
    errors = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(inspect, row): row["path"] for row in entries}
        for future in as_completed(futures):
            try:
                name, record = future.result()
                files[name] = record
            except Exception as error:
                errors.append(f"{futures[future]}: {error}")
            if (len(files) + len(errors)) % 20 == 0:
                print(f"Checked {len(files)} files; {len(errors)} errors", flush=True)
    if errors:
        raise ValueError("No manifest written:\n" + "\n".join(errors))
    manifest = {
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = build(args.commit, args.cache_dir, args.output)
    print(f"Wrote {len(result['files'])} pinned file fingerprints to {args.output}")


if __name__ == "__main__":
    main()

"""Acquire the DE440 kernel for local ephemeris reference verification."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    """Download or verify the DE440 kernel declared in the astronomy metadata."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    options = parser.parse_args(argv)
    payload: object = json.loads(
        (ROOT / "src/fatebridge/data/astronomy/de440-solar-v1.json").read_text(
            encoding="utf-8"
        )
    )
    if not isinstance(payload, dict):
        raise ValueError("DE440 metadata must be a JSON object")
    source = payload["source"]
    if not isinstance(source, dict):
        raise ValueError("DE440 metadata source must be a JSON object")
    expected_sha = source["kernel_sha256"]
    source_url = source["url"]
    if not isinstance(expected_sha, str) or not isinstance(source_url, str):
        raise ValueError(
            "DE440 metadata source must declare string url and kernel_sha256"
        )
    target = ROOT / "ephe/solar-de440.bsp"
    digest = (
        hashlib.sha256(target.read_bytes()).hexdigest() if target.is_file() else None
    )
    if digest != expected_sha:
        if options.verify_only:
            raise ValueError("The pinned DE440 reference kernel is missing or corrupt")
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(dir=target.parent, suffix=".download")
        os.close(descriptor)
        temporary = Path(name)
        try:
            urllib.request.urlretrieve(source_url, temporary)
            digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
            if digest != expected_sha:
                raise ValueError(
                    "Downloaded DE440 bytes do not match the declared source"
                )
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    print(json.dumps({"path": str(target), "sha256": digest, "source": source_url}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

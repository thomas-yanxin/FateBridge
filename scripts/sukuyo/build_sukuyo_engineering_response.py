"""Assemble a whole engineering answer with frozen evidence and literal spans."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from fatebridge.validation.sukuyo_engineering import (
    Artifact,
    build_engineering_response_request,
)


def publish_output(path: Path, raw: bytes) -> None:
    """Publish completed bytes without replacing any existing path."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix="." + path.name + ".", delete=False
        ) as output:
            temporary = Path(output.name)
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
        os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--request-sha256", required=True)
    parser.add_argument("--request-version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_engineering_response_request(
        Artifact(args.request, args.request_sha256, args.request_version)
    )
    raw = (
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode()
    publish_output(args.output, raw)
    print(f"Wrote {len(raw)} bytes; semantic_verdict=not_assessed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

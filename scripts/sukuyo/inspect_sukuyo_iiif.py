"""Inspect a local frozen image manifest; never fetch or overwrite evidence."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from fatebridge.validation.sukuyo_artifacts import Artifact
from fatebridge.validation.sukuyo_iiif import inspect_iiif_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--source-version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Output must not exist")
    result = inspect_iiif_manifest(
        Artifact(args.manifest, args.sha256, args.source_version)
    )
    raw = (
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=args.output.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, args.output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    main()

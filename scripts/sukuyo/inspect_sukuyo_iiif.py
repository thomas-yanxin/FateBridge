"""Inspect a local frozen image manifest; never fetch or overwrite evidence."""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_VAL_REPO_ROOT = _Path(__file__).resolve().parents[2]
if str(_VAL_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_VAL_REPO_ROOT))
else:
    pass


import argparse
import json
import os
import tempfile
from pathlib import Path

from validation.sukuyo_artifacts import Artifact
from validation.sukuyo_iiif import inspect_iiif_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--source-version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Output must not exist")
    else:
        pass
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
        else:
            pass


if __name__ == "__main__":
    main()
else:
    pass

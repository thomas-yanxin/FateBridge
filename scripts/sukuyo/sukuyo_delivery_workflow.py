"""Coordinate frozen inputs and external role outputs; never invoke a model."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from fatebridge.validation.sukuyo_delivery_workflow import (
    capture_generation,
    finalize_delivery,
    prepare_delivery,
    submit_review,
)
from fatebridge.validation.sukuyo_engineering import Artifact


def publish_output(path: Path, raw: bytes) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix="." + path.name + ".", delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    inputs = {
        "prepare": ("request",),
        "capture-generation": ("prepared", "answers", "receipt"),
        "submit-review": ("generation",),
        "finalize": ("review-input", "review", "receipt"),
    }
    for name, arguments in inputs.items():
        command = actions.add_parser(name)
        for argument in arguments:
            command.add_argument("--" + argument, type=Path, required=True)
            command.add_argument("--" + argument + "-sha256", required=True)
            command.add_argument("--" + argument + "-version", required=True)
        command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    def artifact(name: str) -> Artifact:
        key = name.replace("-", "_")
        return Artifact(
            getattr(args, key),
            getattr(args, key + "_sha256"),
            getattr(args, key + "_version"),
        )

    if args.action == "prepare":
        result = prepare_delivery(artifact("request"))
    elif args.action == "capture-generation":
        result = capture_generation(
            artifact("prepared"), artifact("answers"), artifact("receipt")
        )
    elif args.action == "submit-review":
        result = submit_review(artifact("generation"))
    else:
        result = finalize_delivery(
            artifact("review-input"), artifact("review"), artifact("receipt")
        )
    raw = (
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")
    publish_output(args.output, raw)
    print(f"Wrote {len(raw)} bytes; action={args.action}; no model invoked by CLI")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Bind complete frozen input and answer files for whole-question review."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from fatebridge.validation.sukuyo_engineering import Artifact
from fatebridge.validation.sukuyo_semantic_packet import (
    build_whole_answer_review_packet,
)

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_sukuyo_engineering_response import publish_output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--request-sha256", required=True)
    parser.add_argument("--request-version", required=True)
    parser.add_argument("--answers", type=Path, required=True)
    parser.add_argument("--answers-sha256", required=True)
    parser.add_argument("--answers-version", required=True)
    parser.add_argument("--id-field", choices=("id", "case_id"), default="id")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    packet = build_whole_answer_review_packet(
        Artifact(args.request, args.request_sha256, args.request_version),
        Artifact(args.answers, args.answers_sha256, args.answers_version),
        id_field=args.id_field,
    )
    raw = (
        json.dumps(packet, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode()
    publish_output(args.output, raw)
    print(
        f"Wrote {len(raw)} bytes; cases={packet['case_count']}; semantic_verdict=not_assessed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Read pinned preparation or literal answer evidence; never invoke a model."""

import argparse
import json
from pathlib import Path

from fatebridge.services.replay_metadata import digest
from fatebridge.validation.meihua_semantic_binding import (
    audit_preparation,
    bind_answer_fields,
    file_sha,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("preparation")
    prep.add_argument("directory", type=Path)
    prep.add_argument("--commitment", type=Path, required=True)
    prep.add_argument("--expected-commitment-sha256", required=True)
    answer = commands.add_parser("answer")
    answer.add_argument("--answer", type=Path, required=True)
    answer.add_argument("--capture", type=Path, required=True)
    answer.add_argument("--claims", type=Path, required=True)
    answer.add_argument("--receipt", type=Path, required=True)
    answer.add_argument("--expected-receipt-sha256", required=True)
    args = parser.parse_args()
    try:
        if args.command == "preparation":
            receipt = json.loads(args.commitment.read_bytes())
            result = audit_preparation(
                args.directory,
                receipt["commitment"],
                expected_commitment_sha256=args.expected_commitment_sha256,
            )
        else:
            receipt = json.loads(args.receipt.read_bytes())
            if digest(receipt) != args.expected_receipt_sha256:
                raise ValueError("Review receipt differs from its separate commitment")
            if file_sha(args.claims) != receipt["claims_sha256"]:
                raise ValueError("Selected literal claims differ from their receipt")
            result = bind_answer_fields(
                args.answer,
                args.capture,
                json.loads(args.claims.read_bytes()),
                expected_answer_sha256=receipt["answer_sha256"],
                expected_capture_sha256=receipt["capture_sha256"],
                reference_run_ids=receipt["reference_run_ids"],
                case=receipt.get("case"),
            )
    except (ValueError, KeyError, IndexError, TypeError, OSError) as error:
        print(
            json.dumps(
                {"binding_passed": False, "error": str(error)}, ensure_ascii=False
            )
        )
        raise SystemExit(2) from error
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

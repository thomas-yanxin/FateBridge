"""Seal/replay local Qimen study packets; no registration or efficacy certificate."""

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fatebridge.validation.predictions import Outcome, digest
from fatebridge.validation.qimen_study import (
    FrozenQimenPolicy,
    QimenCommitment,
    StudyInput,
    audit_study,
    commitment_fingerprint,
    engine_manifest,
    policy_fingerprint,
    seal_forecasts,
)


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    fingerprint = commands.add_parser("fingerprint")
    fingerprint.add_argument("--policy", type=Path, required=True)
    seal = commands.add_parser("seal")
    seal.add_argument("--study", type=Path, required=True)
    seal.add_argument(
        "--synthetic-at", help="Only data_kind=synthetic allows an injected clock"
    )
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("--commitment", type=Path, required=True)
    evaluate.add_argument("--outcomes", type=Path, required=True)
    evaluate.add_argument("--as-of", required=True)
    evaluate.add_argument(
        "--expected-commitment-sha256",
        help="Canonical packet digest retained independently before outcomes; required for real_world_submission",
    )
    for subcommand in (fingerprint, seal, evaluate):
        subcommand.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    details = {}
    if args.command == "fingerprint":
        manifest = engine_manifest()
        policy = FrozenQimenPolicy.model_validate(_read(args.policy))
        result = {
            "engine_manifest": manifest,
            "model_sha256": digest(manifest),
            "interpretation_policy_sha256": policy_fingerprint(policy),
            "registration_status": "local_draft_not_external_registration",
        }
    elif args.command == "seal":
        study = StudyInput.model_validate(_read(args.study))
        at = datetime.fromisoformat(args.synthetic_at) if args.synthetic_at else None
        packet = seal_forecasts(study, at=at)
        result = packet.model_dump(mode="json")
        details = {
            "commitment_sha256": commitment_fingerprint(packet),
            "study_input_sha256": packet.study_input_sha256,
        }
    else:
        packet = QimenCommitment.model_validate(_read(args.commitment))
        outcomes = [Outcome.model_validate(row) for row in _read(args.outcomes)]
        result = audit_study(
            packet,
            outcomes,
            as_of=datetime.fromisoformat(args.as_of),
            expected_commitment_sha256=args.expected_commitment_sha256,
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            {
                "command": args.command,
                "output": str(args.output),
                "authority_certified": False,
                **details,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

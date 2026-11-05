"""Verify the original future365 ledger; execution success is not predictive skill."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from fatebridge.validation.meihua_weather_prospective import (
    audit_prospective_weather_study,
    parse_source_receipt,
    parse_study_timestamp,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--attestation", type=Path, required=True)
    parser.add_argument(
        "--as-of", default=None, help="Aware ISO audit clock; defaults to local UTC now"
    )
    parser.add_argument("--observations", type=Path)
    parser.add_argument("--source-receipt", type=Path)
    parser.add_argument(
        "--openssl",
        type=Path,
        default=None,
        help="Explicit capable OpenSSL executable; defaults to openssl on PATH",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if bool(args.observations) != bool(args.source_receipt):
        parser.error("--observations and --source-receipt must be supplied together")
    try:
        report = audit_prospective_weather_study(
            args.study,
            args.attestation,
            as_of=(
                parse_study_timestamp(args.as_of)
                if args.as_of
                else datetime.now(timezone.utc)
            ),
            observation_bytes=(
                args.observations.read_bytes() if args.observations else None
            ),
            source_receipt=(
                parse_source_receipt(args.source_receipt.read_bytes())
                if args.source_receipt
                else None
            ),
            openssl_binary=args.openssl,
        )
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    except (ValueError, RuntimeError, OSError) as exc:
        print(
            json.dumps(
                {"execution_integrity": False, "error": str(exc)}, ensure_ascii=False
            ),
            file=sys.stderr,
        )
        return 2
    print(
        json.dumps(
            {
                "execution_integrity": report["execution_integrity"],
                "status": report["status"],
                "cohort_days": report["ledger"]["cohort_days"],
                "ingested_outcome_rows": report["ingested_outcome_rows"],
                "real_world_predictive_efficacy_established": False,
                "authority_certified": False,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

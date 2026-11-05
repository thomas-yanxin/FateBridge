"""Compare the complete 400-year Shoushi winter cohort and error components."""

from __future__ import annotations

import argparse
import json

from fatebridge.core.guolao_winter_error_budget import century_year_diagnostic
from fatebridge.validation.guolao_winter_error_budget import audit_winter_error_budget


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    audit = sub.add_parser("audit")
    audit.add_argument("--reference-only", action="store_true")
    year = sub.add_parser("year")
    year.add_argument("--elapsed-years", type=int, required=True)
    args = parser.parse_args()
    try:
        result = (
            audit_winter_error_budget(include_native=not args.reference_only)
            if args.command == "audit"
            else century_year_diagnostic(args.elapsed_years)
        )
    except (ValueError, TypeError, ZeroDivisionError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

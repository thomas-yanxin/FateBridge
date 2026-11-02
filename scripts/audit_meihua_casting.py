"""Audit explicit classical casts without treating anecdotes as future data."""

import argparse
import json
from pathlib import Path

from fatebridge.validation.meihua_casting import audit_explicit_casts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--references",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "tests/fixtures/meihua_casting_v1",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit_explicit_casts(args.references)
    content = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    print(content)
    return 0 if report["selected_calculation_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

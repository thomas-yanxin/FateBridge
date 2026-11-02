"""Audit selected body-strength/source relation clauses against frozen probes."""

import argparse
import json
from pathlib import Path

from fatebridge.validation.meihua_seasonal_reading import audit_seasonal_reading


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--references",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "tests/fixtures/meihua_seasonal_reading_v1",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit_seasonal_reading(args.references)
    text = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text)
    return 0 if report["selected_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

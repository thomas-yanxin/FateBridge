"""Audit frozen published solar dates without adjusting the calculated events."""

import argparse
import json
from pathlib import Path

from fatebridge.validation.meihua_solar_reference import audit_solar_date_reference


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--references",
        type=Path,
        default=Path("tests/fixtures/meihua_solar_reference_v1"),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit_solar_date_reference(args.references)
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    raise SystemExit(0 if report["selected_checks_passed"] else 1)


if __name__ == "__main__":
    main()

"""Check text-count arithmetic and witness integrity; not predictive acceptance."""

import argparse
import json
from pathlib import Path

from fatebridge.validation.meihua_text_count import audit_text_count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixtures", type=Path, default=Path("tests/fixtures/meihua_text_count_v1")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit_text_count(args.fixtures)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "hand_arithmetic_checks_passed": report[
                    "selected_hand_arithmetic_checks_passed"
                ],
                "arithmetic_mismatches": report["arithmetic_mismatches"],
                "unique_classical_convention_established": False,
                "predictive_acceptance": False,
            }
        )
    )


if __name__ == "__main__":
    main()

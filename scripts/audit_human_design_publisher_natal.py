"""Audit the pinned publisher example without inferring an unprinted time zone."""

import argparse
import json
from pathlib import Path

from fatebridge.validation.human_design_publisher import publisher_natal_checks

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--capture", type=Path)
    p.add_argument("--require-exact-source-chart", action="store_true")
    args = p.parse_args()
    report = publisher_natal_checks(ROOT, capture=args.capture)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "independent_example_count",
                    "literal_hypothesis_computation_count",
                    "literal_structure_matches",
                    "publisher_time_zone_resolved",
                    "exact_birth_epoch_accepted",
                )
            }
        )
    )
    exact_accepted = all(
        report.get(k) is True
        for k in (
            "publisher_time_zone_resolved",
            "exact_birth_epoch_accepted",
            "complete_activation_glyphs_accepted",
        )
    )
    return int(
        report["literal_structure_status"] == "failed"
        or args.require_exact_source_chart
        and not exact_accepted
    )


if __name__ == "__main__":
    raise SystemExit(main())

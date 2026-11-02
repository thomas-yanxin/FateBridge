"""Reproduce reference comparisons; exit0 means execution, never forecast skill."""

import argparse
import json
from pathlib import Path

from fatebridge.validation.meihua_weather_reference_study import (
    audit_weather_reference_study,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit_weather_reference_study(args.study)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "execution_integrity": report["execution_integrity"],
                "normals_match": report[
                    "all12_official_normals_match_published_precision"
                ],
                "original_primary_gate": report["old_primary_endpoint"][
                    "passes_full_cohort_baselines"
                ],
                "real_world_efficacy_established": False,
            }
        )
    )


if __name__ == "__main__":
    main()

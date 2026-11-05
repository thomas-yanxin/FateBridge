"""Audit original weather traces against frozen published lunar date labels."""

import argparse
import json
import sys
from pathlib import Path

from fatebridge.validation.meihua_weather_calendar_binding import (
    audit_calendar_bound_weather_study,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        study = args.study.resolve()
        output = args.output.resolve()
        if output.is_relative_to(study):
            raise ValueError(
                "Audit output must be outside the immutable study directory"
            )
        if output.exists():
            raise ValueError("Audit output must be a new file")
        result = audit_calendar_bound_weather_study(study)
        with output.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    except (ValueError, OSError) as exc:
        print(
            json.dumps(
                {"published_lunar_date_binding_verified": False, "error": str(exc)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2
    print(
        json.dumps(
            {
                "evidence_records": result["evidence_records"],
                "lunar_date_labels_verified": result["published_lunar_date_binding"][
                    "all_selected_date_labels_verified"
                ],
                "outcomes_read": 0,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Audit selected weather-chapter witnesses and frozen conditional probes."""

import argparse
import json
from pathlib import Path

from fatebridge.validation.meihua_weather_chapter import audit_weather_chapter


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = audit_weather_chapter(root / "tests/fixtures/meihua_weather_chapter_v5")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "selected_checks_passed": report["selected_checks_passed"],
            }
        )
    )
    return 0 if report["selected_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

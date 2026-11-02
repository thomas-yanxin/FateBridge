"""Audit a locked historical Meihua weather pilot without training on outcomes."""

import argparse
import json
from pathlib import Path

from fatebridge.validation.meihua_weather_study import audit_locked_weather_pilot


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit_locked_weather_pilot(args.study)
    content = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    print(content)
    # Exit status describes execution and data integrity, not forecasting skill.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

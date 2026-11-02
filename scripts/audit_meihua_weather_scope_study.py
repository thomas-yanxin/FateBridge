"""Evaluate the sealed1.7.0 scope-aware weather study without retuning it."""

import argparse
import json
from pathlib import Path

from fatebridge.validation.meihua_weather_scope_study import audit_scope_weather_study


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit_scope_weather_study(args.study)
    content = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content)
    print(content)
    # Execution/data integrity success is not predictive acceptance.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

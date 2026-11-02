"""Audit the selected Gen rain/clear distinction, not empirical prediction."""

import argparse
import json
from pathlib import Path

from fatebridge.validation.meihua_weather import audit_weather_gen_rain


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--references",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "tests/fixtures/meihua_weather_gen_v4",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit_weather_gen_rain(args.references)
    text = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text)
    return 0 if report["selected_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

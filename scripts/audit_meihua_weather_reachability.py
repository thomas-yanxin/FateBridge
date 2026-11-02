"""Reproduce source-state support; optional readiness gate keeps failure visible."""

import argparse
import json
from pathlib import Path

from fatebridge.validation.meihua_weather_reachability import (
    audit_time_weather_reachability,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-potential-superiority", action="store_true")
    args = parser.parse_args()
    report = audit_time_weather_reachability()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    gate = report["locked_noon_preflight"]
    print(
        json.dumps(
            {
                "output": str(args.output),
                "rows": len(report["state_cases"]),
                "locked_noon_preflight": gate,
            },
            ensure_ascii=False,
        )
    )
    if args.require_potential_superiority and gate["structural_obstruction"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

"""Independent modern TT season and historical solar-clock comparison."""

from __future__ import annotations

import argparse
import json
from fractions import Fraction as F

from fatebridge.core.guolao_modern_time import (
    CLOCK_POLICY,
    historical_clock_components,
    solar_crossing_tt,
)
from fatebridge.validation.guolao_modern_solstices import audit_modern_solstices


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    audit = sub.add_parser("audit")
    audit.add_argument(
        "--include-swieph",
        action="store_true",
        help="Require declared DE441 data files; no fallback",
    )
    event = sub.add_parser("event")
    event.add_argument("--target-degrees", type=float, required=True)
    event.add_argument("--start-tt", type=float, required=True)
    event.add_argument("--end-tt", type=float, required=True)
    clock = sub.add_parser("clock")
    clock.add_argument("--year", type=int, required=True)
    clock.add_argument("--tt-jd", required=True)
    clock.add_argument("--tdb-minus-ut1-seconds", required=True)
    clock.add_argument("--apparent-solar-hours", required=True)
    clock.add_argument("--longitude-east-degrees", required=True)
    clock.add_argument("--policy", choices=[CLOCK_POLICY], required=True)
    args = parser.parse_args()
    try:
        if args.command == "audit":
            result = audit_modern_solstices(include_swieph=args.include_swieph)
        elif args.command == "event":
            result = solar_crossing_tt(args.target_degrees, args.start_tt, args.end_tt)
        else:
            result = historical_clock_components(
                F(args.tt_jd),
                F(args.tdb_minus_ut1_seconds),
                F(args.apparent_solar_hours),
                F(args.longitude_east_degrees),
                year=args.year,
                timescale_difference_policy=args.policy,
            )
    except (ValueError, TypeError, ZeroDivisionError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

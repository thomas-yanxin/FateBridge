"""Published Ganzhi anchor and conditional source calendar date-label audit."""

from __future__ import annotations

import argparse
import json
from fractions import Fraction as F

from fatebridge.core.guolao_calendar_date_bridge import (
    CALENDARS,
    COUNTER_BASIS,
    PROFILE,
    SEARCH_POLICY,
    load_calendar_date_bridge,
)
from fatebridge.validation.guolao_calendar_date_bridge import audit_calendar_date_bridge


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("audit")
    label = sub.add_parser("label")
    label.add_argument("--profile", choices=[PROFILE], required=True)
    label.add_argument("--calendar", choices=CALENDARS, required=True)
    label.add_argument(
        "--date", nargs=3, type=int, required=True, metavar=("YEAR", "MONTH", "DAY")
    )
    for command in ("winter", "counter"):
        p = sub.add_parser(command)
        p.add_argument("--profile", choices=[PROFILE], required=True)
        p.add_argument("--source-year", type=int, required=True)
        p.add_argument("--search-policy", choices=[SEARCH_POLICY], required=True)
        if command == "counter":
            p.add_argument("--counter", required=True)
            p.add_argument("--counter-basis", choices=[COUNTER_BASIS], required=True)
    args = parser.parse_args()
    try:
        if args.command == "audit":
            result = audit_calendar_date_bridge()
        else:
            model = load_calendar_date_bridge(args.profile)
            if args.command == "label":
                result = model.label(*args.date, calendar=args.calendar)
            elif args.command == "winter":
                result = model.winter_candidates(
                    source_year=args.source_year, search_policy=args.search_policy
                )
            else:
                result = model.source_counter_label(
                    F(args.counter),
                    source_year=args.source_year,
                    search_policy=args.search_policy,
                    counter_basis=args.counter_basis,
                )
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

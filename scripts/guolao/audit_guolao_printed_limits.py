"""Read literal NLC3150 limit cells and retain source gaps and formula differences."""

from __future__ import annotations

import argparse
import json
from fractions import Fraction as F

from fatebridge.core.guolao_ruler_calendar import NominalSourceDate
from fatebridge.core.guolao_ruler_printed_table import (
    GROUPS,
    PROFILE,
    load_printed_limit_table,
)
from fatebridge.validation.guolao_ruler_printed_table import audit_printed_limit_table


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=[PROFILE], required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("audit")
    for command in ["cell", "lookup"]:
        p = sub.add_parser(command)
        p.add_argument("--group", choices=GROUPS, required=True)
        if command == "cell":
            p.add_argument("--column", type=int, required=True)
        else:
            p.add_argument("--nominal-source-date", required=True)
            p.add_argument("--fraction-of-nominal-day", default="0")
    args = parser.parse_args()
    try:
        if args.command == "audit":
            result = audit_printed_limit_table()
        else:
            table = load_printed_limit_table(args.profile)
            if args.command == "cell":
                result = table.cell(args.group, args.column)
            else:
                pieces = args.nominal_source_date.split("-")
                if len(pieces) != 3:
                    raise ValueError("须为本限序年-月-日")
                year, month, day = map(int, pieces)
                date = NominalSourceDate(
                    year, month, day, F(args.fraction_of_nominal_day)
                )
                result = table.lookup(args.group, date)
    except (ValueError, TypeError, ZeroDivisionError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

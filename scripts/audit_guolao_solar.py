"""Reproduce Shoushi winter Sun in source equatorial du, never a modern date."""

import argparse
import json

from fatebridge.core.guolao_solar import shoushi_winter_sun
from fatebridge.core.guolao_year_labels import shoushi_year_context


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument(
        "--elapsed-years",
        type=int,
        help="原历下算非负距算年数；不是公历年，不自动连接出生盘",
    )
    inputs.add_argument(
        "--source-year", type=int, help="原历历书标年，不是冬至发生年或出生日期"
    )
    inputs.add_argument(
        "--winter-year", type=int, help="该历书岁前冬至所属标年；不是UTC日期"
    )
    args = parser.parse_args()
    try:
        context = (
            shoushi_year_context(
                source_year=args.source_year, winter_year=args.winter_year
            )
            if args.source_year is not None or args.winter_year is not None
            else None
        )
        result = shoushi_winter_sun(
            context["elapsed_years"] if context is not None else args.elapsed_years
        )
        if context is not None:
            result["source_year_context"] = context
    except ValueError as error:
        parser.error(f"原历距算无效：{error}")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

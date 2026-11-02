"""复算具名原历正月至腊月，并按独立历书可读项核对；不认证现代日期。"""

import argparse
import json
import sys
from fractions import Fraction

from fatebridge.core.guolao_calendar_year import gujin_fixed_qice_year
from fatebridge.core.guolao_historical import shoushi_winter_cycle
from fatebridge.core.guolao_year_labels import shoushi_year_context
from fatebridge.validation.guolao_calendars import (
    audit_named_year_grid,
    compare_literal_calendar_methods,
    compare_named_calendar_methods,
    compare_official_calendar,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--conjunction-method",
        choices=["floor_table", "day_rate", "literal_table"],
        default="floor_table",
        help="明确具名定朔方法；literal_table用原刊积度及损益，仍有日率歧义，不自动按吻合程度选法",
    )
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument(
        "--reference-id", choices=["jiajing3_1524_wdl108", "wanli27_1599_nlc_preview"]
    )
    inputs.add_argument("--zhongji-days", help="明确原历中积，不是现代JD")
    inputs.add_argument("--elapsed-years", type=int)
    inputs.add_argument("--source-year", type=int)
    inputs.add_argument("--winter-year", type=int)
    inputs.add_argument(
        "--compare-methods-grid",
        type=int,
        nargs=2,
        metavar=("START", "STOP"),
        help="同一整数范围逐年对照两种方法，不择优拼接；不要同时指定单一方法",
    )
    inputs.add_argument(
        "--compare-literal-grid",
        type=int,
        nargs=2,
        metavar=("START", "STOP"),
        help="同一范围对照day_rate与literal_table，不择优拼接；不要同时指定单一方法",
    )
    inputs.add_argument(
        "--elapsed-year-grid",
        type=int,
        nargs=2,
        metavar=("START", "STOP"),
        help="原历距算整数范围，前含后不含；只查内部覆盖",
    )
    args = parser.parse_args()
    try:
        if (
            args.compare_methods_grid is not None
            or args.compare_literal_grid is not None
        ):
            if "--conjunction-method" in sys.argv[1:] or any(
                a.startswith("--conjunction-method=") for a in sys.argv[1:]
            ):
                parser.error("双方法对照不能同时选择单一具名方法")
            result = (
                compare_named_calendar_methods(*args.compare_methods_grid)
                if args.compare_methods_grid is not None
                else compare_literal_calendar_methods(*args.compare_literal_grid)
            )
        elif args.elapsed_year_grid is not None:
            result = audit_named_year_grid(
                *args.elapsed_year_grid, conjunction_method=args.conjunction_method
            )
        elif args.reference_id is not None:
            result = compare_official_calendar(
                args.reference_id, conjunction_method=args.conjunction_method
            )
        else:
            context = (
                shoushi_year_context(
                    source_year=args.source_year, winter_year=args.winter_year
                )
                if args.source_year is not None or args.winter_year is not None
                else None
            )
            elapsed = (
                context["elapsed_years"] if context is not None else args.elapsed_years
            )
            middle = (
                shoushi_winter_cycle(elapsed).zhongji_days
                if elapsed is not None
                else Fraction(args.zhongji_days)
            )
            result = gujin_fixed_qice_year(
                middle, conjunction_method=args.conjunction_method
            )
            if context is not None:
                result["source_year_context"] = context
            if elapsed is not None:
                result["elapsed_years"] = elapsed
    except (ValueError, ZeroDivisionError) as error:
        parser.error(f"原历输入无效：{error}")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

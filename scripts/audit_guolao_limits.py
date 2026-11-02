"""Audit the selected source's local limit ruler; does not produce a birth schedule."""

import argparse
import json
from fractions import Fraction

from fatebridge.core.guolao_limits import limit_scale, limit_scale_audit
from fatebridge.core.guolao_ruler_calendar import (
    NominalSourceDate,
    ruler_calendar_audit,
    ruler_calendar_scale,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--palace", help="原尺宫限名，如官禄；命宫起限尚未复原")
    parser.add_argument(
        "--source-calendar", choices=["nlc3150"], help="显式选择NLC3150刊载月日尺"
    )
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument(
        "--elapsed-source-years", help="已入本限的原尺年数，十进制或分数"
    )
    inputs.add_argument(
        "--scale-degrees", help="本限30格尺内的位置，十进制或分数；不是黄经"
    )
    inputs.add_argument("--cell", type=int, help="查原尺第1至30格的原尺年数区间")
    inputs.add_argument(
        "--nominal-source-date", help="本限原尺序年-月-日，如1-5-12；不是公历或周岁"
    )
    args = parser.parse_args()
    has_input = any(
        value is not None
        for value in (
            args.elapsed_source_years,
            args.scale_degrees,
            args.cell,
            args.nominal_source_date,
        )
    )
    if has_input != (args.palace is not None):
        parser.error("指定宫限时须且仅须提供一种局部原尺输入；不提供参数则查看速率审计")
    if args.nominal_source_date is not None and args.source_calendar is None:
        parser.error("名义原尺日期须显式选择 --source-calendar nlc3150")
    if args.source_calendar is not None and args.elapsed_source_years is not None:
        parser.error("NLC3150月日尺只接受名义日期、尺格度或格号；不隐式转换原尺年")
    result = (
        ruler_calendar_audit()
        if args.source_calendar is not None
        else limit_scale_audit()
    )
    result["calculation"] = None
    if has_input:
        try:
            if args.source_calendar is not None:
                calendar_scale = ruler_calendar_scale(args.palace)
                if args.cell is not None:
                    result["calculation"] = calendar_scale.cell_interval(args.cell)
                elif args.nominal_source_date is not None:
                    parts = args.nominal_source_date.split("-")
                    if len(parts) != 3 or not all(
                        p.isascii() and p.isdigit() for p in parts
                    ):
                        raise ValueError("名义日期须为三个正整数序年-月-日")
                    year, month, day = map(int, parts)
                    result["calculation"] = calendar_scale.position(
                        NominalSourceDate(year, month, day)
                    )
                else:
                    result["calculation"] = calendar_scale.at_degrees(
                        Fraction(args.scale_degrees)
                    )
                result["calculation"]["requested_palace"] = args.palace
                print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
                return 0
            scale = limit_scale(args.palace)
            if args.cell is not None:
                start, end = scale.cell_interval(args.cell)
                result["calculation"] = {
                    "palace": args.palace,
                    "cell": args.cell,
                    "interval_start_source_years_exact": str(start),
                    "interval_end_source_years_exact": str(end),
                    "interval_convention": "zero_based_start_inclusive_end_exclusive",
                    "calendar_date": None,
                    "birth_age": None,
                }
            else:
                elapsed = (
                    Fraction(args.elapsed_source_years)
                    if args.elapsed_source_years is not None
                    else scale.elapsed_years(Fraction(args.scale_degrees))
                )
                result["calculation"] = scale.position(elapsed)
                result["calculation"]["requested_palace"] = args.palace
        except (ValueError, ZeroDivisionError) as exc:
            parser.error(f"原尺输入无效：{exc}")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

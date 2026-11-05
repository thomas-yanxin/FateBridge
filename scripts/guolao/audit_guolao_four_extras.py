"""复算具名古历中积的四余至后策、顺逆入宿及下一入口干支。"""

import argparse
import json
from fractions import Fraction

from fatebridge.core.guolao_four_extras import four_extras_source_days
from fatebridge.core.guolao_historical import shoushi_winter_cycle
from fatebridge.core.guolao_year_labels import shoushi_year_context


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--zhongji-days", help="原历中积日数，十进制或分数；不是现代JD")
    inputs.add_argument("--elapsed-years", type=int, help="原历下算非负整数距算")
    inputs.add_argument("--source-year", type=int, help="历书标年；不是冬至发生年")
    inputs.add_argument("--winter-year", type=int, help="岁前冬至所属标年；不是UTC日期")
    parser.add_argument("--winter-cycle-days", help="仅配合中积，明确原历[0,60)冬至分")
    parser.add_argument(
        "--include-mean-lunations",
        action="store_true",
        help="追加具名古今律历考经朔/月数钤审计；不输出定朔农历日期",
    )
    args = parser.parse_args()
    if args.winter_cycle_days is not None and args.zhongji_days is None:
        parser.error(
            "距算或标年路径已有冬至分，不接受重复覆盖；手给冬至分仅配合--zhongji-days"
        )
    try:
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
        cycle = shoushi_winter_cycle(elapsed) if elapsed is not None else None
        middle = (
            cycle.zhongji_days if cycle is not None else Fraction(args.zhongji_days)
        )
        winter = (
            cycle.winter_cycle_days
            if cycle is not None
            else (
                Fraction(args.winter_cycle_days)
                if args.winter_cycle_days is not None
                else None
            )
        )
        result = four_extras_source_days(middle, winter_cycle_days=winter)
        if args.include_mean_lunations:
            from fatebridge.core.guolao_lunations import gujin_four_extras_lunations

            lunations = gujin_four_extras_lunations(middle)
            declared_winter = Fraction(
                lunations["reference_at_winter"]["winter_cycle_days_exact"]
            )
            if winter is not None and winter != declared_winter:
                raise ValueError("所给冬至分与具名古今律历考气应不符，不能混合经朔链")
            result["mean_lunation_audit"] = lunations
        if context is not None:
            result["source_year_context"] = context
        if cycle is not None:
            result["elapsed_years"] = cycle.elapsed_years
    except (ValueError, ZeroDivisionError) as error:
        parser.error(f"原历输入无效：{error}")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

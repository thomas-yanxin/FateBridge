"""卷45刊载行度及36/37/45具名定朔研究；不认证现代农历。"""

import argparse
import json
from fractions import Fraction

from fatebridge.core.guolao_historical import shoushi_winter_cycle
from fatebridge.core.guolao_lunar_velocity import (
    gujin45_lunar_velocity,
    gujin_four_extras_table_days,
    gujin_table_conjunction,
)
from fatebridge.core.guolao_year_labels import shoushi_year_context


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--anomaly-days", help="明确原历入转日数；只查卷45行度")
    inputs.add_argument("--zhongji-days", help="明确原历中积日数；不是现代JD")
    inputs.add_argument("--elapsed-years", type=int)
    inputs.add_argument("--source-year", type=int)
    inputs.add_argument("--winter-year", type=int)
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("--lunation-index", type=int, help="0为天正经朔；不是月号")
    operation.add_argument(
        "--four-extras", action="store_true", help="复算四余入口日号诊断，不赋农历月名"
    )
    args = parser.parse_args()
    try:
        if args.anomaly_days is not None:
            if args.lunation_index is not None or args.four_extras:
                parser.error("入转查表不接受经朔序号或四余历日操作")
            result = gujin45_lunar_velocity(Fraction(args.anomaly_days))
        else:
            if args.lunation_index is None and not args.four_extras:
                parser.error("中积或标年须明确经朔序号，或显式选择--four-extras")
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
            result = (
                gujin_four_extras_table_days(middle)
                if args.four_extras
                else gujin_table_conjunction(middle, args.lunation_index)
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

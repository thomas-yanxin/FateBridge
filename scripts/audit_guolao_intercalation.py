"""卷36固定气策与36/37/45定朔的民用月序研究；不认证现代历日。"""

import argparse
import json
from fractions import Fraction

from fatebridge.core.guolao_historical import shoushi_winter_cycle
from fatebridge.core.guolao_intercalation import (
    gujin_fixed_qice_months,
    gujin_four_extras_calendar,
)
from fatebridge.core.guolao_year_labels import shoushi_year_context


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--zhongji-days", help="明确原历中积，不是现代JD")
    inputs.add_argument("--elapsed-years", type=int)
    inputs.add_argument("--source-year", type=int)
    inputs.add_argument("--winter-year", type=int)
    parser.add_argument("--four-extras", action="store_true")
    args = parser.parse_args()
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
        result = (
            gujin_four_extras_calendar(middle)
            if args.four_extras
            else gujin_fixed_qice_months(middle)
        )
        if context is not None:
            result["source_year_context"] = context
        if cycle is not None:
            following = shoushi_winter_cycle(elapsed + 1)
            increment = following.zhongji_days - cycle.zhongji_days
            result["year_accumulation_diagnostic"] = {
                "elapsed_years": elapsed,
                "effective_year_days_exact": str(cycle.effective_year_days),
                "next_independently_accumulated_winter_increment_days_exact": str(
                    increment
                ),
                "printed_24_qice_minus_that_increment_days_exact": str(
                    Fraction("365.2425") - increment
                ),
                "qice_rescaled_or_endpoint_forced": False,
            }
    except (ValueError, ZeroDivisionError) as error:
        parser.error(f"原历输入无效：{error}")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""按具名原典研究法复算朔弦望；弦望日期须明确原历日出份额。"""

import argparse
import json
from fractions import Fraction

from fatebridge.core.guolao_historical import shoushi_winter_cycle
from fatebridge.core.guolao_lunar_phases import source_lunar_phase
from fatebridge.validation.guolao_lunar_phases import audit_lunar_phase_grid


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--zhongji-days", help="原历中积，不是现代JD")
    inputs.add_argument("--elapsed-years", type=int)
    inputs.add_argument(
        "--elapsed-year-grid", type=int, nargs=2, metavar=("START", "STOP")
    )
    parser.add_argument(
        "--phase-index", type=int, help="0为天正经朔，其后依次上弦、望、下弦、次朔"
    )
    parser.add_argument(
        "--source-sunrise-fraction",
        help="明确给定的原历日内份额，如1/4；不据此认证地点或现代日出",
    )
    args = parser.parse_args()
    if args.elapsed_year_grid is not None:
        if args.phase_index is not None or args.source_sunrise_fraction is not None:
            parser.error(
                "全范围诊断固定72个相位且不供日出分，不能同时选单一相位或日出份额"
            )
    elif args.phase_index is None:
        parser.error("单例须明确--phase-index，不套默认相位")
    try:
        if args.elapsed_year_grid is not None:
            result = audit_lunar_phase_grid(*args.elapsed_year_grid)
        else:
            assert args.phase_index is not None
            middle = (
                shoushi_winter_cycle(args.elapsed_years).zhongji_days
                if args.elapsed_years is not None
                else Fraction(args.zhongji_days)
            )
            sunrise = (
                Fraction(args.source_sunrise_fraction)
                if args.source_sunrise_fraction is not None
                else None
            )
            result = source_lunar_phase(
                middle, args.phase_index, source_sunrise_fraction=sunrise
            )
            if args.elapsed_years is not None:
                result["elapsed_years"] = args.elapsed_years
    except (ValueError, ZeroDivisionError) as error:
        parser.error(f"原历输入无效：{error}")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

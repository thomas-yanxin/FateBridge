"""传播原刊倒序日率的具名候选；共同历日事实只在声明的候选政策下成立。"""

import argparse
import json
from fractions import Fraction

from fatebridge.core.guolao_historical import shoushi_winter_cycle
from fatebridge.core.guolao_literal_candidates import (
    literal_candidate_year,
    literal_lunar_candidates,
)
from fatebridge.validation.guolao_literal_candidates import audit_literal_candidate_grid


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--anomaly-days", help="原历入转日数，不是现代JD")
    inputs.add_argument("--elapsed-years", type=int)
    inputs.add_argument("--zhongji-days", help="原历中积，不是现代JD")
    inputs.add_argument(
        "--elapsed-year-grid", type=int, nargs=2, metavar=("START", "STOP")
    )
    args = parser.parse_args()
    try:
        if args.anomaly_days is not None:
            result = literal_lunar_candidates(Fraction(args.anomaly_days))
        elif args.elapsed_year_grid is not None:
            result = audit_literal_candidate_grid(*args.elapsed_year_grid)
        else:
            middle = (
                shoushi_winter_cycle(args.elapsed_years).zhongji_days
                if args.elapsed_years is not None
                else Fraction(args.zhongji_days)
            )
            result = literal_candidate_year(middle)
            if args.elapsed_years is not None:
                result["elapsed_years"] = args.elapsed_years
    except (ValueError, ZeroDivisionError) as error:
        parser.error(f"原历输入无效：{error}")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

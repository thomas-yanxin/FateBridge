"""检查原刊日率冲突或具名整数积度插值，不填原刊空格。"""

import argparse
import json
from fractions import Fraction

from fatebridge.core.guolao_day_rate import audit_day_rate_table, gujin_day_rate_lunar


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--table-audit", action="store_true")
    group.add_argument("--anomaly-days", help="明确原历入转日数，不是现代JD")
    args = parser.parse_args()
    try:
        result = (
            audit_day_rate_table()
            if args.table_audit
            else gujin_day_rate_lunar(Fraction(args.anomaly_days))
        )
    except (ValueError, ZeroDivisionError) as error:
        parser.error(f"原历输入无效：{error}")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

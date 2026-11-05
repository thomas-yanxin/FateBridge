"""审计卷45全字段积度/损益或计算原刊插值，不用相邻差改写损益。"""

import argparse
import json
from fractions import Fraction

from fatebridge.core.guolao_cumulative_table import (
    audit_gujin45_cumulative_table,
    gujin_literal_lunar,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--table-audit", action="store_true")
    group.add_argument("--anomaly-days", help="明确原历入转日数，不是现代JD")
    args = parser.parse_args()
    try:
        result = (
            audit_gujin45_cumulative_table()
            if args.table_audit
            else gujin_literal_lunar(Fraction(args.anomaly_days))
        )
    except (ValueError, ZeroDivisionError) as error:
        parser.error(f"原历输入无效：{error}")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

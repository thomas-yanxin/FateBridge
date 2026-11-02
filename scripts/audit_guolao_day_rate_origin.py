"""严格核对日率空格输出修复；旧命令和其他计算数值不得改变。"""

import argparse
import json
from pathlib import Path

from fatebridge.validation.guolao_day_rate_origin import compare_origin_schema_outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = compare_origin_schema_outputs(
            json.loads(args.before.read_text()), json.loads(args.after.read_text())
        )
    except (ValueError, TypeError, KeyError) as error:
        parser.error(f"存在未声明的输出变化：{error}")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Read the named Qianyuan source-day ratio, without angular or natal fallback."""

import argparse
import json
from fractions import Fraction

from fatebridge.core.guolao_qianyuan_initial import (
    BASIS,
    QianyuanSourceDays,
    audit_original_examples,
    initial_limit,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elapsed-source-days")
    parser.add_argument("--quantity-basis", help="须明确为" + BASIS)
    args = parser.parse_args()
    if (args.elapsed_source_days is None) != (args.quantity_basis is None):
        parser.error("查询须同时声明原书日数和quantity-basis；不自动把度数当日数")
    try:
        if args.elapsed_source_days is None:
            result = audit_original_examples()
        else:
            result = initial_limit(
                QianyuanSourceDays(
                    Fraction(args.elapsed_source_days), args.quantity_basis
                )
            )
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

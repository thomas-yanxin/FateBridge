"""Read the complete NIJL image77 grid or retain full cross-witness comparisons."""

import argparse
import json

from fatebridge.core.guolao_nijl_grid import (
    audit_nijl_grid,
    compare_intro_examples,
    compare_ma591,
    literal_cell,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--compare-ma591", action="store_true")
    modes.add_argument("--compare-intro-examples", action="store_true")
    parser.add_argument("--palace")
    parser.add_argument("--column", type=int)
    args = parser.parse_args()
    if (args.palace is None) != (args.column is None):
        parser.error("原格查询须同时给出宫支和原列号")
    if args.palace is not None and (args.compare_ma591 or args.compare_intro_examples):
        parser.error("完整比较不能混用单格查询，不自动选列或移列")
    try:
        if args.compare_ma591:
            result = compare_ma591()
        elif args.compare_intro_examples:
            result = compare_intro_examples()
        elif args.palace is not None:
            result = literal_cell(palace=args.palace, column=args.column)
        else:
            result = audit_nijl_grid()
    except (TypeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

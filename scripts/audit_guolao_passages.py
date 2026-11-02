"""Read Lu Wei image27's four calendars with an explicit whole-degree policy."""

import argparse
import json

from fatebridge.core.guolao_passages import (
    CALENDARS,
    POLICIES,
    compare_nijl_shoushi,
    load_registry,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--whole-degree-policy", required=True, choices=POLICIES)
    parser.add_argument("--calendar", choices=CALENDARS)
    parser.add_argument("--branch")
    parser.add_argument("--compare-yuanshi", action="store_true")
    parser.add_argument("--compare-nijl-shoushi", action="store_true")
    args = parser.parse_args()
    if args.compare_nijl_shoushi and (
        args.calendar is not None or args.branch is not None or args.compare_yuanshi
    ):
        parser.error("NIJL授时对照须单独读取十二格，不与原见证的选格或元史对照混用")
    if (args.calendar is None) != (args.branch is None):
        parser.error("单格查询须同时给历名与辰支")
    if args.compare_yuanshi and args.calendar is None:
        parser.error("版本对照须明确给历名与辰支")
    registry = load_registry()
    try:
        if args.compare_nijl_shoushi:
            result = compare_nijl_shoushi(whole_degree_policy=args.whole_degree_policy)
        elif args.calendar is None:
            result = registry.audit(whole_degree_policy=args.whole_degree_policy)
        elif args.compare_yuanshi:
            result = registry.compare_yuanshi(
                args.calendar, args.branch, whole_degree_policy=args.whole_degree_policy
            )
        else:
            result = registry.entry(
                args.calendar, args.branch, whole_degree_policy=args.whole_degree_policy
            )
    except (TypeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

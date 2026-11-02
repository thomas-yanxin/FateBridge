"""Audit a named Shoushi width witness without closing the circle by repair."""

import argparse
import json

from fatebridge.core.guolao_passages import POLICIES
from fatebridge.core.guolao_widths import QUARTER_POLICIES, SOURCES, load_row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=tuple(SOURCES), default="tohoku")
    parser.add_argument("--quarter-policy", required=True, choices=QUARTER_POLICIES)
    parser.add_argument("--compare-passages", action="store_true")
    parser.add_argument("--whole-degree-policy", choices=POLICIES)
    args = parser.parse_args()
    if args.compare_passages != (args.whole_degree_policy is not None):
        parser.error("过宫对照须同时给--compare-passages与--whole-degree-policy")
    row = load_row(args.source)
    result = (
        row.audit_passages(
            quarter_policy=args.quarter_policy,
            whole_degree_policy=args.whole_degree_policy,
        )
        if args.compare_passages
        else row.audit(quarter_policy=args.quarter_policy)
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

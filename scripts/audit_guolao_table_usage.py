"""Audit literal locations with a required, unadjudicated context hypothesis."""

import argparse
import json

from fatebridge.core.guolao_table_usage import (
    POLICY,
    audit_intro_usage,
    conditional_contexts,
    locate_label,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context-policy", required=True, choices=[POLICY])
    parser.add_argument("--all-contexts", action="store_true")
    parser.add_argument("--palace")
    parser.add_argument("--mansion")
    parser.add_argument("--label")
    args = parser.parse_args()
    labels = [args.palace, args.mansion, args.label]
    if any(value is not None for value in labels) and (
        args.all_contexts or not all(value is not None for value in labels)
    ):
        parser.error("原字查询须齐全给出宫支、宿名、标签，不能混用全表模式")
    try:
        if args.palace is not None:
            label = "初" if args.label == "初" else int(args.label)
            result = locate_label(
                palace=args.palace,
                mansion=args.mansion,
                label=label,
                context_policy=args.context_policy,
            )
        elif args.all_contexts:
            result = conditional_contexts(context_policy=args.context_policy)
        else:
            result = audit_intro_usage(context_policy=args.context_policy)
    except (TypeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

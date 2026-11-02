"""Convert within a named historical table; does not infer modern 命度 or longitude."""

import argparse
import json
from fractions import Fraction

from fatebridge.core.guolao_coordinates import PROFILES, audit_opposite_examples


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        required=True,
        choices=PROFILES,
        help="明确选择文献版本，不自动合并异文",
    )
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument(
        "--angle-from-jiao", help="角初起古度，可正负周回；不是现代黄经"
    )
    inputs.add_argument("--mansion", help="所选原典的简体宿名，须同时给--degree")
    inputs.add_argument("--palace", help="十二次辰支，须同时给--degree；不是功能宫")
    parser.add_argument("--degree", help="宿内或十二次内古度，十进制或分数文本")
    parser.add_argument(
        "--audit-opposite-examples",
        action="store_true",
        help="逐一比较具名跨书原例及未采纳的对度候选，不选择高命中版本",
    )
    args = parser.parse_args()
    local_input = args.mansion is not None or args.palace is not None
    if local_input != (args.degree is not None):
        parser.error("宿名或辰支须且仅须配一个--degree；不可将局部度数用于全周角")
    profile = PROFILES[args.profile]
    if args.audit_opposite_examples and (
        local_input or args.degree is not None or args.angle_from_jiao is not None
    ):
        parser.error("原例审计不可混用局部坐标或全周角输入")
    result = {"audit": profile.audit(), "calculation": None}
    try:
        if args.audit_opposite_examples:
            result["opposite_degree_candidates"] = audit_opposite_examples(profile)
        if args.angle_from_jiao is not None:
            result["calculation"] = profile.locate(Fraction(args.angle_from_jiao))
        elif args.mansion is not None:
            result["calculation"] = profile.from_mansion(
                args.mansion, Fraction(args.degree)
            )
        elif args.palace is not None:
            result["calculation"] = profile.from_palace(
                args.palace, Fraction(args.degree)
            )
    except (ValueError, ZeroDivisionError) as error:
        parser.error(f"原典坐标输入无效：{error}")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

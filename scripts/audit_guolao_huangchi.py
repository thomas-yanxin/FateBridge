"""Audit named source 黄赤道率 or project fixed source mansion boundaries."""

import argparse
import json
from fractions import Fraction

from fatebridge.core.guolao_huangchi import load_table, project_reference_mansions
from fatebridge.core.guolao_solar import shoushi_winter_sun


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, choices=["nlc166", "wikisource"])
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--degree", help="至后或分后本地积度，不是宿内度或现代坐标")
    inputs.add_argument(
        "--winter-mansion", help="投影28宿时明确给定固定赤道表的冬至宿名"
    )
    inputs.add_argument(
        "--elapsed-years",
        type=int,
        help="明确原历下算距算，接冬至太阳赤道推步后投影28宿",
    )
    parser.add_argument("--winter-degree", help="须与--winter-mansion成对的宿内古度")
    parser.add_argument("--origin", choices=["solstice", "equinox"])
    parser.add_argument(
        "--direction", choices=["equatorial_to_ecliptic", "ecliptic_to_equatorial"]
    )
    args = parser.parse_args()
    if (args.winter_mansion is not None) != (args.winter_degree is not None):
        parser.error("冬至宿名与宿内古度须同时提供")
    if args.degree is not None:
        if args.origin is None or args.direction is None:
            parser.error("本地积度转换须明确至后/分后与转换方向")
    elif args.origin is not None or args.direction is not None:
        parser.error("至后/分后与转换方向只用于--degree本地积度")
    try:
        table = load_table(args.profile)
        result = {
            "audit": table.audit(),
            "calculation": None,
            "source_winter_sun": None,
            "projection": None,
        }
        if args.degree is not None:
            assert args.origin is not None and args.direction is not None
            result["calculation"] = table.convert(
                Fraction(args.degree), origin=args.origin, direction=args.direction
            )
        elif args.winter_mansion is not None:
            result["projection"] = project_reference_mansions(
                profile=args.profile,
                winter_mansion=args.winter_mansion,
                winter_degree_du=Fraction(args.winter_degree),
            )
        elif args.elapsed_years is not None:
            solar = shoushi_winter_sun(args.elapsed_years)
            result["source_winter_sun"] = solar
            result["projection"] = project_reference_mansions(
                profile=args.profile,
                winter_mansion=solar["mansion"],
                winter_degree_du=Fraction(solar["degree_in_mansion_du_exact"]),
            )
    except (ValueError, ZeroDivisionError) as error:
        parser.error(f"原历黄赤道输入无效：{error}")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

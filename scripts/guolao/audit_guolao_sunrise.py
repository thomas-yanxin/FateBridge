"""具名半夜分表与九服漏刻研究；不推定出生地、日太阳积度或现代日出。"""

import argparse
import json
from fractions import Fraction as F

from fatebridge.core.guolao_sunrise import load_table, local_solstice_sunrise
from fatebridge.validation.guolao_sunrise import audit_sunrise_tables


def exact_arg(value: str) -> F:
    try:
        return F(value)
    except (ValueError, ZeroDivisionError) as error:
        raise argparse.ArgumentTypeError(
            "须为有效的原单位有理数，分母不能为零"
        ) from error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("audit", help="保留两版全部刊差残差、短末段及异文")
    table = commands.add_parser("table", help="明确大都原表及已折叠源积度")
    table.add_argument(
        "--profile", required=True, choices=["gujin37_siku", "yuanshi55_digital"]
    )
    table.add_argument("--local-degree", required=True, type=exact_arg)
    table.add_argument("--solar-side", required=True, choices=["inside", "outside"])
    table.add_argument("--basis", required=True, choices=["dadu_source_table"])
    local = commands.add_parser("local", help="需提供当地至日夜刻及观测引用")
    local.add_argument("--declination-du", required=True, type=exact_arg)
    local.add_argument("--solar-side", required=True, choices=["inside", "outside"])
    local.add_argument(
        "--measured-solstice", required=True, choices=["winter", "summer"]
    )
    local.add_argument("--measured-night-ke", required=True, type=exact_arg)
    local.add_argument("--observation-reference", required=True)
    args = parser.parse_args()
    try:
        if args.command == "audit":
            result = audit_sunrise_tables()
        elif args.command == "table":
            result = load_table(args.profile).sunrise(
                args.local_degree, solar_side=args.solar_side, basis=args.basis
            )
        else:
            result = local_solstice_sunrise(
                args.declination_du,
                solar_side=args.solar_side,
                measured_solstice=args.measured_solstice,
                measured_night_ke=args.measured_night_ke,
                observation_reference=args.observation_reference,
            )
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

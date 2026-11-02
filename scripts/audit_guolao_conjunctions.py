"""具名经朔、盈缩、迟疾及论文定朔公式研究；不输出已校准农历。"""

import argparse
import csv
import hashlib
import json
from fractions import Fraction
from pathlib import Path

from fatebridge.core.guolao_conjunctions import (
    GUJIN_COMPONENTS,
    LI_1996,
    solar_correction,
    source_conjunction,
)
from fatebridge.core.guolao_historical import shoushi_winter_cycle
from fatebridge.core.guolao_year_labels import shoushi_year_context


def compare_paper_table(path: Path) -> dict:
    """Compare all printed fields, never repair a datum to make a test pass."""
    rows = list(csv.DictReader(path.read_text().splitlines()))
    if len(rows) != 28 or [int(row["index"]) for row in rows] != list(range(28)):
        raise ValueError("论文算例须保留全部28行及原顺序")
    middle = shoushi_winter_cycle(19).zhongji_days
    output = []
    screen = Fraction("0.0003")
    for row in rows:
        result = source_conjunction(middle, int(row["index"]), profile_id=LI_1996)
        calculated = {
            "mean_cycle": result["mean_conjunction_day_cycle_exact"],
            "solar_phase": result["solar"]["solar_phase_days_exact"],
            "solar_du": result["solar"]["signed_correction_ancient_du_exact"],
            "anomaly_days": result["lunar"]["anomaly_phase_days_exact"],
            "lunar_du": result["lunar"]["signed_correction_ancient_du_exact"],
            "velocity_du_per_limit": result["lunar_velocity"][
                "velocity_ancient_du_per_limit_exact"
            ],
            "correction_days": result["time_correction_days_exact"],
            "conjunction_cycle": result["research_conjunction_day_cycle_exact"],
        }
        deltas = {
            key: Fraction(value) - Fraction(row[key])
            for key, value in calculated.items()
        }
        printed_identity_residual = (
            Fraction(row["conjunction_cycle"])
            - Fraction(row["mean_cycle"])
            - Fraction(row["correction_days"])
        )
        gujin_solar = solar_correction(
            Fraction(row["solar_phase"]), profile_id=GUJIN_COMPONENTS
        )
        output.append(
            {
                "index": int(row["index"]),
                "printed": {key: row[key] for key in calculated},
                "calculated_exact": calculated,
                "calculated_minus_printed_exact": {
                    key: str(value) for key, value in deltas.items()
                },
                "fields_exceeding_display_screen": [
                    key for key, delta in deltas.items() if abs(delta) > screen
                ],
                "printed_mean_plus_correction_identity_residual_days_exact": str(
                    printed_identity_residual
                ),
                "gujin_22100_solar_at_identical_printed_phase_comparison_exact": gujin_solar[
                    "signed_correction_ancient_du_exact"
                ],
                "comparison_substituted_into_paper_formula": False,
            }
        )
    return {
        "profile_id": LI_1996,
        "table_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "input_zhongji_days_exact": str(middle),
        "rows": output,
        "display_screen_exact": str(screen),
        "screen_is_scientific_accuracy_threshold": False,
        "rows_exceeding_display_screen": [
            r["index"] for r in output if r["fields_exceeding_display_screen"]
        ],
        "printed_identity_residual_rows_over_screen": [
            r["index"]
            for r in output
            if abs(
                Fraction(r["printed_mean_plus_correction_identity_residual_days_exact"])
            )
            > screen
        ],
        "all_published_values_exact": all(
            Fraction(delta) == 0
            for row in output
            for delta in row["calculated_minus_printed_exact"].values()
        ),
        "all_published_values_within_display_screen": not any(
            row["fields_exceeding_display_screen"] for row in output
        ),
        "original_gujin_velocity_table_adjudicated": False,
        "modern_calendar_calibrated": False,
        "real_world_predictive_validity_tested": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--zhongji-days", help="明确原历中积，不是现代JD")
    inputs.add_argument("--elapsed-years", type=int)
    inputs.add_argument("--source-year", type=int)
    inputs.add_argument("--winter-year", type=int)
    inputs.add_argument(
        "--paper-table", type=Path, help="核对论文全部28行数值CSV，不修订刊载数字"
    )
    parser.add_argument("--profile", choices=[GUJIN_COMPONENTS, LI_1996])
    parser.add_argument("--lunation-index", type=int, help="0为天正经朔；不是农历月号")
    args = parser.parse_args()
    try:
        if args.paper_table is not None:
            if args.profile is not None or args.lunation_index is not None:
                parser.error("论文全表核对不接受覆盖具名参数或行号")
            print(
                json.dumps(
                    compare_paper_table(args.paper_table), ensure_ascii=False, indent=2
                )
            )
            return 0
        if args.profile is None or args.lunation_index is None:
            parser.error("经朔研究须同时明确--profile与--lunation-index")
        context = (
            shoushi_year_context(
                source_year=args.source_year, winter_year=args.winter_year
            )
            if args.source_year is not None or args.winter_year is not None
            else None
        )
        elapsed = (
            context["elapsed_years"] if context is not None else args.elapsed_years
        )
        middle = (
            shoushi_winter_cycle(elapsed).zhongji_days
            if elapsed is not None
            else Fraction(args.zhongji_days)
        )
        result = source_conjunction(
            middle, args.lunation_index, profile_id=args.profile
        )
        if context is not None:
            result["source_year_context"] = context
        if elapsed is not None:
            result["elapsed_years"] = elapsed
    except (ValueError, ZeroDivisionError, OSError, KeyError) as error:
        parser.error(f"原历输入无效：{error}")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Replay source 中积 arithmetic; never convert it into a modern birth chart."""

import argparse
import json
from fractions import Fraction

from fatebridge.core.guolao_classical import purple_cycle_reference
from fatebridge.core.guolao_historical import (
    GUJIN_58_PURPLE,
    purple_historical_position,
    shoushi_winter_cycle,
)
from fatebridge.core.guolao_year_labels import shoushi_year_context


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument(
        "--zhongji-days",
        help="原历中积日数，以十进制或分数输入；不是UTC/TT儒略日",
    )
    inputs.add_argument(
        "--elapsed-years",
        type=int,
        help="授时下算距至元辛巳的非负整数年数；不是现代年份或出生日期",
    )
    inputs.add_argument(
        "--source-year", type=int, help="原历历书标年，不是冬至发生年或出生日期"
    )
    inputs.add_argument(
        "--winter-year", type=int, help="该历书岁前冬至所属标年；不是UTC日期"
    )
    args = parser.parse_args()
    try:
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
        year_cycle = shoushi_winter_cycle(elapsed) if elapsed is not None else None
        middle = (
            year_cycle.zhongji_days
            if year_cycle is not None
            else Fraction(args.zhongji_days)
        )
        result = purple_cycle_reference(middle)
        position = purple_historical_position(middle)
    except (ValueError, ZeroDivisionError) as exc:
        parser.error(f"原历输入无效：{exc}")
    print(
        json.dumps(
            {
                "source": "邢云路《古今律历考》卷58，四库本原页787-635、642、643、647已核",
                "input_kind": (
                    context["input_kind"]
                    if context is not None
                    else (
                        "source_elapsed_years_not_modern_calendar_year"
                        if year_cycle is not None
                        else "source_zhongji_days_not_modern_julian_day"
                    )
                ),
                "zhongji_days_exact": str(middle),
                "year_accumulation": (
                    {
                        "method": "shoushi_whole_century_step_applied_to_full_elapsed_count",
                        "elapsed_years": year_cycle.elapsed_years,
                        "effective_year_days_exact": str(
                            year_cycle.effective_year_days
                        ),
                        "winter_cycle_days_exact": str(year_cycle.winter_cycle_days),
                        "winter_sexagenary_day": year_cycle.winter_sexagenary_day,
                        "winter_fraction_of_day_exact": str(
                            year_cycle.winter_fraction_of_day
                        ),
                        "modern_calendar_date_assigned": False,
                    }
                    if year_cycle is not None
                    else None
                ),
                "arithmetic": {
                    k: {"exact": str(v), "decimal": float(v)} for k, v in result.items()
                },
                "printed_historical_table": {
                    "source_id": position.source_id,
                    "coordinate_frame": GUJIN_58_PURPLE.coordinate_frame,
                    "phase_origin": "箕初",
                    "circle_du_exact": str(GUJIN_58_PURPLE.circle_du),
                    "mansion": position.mansion,
                    "next_mansion": position.next_mansion,
                    "degree_in_mansion_historical_du_exact": str(
                        position.degree_in_mansion_du
                    ),
                    "interval_start_days_exact": str(position.interval_start_days),
                    "interval_end_days_exact": str(position.interval_end_days),
                    "days_until_next_mansion_exact": str(
                        position.days_until_next_mansion
                    ),
                    "coordinate_mapping_to_modern_sky": "unresolved",
                    "used_in_native_birth_chart": False,
                },
                "modern_longitude": None,
                "modern_epoch_calibrated": False,
                "corrected_phase_is_experiment_with_original_offset": True,
                **({"source_year_context": context} if context is not None else {}),
            },
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

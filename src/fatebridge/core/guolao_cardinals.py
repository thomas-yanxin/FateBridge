"""Gujin lvli kao 43's named 318-year four-cardinal worked example.

The source divides mansion-relative winter RA by the *initial* rate, not by
interpolating that value as an accumulation after a solstice. Printed operands
and unrounded quotients have separate calculation lanes. The calendar year's
quarter, coordinate circle's quarter and corrected quarter remain distinct.
No civil date, modern longitude, redated mansion table or life degree follows.
"""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import Any

from fatebridge.core.guolao_classical import BRANCHES, STEMS
from fatebridge.core.guolao_historical import shoushi_winter_cycle
from fatebridge.core.guolao_huangchi import load_table
from fatebridge.core.guolao_solar import shoushi_winter_sun

DATA = Path(__file__).resolve().parents[1] / "data/guolao/gujin43-cardinals-v1.json"
CARDINALS = ("winter", "spring", "summer", "autumn", "next_winter")


def _position_lane(
    *,
    equatorial: tuple[Fraction, Fraction],
    ecliptic: tuple[Fraction, Fraction],
    year: Fraction,
    circle: Fraction,
) -> dict[str, Any]:
    differences = tuple(a - b for a, b in zip(equatorial, ecliptic))
    correction = (differences[0] - differences[1]) / 4
    # Gujin 43 explicitly uses 岁周象限 here. Do not substitute 周天 / 4.
    quarter = year / 4 + correction
    unwrapped = [ecliptic[0] + n * quarter for n in range(5)]
    return {
        "winter_equatorial_du_exact": [str(v) for v in equatorial],
        "winter_ecliptic_du_exact": [str(v) for v in ecliptic],
        "huangchi_differences_du_exact": [str(v) for v in differences],
        "quarter_correction_du_exact": str(correction),
        "year_quarter_du_exact": str(year / 4),
        "coordinate_circle_quarter_du_exact": str(circle / 4),
        "corrected_quarter_du_exact": str(quarter),
        "positions": [
            {
                "cardinal": name,
                "unwrapped_from_ji_start_du_exact": str(value),
                "modulo_circle_from_ji_start_du_exact": str(value % circle),
            }
            for name, value in zip(CARDINALS, unwrapped)
        ],
        "next_winter_closure_residual_du_exact": str(
            unwrapped[-1] - circle - ecliptic[1]
        ),
        "wrong_circle_quarter_closure_residual_du_exact": str(
            ecliptic[0] + 4 * (circle / 4 + correction) - circle - ecliptic[1]
        ),
        "coordinate_unit": "historical_du_not_modern_degrees",
        "position_origin": "source_ji_start_without_a_redated_mansion_reduction",
        "closure_is_internal_identity_not_independent_acceptance": True,
    }


def gujin43_cardinal_example(*, profile: str) -> dict[str, Any]:
    """Replay only the named 318 example, without generalizing its policies.

    Printed winter ecliptic operands belong only to the printed lane. The raw
    lane derives both from the chosen table's initial rate. Neither is selected
    by match count, and neither is substituted into native chart calculations.
    """
    table = load_table(profile)
    raw = DATA.read_bytes()
    source = json.loads(raw)
    current = shoushi_winter_sun(318)
    following = shoushi_winter_sun(319)
    if current["mansion"] != "箕" or following["mansion"] != "箕":
        raise ValueError("具名示例的本、次年冬至须均在箕宿，不套用跨宿差法")
    equatorial = (
        Fraction(current["degree_in_mansion_du_exact"]),
        Fraction(following["degree_in_mansion_du_exact"]),
    )
    year = Fraction(current["effective_year_days_exact"])
    circle = Fraction(current["remainder_period_du_exact"])
    first_rate, second_rate = table.rows[0].rates()
    raw_ecliptic = (
        equatorial[0] * first_rate / second_rate,
        equatorial[1] * first_rate / second_rate,
    )
    printed_ecliptic = tuple(Fraction(v) for v in source["printed_winter_ecliptic_du"])
    printed_lane = _position_lane(
        equatorial=equatorial,
        ecliptic=(printed_ecliptic[0], printed_ecliptic[1]),
        year=year,
        circle=circle,
    )
    raw_lane = _position_lane(
        equatorial=equatorial, ecliptic=raw_ecliptic, year=year, circle=circle
    )

    cycle = shoushi_winter_cycle(318)
    initial_day = cycle.winter_cycle_days
    short = Fraction(source["yingchu_suomo_days"])
    long = Fraction(source["suochu_yingmo_days"])
    spans = (short, long, long, short)
    days = [initial_day]
    for span in spans:
        days.append(days[-1] + span)
    times = []
    for name, value in zip(CARDINALS, days):
        cycle_day = value % 60
        index = int(cycle_day)
        times.append(
            {
                "cardinal": name,
                "unwrapped_source_day_exact": str(value),
                "sexagenary_cycle_day_exact": str(cycle_day),
                "sexagenary_day": STEMS[index % 10] + BRANCHES[index % 12],
                "fraction_of_day_exact": str(cycle_day - index),
            }
        )
    return {
        "method": source["source_id"],
        "source_url": source["source_url"],
        "source_locator": source["locator"],
        "data_sha256": hashlib.sha256(raw).hexdigest(),
        "source_status": "named_digital_original_text_not_newly_facsimile_collated",
        "elapsed_years": 318,
        "source_winter_sun": [current, following],
        "rate_profile": table.audit(),
        "winter_conversion_policy": "source_mansion_relative_RA_times_initial_ecliptic_rate_over_initial_equatorial_rate",
        "initial_ecliptic_rate_du_exact": str(first_rate),
        "initial_equatorial_rate_du_exact": str(second_rate),
        "printed_operands_lane": printed_lane,
        "printed_lane_is_replay_of_explicit_source_operands": True,
        "unrounded_rate_lane": raw_lane,
        "unrounded_minus_printed_winter_du_exact": [
            str(a - b) for a, b in zip(raw_ecliptic, printed_ecliptic)
        ],
        "intermediate_rounding_applied": False,
        "printed_values_used_in_unrounded_lane": False,
        "printed_precision_policy_established": False,
        "source_time_spans_days_exact": [str(v) for v in spans],
        "source_time_spans_minus_year_days_exact": str(sum(spans) - year),
        "cardinal_times": times,
        "integer_day_distances": [int(b) - int(a) for a, b in zip(days, days[1:])],
        "next_winter_time_closure_residual_days_exact": str(
            days[-1] % 60 - shoushi_winter_cycle(319).winter_cycle_days
        ),
        "time_unit": "source_day_and_sexagenary_cycle_not_UTC_or_TT",
        "modern_calendar_date_assigned": False,
        "modern_epoch_calibrated": False,
        "redated_mansion_widths_reconstructed": False,
        "life_degree_accepted": False,
        "used_in_native_birth_chart": False,
        "real_world_efficacy_tested": False,
    }

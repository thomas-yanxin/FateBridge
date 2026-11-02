"""Conditional winter error attribution without changing Shoushi source rules.

The source label serial is not a physical epoch. Terms involving TT days and
solar-clock label days are an algebraic diagnostic, not a fitted time scale.
"""

from __future__ import annotations

from fractions import Fraction as F
from typing import Any

from fatebridge.core.guolao_calendar_date_bridge import (
    CALENDARS,
    calendar_label_from_noon_jdn,
)
from fatebridge.core.guolao_historical import shoushi_winter_cycle

PROFILE = "shoushi_whole_century_conditional_winter_error_budget_v1"
BASE_YEAR = F("365.2425")
# Conditional HKO date-label bridge: Gregorian1280-12-21 plus original0.06day.
# This does not identify an observed TT, UT1 or UTC instant.
SOURCE_EPOCH_LABEL_SERIAL = F(2188926) + F("0.06")
CLOCK_HYPOTHESES = ("local_mean_solar", "local_apparent_solar")


def century_year_diagnostic(elapsed_years: int) -> dict[str, Any]:
    """Keep source year parameter separate from successive winter intervals."""
    if type(elapsed_years) is not int or not 0 <= elapsed_years < 400:
        raise ValueError("本诊断仅覆盖明确的0至399年距算")
    current = shoushi_winter_cycle(elapsed_years)
    previous = shoushi_winter_cycle(elapsed_years - 1) if elapsed_years else None
    interval = current.zhongji_days - previous.zhongji_days if previous else None
    jump = (
        interval - previous.effective_year_days
        if previous is not None and interval is not None
        else None
    )
    return {
        "elapsed_years": elapsed_years,
        "source_year_parameter_days_exact": str(current.effective_year_days),
        "source_zhongji_days_exact": str(current.zhongji_days),
        "successive_winter_interval_days_exact": (
            str(interval) if interval is not None else None
        ),
        "century_step_vs_previous_rate_days_exact": (
            str(jump) if jump is not None else None
        ),
        "century_adjustment_from_fixed_base_year_days_exact": str(
            current.zhongji_days - elapsed_years * BASE_YEAR
        ),
        "source_rule_replaced_with_cumulative_year_sum": False,
    }


def shoushi_winter_error_budget(
    elapsed_years: int,
    *,
    reference_tt_jd: F,
    reference_epoch_tt_jd: F,
    reference_local_label_serial: F,
    reference_epoch_local_label_serial: F,
    clock_hypothesis: str,
) -> dict[str, Any]:
    """Four exact signed terms, source minus conditional external reference.

    The caller supplies independent winter TT and explicit mean/apparent local
    clock labels. No site, year rate, source epoch or offset is estimated here.
    """
    diagnostic = century_year_diagnostic(elapsed_years)
    values = (
        reference_tt_jd,
        reference_epoch_tt_jd,
        reference_local_label_serial,
        reference_epoch_local_label_serial,
    )
    if any(not isinstance(v, F) for v in values):
        raise TypeError("外部TT和地方钟标签须明确提供Fraction，不作隐式转换")
    if clock_hypothesis not in CLOCK_HYPOTHESES:
        raise ValueError("须分别声明地方平太阳时或地方真太阳时假设")
    for tt, year in (
        (reference_tt_jd, 1280 + elapsed_years),
        (reference_epoch_tt_jd, 1280),
    ):
        label = calendar_label_from_noon_jdn(int(tt + F(1, 2)), calendar=CALENDARS[0])
        if label[0] != year or label[1] != 12 or not 19 <= label[2] <= 24:
            raise ValueError("参考TT须属于对应冬至年的固定12月19至24日窗口")
    # Reference clocks must describe the same local day as their TT. This broad
    # guard is not a historical clock accuracy bound or a fitted tolerance.
    if any(
        abs(local - (tt + F(1, 2))) >= 1
        for tt, local in (
            (reference_tt_jd, reference_local_label_serial),
            (reference_epoch_tt_jd, reference_epoch_local_label_serial),
        )
    ):
        raise ValueError("地方钟标签与对应TT相差整日，不能混用日序")
    if elapsed_years == 0 and (
        reference_tt_jd != reference_epoch_tt_jd
        or reference_local_label_serial != reference_epoch_local_label_serial
    ):
        raise ValueError("距算0的参考必须与参考历元相同，不能隐式拟合起点")
    source_zhongji = F(diagnostic["source_zhongji_days_exact"])
    tt_interval = reference_tt_jd - reference_epoch_tt_jd
    local_interval = reference_local_label_serial - reference_epoch_local_label_serial
    terms = {
        "epoch_clock_label_offset": SOURCE_EPOCH_LABEL_SERIAL
        - reference_epoch_local_label_serial,
        "source_whole_century_adjustment": source_zhongji - elapsed_years * BASE_YEAR,
        "fixed_base_year_vs_TT_interval": elapsed_years * BASE_YEAR - tt_interval,
        "TT_interval_vs_local_clock_label_interval": tt_interval - local_interval,
    }
    difference = (
        SOURCE_EPOCH_LABEL_SERIAL + source_zhongji - reference_local_label_serial
    )
    if sum(terms.values(), F()) != difference:
        raise ArithmeticError("冬至误差分解未闭合")
    return {
        "profile_id": PROFILE,
        "source_year": 1281 + elapsed_years,
        "winter_year": 1280 + elapsed_years,
        "clock_hypothesis": clock_hypothesis,
        "source_epoch_calendar_label_serial_exact": str(SOURCE_EPOCH_LABEL_SERIAL),
        "source_winter_calendar_label_serial_exact": str(
            SOURCE_EPOCH_LABEL_SERIAL + source_zhongji
        ),
        "reference_tt_jd_exact": str(reference_tt_jd),
        "reference_epoch_tt_jd_exact": str(reference_epoch_tt_jd),
        "reference_local_calendar_label_serial_exact": str(
            reference_local_label_serial
        ),
        "reference_epoch_local_calendar_label_serial_exact": str(
            reference_epoch_local_label_serial
        ),
        "signed_terms_nominal_days_exact": {
            name: str(value) for name, value in terms.items()
        },
        "source_minus_reference_nominal_minutes_exact": str(difference * 1440),
        "algebraic_closure_error_nominal_days_exact": "0",
        "year_diagnostic": diagnostic,
        "clock_label_days_equated_to_uniform_TT_days": False,
        "reference_epoch_fitted_to_source": False,
        "source_midnight_calibrated": False,
        "historical_earth_rotation_uncertainty_quantified": False,
        "physical_accuracy_or_prediction_certified": False,
    }

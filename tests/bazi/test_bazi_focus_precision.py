"""Precision receipts must not promote a classical label or hide an unknown."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
from fractions import Fraction
from zoneinfo import ZoneInfo

import pytest

from fatebridge.core import almanac
from fatebridge.core.bazi.bazi_evidence import build_natal_evidence
from fatebridge.core.calendar import BaZiCalendar
from fatebridge.core.classical_force import build_force_components
from fatebridge.core.contracts.output_classical_force import ClassicalForceComponents
from fatebridge.core.elements import ElementAnalysis
from fatebridge.utils.civil_time import ZonedCalendar


def chart(text):
    return dict(zip(("year", "month", "day", "hour"), map(tuple, text.split())))


def test_actual_case_body_seal_ratio_uses_unrounded_input_and_preserves_display() -> (
    None
):
    pillars = chart("壬午 己酉 戊辰 庚申")
    result = ElementAnalysis.analyze_day_master_strength(pillars)
    assessment = result["assessment"]
    before = deepcopy(assessment)
    force = build_natal_evidence(pillars, result)["force_components"]
    parts = force["components"]
    with localcontext() as context:
        context.prec = 80
        body = Decimal.from_float(parts["body"]["engineering_energy_unrounded"])
        seal = Decimal.from_float(parts["seal"]["engineering_energy_unrounded"])
        expected = float(body / (body + seal))
    composition = force["engineering_composition"]
    assert composition["ratio_basis"] == "unrounded_same_assessment"
    assert composition["body_within_support_share"] == pytest.approx(
        expected, abs=1e-15, rel=0
    )
    assert {
        v["element"]: v["engineering_energy"] for v in parts.values()
    } == assessment["effective_elements"]
    assert parts["body"]["engineering_energy"] != float(body)
    assert assessment == before and assessment["strength_level"] == "弱"
    classical = force["classical_adjudication"]
    assert classical["status"] == "not_adjudicated"
    assert all(
        classical[key] is None
        for key in (
            "body_strength",
            "seal_weight",
            "body_seal_relation",
            "ordinary_fuyi_applicable",
        )
    )
    assert classical["pending_conditions"]
    ClassicalForceComponents.model_validate(force)


def test_different_unrounded_values_do_not_become_equal_through_display_rounding() -> (
    None
):
    pillars = chart("甲子 丙寅 戊辰 庚申")
    exact = {"木": 0.0, "火": 1.0000002, "土": 1.0000001, "金": 0.0, "水": 0.0}
    assessment = {
        "effective_elements": {e: round(v, 6) for e, v in exact.items()},
        "effective_elements_unrounded": exact,
    }
    force = build_force_components(pillars, assessment, {})
    assert (
        force["engineering_composition"]["body_seal_energy_relation"] == "seal_greater"
    )
    assert force["engineering_composition"]["body_within_support_share"] < 0.5


def test_partial_and_missing_receipts_do_not_recalculate_or_use_rounded_energy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("Never recalculate a missing evidence quantity")

    monkeypatch.setattr(ElementAnalysis, "analyze_day_master_strength", forbidden)
    pillars = chart("甲子 丙寅 戊辰 庚申")
    absent = build_force_components(pillars, {}, {})
    assert absent["engineering_composition"]["ratio_basis"] == "not_supplied"
    assert absent["engineering_composition"]["body_within_support_share"] is None
    partial = build_force_components(
        pillars, {"effective_elements": dict.fromkeys("木火土金水", 1.0)}, {}
    )
    assert partial["engineering_composition"]["ratio_basis"] == "not_supplied"
    assert partial["components"]["body"]["engineering_energy_unrounded"] is None


def test_rounded_elapsed_days_cannot_be_used_as_a_subday_duty_boundary() -> None:
    zone = "Asia/Shanghai"
    term = next(
        t for t in almanac.get_solar_terms_for_year(2026, zone) if t.name == "惊蛰"
    )
    left = almanac.get_bazi_month_context(
        term.moment + timedelta(days=7, microseconds=-1), zone
    )
    right = almanac.get_bazi_month_context(
        term.moment + timedelta(days=7, microseconds=1), zone
    )
    assert term.civil_point is not None
    unix_epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    unix_epoch_jd = Fraction("2440587.5")
    displayed = term.moment.astimezone(timezone.utc) - unix_epoch
    displayed_seconds = Fraction(displayed // timedelta(microseconds=1), 1_000_000)
    exact_term_seconds = (term.civil_point.day - unix_epoch_jd) * 86400
    display_delta = displayed_seconds - exact_term_seconds
    seven_days = 7 * 86400
    assert left["days_since_start"] == right["days_since_start"] == 7.0
    assert left["elapsed_seconds_since_start"] == float(
        seven_days + display_delta - Fraction(1, 1_000_000)
    )
    assert right["elapsed_seconds_since_start"] == float(
        seven_days + display_delta + Fraction(1, 1_000_000)
    )
    assert left["elapsed_seconds_since_start"] < seven_days
    assert right["elapsed_seconds_since_start"] > seven_days
    assert left["elapsed_basis"] == right["elapsed_basis"] == "utc_instant_seconds"
    evidence = build_natal_evidence(chart("甲戌 丙寅 戊辰 庚申"))
    assert evidence["month_command"]["intra_month_duty"]["status"] == "not_adjudicated"
    assert evidence["month_command"]["intra_month_duty"]["selected_stem"] is None


def test_monthly_elapsed_seconds_use_physical_time_across_dst(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    zone = ZoneInfo("America/New_York")
    start = datetime(2024, 3, 10, tzinfo=zone)
    end = datetime(2024, 4, 4, tzinfo=zone)

    def term(name, moment):
        return almanac.SolarTerm(name, ZonedCalendar.from_datetime(moment))

    monkeypatch.setattr(
        almanac,
        "get_bazi_month_boundaries",
        lambda *args: (term("惊蛰", start), term("清明", end), "卯", 1),
    )
    value = almanac.get_bazi_month_context(
        datetime(2024, 3, 11, tzinfo=zone), str(zone)
    )
    assert value["elapsed_seconds_since_start"] == 23 * 3600
    assert value["comparison_datetime"] == "2024-03-11T00:00:00-04:00"


def test_identical_four_pillars_do_not_determine_the_day_since_the_monthly_jie() -> (
    None
):
    # Synthetic information-loss witness, not an independent calendar reference.
    dates = [datetime(1900, 2, 22, 10), datetime(1960, 2, 8, 10)]
    pillars = [
        BaZiCalendar.get_four_pillars(
            d, timezone_name="Asia/Shanghai", civil_datetime=d
        )
        for d in dates
    ]
    assert pillars[0] == pillars[1] == chart("庚子 戊寅 丙寅 癸巳")
    windows = [almanac.get_bazi_month_context(d, "Asia/Shanghai") for d in dates]
    assert windows[0]["elapsed_seconds_since_start"] > 15 * 86400
    assert windows[1]["elapsed_seconds_since_start"] < 7 * 86400
    assert all(
        build_natal_evidence(p)["month_command"]["intra_month_duty"]["selected_stem"]
        is None
        for p in pillars
    )

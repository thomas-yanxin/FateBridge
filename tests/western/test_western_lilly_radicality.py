"""Frozen primary clauses, exact boundaries, reported context and native-hour inputs."""

import copy
import json
import math
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

import fatebridge.core.lilly_radicality_inputs as clock
from fatebridge.core.astro.classical import _sun_event
from fatebridge.core.astro.time_scales import datetime_from_ut1, ephemeris_time
from fatebridge.core.ephemeris_runtime import (
    configure_ephemeris_path,
    configured_ephemeris_path,
)
from fatebridge.core.lilly_radicality import (
    evaluate_radicality,
    hour_affinity,
    normalize_context,
)
from fatebridge.core.output_western import HoraryRadicality
from fatebridge.core.predictive.native_chart import build_native_subject
from fatebridge.core.requests.western_events import LillyRadicalityContext
from fatebridge.utils.errors import EphemerisSourceError
from scripts.western.audit_western_lilly_radicality import audit

REFERENCE = json.loads(
    (
        Path(__file__).parents[1] / "fixtures/western-lilly-radicality-1647.json"
    ).read_text()
)


def states():
    return {
        p: {
            "longitude": float(lon),
            "speed": float(speed),
            "retrograde": speed < 0,
            "occupied_house": house,
            "house_assignment": {"assigned_house": house},
        }
        for p, lon, speed, house in [
            ("Sun", 123, 1, 10),
            ("Moon", 50, 13, 2),
            ("Mercury", 200, 1.5, 7),
            ("Venus", 170, 1, 6),
            ("Mars", 10, 0.5, 1),
            ("Jupiter", 100, 0.08, 4),
            ("Saturn", 250, 0.03, 9),
        ]
    }


def review(
    asc=10,
    *,
    planets=None,
    context=None,
    voc=False,
    seventh="Libra",
    topic=10,
    hour="Mars",
):
    return evaluate_radicality(
        asc,
        planets if planets is not None else states(),
        {
            "void_of_course": voc,
            "motion_basis": {"method_id": "synthetic_predicate_control"},
        },
        {"status": "transcribed_or_synthetic_hour", "hour": {"hour_ruler": hour}},
        seventh_sign=seventh,
        quesited_house=topic,
        sect="day",
        context=context,
        house_system="R",
        zodiac_type="Tropic",
    )


def clause(value, code):
    return next(c for c in value["clauses"] if c["code"] == code)


def test_primary_assets_inventory_natures_and_all_four_printed_affinity_examples():
    value = audit()
    assert value["source_assets_verified"] == 35
    assert value["manual_clause_inventory_checked"] == 12
    assert value["own_nature_records_checked"] == 7
    assert (
        value["printed_affinity_examples_compared"]
        == value["printed_affinity_examples_reproduced"]
        == 4
    )
    assert value["bounded_reference_gate_passed"] is True
    assert value["full_original_text_acceptance"] is False
    assert value["real_world_observations_added"] == 0


@pytest.mark.parametrize(
    "case", REFERENCE["declared_boundary_controls"], ids=lambda c: c["id"]
)
def test_independently_frozen_operational_boundary_controls(case):
    if "asc_degrees_in_sign" in case:
        value = review(Fraction(case["asc_degrees_in_sign"]))
        assert value["ascendant_degree_gate"]["early"] is case["early"]
        assert value["ascendant_degree_gate"]["late"] is case["late"]
    else:
        s = states()
        s["Moon"]["longitude"] = Fraction(case["moon_longitude"])
        assert (
            clause(review(planets=s), "C04")["condition_present"]
            is case["via_combusta"]
        )


@pytest.mark.parametrize("side,late", [(-1, False), (0, True), (1, True)])
def test_late_ascendant_27_boundary_does_not_drop_exact_27_or_round_adjacent_doubles(
    side, late
):
    at = (
        27.0 if side == 0 else math.nextafter(27.0, math.inf if side > 0 else -math.inf)
    )
    value = review(at)
    assert clause(value, "C02")["condition_present"] is late
    assert ("C02" in {c["code"] for c in value["strictures"]}) is late
    assert value["safe_to_judge"] is None


@pytest.mark.parametrize(
    "young,agreement,expected",
    [
        (None, None, None),
        (True, True, True),
        (True, None, None),
        (False, None, False),
        (True, False, False),
    ],
)
def test_early_exception_requires_both_reported_parts_without_age_or_appearance_inference(
    young, agreement, expected
):
    value = review(
        1,
        context={
            "very_young_querent_reported": young,
            "rising_description_agreement_reported": agreement,
        },
    )
    assert clause(value, "C01")["exception_satisfied"] is expected
    assert value["safe_to_judge"] is None
    assert clause(value, "C01")["condition_present"] is True


@pytest.mark.parametrize(
    "origin,certain,expected",
    [
        (None, True, False),
        ("propounded_question", True, False),
        ("timed_event", True, True),
        ("timed_event", None, None),
        ("unknown", True, None),
        ("timed_event", False, False),
    ],
)
def test_filled_question_clock_is_not_a_certain_timed_event_exception(
    origin, certain, expected
):
    value = review(
        27, context={"figure_origin": origin, "event_time_certain_reported": certain}
    )
    assert value["ascendant_degree_gate"]["certain_timed_event_exception"] is expected
    if expected is True:
        assert clause(value, "C02")["status"] == "qualified_by_reported_exception"
    assert value["safe_to_judge"] is None


def test_reported_age_correspondence_is_separate_from_the_numeric_ascendant_degree():
    missing = review(27)
    assert missing["reported_context"]["age_degree_agreement_reported"] is None
    assert clause(missing, "C02")["exception_satisfied"] is None
    reported = review(27, context={"age_degree_agreement_reported": True})
    assert clause(reported, "C02")["exception_satisfied"] is True
    assert reported["reported_context"]["provided_fields"] == [
        "age_degree_agreement_reported"
    ]


@pytest.mark.parametrize("longitude", [59.999, 89.999, 239.999, 299.999, 359.999])
def test_moon_late_degree_cutoff_stays_unknown_instead_of_borrowing_ascendant_threshold(
    longitude,
):
    s = states()
    s["Moon"]["longitude"] = longitude
    row = clause(review(planets=s), "C03")
    assert row["condition_present"] is None
    assert row["inputs"]["numeric_cutoff_supplied_by_source"] is False
    assert row["status"] == "unknown"


@pytest.mark.parametrize("sign_start", [30, 90, 240, 330])
def test_void_moon_sign_qualification_never_changes_the_geometric_voc_flag(sign_start):
    s = states()
    s["Moon"]["longitude"] = sign_start + 10
    value = review(planets=s, voc=True)
    row = clause(value, "C05")
    assert (
        row["condition_present"] is True
        and row["inputs"]["some_performance_sign_qualification"] is True
    )
    assert row["exception_satisfied"] is None
    assert any(c["code"] == "C05" for c in value["strictures"])
    strong = review(
        planets=s,
        voc=True,
        context={"principal_significators_very_strong_reported": True},
    )
    assert clause(strong, "C05")["status"] == "qualified_by_reported_exception"
    assert clause(strong, "C05")["condition_present"] is True


def test_unavailable_moon_history_is_not_a_void_moon_caution():
    value = review(voc=None)
    assert clause(value, "C05")["condition_present"] is None
    assert not any(c["code"] == "C05" for c in value["strictures"])


def test_seventh_topic_guard_does_not_erase_separate_saturn_clause():
    s = states()
    s["Venus"]["retrograde"] = True
    s["Venus"]["speed"] = -0.1
    s["Saturn"]["house_assignment"]["assigned_house"] = 7
    value = review(planets=s, topic=7)
    assert clause(value, "C06")["condition_present"] is True
    assert clause(value, "C06")["status"] == "not_applicable"
    assert clause(value, "C08")["condition_present"] is True
    assert any(c["code"] == "C08" for c in value["strictures"])
    assert not any(c["code"] == "C06" for c in value["strictures"])


def test_saturn_cusp_virtue_is_not_mislabeled_as_literal_geometric_occupancy():
    s = states()
    s["Saturn"]["occupied_house"] = 12
    s["Saturn"]["house_assignment"]["assigned_house"] = 1
    value = review(planets=s)
    row = clause(value, "C07")
    assert row["condition_present"] is True
    assert (
        row["inputs"]["geometric_house"] == 12
        and row["inputs"]["cusp_virtue_house"] == 1
    )
    s["Saturn"]["house_assignment"]["assigned_house"] = None
    assert clause(review(planets=s), "C07")["condition_present"] is None


@pytest.mark.parametrize(
    "distance,combust", [(1, True), (12, False), (Fraction(1, 10), False)]
)
def test_ascendant_lord_solar_state_does_not_conflate_beams_cazimi_or_sun_self(
    distance, combust
):
    s = states()
    s["Mercury"]["longitude"] = Fraction(s["Sun"]["longitude"]) + distance
    value = review(65, planets=s)
    assert clause(value, "C09")["condition_present"] is combust
    sun_lord = review(125, planets=s)
    assert clause(sun_lord, "C09")["status"] == "not_applicable"


def test_known_seventh_fall_or_bound_can_resolve_an_or_with_unspecified_unfortunate_state():
    # Venus in Virgo is fallen; Mercury in Virgo20 is in Saturn's printed p104 bound.
    assert clause(review(seventh="Taurus"), "C10")["condition_present"] is True
    s = states()
    s["Mercury"]["longitude"] = 170
    assert (
        clause(review(planets=s, seventh="Gemini"), "C10")["condition_present"] is True
    )
    s["Venus"]["longitude"] = 40
    assert (
        clause(review(planets=s, seventh="Taurus"), "C10")["condition_present"] is None
    )


def test_zero_score_never_supplies_equal_testimonies_and_no_caution_never_certifies_fitness():
    s = states()
    for row in s.values():
        row["literal_table_balance"] = 0
    value = review(planets=s)
    assert clause(value, "C11")["condition_present"] is None
    assert value["safe_to_judge"] is None
    reported = review(context={"equal_fortune_infortune_testimonies_reported": True})
    assert clause(reported, "C11")["condition_present"] is True
    assert reported["full_original_text_acceptance"] is False
    HoraryRadicality.model_validate(reported)


@pytest.mark.parametrize("value", ["true", 1, [], {"not_a_source_field": True}])
def test_context_reports_are_strict_and_unknown_keys_not_silently_discarded(value):
    data = value if isinstance(value, dict) else {"event_time_certain_reported": value}
    with pytest.raises(ValueError):
        normalize_context(data)
    with pytest.raises(ValidationError):
        LillyRadicalityContext.model_validate(data)


def test_direct_review_never_mutates_inputs_or_turns_unknowns_into_false():
    s = states()
    s["Saturn"]["house_assignment"]["assigned_house"] = None
    context = {"figure_origin": "unknown", "event_time_certain_reported": False}
    before = copy.deepcopy((s, context))
    value = review(planets=s, context=context, hour=None, seventh=None)
    assert value["hour_affinity"]["supported_under_declared_policy"] is None
    assert value["reported_context"]["event_time_certain_reported"] is False
    assert (s, context) == before


def test_missing_native_clock_does_not_get_a_civil_hour_or_default_location():
    value = clock.collect_radicality_hour(SimpleNamespace())
    assert value["hour"] is None and value["status"] == "not_computed"


def test_clock_unavailable_and_configuration_changes_remain_explicit(
    monkeypatch, tmp_path
):
    subject = SimpleNamespace(
        julian_day=2451545.0, lng=0.0, lat=51.5, tz_str="UTC", is_diurnal=True
    )
    monkeypatch.setattr(clock, "_planetary_hours", lambda *args: None)
    value = clock.collect_radicality_hour(subject)
    assert value["status"] == "unavailable" and value["hour"] is None
    previous = configured_ephemeris_path()

    try:
        # Explicit SE_EPHE_PATH correctly wins over configure()'s argument.
        # Change the effective configuration too, then restore env before the
        # final native-path restoration. This fault must work in both modes.
        with monkeypatch.context() as mutation:

            def changed(*args):
                mutation.setenv("SE_EPHE_PATH", str(tmp_path))
                configure_ephemeris_path(str(tmp_path))
                return {"hour_ruler": "Mars", "is_day": True}

            mutation.setattr(clock, "_planetary_hours", changed)
            with pytest.raises(EphemerisSourceError):
                clock.collect_radicality_hour(subject)
    finally:
        configure_ephemeris_path(previous)


def test_actual_apparent_sunrise_day_and_geometric_sect_keep_distinct_boundaries():
    jd = ephemeris_time(datetime(2024, 6, 1, tzinfo=timezone.utc)).jd_ut1
    rise = _sun_event(jd, 0, 51.5, True)
    subject = build_native_subject(
        name="fictional horizon control",
        local_datetime=datetime_from_ut1(rise + 1 / 86400),
        longitude=0,
        latitude=51.5,
        timezone_name="UTC",
        house_system="R",
    )
    before = [
        (key, point.abs_pos, point.house) for key, point in subject.points.items()
    ]
    value = clock.collect_radicality_hour(subject)
    assert value["status"] == "computed" and value["hour"]["hour_number"] == 1
    assert value["hour"]["is_day"] is True and subject.is_diurnal is False
    assert value["hour_and_geometric_sect_differ"] is True
    assert value["actual_solar_backend_verified"] is False
    assert before == [
        (key, point.abs_pos, point.house) for key, point in subject.points.items()
    ]

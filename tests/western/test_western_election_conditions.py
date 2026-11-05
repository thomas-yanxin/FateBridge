"""Frozen failure, analytic controls and posthoc existing JPL integration.

Mock native-event rows isolate score propagation, never astronomy accuracy.
The JPL cases are reused from the existing independent three-window corpus.
"""

import hashlib
import json
import math
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator

import fatebridge.core.astrology_election as election
import fatebridge.core.astrology_horary as horary
from fatebridge.core.astro.time_scales import datetime_from_tt
from fatebridge.core.predictive.native_chart import build_native_subject
from fatebridge.core.response_models import Election
from fatebridge.services.western_election import calculate_election
from tests.western.test_western_election import CANDIDATE

FIXTURE = Path(__file__).parents[1] / "fixtures"
REFERENCE = json.loads((FIXTURE / "western-horary-horizons.json").read_text())


def synthetic_subject(**changes):
    rows = {
        "sun": (310, 1),
        "moon": (55, 13),
        "mercury": (280, 1.2),
        "venus": (230, 1),
        "mars": (105, 0.5),
        "jupiter": (345, 0.08),
        "saturn": (210, 0.03),
        "ascendant": (70, None),
        "medium_coeli": (160, None),
        "first_house": (60, None),
        "tenth_house": (150, None),
    }
    rows.update(changes)
    points = {
        p: SimpleNamespace(
            abs_pos=float(lon), speed=speed, sign="Aries", house="First_House"
        )
        for p, (lon, speed) in rows.items()
    }
    for i, attr in enumerate(horary.HOUSE_ATTRIBUTES):
        points.setdefault(
            attr, SimpleNamespace(abs_pos=float(i * 30), sign=horary.SIGNS[i])
        )
    return SimpleNamespace(
        **points,
        julian_day_tt=2451545.0,
        zodiac_type="Tropical",
        is_diurnal=True,
        calculation_basis={"julian_day_tt": 2451545.0},
    )


def event_result(voc=False):
    return {
        "status": "unavailable" if voc is None else "computed",
        "method_id": "native_tt_lunar_contacts_before_ingress_v1",
        "constant_velocity_projection": False,
        "void_of_course": voc,
        "contacts": [],
        "start_julian_day_tt": 2451545.0,
    }


@pytest.fixture
def known_motion(monkeypatch):
    monkeypatch.setattr(
        election, "native_lunar_contacts", lambda subject: event_result(False)
    )


def validate(result):
    Election.model_validate(result)
    Draft202012Validator(Election.model_json_schema()).validate(result)
    return result


def codes(result):
    return {f["code"] for f in result["factors"]}


def test_unknown_native_events_cannot_become_complete_favourable_score(monkeypatch):
    monkeypatch.setattr(
        election, "native_lunar_contacts", lambda subject: event_result(None)
    )
    result = validate(
        election.build_election_payload(synthetic_subject(), topic_id="general")
    )
    assert result["score"] is None and result["has_hard_block"] is None
    assert result["verdict"] == "incomplete" and "moon_void_of_course" not in codes(
        result
    )
    assert result["score_bounds"] == [53, 78]
    assert [f["code"] for f in result["unresolved_factors"]] == ["moon_void_of_course"]
    blocked = validate(
        election.build_election_payload(
            synthetic_subject(mars=(160, 0.5)), topic_id="general"
        )
    )
    assert (
        blocked["score"] is None
        and blocked["has_hard_block"] is True
        and blocked["verdict"] == "avoid"
    )
    assert "malefic_on_angle_mars" in codes(blocked)


def test_missing_speed_is_not_stationary_and_no_native_epoch_is_not_linear_success(
    known_motion,
):
    result = validate(
        election.build_election_payload(
            synthetic_subject(mercury=(280, None)), topic_id="contract"
        )
    )
    assert (
        result["planets"]["Mercury"]["speed"] is None
        and result["planets"]["Mercury"]["retrograde"] is None
    )
    assert result["score"] is None and len(result["unresolved_factors"]) == 1
    assert result["unresolved_factors"][0]["minimum_weight"] == -15
    subject = synthetic_subject()
    subject.julian_day_tt = None
    missing = validate(election.build_election_payload(subject, topic_id="general"))
    assert (
        missing["moon"]["motion_basis"]["status"] == "unavailable"
        and missing["score"] is None
    )
    with pytest.raises(RuntimeError, match="Nonfinite"):
        election.build_election_payload(
            synthetic_subject(mercury=(280, math.nan)), topic_id="general"
        )


def test_score_bounds_sum_before_clipping_and_retain_declared_weights():
    factors = [{"weight": 50, "hard": False, "polarity": "favorable"}]
    pending = [
        {
            "code": "moon_void_of_course",
            "minimum_weight": -25,
            "maximum_weight": 0,
            "may_be_hard": True,
        }
    ]
    result = election._score_with_unknowns(factors, pending, "synthetic")
    assert result["score"] is None and result["score_bounds"] == [85, 100]
    assert result["score_evidence"]["raw_known_subtotal"] == 110
    assert election._score_with_unknowns(factors, [], "synthetic")["score"] == 100


@pytest.mark.parametrize(
    "longitude,expected", [(0.5, True), (math.nextafter(0.5, math.inf), False)]
)
def test_angle_gate_compares_supplied_doubles_before_rounding(
    longitude, expected, known_motion
):
    result = validate(
        election.build_election_payload(
            synthetic_subject(
                mars=(longitude, 0.5), ascendant=(355.5, None), medium_coeli=(100, None)
            ),
            topic_id="general",
        )
    )
    exact = abs((Decimal.from_float(longitude) - Decimal("355.5")) + 360)
    assert ("malefic_on_angle_mars" in codes(result)) is expected
    assert expected == (exact <= 5)


def test_physical_axes_not_first_or_tenth_cusp_and_changes_can_increase_or_decrease_score(
    known_motion,
):
    a = validate(
        election.build_election_payload(
            synthetic_subject(mars=(160, 0.5)), topic_id="general"
        )
    )
    assert "malefic_on_angle_mars" in codes(a)
    b = validate(
        election.build_election_payload(
            synthetic_subject(mars=(150, 0.5)), topic_id="general"
        )
    )
    assert "malefic_on_angle_mars" not in codes(b)
    assert a["score"] < b["score"]
    assert (
        a["axes"]["midheaven_longitude"] == 160 and a["axes"]["tenth_house_cusp"] == 150
    )
    c = validate(
        election.build_election_payload(
            synthetic_subject(mars=(60, 0.5)), topic_id="general"
        )
    )
    assert "malefic_on_angle_mars" not in codes(c)
    assert c["ascendant"]["sign"] == "Gemini"  # point.sign was deliberately stale


@pytest.mark.parametrize(
    "moon,sun,state,combust",
    [
        (31, 29, "under_beams", False),
        (0.1, 0, "cazimi", False),
        (8, 0, "combust", True),
        (8.5, 0, "under_beams", False),
        (17, 0, None, False),
    ],
)
def test_selected_solar_definitions_and_only_existing_combust_weight(
    moon, sun, state, combust, known_motion
):
    result = validate(
        election.build_election_payload(
            synthetic_subject(moon=(moon, 13), sun=(sun, 1)), topic_id="general"
        )
    )
    assert result["moon"]["solar_condition"] == state
    assert ("moon_combust" in codes(result)) is combust
    assert result["solar_condition_policy"]["full_page_acceptance"] is False
    if combust:
        assert (
            next(f["weight"] for f in result["factors"] if f["code"] == "moon_combust")
            == -12
        )


@pytest.mark.parametrize(
    "moon,phase,weight",
    [
        (10, "new", 8),
        (190, "full", -6),
        (math.nextafter(190.0, 0), "waxing", 8),
        (math.nextafter(190.0, math.inf), "waning", -6),
    ],
)
def test_phase_facts_distinct_from_legacy_half_cycle_weights(
    moon, phase, weight, known_motion
):
    result = validate(
        election.build_election_payload(
            synthetic_subject(moon=(moon, 13), sun=(10, 1)), topic_id="general"
        )
    )
    assert result["moon"]["phase"] == phase
    assert (
        next(
            f["weight"]
            for f in result["factors"]
            if f["code"] in {"moon_waxing", "moon_waning"}
        )
        == weight
    )


def test_horary_named_ascendant_ruler_and_unrounded_strictures(monkeypatch):
    # This fixture's planets are invented and do not match its native TT epoch.
    # Isolate the ASC predicate; physical collectors must keep rejecting such
    # mixed coordinates in the real input-coherence regression tests.
    monkeypatch.setattr(
        horary,
        "collect_fortitude_inputs",
        lambda subject: {
            "status": "synthetic_geometry_only",
            "motion": {},
            "star_longitudes": {},
        },
    )
    monkeypatch.setattr(
        horary,
        "native_planetary_events",
        lambda subject: {
            "status": "unavailable",
            "method_id": "synthetic_geometry_only",
            "constant_velocity_projection": False,
            "unavailable_reason": "Synthetic planets are not a physical ephemeris",
        },
    )
    monkeypatch.setattr(
        horary, "native_lunar_contacts", lambda subject: event_result(False)
    )
    subject = synthetic_subject(
        ascendant=(math.nextafter(30.0, 0), None), first_house=(0, None)
    )
    result = horary.build_horary_payload(subject, category="general")
    assert result["ascendant"]["degree"] == math.nextafter(30.0, 0)
    strict = {s["code"] for s in result["radicality"]["strictures"]}
    assert "ascendant_too_late" in strict and "ascendant_too_early" not in strict
    subject.ascendant.abs_pos = 31.0
    assert (
        horary.build_horary_payload(subject, category="general")["significators"][
            "querent"
        ]["planet"]
        == "Venus"
    )


@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda c: c["case_id"])
def test_election_native_tt_events_reuse_existing_independent_jpl(case):
    at = datetime_from_tt(case["start_julian_day_tt"])
    subject = build_native_subject(
        name="JPL integration",
        local_datetime=at,
        longitude=0.0,
        latitude=31.0,
        timezone_name="UTC",
        house_system="R",
    )
    result = validate(election.build_election_payload(subject, topic_id="general"))
    motion = result["moon"]["motion_basis"]
    expected = case["expected"]
    assert motion["status"] == "computed"
    assert motion["start_julian_day_tt"] == result["calculation_basis"]["julian_day_tt"]
    assert (
        abs(motion["start_julian_day_tt"] - case["start_julian_day_tt"]) * 86400 < 0.001
    )
    assert [(e["other"], e["ray_degrees"]) for e in motion["contacts"]] == [
        (e["other"], e["ray_degrees"]) for e in expected["contacts"]
    ]
    assert (
        abs(motion["sign_exit_julian_day_tt"] - expected["sign_exit_julian_day_tt"])
        * 86400
        <= 30
    )
    for actual, ref in zip(motion["contacts"], expected["contacts"]):
        assert abs(actual["julian_day_tt"] - ref["julian_day_tt"]) * 86400 <= 30
    assert result["moon"]["void_of_course"] == expected["void_of_course"]


def test_service_failure_text_retains_null_score_and_pending_factor(monkeypatch):
    monkeypatch.setattr(
        election, "native_lunar_contacts", lambda subject: event_result(None)
    )
    result = calculate_election(**CANDIDATE, topic_id="general")
    assert "error" not in result, result
    assert result["election"]["score"] is None and "未完成" in result["summary"]
    assert (
        '"score": null' in result["snapshot_text"]
        and "未核算因子" in result["snapshot_text"]
    )


@pytest.mark.parametrize("code", ["R", "W", "V", "N", "D"])
def test_real_house_variants_use_named_axes_in_both_event_engines(code):
    subject = build_native_subject(
        name="axis integration",
        local_datetime=datetime(2024, 6, 1, 6, 30, tzinfo=timezone.utc),
        longitude=116.4,
        latitude=39.9,
        timezone_name="UTC",
        house_system=code,
    )
    result = validate(election.build_election_payload(subject, topic_id="general"))
    assert result["axes"]["ascendant_longitude"] == subject.ascendant.abs_pos
    assert result["axes"]["midheaven_longitude"] == subject.medium_coeli.abs_pos
    h = horary.build_horary_payload(subject, category="general")
    assert h["ascendant"]["longitude"] == subject.ascendant.abs_pos
    if code in {"W", "V", "N"}:
        assert subject.first_house.abs_pos != subject.ascendant.abs_pos

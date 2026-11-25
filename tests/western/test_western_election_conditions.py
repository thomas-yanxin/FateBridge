"""Frozen failure, analytic controls and posthoc existing JPL integration.

Mock native-event rows isolate condition propagation from astronomy accuracy.
The JPL cases are reused from the existing independent three-window corpus.
"""

import json
import math
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator

import fatebridge.core.astro.astrology_election as election
import fatebridge.core.astro.astrology_horary as horary
from fatebridge.core.astro.time_scales import datetime_from_tt
from fatebridge.core.predictive.native_chart import build_native_subject
from fatebridge.core.response_models import Election
from fatebridge.services.western_election import calculate_election
from tests.unit_test.fixtures.western_event_cases import (
    CANDIDATE,
    event_result,
    synthetic_subject,
)

FIXTURE = Path(__file__).parents[1] / "fixtures"
REFERENCE = json.loads((FIXTURE / "western-horary-horizons.json").read_text())


@pytest.fixture(autouse=True)
def isolate_synthetic_history(monkeypatch):
    native = election.native_planetary_events

    def history(subject):
        if isinstance(subject, SimpleNamespace):
            return {
                "status": "unavailable",
                "constant_velocity_projection": False,
                "events": [],
                "unavailable_reason": "Synthetic controls do not supply native events",
            }
        else:
            pass
        return native(subject)

    monkeypatch.setattr(election, "native_planetary_events", history)


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


def test_unknown_native_events_retain_unresolved_factors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        election, "native_lunar_contacts", lambda subject: event_result(None)
    )
    result = validate(
        election.build_election_payload(synthetic_subject(), topic_id="general")
    )
    assert result["moon"]["void_of_course"] is None
    assert "moon_void_of_course" not in codes(result)
    assert [f["code"] for f in result["unresolved_factors"]] == ["moon_void_of_course"]
    blocked = validate(
        election.build_election_payload(
            synthetic_subject(mars=(160, 0.5)), topic_id="general"
        )
    )
    assert blocked["moon"]["void_of_course"] is None
    assert "malefic_on_angle_mars" in codes(blocked)


def test_missing_speed_is_not_stationary_and_no_native_epoch_is_not_linear_success(
    known_motion,
) -> None:
    result = validate(
        election.build_election_payload(
            synthetic_subject(mercury=(280, None)), topic_id="contract"
        )
    )
    assert (
        result["planets"]["Mercury"]["speed"] is None
        and result["planets"]["Mercury"]["retrograde"] is None
    )
    assert [row["code"] for row in result["unresolved_factors"]] == [
        "mercury_retrograde"
    ]
    subject = synthetic_subject()
    subject.julian_day_tt = None
    missing = validate(election.build_election_payload(subject, topic_id="general"))
    assert missing["moon"]["motion_basis"]["status"] == "unavailable"
    with pytest.raises(RuntimeError, match="Nonfinite"):
        election.build_election_payload(
            synthetic_subject(mercury=(280, math.nan)), topic_id="general"
        )


@pytest.mark.parametrize(
    "longitude,expected", [(0.5, True), (math.nextafter(0.5, math.inf), False)]
)
def test_angle_gate_compares_supplied_doubles_before_rounding(
    longitude, expected: bool, known_motion
) -> None:
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


def test_angle_conditions_use_physical_axes(
    known_motion,
) -> None:
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
def test_selected_solar_definitions(
    moon: float | int, sun: int, state: str | None, combust: bool, known_motion
) -> None:
    result = validate(
        election.build_election_payload(
            synthetic_subject(moon=(moon, 13), sun=(sun, 1)), topic_id="general"
        )
    )
    assert result["moon"]["solar_condition"] == state
    assert ("moon_combust" in codes(result)) is combust
    assert result["solar_condition_policy"]["full_page_acceptance"] is False


@pytest.mark.parametrize(
    "moon,phase",
    [
        (10, "new"),
        (190, "full"),
        (math.nextafter(190.0, 0), "waxing"),
        (math.nextafter(190.0, math.inf), "waning"),
    ],
)
def test_phase_boundaries(moon, phase: str, known_motion) -> None:
    result = validate(
        election.build_election_payload(
            synthetic_subject(moon=(moon, 13), sun=(10, 1)), topic_id="general"
        )
    )
    assert result["moon"]["phase"] == phase


def test_horary_named_ascendant_ruler_and_unrounded_strictures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    gate = result["radicality"]["ascendant_degree_gate"]
    assert gate["late"] is True and gate["early"] is False
    assert "C02" in strict and "C01" not in strict
    subject.ascendant.abs_pos = 31.0
    assert (
        horary.build_horary_payload(subject, category="general")["significators"][
            "querent"
        ]["planet"]
        == "Venus"
    )


@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda c: c["case_id"])
def test_election_native_tt_events_reuse_existing_independent_jpl(case) -> None:
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


def test_service_failure_text_retains_pending_factor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        election, "native_lunar_contacts", lambda subject: event_result(None)
    )
    result = calculate_election(**CANDIDATE, topic_id="general")
    assert "error" not in result, result
    assert result["election"]["moon"]["void_of_course"] is None
    assert "moon_void_of_course" in result["snapshot_text"]


@pytest.mark.parametrize("code", ["R", "W", "V", "N", "D"])
def test_real_house_variants_use_named_axes_in_both_event_engines(code: str) -> None:
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
    else:
        pass

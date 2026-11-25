"""
Tests for the 卜卦 (horary) judgment engine.

The geometry helpers (applying/separating aspects, perfection routing, Moon void
of course) are pure functions of synthetic state dicts, so they are pinned
exactly and are environment-independent. The service-level tests assert the
structural classical facts (querent = Ascendant ruler, quesited house per topic,
a valid verdict) rather than ephemeris-sensitive exact verdicts — the byte-level
output is locked separately by the golden master.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fatebridge.core.astrology_horary import (
    CATEGORY_LABELS_ZH,
    HOUSE_BY_CATEGORY,
    _applying_aspect,
    _moon_void_of_course,
)
from fatebridge.core.astrology_tables import RULER_BY_SIGN
from fatebridge.services.western_horary import calculate_horary
from tests.support.lunar_sampler import sampled_motion
from tests.support.transports import AS_OF, SPECS, business, rest, surface_calls

VALID_VERDICTS = {"yes", "no", "qualified_yes", "uncertain"}


def _state(planet: str, longitude: float, speed: float) -> dict:
    """Synthetic significator state for the pure geometry tests."""
    return {
        "planet": planet,
        "planet_label": planet,
        "sign": "Aries",
        "sign_label": "白羊",
        "longitude": longitude % 360.0,
        "speed": speed,
        "dignities": [],
    }


def test_applying_aspect_detects_applying_conjunction():
    moon = _state("Moon", 8.0, 13.0)
    sun = _state("Sun", 12.0, 1.0)
    aspect = _applying_aspect(moon, sun)
    assert aspect is not None
    assert aspect["aspect"] == "conjunction"
    assert aspect["applying"] is True


def test_applying_aspect_detects_separating():
    moon = _state("Moon", 16.0, 13.0)
    sun = _state("Sun", 12.0, 1.0)
    aspect = _applying_aspect(moon, sun)
    assert aspect is not None
    assert aspect["aspect"] == "conjunction"
    assert aspect["applying"] is False


def test_applying_aspect_returns_none_outside_orb():
    a = _state("Saturn", 0.0, 0.1)
    b = _state("Mars", 47.0, 0.5)
    assert _applying_aspect(a, b) is None


def test_moon_void_of_course_true_when_no_applying_aspect_before_sign_exit():
    moon = _state("Moon", 29.0, 13.0)
    others = [_state("Saturn", 200.0, 0.1), _state("Jupiter", 250.0, 0.2)]
    result = _moon_void_of_course(
        moon, others, physical_motion=sampled_motion(moon, others)
    )
    assert result["void_of_course"] is True
    assert result["next_aspect"] is None


def test_moon_void_of_course_false_with_imminent_aspect():
    moon = _state("Moon", 5.0, 13.0)
    others = [_state("Mars", 9.0, 0.5)]
    result = _moon_void_of_course(
        moon, others, physical_motion=sampled_motion(moon, others)
    )
    assert result["void_of_course"] is False
    assert result["next_aspect"]["other"] == "Mars"


def test_house_by_category_covers_allowed_consultation_topics():
    for topic in (
        "general",
        "wealth",
        "family",
        "property",
        "marriage",
        "lawsuit",
        "theft",
        "travel",
        "career",
        "hope",
        "enemy",
    ):
        assert topic in HOUSE_BY_CATEGORY
        assert topic in CATEGORY_LABELS_ZH


QUESTION = dict(
    question_year=2024,
    question_month=6,
    question_day=1,
    question_hour=14,
    question_minute=30,
    timezone_name="Asia/Shanghai",
    longitude=116.4,
    latitude=39.9,
)


def test_horary_querent_is_ascendant_ruler_and_quesited_house_matches_topic():
    result = calculate_horary(**QUESTION, category="marriage")
    assert "error" not in result, result
    payload = result["horary"]
    asc_sign = payload["ascendant"]["sign"]
    assert payload["significators"]["querent"]["planet"] == RULER_BY_SIGN[asc_sign]
    assert payload["quesited_house"] == HOUSE_BY_CATEGORY["marriage"] == 7
    assert payload["verdict"] in VALID_VERDICTS


def test_horary_unknown_category_is_rejected():
    result = calculate_horary(**QUESTION, category="not_a_topic")
    assert result["error_code"] == "validation_error"
    assert "horary" not in result


def test_horary_envelope_has_snapshot_and_moon_block():
    result = calculate_horary(**QUESTION, category="career")
    assert result["snapshot_text"]
    assert "void_of_course" in result["horary"]["moon"]
    assert result["analysis_context"]["house_system"]
    assert result["horary"]["verdict"] in VALID_VERDICTS


def test_real_horary_event_dates_and_source_identity_on_all_protocols(surface_calls):
    specification = SPECS["astro_horary"]
    payload = {
        "question_year": 2022,
        "question_month": 10,
        "question_day": 30,
        "question_hour": 12,
        "timezone_name": "UTC",
        "longitude": 0,
        "latitude": 40,
        "category": "marriage",
    }
    controls = json.loads(
        (
            Path(__file__).parents[1] / "fixtures/western-event-station-controls.json"
        ).read_text()
    )
    reference_station = next(
        station
        for station in controls["stations"]
        if station["case_id"] == "1"
        and station["frame"] == controls["primary_frame"]
        and station["target"] == 6
    )
    reference_utc = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(
        days=reference_station["julian_day_tt"] - 2440587.5, seconds=-69.184
    )
    full_response = None
    for fields in (
        None,
        [
            "horary.perfection.event_history",
            "horary.perfection.lilly_conditions.event_paths",
        ],
    ):
        projection = {
            "strict_fields": True,
            "include_snapshot_text": False,
            "response_char_limit": 0,
        }
        if fields is not None:
            projection["fields"] = fields
        else:
            pass
        response, protocol, code, cli = surface_calls(
            specification, payload, projection=projection, rest_as_of=AS_OF
        )
        assert response.status_code == 200, response.text
        assert not protocol.is_error and code == 0
        responses = [response.json(), protocol.structured_content, cli]
        assert (
            business(responses[0]) == business(responses[1]) == business(responses[2])
        )
        for delivered in responses:
            specification.output_model.model_validate(delivered)
        perfection = responses[0]["horary"]["perfection"]
        event_paths = perfection["lilly_conditions"]["event_paths"]
        assert event_paths["status"] == "computed_conditions"
        direct_path = next(
            path for path in event_paths["paths"] if path["mode"] == "direct"
        )
        assert len(set(direct_path["actors"])) == 2
        history = perfection["event_history"]
        assert history["status"] == "computed", history
        assert history["ephemeris_reference_points"]["system_barycenters"] == [
            "Mars",
            "Jupiter",
            "Saturn",
        ]
        assert history["longitude_frame"] == "tropical_true_ecliptic_of_date"
        station = next(
            event
            for event in history["events"]
            if event["kind"] == "station" and event["bodies"] == ["Saturn"]
        )
        assert station["epoch_relation"] == "past" and station["direction"] == 1
        assert (
            abs(
                (
                    datetime.fromisoformat(station["datetime_utc"]) - reference_utc
                ).total_seconds()
            )
            <= 120
        )
        assert history["physical_ephemeris_source"]["by_factor"]["Saturn"]["model"] in {
            "swieph",
            "moshier",
            "jpl",
        }
        qualified_contacts = [
            event
            for event in history["events"]
            if event["kind"] == "contact"
            and event["topology"] == "crossing"
            and event["epoch_relation"] == "future"
            and set(event["bodies"]) == set(direct_path["actors"])
        ]
        assert direct_path["future_contact"] == min(
            qualified_contacts, key=lambda event: event["root_bracket_tt"][0]
        )
        assert (
            next(
                condition
                for condition in direct_path["conditions"]
                if condition["code"] == "first_future_principal_contact_in_window"
            )["passed"]
            is True
        )
        assert history["events"]
        assert all(event["datetime_utc"] is not None for event in history["events"])
        assert [event["julian_day_tt"] for event in history["events"]] == sorted(
            event["julian_day_tt"] for event in history["events"]
        )
        for event in history["events"]:
            left, right = event["root_bracket_tt"]
            assert event["epoch_relation"] == (
                "past"
                if right < history["question_julian_day_tt"]
                else (
                    "future"
                    if left > history["question_julian_day_tt"]
                    else "question_boundary"
                )
            )
        if fields is None:
            full_response = perfection
        else:
            assert perfection == {
                name: full_response[name] for name in ("event_history",)
            } | {
                "lilly_conditions": {
                    "event_paths": full_response["lilly_conditions"]["event_paths"]
                }
            }
            assert "moon" not in responses[0]["horary"]

"""
Tests for the 卜卦 (horary) evidence engine.

Synthetic states exercise aspect phase and lunar contacts. Service tests cover
significator assignment, source conditions and the snapshot.
"""

from fatebridge.core.astro.astrology_horary import (
    CATEGORY_LABELS_ZH,
    HOUSE_BY_CATEGORY,
    _applying_aspect,
    _moon_void_of_course,
)
from fatebridge.core.astro.astrology_tables import RULER_BY_SIGN
from fatebridge.services.western_horary import calculate_horary
from tests.support.lunar_sampler import sampled_motion
from tests.support.transports import AS_OF, SPECS, business
from tests.unit_test.fixtures.western_event_cases import QUESTION


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


def test_applying_aspect_detects_applying_conjunction() -> None:
    moon = _state("Moon", 8.0, 13.0)
    sun = _state("Sun", 12.0, 1.0)
    aspect = _applying_aspect(moon, sun)
    assert aspect is not None
    assert aspect["aspect"] == "conjunction"
    assert aspect["applying"] is True


def test_applying_aspect_detects_separating() -> None:
    moon = _state("Moon", 16.0, 13.0)
    sun = _state("Sun", 12.0, 1.0)
    aspect = _applying_aspect(moon, sun)
    assert aspect is not None
    assert aspect["aspect"] == "conjunction"
    assert aspect["applying"] is False


def test_applying_aspect_returns_none_outside_orb() -> None:
    a = _state("Saturn", 0.0, 0.1)
    b = _state("Mars", 47.0, 0.5)
    assert _applying_aspect(a, b) is None


def test_moon_void_of_course_true_when_no_applying_aspect_before_sign_exit() -> None:
    moon = _state("Moon", 29.0, 13.0)
    others = [_state("Saturn", 200.0, 0.1), _state("Jupiter", 250.0, 0.2)]
    result = _moon_void_of_course(
        moon, others, physical_motion=sampled_motion(moon, others)
    )
    assert result["void_of_course"] is True
    assert result["next_aspect"] is None


def test_moon_void_of_course_false_with_imminent_aspect() -> None:
    moon = _state("Moon", 5.0, 13.0)
    others = [_state("Mars", 9.0, 0.5)]
    result = _moon_void_of_course(
        moon, others, physical_motion=sampled_motion(moon, others)
    )
    assert result["void_of_course"] is False
    assert result["next_aspect"]["other"] == "Mars"


def test_house_by_category_covers_allowed_consultation_topics() -> None:
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


def test_horary_querent_is_ascendant_ruler_and_quesited_house_matches_topic() -> None:
    result = calculate_horary(**QUESTION, category="marriage")
    assert "error" not in result, result
    payload = result["horary"]
    asc_sign = payload["ascendant"]["sign"]
    assert payload["significators"]["querent"]["planet"] == RULER_BY_SIGN[asc_sign]
    assert payload["quesited_house"] == HOUSE_BY_CATEGORY["marriage"] == 7
    assert payload["perfection"]["status"] == "perfected_direct"
    assert payload["perfection"]["perfected"] is True


def test_horary_unknown_category_is_rejected() -> None:
    result = calculate_horary(**QUESTION, category="not_a_topic")
    assert result["error_code"] == "validation_error"
    assert "horary" not in result


def test_horary_envelope_has_moon_block() -> None:
    result = calculate_horary(**QUESTION, category="career")
    assert "void_of_course" in result["horary"]["moon"]
    assert result["analysis_context"]["house_system"]
    assert "verdict" not in result["horary"] and "reasoning" not in result["horary"]


def test_horary_saturn_station_identity_and_event_order_reach_three_surfaces(
    surface_calls,
):
    # JPL Horizons target 6 (system barycenter), IAU2006/2000A true ecliptic.
    reference_tt = 2459875.672683134
    fields = [
        "horary.perfection.event_history",
        "horary.perfection.lilly_conditions.event_paths",
    ]
    response, protocol, code, cli = surface_calls(
        SPECS["horary_chart"],
        {
            "question_year": 2022,
            "question_month": 10,
            "question_day": 30,
            "question_hour": 12,
            "timezone_name": "UTC",
            "longitude": 0,
            "latitude": 40,
            "category": "marriage",
        },
        projection={
            "fields": fields,
            "detail": "audit",
        },
        rest_as_of=AS_OF,
    )
    assert response.status_code == 200, response.text
    assert not protocol.is_error and code == 0
    result = response.json()
    assert business(result) == business(protocol.structured_content) == business(cli)
    perfection = result["horary"]["perfection"]
    history = perfection["event_history"]
    assert history["status"] == "computed"
    assert "Saturn" in history["ephemeris_reference_points"]["system_barycenters"]
    station = next(
        event
        for event in history["events"]
        if event["kind"] == "station" and event["bodies"] == ["Saturn"]
    )
    assert station["epoch_relation"] == "past" and station["direction"] == 1
    assert abs(station["julian_day_tt"] - reference_tt) * 86400 <= 120
    times = [event["julian_day_tt"] for event in history["events"]]
    assert times == sorted(times)
    direct = next(
        path
        for path in perfection["lilly_conditions"]["event_paths"]["paths"]
        if path["mode"] == "direct"
    )
    eligible = [
        event
        for event in history["events"]
        if event["kind"] == "contact"
        and event["epoch_relation"] == "future"
        and event["topology"] == "crossing"
        and set(event["bodies"]) == set(direct["actors"])
    ]
    assert direct["future_contact"] == min(
        eligible, key=lambda event: event["root_bracket_tt"][0]
    )

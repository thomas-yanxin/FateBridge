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
    assert payload["perfection"]["status"] == "source_conditions_incomplete"


def test_horary_unknown_category_is_rejected() -> None:
    result = calculate_horary(**QUESTION, category="not_a_topic")
    assert result["error_code"] == "validation_error"
    assert "horary" not in result


def test_horary_envelope_has_snapshot_and_moon_block() -> None:
    result = calculate_horary(**QUESTION, category="career")
    assert result["snapshot_text"]
    assert "void_of_course" in result["horary"]["moon"]
    assert result["analysis_context"]["house_system"]
    assert "[主星与原典条件]" in result["snapshot_text"]
    assert "verdict" not in result["horary"] and "reasoning" not in result["horary"]

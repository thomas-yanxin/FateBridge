"""
Tests for the 卜卦 (horary) judgment engine.

The geometry helpers (applying/separating aspects, perfection routing, Moon void
of course) are pure functions of synthetic state dicts, so they are pinned
exactly and are environment-independent. The service-level tests assert the
structural classical facts (querent = Ascendant ruler, quesited house per topic,
a valid verdict) rather than ephemeris-sensitive exact verdicts — the byte-level
output is locked separately by the golden master.
"""

from fatebridge.core.astrology_horary import (
    CATEGORY_LABELS_ZH,
    HOUSE_BY_CATEGORY,
    _applying_aspect,
    _moon_void_of_course,
)
from fatebridge.core.astrology_tables import RULER_BY_SIGN
from fatebridge.services.western_horary import calculate_horary

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


# ---------------------------------------------------------------------------
# Pure geometry (exact, environment-independent).
# ---------------------------------------------------------------------------


def test_applying_aspect_detects_applying_conjunction():
    # Faster Moon (13°/day) behind slower Sun, both near same degree -> applying.
    moon = _state("Moon", 8.0, 13.0)
    sun = _state("Sun", 12.0, 1.0)
    aspect = _applying_aspect(moon, sun)
    assert aspect is not None
    assert aspect["aspect"] == "conjunction"
    assert aspect["applying"] is True


def test_applying_aspect_detects_separating():
    # Moon already past the Sun and pulling ahead -> separating.
    moon = _state("Moon", 16.0, 13.0)
    sun = _state("Sun", 12.0, 1.0)
    aspect = _applying_aspect(moon, sun)
    assert aspect is not None
    assert aspect["aspect"] == "conjunction"
    assert aspect["applying"] is False


def test_applying_aspect_returns_none_outside_orb():
    a = _state("Saturn", 0.0, 0.1)
    b = _state("Mars", 47.0, 0.5)  # ~47° from a sextile(60)/square(90), outside orb
    assert _applying_aspect(a, b) is None


def test_moon_void_of_course_true_when_no_applying_aspect_before_sign_exit():
    # Moon at 29° Aries (1° left in sign), no planet within reach -> void.
    moon = _state("Moon", 29.0, 13.0)
    others = [_state("Saturn", 200.0, 0.1), _state("Jupiter", 250.0, 0.2)]
    result = _moon_void_of_course(moon, others)
    assert result["void_of_course"] is True
    assert result["next_aspect"] is None


def test_moon_void_of_course_false_with_imminent_aspect():
    # Moon at 5° Aries applying to a conjunction with Mars at 9° Aries.
    moon = _state("Moon", 5.0, 13.0)
    others = [_state("Mars", 9.0, 0.5)]
    result = _moon_void_of_course(moon, others)
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


# ---------------------------------------------------------------------------
# Service-level structural facts.
# ---------------------------------------------------------------------------

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
    assert result["analysis_context"]["house_system"]  # Regiomontanus normalized
    # build_horary_payload is callable directly on a subject too (no crash path).
    assert result["horary"]["verdict"] in VALID_VERDICTS

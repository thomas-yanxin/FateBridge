"""
Tests for the 择日 (electional) engine.

The scoring primitives (dignity, void-of-course, verdict banding, angular gap)
are pure and pinned exactly; the service-level tests assert structural facts
(topic → significator/house, valid verdict, hard-block routing) rather than
ephemeris-sensitive exact scores — the byte-level output is golden-locked.
"""

from fatebridge.core.astrology_election import (
    TOPIC_MASTER,
    _angular_gap,
    _dignity,
    _moon_void_of_course,
    _verdict,
)
from fatebridge.services.western_election import calculate_election

VALID_VERDICTS = {"auspicious", "workable", "marginal", "avoid"}


# ---------------------------------------------------------------------------
# Pure scoring primitives (exact, environment-independent).
# ---------------------------------------------------------------------------


def test_dignity_table():
    assert _dignity("Mars", "Capricorn") == "exaltation"
    assert _dignity("Mars", "Cancer") == "fall"
    assert _dignity("Mars", "Aries") == "rulership"
    assert _dignity("Mars", "Libra") == "detriment"
    assert _dignity("Venus", "Libra") == "rulership"
    assert _dignity("Saturn", "Leo") == "detriment"  # opposite its domicile Aquarius
    assert _dignity("Saturn", "Sagittarius") == "peregrine"  # no dignity nor debility


def test_angular_gap_wraps():
    assert _angular_gap(10.0, 350.0) == 20.0
    assert _angular_gap(0.0, 180.0) == 180.0


def test_verdict_hard_block_overrides_score():
    verdict, _ = _verdict(95, True, "结婚")  # high score but a red line present
    assert verdict == "avoid"


def test_verdict_bands():
    assert _verdict(80, False, "x")[0] == "auspicious"
    assert _verdict(60, False, "x")[0] == "workable"
    assert _verdict(45, False, "x")[0] == "marginal"
    assert _verdict(20, False, "x")[0] == "avoid"


def test_moon_void_of_course_true_when_no_applying_aspect():
    moon = {"longitude": 29.0, "speed": 13.0}
    others = [{"longitude": 200.0, "speed": 0.1}, {"longitude": 250.0, "speed": 0.2}]
    assert _moon_void_of_course(moon, others) is True


def test_moon_not_void_with_imminent_aspect():
    moon = {"longitude": 5.0, "speed": 13.0}
    others = [{"longitude": 9.0, "speed": 0.5}]  # conjunction within 1° sign reach
    assert _moon_void_of_course(moon, others) is False


def test_topic_master_covers_allowed_consultation_topics():
    for topic in (
        "marriage",
        "business",
        "move_in",
        "buy_property",
        "trade",
        "buy_car",
        "contract",
        "travel",
        "job_hunt",
        "general",
    ):
        assert topic in TOPIC_MASTER
        assert TOPIC_MASTER[topic]["significator"]
        assert 1 <= TOPIC_MASTER[topic]["house"] <= 12


# ---------------------------------------------------------------------------
# Service-level structural facts.
# ---------------------------------------------------------------------------

CANDIDATE = dict(
    candidate_year=2025,
    candidate_month=3,
    candidate_day=15,
    candidate_hour=10,
    candidate_minute=0,
    timezone_name="Asia/Shanghai",
    longitude=116.4,
    latitude=39.9,
)


def test_election_marriage_uses_venus_and_seventh_house():
    result = calculate_election(**CANDIDATE, topic_id="marriage")
    assert "error" not in result, result
    payload = result["election"]
    assert payload["significator"] == "Venus"
    assert payload["topic_house"] == 7
    assert payload["verdict"] in VALID_VERDICTS
    assert 0 <= payload["score"] <= 100


def test_election_unknown_topic_is_rejected():
    result = calculate_election(**CANDIDATE, topic_id="not_a_topic")
    assert result["error_code"] == "validation_error"
    assert "election" not in result


def test_election_envelope_has_snapshot_and_factors():
    result = calculate_election(**CANDIDATE, topic_id="contract")
    assert result["snapshot_text"]
    assert isinstance(result["election"]["factors"], list)
    # every factor carries polarity + signed weight + hard flag
    for factor in result["election"]["factors"]:
        assert factor["polarity"] in {"favorable", "adverse", "neutral"}
        assert isinstance(factor["weight"], int)
        assert isinstance(factor["hard"], bool)

"""Named source facts, separate from full chart or election judgement."""

import json
from pathlib import Path

import pytest

import fatebridge.core.astrology_election as election
import scripts.western.audit_western_election_worked_sources as worked_audit
from fatebridge.core.classical_western import combustion_state, essential_dignities
from tests.support.western_election import event_result, synthetic_subject

REFERENCE = json.loads(
    (
        Path(__file__).parents[1] / "fixtures/western-election-worked-sources.json"
    ).read_text()
)
JANUARY = next(c for c in REFERENCE["charts"] if c["id"] == "warnock_2001_01")
SIGNS = (
    "Aries",
    "Taurus",
    "Gemini",
    "Cancer",
    "Leo",
    "Virgo",
    "Libra",
    "Scorpio",
    "Sagittarius",
    "Capricorn",
    "Aquarius",
    "Pisces",
)


@pytest.mark.parametrize("planet", list(JANUARY["essential_score_in_graphic"]))
def test_published_day_chart_major_and_minor_dignity_scores(planet):
    sign, degree, minute = JANUARY["points"][planet]
    actual = essential_dignities(planet, sign, degree + minute / 60, True)
    assert actual is not None
    assert actual["score"] == JANUARY["essential_score_in_graphic"][planet]
    if planet in JANUARY["peregrine_in_graphic"]:
        assert actual["peregrine"] is True


def test_published_cazimi_keeps_the_simultaneous_major_debilities():
    source = next(c for c in REFERENCE["charts"] if c["id"] == "gillman_figure5")
    sign, degree, minute = source["points"]["Mercury"]
    essential = essential_dignities("Mercury", sign, degree + minute / 60, True)
    assert essential is not None
    assert set(essential["debilities"]) == set(source["major_debilities"]["Mercury"])
    mercury = SIGNS.index(sign) * 30 + degree + minute / 60
    sun_sign, sun_degree, sun_minute = source["points"]["Sun"]
    sun = SIGNS.index(sun_sign) * 30 + sun_degree + sun_minute / 60
    assert combustion_state(mercury, sun) == source["solar_conditions"]["Mercury"]


def test_worked_audit_retains_every_reading_when_calculation_is_unavailable(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        worked_audit,
        "calculate_election",
        lambda **request: {"error": "Synthetic unavailable ephemeris source"},
    )
    checkpoint = tmp_path / "worked-checkpoint.json"
    report = worked_audit.audit(output_path=checkpoint)
    receipt = json.loads(checkpoint.read_text())
    assert receipt["status"] == "in_progress"
    assert receipt["completed_input_count"] == len(receipt["results"]) == 13
    assert report["input_count"] == report["unavailable_case_count"] == 13
    assert sum(len(case["readings"]) for case in report["results"]) == 117
    assert report["evaluated_reading_count"] == 0
    assert report["current_reading_failures"] == report["condition_failures"] == 0
    assert report["unevaluated_condition_count"] > 0
    assert all(case["response"]["error"] for case in report["results"])


def test_worked_audit_does_not_turn_unknown_lunar_order_into_failure_or_success(
    monkeypatch,
):
    epoch = 2451545.0
    history = {
        "status": "computed",
        "constant_velocity_projection": False,
        "unresolved_intervals": [{"bodies": ["Moon", "Mars"]}],
        "events": [
            {
                "kind": "contact",
                "bodies": ["Moon", "Venus"],
                "julian_day_tt": epoch + 0.1,
                "root_bracket_tt": [epoch + 0.099, epoch + 0.101],
                "epoch_relation": "future",
                "topology": "crossing",
                "aspect": "trine",
                "ray_degrees": 120,
                "direction": 1,
                "states": {},
                "state_brackets": {},
            }
        ],
    }
    monkeypatch.setattr(
        election, "native_lunar_contacts", lambda subject: event_result(False)
    )
    monkeypatch.setattr(election, "native_planetary_events", lambda subject: history)
    subject = synthetic_subject()
    subject.houses_system_identifier = "R"
    response = {
        "election": election.build_election_payload(subject, topic_id="marriage")
    }
    monkeypatch.setattr(worked_audit, "calculate_election", lambda **request: response)
    report = worked_audit.audit()
    lunar_conditions = [
        condition
        for case in report["results"]
        for condition in case["conditions"]
        if condition["field"].startswith("lunar_")
    ]
    assert lunar_conditions
    assert all(condition["matches"] is None for condition in lunar_conditions)
    assert all(condition["reason"] for condition in lunar_conditions)

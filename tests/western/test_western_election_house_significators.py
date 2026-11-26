"""Selected source identities; not a whole electional or predictive method."""

import json
import math
from fractions import Fraction
from pathlib import Path

import pytest

import fatebridge.core.astro.astrology_election as election
from fatebridge.core.response_models import Election
from tests.unit_test.fixtures.western_event_cases import (
    event_result,
    synthetic_subject,
)

REFERENCE = json.loads(
    (
        Path(__file__).parents[1] / "fixtures/western-ramesey-marriage-1653.json"
    ).read_text()
)


@pytest.fixture(autouse=True)
def synthetic_lunar_condition(monkeypatch):
    monkeypatch.setattr(
        election, "native_lunar_contacts", lambda subject: event_result(False)
    )
    monkeypatch.setattr(
        election,
        "native_planetary_events",
        lambda subject: {
            "status": "unavailable",
            "constant_velocity_projection": False,
            "events": [],
            "unavailable_reason": "Synthetic angles do not supply a physical event history",
        },
    )


@pytest.mark.parametrize("asc", [0.0, math.nextafter(30.0, 0.0), 30.0, 359.0])
@pytest.mark.parametrize("mc", [90.0, 120.0, math.nextafter(360.0, 0.0)])
def test_four_source_roles_use_the_selected_physical_angles_without_rounding(
    asc, mc
) -> None:
    subject = synthetic_subject(ascendant=(asc, None), medium_coeli=(mc, None))
    subject.houses_system_identifier = "R"
    result = election.build_election_payload(subject, topic_id="marriage")
    Election.model_validate(result)
    evidence = result["marriage_significators"]
    assert evidence["method_id"] == REFERENCE["reference_id"]
    assert evidence["full_original_text_acceptance"] is False
    expected = [
        Fraction(asc),
        (Fraction(asc) + 180) % 360,
        Fraction(mc),
        (Fraction(mc) + 180) % 360,
    ]
    for row, role, longitude in zip(
        evidence["houses"], REFERENCE["source_role_mapping"], expected
    ):
        assert {key: row[key] for key in role} == role
        assert row["sign"] == election.SIGNS[int(longitude // 30)]
        assert row["ruler"] == election.RULER_BY_SIGN[row["sign"]]
        assert row["ruler_state"]["planet"] == row["ruler"]


def test_unknown_asc_preserves_mc_lords_and_does_not_reuse_backend_ruler() -> None:
    subject = synthetic_subject(ascendant=(0.0, None), medium_coeli=(120.0, None))
    subject.houses_system_identifier = "R"
    subject.calculation_basis["angle_definition"] = {
        "geometric_ascendant_resolved": False
    }
    result = election.build_election_payload(subject, topic_id="marriage")
    facts = result["marriage_significators"]
    assert facts["status"] == "partial_reference_geometry"
    first, seventh, tenth, fourth = facts["houses"]
    for row in [first, seventh]:
        assert (
            row["longitude"] is None
            and row["ruler"] is None
            and row["ruler_state"] is None
        )
    assert tenth["ruler"] == "Sun" and fourth["ruler"] == "Saturn"
    for row in [tenth, fourth]:
        assert row["ruler_state"]["longitude"] is not None
        assert row["ruler_state"]["house"] is None


@pytest.mark.parametrize(
    "code,zodiac", [("N", "Tropic"), ("W", "Tropic"), ("R", "Sidereal")]
)
def test_other_selected_methods_are_unassessed_without_substituting_a_chart(
    code: str, zodiac: str
) -> None:
    subject = synthetic_subject()
    subject.houses_system_identifier = code
    subject.zodiac_type = zodiac
    result = election.build_election_payload(subject, topic_id="marriage")
    facts = result["marriage_significators"]
    assert facts["status"] == "not_assessed_for_selected_method"
    assert facts["houses"] == []
    assert facts["house_system"] == code and facts["zodiac_type"] == zodiac


def test_marriage_source_subset_is_not_applied_to_another_topic() -> None:
    subject = synthetic_subject()
    subject.houses_system_identifier = "R"
    assert (
        election.build_election_payload(subject, topic_id="contract")[
            "marriage_significators"
        ]
        is None
    )

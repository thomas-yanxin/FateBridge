"""Causal model-upgrade checks, independent ledgers and public score provenance."""

from copy import deepcopy
from decimal import Decimal

import pytest

from fatebridge.analysis.compatibility import AdvancedCompatibility, RelationshipType
from fatebridge.application.examples import example_input
from fatebridge.services.birth_context import build_birth_computation_context
from fatebridge.services.birth_payload import build_destiny_payload
from fatebridge.services.tool_catalog import CATALOG
from tests.fixtures.compatibility import (
    REFERENCE,
    assert_score_reference,
    reference_dimensions,
    reference_total,
)


def frozen_analyses(version):
    """Replay old/new input contracts without running or restoring old source."""
    record = REFERENCE["versions"][version]
    results = []
    for person, profile in zip(REFERENCE["persons"], record["profiles"], strict=True):
        results.append(
            {
                "four_pillars": {
                    name: {"stem": pair[0], "branch": pair[1]}
                    for name, pair in person["pillars"].items()
                },
                "element_distribution": person["distribution"],
                "day_master": {
                    "stem": person["pillars"]["day"][0],
                    "element": person["element"],
                    "strength": profile["strength"],
                    "assessment": {
                        "method_id": record["strength_method_id"],
                        "status": "frozen_reference",
                    },
                },
                "structure_profile": {
                    "resolution_policy": REFERENCE["resolution_policy"],
                    "assessment_status": "conditional",
                    "useful_elements": profile["useful"],
                    "avoid_elements": profile["avoid"],
                    "conditional_elements": profile["conditional"],
                    "neutral_elements": profile["neutral"],
                    "useful_ten_gods": profile["useful_ten_gods"],
                    "recognized_structures": [],
                },
            }
        )
    return results


@pytest.fixture
def production_analyses():
    spec = next(s for s in CATALOG if s.key == "two_person_compatibility")
    _, args, _ = spec.bind(spec.request_model(**example_input(spec)))
    return [
        build_destiny_payload(build_birth_computation_context(person))
        for person in args[:2]
    ]


@pytest.mark.parametrize("kind", list(RelationshipType))
@pytest.mark.parametrize("version", ["static_v1", "season_root_v2"])
def test_frozen_old_and_new_inputs_match_independent_dimension_ledgers(kind, version):
    result = AdvancedCompatibility.analyze_comprehensive_compatibility(
        *frozen_analyses(version), kind
    )
    scores = {
        name: value.get("score", value.get("normalized_score"))
        for name, value in result["detailed_analysis"].items()
    }
    assert scores == reference_dimensions(kind.value, version)
    assert result["overall_score"] == reference_total(kind.value, version)
    assert {
        name: data["weight"] for name, data in result["scoring"]["dimensions"].items()
    } == REFERENCE["weights"][kind.value]


def test_production_inputs_explain_the_new_strength_instead_of_retuning_weights(
    production_analyses,
):
    expected_profiles = REFERENCE["versions"]["season_root_v2"]["profiles"]
    for index, analysis in enumerate(production_analyses):
        assert {
            name: value["stem"] + value["branch"]
            for name, value in analysis["four_pillars"].items()
        } == REFERENCE["persons"][index]["pillars"]
        # Display rounding is not a change of the structural distribution.
        assert analysis["element_distribution"] == pytest.approx(
            REFERENCE["persons"][index]["distribution"], abs=0.11
        )
        profile = analysis["structure_profile"]
        expected = expected_profiles[index]
        assert analysis["day_master"]["strength"] == expected["strength"]
        assert set(profile["useful_elements"]) == set(expected["useful"])
        assert set(profile["avoid_elements"]) == set(expected["avoid"])
        assert set(profile["conditional_elements"]) == set(expected["conditional"])
        assert set(profile["useful_ten_gods"]) == set(expected["useful_ten_gods"])
    second = production_analyses[1]["day_master"]["assessment"]
    assert second["method_id"] == "season_root_revelation_relations_v2"
    assert second["status"] == "rule_based"
    assert second["structural_decision"]["rule"] == "weighted_balance"
    assert second["parameters"]["strong_share"] == 0.60
    assert second["support_share"] > 0.60
    assert second["sensitivity"]["candidate_strengths"] == ["强"]
    assert all(
        variant["strength"] == "强" for variant in second["sensitivity"]["variants"]
    )


def test_only_second_person_input_upgrade_reproduces_the_whole_delta(
    production_analyses,
):
    old = frozen_analyses("static_v1")
    evaluate = AdvancedCompatibility.analyze_comprehensive_compatibility
    before = evaluate(*old)
    person1_only = evaluate(production_analyses[0], old[1])
    person2_only = evaluate(old[0], production_analyses[1])
    current = evaluate(*production_analyses)
    assert before["overall_score"] == person1_only["overall_score"] == 62.4
    assert (
        person2_only["overall_score"] == current["overall_score"] == reference_total()
    )
    for name, expected_delta in REFERENCE["general_weighted_deltas"].items():
        old_term = before["scoring"]["dimensions"][name]
        new_term = current["scoring"]["dimensions"][name]
        assert (
            old_term["weight"]
            == new_term["weight"]
            == REFERENCE["weights"]["general"][name]
        )
        assert Decimal(str(new_term["weighted_score"])) - Decimal(
            str(old_term["weighted_score"])
        ) == Decimal(str(expected_delta))
    assert current["scoring"]["unrounded_score"] == 71.63
    assert (
        current["scoring"]["input_methods"]["person2"]["strength_method_id"]
        != before["scoring"]["input_methods"]["person2"]["strength_method_id"]
    )


@pytest.mark.parametrize("kind", list(RelationshipType))
def test_public_service_receipt_matches_independent_reference(kind):
    spec = next(s for s in CATALOG if s.key == "two_person_compatibility")
    request = spec.request_model(
        **{**example_input(spec), "relationship_type": kind.value}
    )
    service, args, kwargs = spec.bind(request)
    result = service(*args, **kwargs)
    assert "error" not in result
    assert_score_reference(result["summary"], result["detailed_analysis"], kind.value)
    assert result["summary"]["scoring"]["unrounded_score"] == pytest.approx(
        sum(
            entry["weighted_score"]
            for entry in result["summary"]["scoring"]["dimensions"].values()
        )
    )


def test_missing_method_is_not_mislabeled_as_current_version():
    analyses = deepcopy(frozen_analyses("static_v1"))
    for analysis in analyses:
        analysis["day_master"].pop("assessment")
    result = AdvancedCompatibility.analyze_comprehensive_compatibility(*analyses)
    assert all(
        item["strength_method_id"] == "unversioned"
        for item in result["scoring"]["input_methods"].values()
    )

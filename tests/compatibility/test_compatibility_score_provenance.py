"""Current independent ledgers, exact energy budgets and score provenance."""

import json
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.analysis.compatibility import AdvancedCompatibility, RelationshipType
from fatebridge.application.examples import example_input
from fatebridge.services.birth_context import build_birth_computation_context
from fatebridge.services.birth_payload import build_destiny_payload
from fatebridge.services.tool_catalog import CATALOG
from tests.support.compatibility_reference import (
    CURRENT_STRENGTH_METHOD_ID,
    REFERENCE,
    SOURCE_CONDITION_REFERENCE,
    assert_score_reference,
    assert_source_condition_score_reference,
    current_reference_dimensions,
    current_reference_total,
    source_condition_reference_dimensions,
    source_condition_reference_total,
)


def literal_analyses():
    """Fixed independently enumerated input facts for the current scoring rules."""
    record = REFERENCE
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
                        "method_id": CURRENT_STRENGTH_METHOD_ID,
                        "status": "literal_test_input",
                    },
                },
                "structure_profile": {
                    "resolution_policy": "source_conditions_before_preference_v3",
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
def test_current_inputs_match_independent_dimension_ledgers(kind):
    result = AdvancedCompatibility.analyze_comprehensive_compatibility(
        *literal_analyses(), kind
    )
    scores = {
        name: value.get("score", value.get("normalized_score"))
        for name, value in result["detailed_analysis"].items()
    }
    assert scores == current_reference_dimensions(kind.value)
    assert_score_reference(
        {"scoring": result["scoring"], "overall_score": result["overall_score"]},
        kind=kind.value,
    )
    assert result["overall_score"] == current_reference_total(kind.value)
    assert {
        name: data["weight"] for name, data in result["scoring"]["dimensions"].items()
    } == REFERENCE["weights"][kind.value]


def test_production_inputs_explain_the_new_strength_instead_of_retuning_weights(
    production_analyses,
):
    # The original ledger deliberately supplies fully selected preferences.
    # A structural strong label is not a source decision to use that profile.
    expected_profiles = [
        SOURCE_CONDITION_REFERENCE["source_premises"]["first"],
        REFERENCE["profiles"][1],
    ]
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
        assert set(profile["neutral_elements"]) == set(expected["neutral"])
    first = production_analyses[0]["day_master"]["assessment"]
    assert first["relations"] == []
    # Independent hand ledger for 庚午/辛巳/庚辰/辛巳, not a replay of SUT
    # arithmetic. 午 has 2:1 hidden shares; 巳 and 辰 have 4:2:1. Month
    # budget is 4, other branches 2. Only hidden 庚 is revealed (x5/4);
    # the three non-day metal stems each have one rooted unit.
    roots = {
        "木": Fraction(2 * 2, 7),
        "火": Fraction(2 * 2, 3) + Fraction((4 + 2) * 4, 7),
        "土": Fraction(2, 3) + Fraction(4 + 2, 7) + Fraction(2 * 4, 7),
        "金": Fraction((4 + 2) * 2, 7),
        "水": Fraction(2, 7),
    }
    # v11 correctly selects summer metal=死1/2 and water=囚3/4.
    expected_energy = {
        "木": roots["木"],
        "火": roots["火"] * 2,
        "土": roots["土"] * Fraction(3, 2),
        "金": (roots["金"] * Fraction(5, 4) + 3) * Fraction(1, 2),
        "水": roots["水"] * Fraction(3, 4),
    }
    assert {
        name: Fraction(value)
        for name, value in first["threshold_arithmetic"]["energies_exact"].items()
    } == expected_energy
    expected_share = (expected_energy["金"] + expected_energy["土"]) / sum(
        expected_energy.values(), Fraction()
    )
    assert expected_share == Fraction(276, 709)
    assert first["support_share"] == pytest.approx(float(expected_share))
    assert first["threshold_arithmetic"]["share_exact"] == str(expected_share)
    assert first["structural_decision"]["numerical_label"] == "弱"
    assert first["structural_decision"]["vigorous_roots"] == ["month", "hour"]
    assert first["structural_decision"]["rule"] == (
        "multiple_vigorous_roots_and_rooted_visible_support"
    )
    assert first["ordinary_fuyi_requires_review"] is True
    profile = production_analyses[0]["structure_profile"]
    assert profile["metadata"]["baseline_useful_elements"] == []
    assert profile["layers"][0]["useful_elements"] == []
    assert profile["layers"][0]["avoid_elements"] == []
    climate = next(
        layer for layer in profile["layers"] if layer["source"] == "调候简表"
    )
    assert climate["status"] == "reference_only"
    assert set(climate["useful_elements"]) == {"火", "土", "水"}
    selection = profile["candidate_selection"]
    assert selection["chosen_path_id"] is None
    assert selection["adjudication_status"] == "not_adjudicated"
    paths = {path["id"]: path for path in selection["paths"]}
    assert paths["killer_seal"]["status"] == "requires_force_adjudication"
    assert all(
        row["status"] == "unknown" for row in paths["killer_seal"]["force_conditions"]
    )
    # Printed pillar facts contain seals but no 壬食神 or 酉阳刃. Presence of
    # 戊/己 does not adjudicate 杀印有情 or 身轻杀重 and cannot select the path.
    assert (
        paths["killer_food"]["status"]
        == paths["killer_blade"]["status"]
        == "observable_prerequisite_not_met"
    )
    second = production_analyses[1]["day_master"]["assessment"]
    assert second["method_id"] == CURRENT_STRENGTH_METHOD_ID
    assert second["status"] == "rule_based"
    assert second["structural_decision"]["rule"] == "weighted_balance"
    assert second["parameters"]["strong_share"] == 0.60
    assert second["support_share"] > 0.60
    assert second["sensitivity"]["candidate_strengths"] == ["强"]
    assert all(
        variant["strength"] == "强" for variant in second["sensitivity"]["variants"]
    )


@pytest.mark.parametrize("kind", list(RelationshipType))
def test_explicit_unadjudicated_inputs_match_the_independent_conditional_ledger(kind):
    analyses = deepcopy(literal_analyses())
    first = SOURCE_CONDITION_REFERENCE["source_premises"]["first"]
    analyses[0]["structure_profile"].update(
        useful_elements=first["useful"],
        avoid_elements=first["avoid"],
        conditional_elements=first["conditional"],
        neutral_elements=first["neutral"],
        useful_ten_gods=first["useful_ten_gods"],
    )
    result = AdvancedCompatibility.analyze_comprehensive_compatibility(*analyses, kind)
    assert {
        name: row["score"] for name, row in result["scoring"]["dimensions"].items()
    } == source_condition_reference_dimensions(kind.value)
    assert result["overall_score"] == source_condition_reference_total(kind.value)
    assert result["scoring"]["status"] == "partial"


def test_family_score_uses_exact_decimal_half_even_instead_of_binary_tie_drift():
    result = AdvancedCompatibility.analyze_comprehensive_compatibility(
        *literal_analyses(), RelationshipType.FAMILY
    )
    assert result["scoring"]["unrounded_score"] == 75.85
    assert result["overall_score"] == 75.8
    assert result["scoring"]["rounding"] == (
        "clip_0_100_then_decimal_half_even_1_decimal"
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
    first_profile = result["person_info"]["person1"]["preference_assessment"]
    assert first_profile["useful_elements"] == first_profile["avoid_elements"] == []
    assert set(first_profile["conditional_elements"]) == {"火", "土", "水"}
    assert_source_condition_score_reference(
        result["summary"], result["detailed_analysis"], kind.value
    )
    assert result["summary"]["scoring"]["unrounded_score"] == pytest.approx(
        sum(
            entry["weighted_score"]
            for entry in result["summary"]["scoring"]["dimensions"].values()
        )
    )


def test_missing_method_is_not_mislabeled_as_current_version():
    analyses = deepcopy(literal_analyses())
    for analysis in analyses:
        analysis["day_master"].pop("assessment")
    result = AdvancedCompatibility.analyze_comprehensive_compatibility(*analyses)
    assert all(
        item["strength_method_id"] == "unversioned"
        for item in result["scoring"]["input_methods"].values()
    )


@pytest.mark.local_data
def test_inline_source_case_preserves_the_primary_independent_hand_ledger():
    packet = json.loads(
        (
            Path(__file__).parents[1]
            / "data/compatibility/source-condition-ledger.json"
        ).read_text()
    )
    assert {
        key: packet[key] for key in SOURCE_CONDITION_REFERENCE
    } == SOURCE_CONDITION_REFERENCE
    original = json.loads(
        (Path(__file__).parents[1] / "data/compatibility/score-ledger.json").read_text()
    )
    assert REFERENCE == original

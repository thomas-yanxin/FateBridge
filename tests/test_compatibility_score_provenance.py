"""Causal model-upgrade checks, independent ledgers and public score provenance."""

import hashlib
import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pytest

from fatebridge.analysis.compatibility import AdvancedCompatibility, RelationshipType
from fatebridge.application.examples import example_input
from fatebridge.services.birth_context import build_birth_computation_context
from fatebridge.services.birth_payload import build_destiny_payload
from fatebridge.services.tool_catalog import CATALOG
from tests.compatibility_reference import (
    CURRENT_STRENGTH_METHOD_ID,
    CURRENT_VERSION,
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
                    "resolution_policy": record.get(
                        "resolution_policy", REFERENCE["resolution_policy"]
                    ),
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


def test_source_condition_policy_retains_every_old_ledger_and_numeric_term():
    archive = (
        Path(__file__).parent
        / "fixtures/compatibility-score-reference-before-source-conditions-v2.json"
    )
    assert (
        hashlib.sha256(archive.read_bytes()).hexdigest()
        == archive.with_suffix(".sha256").read_text().strip()
    )
    historical = json.loads(archive.read_text())
    for key in ["weights", "persons", "compatibility_method_id", "resolution_policy"]:
        assert REFERENCE[key] == historical[key]
    for key, value in historical["versions"].items():
        assert REFERENCE["versions"][key] == value
    current = REFERENCE["versions"][CURRENT_VERSION]
    previous = REFERENCE["versions"]["source_root_v4"]
    for key in ["profiles", "dimension_ledgers", "ten_gods_ledgers"]:
        assert current[key] == previous[key]
    assert (
        REFERENCE["versions"]["source_conditions_v2"]["strength_method_id"]
        == previous["strength_method_id"]
    )
    assert current["strength_method_id"] == "season_root_revelation_relations_v6"
    assert current["resolution_policy"] == "source_conditions_before_preference_v2"


@pytest.fixture
def production_analyses():
    spec = next(s for s in CATALOG if s.key == "two_person_compatibility")
    _, args, _ = spec.bind(spec.request_model(**example_input(spec)))
    return [
        build_destiny_payload(build_birth_computation_context(person))
        for person in args[:2]
    ]


@pytest.mark.parametrize("kind", list(RelationshipType))
@pytest.mark.parametrize(
    "version",
    [
        "static_v1",
        "season_root_v2",
        "source_root_v4",
        "source_conditions_v2",
        "source_conditions_v2_v5",
        "source_conditions_v2_v6",
    ],
)
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
    expected_profiles = REFERENCE["versions"][CURRENT_VERSION]["profiles"]
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
    first = production_analyses[0]["day_master"]["assessment"]
    assert first["support_share"] == pytest.approx(0.43421052631578955)
    assert first["structural_decision"]["numerical_label"] == "中和"
    assert first["structural_decision"]["vigorous_roots"] == ["month", "hour"]
    assert first["structural_decision"]["rule"] == (
        "multiple_vigorous_roots_and_visible_support"
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


def test_historical_v2_only_second_person_upgrade_explains_historical_delta():
    old = frozen_analyses("static_v1")
    upgraded = frozen_analyses("season_root_v2")
    evaluate = AdvancedCompatibility.analyze_comprehensive_compatibility
    before = evaluate(*old)
    person1_only = evaluate(upgraded[0], old[1])
    person2_only = evaluate(old[0], upgraded[1])
    current = evaluate(*upgraded)
    assert before["overall_score"] == person1_only["overall_score"] == 62.4
    assert (
        person2_only["overall_score"]
        == current["overall_score"]
        == reference_total(version="season_root_v2")
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


def test_v4_only_first_person_root_upgrade_explains_the_new_delta(production_analyses):
    old = frozen_analyses("season_root_v2")
    evaluate = AdvancedCompatibility.analyze_comprehensive_compatibility
    before = evaluate(*old)
    first_only = evaluate(production_analyses[0], old[1])
    second_only = evaluate(old[0], production_analyses[1])
    current = evaluate(*production_analyses)
    assert second_only["overall_score"] == before["overall_score"] == 71.6
    assert first_only["overall_score"] == current["overall_score"] == 80.0
    assert current["scoring"]["unrounded_score"] == 80.03
    for name, delta in REFERENCE["v4_general_weighted_deltas_from_v2"].items():
        previous = before["scoring"]["dimensions"][name]
        actual = current["scoring"]["dimensions"][name]
        assert actual["weight"] == previous["weight"]
        assert Decimal(str(actual["weighted_score"])) - Decimal(
            str(previous["weighted_score"])
        ) == Decimal(str(delta))


def test_family_score_uses_exact_decimal_half_even_instead_of_binary_tie_drift():
    result = AdvancedCompatibility.analyze_comprehensive_compatibility(
        *frozen_analyses("source_root_v4"), RelationshipType.FAMILY
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

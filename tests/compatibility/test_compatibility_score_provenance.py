"""Current independent ledgers, exact energy budgets and score provenance."""

import json
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.analysis.compatibility import AdvancedCompatibility, RelationshipType
from fatebridge.application.examples import example_input
from fatebridge.application.execution import OutputContractError, validate_output
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
from tests.support.transports import business, projected_outputs
from tests.support.transports import rest as _rest_fixture

rest = _rest_fixture


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
        result = results[-1]
        result["day_master"]["engineering_index"] = {
            "method_id": CURRENT_STRENGTH_METHOD_ID,
            "quantity_kind": "uncalibrated_strength_policy_index",
            "strength_level": profile["strength"],
            "source_adjudication_used": False,
        }
        result["structure_profile"]["engineering_reference"] = {
            **result["structure_profile"],
            "quantity_kind": "conditional_engineering_preference",
            "source_adjudication_used": False,
        }
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
        source_profile = analysis["structure_profile"]
        assert source_profile["assessment_status"] == "not_adjudicated"
        assert (
            source_profile["useful_elements"] == source_profile["avoid_elements"] == []
        )
        profile = source_profile["engineering_reference"]
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
    analyses[0]["structure_profile"]["engineering_reference"].update(
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
    assert first_profile["assessment_status"] == "not_adjudicated"
    assert set(first_profile["conditional_elements"]) == {"木", "火", "土", "金", "水"}
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


def test_engineering_score_cannot_consume_public_source_labels_or_preferences():
    original = literal_analyses()
    changed = deepcopy(original)
    for analysis in changed:
        analysis["day_master"]["strength"] = "来源另审"
        analysis["day_master"]["classical_adjudication"] = {
            "status": "not_adjudicated",
            "body_strength": None,
        }
        analysis["structure_profile"].update(
            assessment_status="not_adjudicated",
            useful_elements=[],
            avoid_elements=[],
            useful_ten_gods=[],
            conditional_elements=["木", "火", "土", "金", "水"],
        )
    before = AdvancedCompatibility.analyze_comprehensive_compatibility(*original)
    after = AdvancedCompatibility.analyze_comprehensive_compatibility(*changed)
    assert before["overall_score"] == after["overall_score"]
    assert before["scoring"]["dimensions"] == after["scoring"]["dimensions"]
    assert after["scoring"]["source_adjudication_used"] is False


@pytest.mark.parametrize("state", ["conditional", "unknown", "neutral", "avoid"])
def test_ten_god_input_states_preserve_the_fixed_index_and_known_empty_preferences(
    state,
):
    analyses = literal_analyses()
    for analysis in analyses:
        analysis["four_pillars"] = {
            name: {"stem": stem, "branch": branch}
            for name, stem, branch in (
                ("year", "庚", "申"),
                ("month", "庚", "申"),
                ("day", "甲", "寅"),
                ("hour", "庚", "申"),
            )
        }
        analysis["day_master"]["stem"] = "甲"
        profile = analysis["structure_profile"]
        profile["assessment_status"] = "not_adjudicated"
        profile["classical_adjudication"] = {"status": "not_adjudicated"}
        profile["engineering_reference"].update(
            useful_elements=[],
            avoid_elements=["木", "火", "土", "金", "水"] if state == "avoid" else [],
            conditional_elements=(
                ["木", "火", "土", "金", "水"] if state == "conditional" else []
            ),
            neutral_elements=(
                ["木", "火", "土", "金", "水"] if state == "neutral" else []
            ),
            useful_ten_gods=[],
        )
    result = AdvancedCompatibility._analyze_ten_gods_relationship(
        *analyses, RelationshipType.GENERAL
    )
    # Two actual officer-rule deductions: the new state receipt never retunes them.
    assert result["score"] == 65 - 2 - 2 == 61
    assert result["score_kind"] == "uncalibrated_rule_index"
    assert result["source_adjudication_used"] is False
    assert result["assessment_status"] == (
        "partial" if state in {"conditional", "unknown"} else "calculated"
    )
    assert {row["engineering_state"] for row in result["preference_evidence"]} == {
        state
    }
    assert {row["source_force_status"] for row in result["preference_evidence"]} == {
        "not_adjudicated"
    }
    assert {
        row["source_preference_status"] for row in result["preference_evidence"]
    } == {"not_adjudicated"}
    if state in {"conditional", "unknown"}:
        assert "未见明显的十神级高风险冲突" not in result["risk_reasons"]
        assert any("工程索引" in text for text in result["details"])


def test_ten_god_missing_upstream_and_actual_business_rule_risk_remain_separate():
    analyses = literal_analyses()
    for analysis in analyses:
        analysis["structure_profile"].pop("engineering_reference")
        analysis["four_pillars"]["year"] = {"stem": "乙", "branch": "卯"}
        analysis["day_master"]["stem"] = "甲"
    result = AdvancedCompatibility._analyze_ten_gods_relationship(
        *analyses, RelationshipType.BUSINESS
    )
    assert result["assessment_status"] == "partial"
    assert {row["engineering_state"] for row in result["preference_evidence"]} == {
        "unknown"
    }
    assert any("劫财" in text for text in result["risk_reasons"])
    assert any("(-5)" in text and "劫财" in text for text in result["score_basis"])


def test_ten_god_partial_state_and_evidence_match_rest_native_mcp_cli(
    rest, tmp_path, capsys
):
    spec = next(s for s in CATALOG if s.key == "two_person_compatibility")
    results = projected_outputs(
        spec,
        example_input(spec),
        [
            "summary.overall_score",
            "summary.scoring.status",
            "summary.scoring.unresolved_dimensions",
            "detailed_analysis.ten_gods_relationship",
        ],
        rest,
        tmp_path,
        capsys,
        include_snapshot_text=False,
    )
    assert business(results[0]) == business(results[1]) == business(results[2])
    for result in results:
        assert result["summary"]["overall_score"] == 72.7
        scoring = result["summary"]["scoring"]
        assert scoring["status"] == "partial"
        assert "ten_gods_relationship" in scoring["unresolved_dimensions"]
        ten_gods = result["detailed_analysis"]["ten_gods_relationship"]
        assert ten_gods["score"] == 90
        assert ten_gods["assessment_status"] == "partial"
        assert ten_gods["preference_evidence"]


def test_complete_ten_god_contract_requires_status_and_preserves_projected_reads():
    from fatebridge.core.output_compatibility import TenGodRelationshipDimension

    spec = next(s for s in CATALOG if s.key == "two_person_compatibility")
    request = spec.request_model(**example_input(spec))
    service, args, kwargs = spec.bind(request)
    result = service(*args, **kwargs)
    validate_output(spec, result, request=request)
    assert result["summary"]["scoring"]["evidence_policy"] == (
        "explicit_preference_and_unresolved_events_v2"
    )
    for field in ("assessment_status", "score_kind", "preference_evidence"):
        changed = deepcopy(result)
        changed["detailed_analysis"]["ten_gods_relationship"].pop(field)
        with pytest.raises(OutputContractError):
            validate_output(spec, changed, request=request)
    changed = deepcopy(result)
    changed["detailed_analysis"]["ten_gods_relationship"][
        "assessment_status"
    ] = "calculated"
    with pytest.raises(OutputContractError):
        validate_output(spec, changed, request=request)
    assert (
        TenGodRelationshipDimension.model_validate(
            {"preference_evidence": [{"engineering_state": "neutral"}]}
        )
        .preference_evidence[0]
        .engineering_state
        == "neutral"
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

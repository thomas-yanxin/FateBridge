"""A chapter's declared actor cannot be replaced by repeated auxiliary roles."""

from copy import deepcopy

import pytest

from fatebridge.application.execution import execute_spec
from fatebridge.services.meihua import calculate_meihua_cast
from fatebridge.services.tool_catalog import CATALOG
from tests.support.meihua_qualified_motion_reference import (
    expected_summary,
    load,
    path_get,
)

GEOMETRY, COUNTING, READING, TEMPLATES = load()
SPEC = next(s for s in CATALOG if s.key == "meihua_cast")


def check_layer(layer, case, result, prefix):
    role = case.get("selected_role", "body" if case["topic"] == "travel" else "use")
    assert layer["selected_role"] == role
    assert layer["selected_trigram"] == case["selected_trigram"]
    assert layer["trigram_fact_path"] == f"{prefix}.{role}_trigram.name"
    assert path_get(result, layer["trigram_fact_path"]) == case["selected_trigram"]
    assert layer["matched_clause_ids"] == case["matched_clause_ids"]
    assert layer["qualified_predicates"] == case["qualified_predicates"]
    assert all("多" in p for p in layer["qualified_predicates"])
    assert layer["summary"] == expected_summary(case, READING, TEMPLATES)
    assert layer["reading_status"] == READING["interpretation_status"]
    assert layer["independent_human_expert_review"] is False
    for key in [
        "event_time",
        "real_location",
        "real_state",
        "travel_instruction",
        "hazard_verdict",
        "success_probability",
        "real_outcome",
        "full_chapter_synthesis",
    ]:
        assert layer[key] is None
    for key in [
        "inner_role_motion_overridden",
        "external_observation_inferred",
        "occurrence_counts_enter_condition",
        "alternative_count_interpretations_adjudicated",
        "unique_all_school_reading_established",
        "predictive_efficacy_established",
    ]:
        assert layer[key] is False
    assert len(layer["clauses"]) == 2
    for row in layer["clauses"]:
        original = next(r for r in READING["rows"] if r["id"] == row["id"])
        assert all(row[k] == v for k, v in original.items())
        assert row["category_matches"] is (row["id"] in case["matched_clause_ids"])
        assert row["numeric_frequency"] is None and row["full_clause_condition"] is None
        assert row["occurrence_count_used"] is False


@pytest.mark.parametrize("case", GEOMETRY, ids=lambda c: c["id"])
def test_all384_line_geometries_in_both_declared_chapters(case):
    args = {
        "casting": {
            "method": "existing",
            "hexagram_code": case["code"],
            "moving_line": case["moving_line"],
        },
        "interpretation_topic": case["topic"],
    }
    result = execute_spec(SPEC, SPEC.request_model(**args))
    assert "error" not in result
    assert (
        result["meihua"]["body_trigram"]["name"],
        result["meihua"]["use_trigram"]["name"],
    ) == (case["body"], case["use"])
    chapter = result["interpretation"]["topic_reading"]["chapter_qualifications"]
    layer = chapter["qualitative_motion"]
    check_layer(layer, case, result, "meihua")
    assert result["summary"].count(layer["summary"]) == 1
    motion = result["interpretation"]["motion_context"]["inner_roles"]
    assert motion[0]["role"] == "body" and motion[0]["motion"] == "static"
    assert motion[1]["role"] == "use" and motion[1]["motion"] == "active"
    if case["topic"] == "travel":
        assert all(
            r["status"] == "pending_source_scope"
            for r in chapter["unadjudicated_source_clauses"]
        )
    else:
        assert all(
            r["selected_scope_condition"] is None and r["threshold"] is None
            for r in chapter["many_clauses"]
        )


@pytest.mark.parametrize("case", COUNTING, ids=lambda c: str(c["arguments"]))
def test_each_distinct_counting_candidate_owns_its_initial_actor(case):
    result = execute_spec(SPEC, SPEC.request_model(**case["arguments"]))
    assert "error" not in result
    main = {
        **case["expected_primary"],
        "topic": case["arguments"]["interpretation_topic"],
    }
    check_layer(
        result["interpretation"]["topic_reading"]["chapter_qualifications"][
            "qualitative_motion"
        ],
        main,
        result,
        "meihua",
    )
    variants = result["interpretation"]["casting_readings"]
    assert len(variants) == len(case["expected_candidates"])
    for index, (row, expected) in enumerate(zip(variants, case["expected_candidates"])):
        wanted = {**expected, "topic": case["arguments"]["interpretation_topic"]}
        layer = row["topic_clause"]["chapter_qualifications"]["qualitative_motion"]
        check_layer(layer, wanted, result, f"meihua.counting_variants.{index}")
        assert row["traditional_judgement"].count(layer["summary"]) == 1


def test_public_result_mutation_cannot_poison_the_cached_source_profile():
    args = {
        "casting": {"method": "existing", "hexagram_code": "111111", "moving_line": 1},
        "interpretation_topic": "travel",
    }
    baseline = calculate_meihua_cast(**args)
    pristine = deepcopy(baseline)
    layer = baseline["interpretation"]["topic_reading"]["chapter_qualifications"][
        "qualitative_motion"
    ]
    layer["clauses"][0]["trigrams"].append("坎")
    layer["source"]["raw_sha256"] = "forged"
    assert calculate_meihua_cast(**args) == pristine

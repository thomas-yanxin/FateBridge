"""All original source conditions remain distinct from actual model decisions."""

import gzip
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.services.source_comparison import calculate_bazi_source_compare

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_source_conditions_public_v1"
FILES = ROOT / "docs/validation/bazi-source-conditions-public-files-v1"
PLAN = json.loads((FIXTURE / "publication-plan-first.json").read_text())


@pytest.mark.parametrize("row", PLAN["reviews"], ids=lambda r: r["case_id"])
def test_every_original_case_supplies_its_own_complete_source_conditions(row):
    result = calculate_bazi_source_compare(*row["review"]["pillars"])
    records = {r["reference_id"]: r for r in result["source_comparison"]["records"]}
    for binding in row["reference_bindings"]:
        record = records[binding["reference_id"]]
        assert record["source_condition_review"] == {
            **row["review"],
            "provenance": {
                "method_id": PLAN["method_id"],
                "condition_layer_sha256": hashlib.sha256(
                    (FIXTURE / "publication-plan-first.json").read_bytes()
                ).hexdigest(),
                "registered_review_sha256": PLAN["registered_developer_review_sha256"],
                "registered_review_row_sha256": row["parent_review_row_sha256"],
                "parent_index_record_sha256": binding["parent_record_sha256"],
            },
        }
    assert result["current_calculation"]["calculation_overridden"] is False
    assert result["source_comparison"]["new_independent_validation_credit"] == 0


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def test_all367_existing_business_values_and_types_change_only_declared_conditions():
    bindings = {
        b["reference_id"]: r for r in PLAN["reviews"] for b in r["reference_bindings"]
    }
    count = 0
    after_source = FILES / "public-all367-source-first.jsonl.gz"
    assert (
        hashlib.sha256(after_source.read_bytes()).hexdigest()
        == "27c7a43b0ab234bd912bc3373b1320a7cd4696509ae523d97515245d9e8a2acf"
    )
    sealed_after = {
        row["reference_id"]: row
        for row in (json.loads(line) for line in gzip.open(after_source, "rt"))
    }
    assert len(sealed_after) == 367
    with gzip.open(FILES / "public-all367-before-first.jsonl.gz", "rt") as handle:
        for line in handle:
            before = json.loads(line)
            sealed = sealed_after[before["reference_id"]]
            assert sealed["pillars"] == before["pillars"]
            actual = deepcopy(sealed["result"])
            original = deepcopy(actual)
            for row in actual["source_comparison"]["records"]:
                review = row.pop("source_condition_review", None)
                assert (review is not None) == (row["reference_id"] in bindings)
                if review is not None:
                    assert (
                        review["case_id"] == row["case_id"]
                        and review["pillars"] == row["pillars"]
                    )
            for key in [
                "source_condition_review_method_id",
                "source_condition_review_sha256",
                "total_registered_source_condition_reviews",
                "total_records_with_source_condition_review",
            ]:
                actual["source_comparison"]["reference_index"].pop(key)
            assert canonical(actual) == canonical(before["result"]), before[
                "reference_id"
            ]
            assert canonical(original["current_calculation"]) == canonical(
                before["result"]["current_calculation"]
            )
            count += 1
    assert count == 367


@pytest.mark.parametrize(
    "patch",
    [
        {"review_kind": "independent_expert_review"},
        {"excerpt_kind": "verbatim_original"},
        {"independent_expert_review": "completed"},
        {"effective_force_adjudication": "strong"},
        {"effective_passage_adjudication": "effective"},
        {"new_independent_validation_credit": 1},
        {"new_independent_validation_credit": True},
        {"new_independent_validation_credit": False},
        {"strength_annotation_assigned_or_regraded": True},
        {"strength_annotation_assigned_or_regraded": 0},
        {"calculation_effect": "strength_override"},
        {"case_id": "another-case"},
        {"source_pdf_sha256": "0" * 64},
        {"passage_conditions": "all passages effective"},
        {"relative_timing_statements": []},
        {"relative_timing_statements": [{"source_elapsed_days": 7}]},
        {"relative_timing_statements": [{"source_elapsed_days": True}]},
        {"relative_timing_statements": [{"source_elapsed_days": "6"}]},
        {"relative_timing_statements": [{"calendar_instant_reconstructed": 0}]},
        {"relative_timing_statements": [{"calendar_instant_reconstructed": True}]},
        {"relative_timing_statements": [{"effective_duty_assigned": True}]},
        {"source_page_anchors": [{"pdf_page": True}]},
        {"source_page_anchors": [{"pdf_page": 171}]},
        {"provenance": {"parent_index_record_sha256": "0" * 64}},
        {"pillars": ["丙寅", "甲戌", "戊辰", "庚申"]},
    ],
)
def test_known_source_conditions_cannot_claim_other_text_or_adjudication(patch):
    from pydantic import ValidationError

    from fatebridge.core.output_source_conditions import SourceConditionReview

    base = deepcopy(
        next(r["review"] for r in PLAN["reviews"] if r["case_id"] == "ML-02")
    )
    SourceConditionReview.model_validate(base)
    with pytest.raises(ValidationError):
        SourceConditionReview.model_validate({**base, **patch})


def test_partial_readings_keep_only_supplied_facts_without_filling_unknowns():
    from fatebridge.core.output_source_conditions import SourceConditionReview

    row = next(r["review"] for r in PLAN["reviews"] if r["case_id"] == "ML-02")
    for value in [
        {},
        {"independent_expert_review": "not_completed"},
        {"review_id": row["review_id"]},
        {"review_id": row["review_id"], "reading_excerpt": row["reading_excerpt"]},
        {"review_id": row["review_id"], "source_page_anchors": [{"pdf_page": 172}]},
        {"review_id": row["review_id"], "source_page_anchors": [{"pdf_page": 173}]},
        {
            "review_id": row["review_id"],
            "relative_timing_statements": [{"source_elapsed_days": 6}],
        },
        {"review_id": row["review_id"], "pillars": ["庚申"]},
    ]:
        before = deepcopy(value)
        parsed = SourceConditionReview.model_validate(value)
        assert parsed.model_dump(exclude_unset=True) == before and value == before


def test_duplicate_unknown_labels_and_returned_mutations_do_not_leak_to_cached_review():
    row = PLAN["reviews"][0]
    one = calculate_bazi_source_compare(*row["review"]["pillars"])
    before = deepcopy(one)
    unknown = next(
        r
        for r in one["source_comparison"]["records"]
        if r["reference_id"].startswith("prior_routes:")
    )
    assert (
        unknown["retained_strength_annotation"] is None
        and unknown["comparison"] == "unadjudicated"
    )
    unknown["source_condition_review"]["body_seal_conditions"] = "corrupted"
    assert calculate_bazi_source_compare(*row["review"]["pillars"]) == before


def test_review_must_stay_on_its_actual_source_reference():
    from pydantic import ValidationError

    from fatebridge.core.output_source_annotations import RegisteredSourceRecord

    row = PLAN["reviews"][0]
    identifier = row["reference_bindings"][0]["reference_id"]
    record = next(
        r
        for r in calculate_bazi_source_compare(*row["review"]["pillars"])[
            "source_comparison"
        ]["records"]
        if r["reference_id"] == identifier
    )
    RegisteredSourceRecord.model_validate(record)
    wrong = deepcopy(record)
    wrong["reference_id"] = "prior_body_spirit_month_hour:ML-02"
    with pytest.raises(ValidationError):
        RegisteredSourceRecord.model_validate(wrong)


def test_public_data_never_packages_private_evaluation_answers_and_old_views_are_identical():
    data = (
        ROOT / "src/fatebridge/data/reference/bazi-source-condition-reviews-v1.json"
    ).read_text()
    for key in [
        "neutral_case_id",
        "model_input_sha256",
        "frozen_original_strength_annotation",
        "frozen_current_engineering_grade",
        "actual_model_semantic_acceptance",
        "rubric",
        "expected_answer",
    ]:
        assert '"' + key + '"' not in data
    before = json.loads(
        gzip.decompress(
            (FIXTURE / "view-configuration-before-first.json.gz").read_bytes()
        )
    )
    current = json.loads(
        (ROOT / "src/fatebridge/data/agent_examples.json").read_bytes()
    )
    original_raw = gzip.decompress(
        (
            ROOT
            / "tests/fixtures/agent_view_compatibility_v1/agent-examples-before-repair.json.gz"
        ).read_bytes()
    )
    # Keep the original whole-file identity. Current compatibility belongs to
    # this tool; other tools' independently tested first views can evolve.
    assert (
        hashlib.sha256(original_raw).hexdigest()
        == "43cb516fb74fbd7f2ae8ec197abbbf8ea0f7217f51f69ff70904dce4494c1a32"
    )
    original = json.loads(original_raw)
    for section in ("tools", "suggested_fields", "evidence_views"):
        assert json.dumps(
            current[section]["bazi_source_compare"], ensure_ascii=False
        ) == json.dumps(original[section]["bazi_source_compare"], ensure_ascii=False)
    views = current["evidence_views"]["bazi_source_compare"]
    assert "source_comparison.records" in views["source_conditions"]["fields"]
    for name, view in before["evidence_views"]["bazi_source_compare"].items():
        assert canonical(views[name]) == canonical(view)


def test_entire_layer_tampering_fails_without_partial_joins(tmp_path):
    from fatebridge.core.source_conditions import condition_reviews

    data = ROOT / "src/fatebridge/data/reference"
    parent_raw = (data / "bazi-source-annotations-v8.json").read_bytes()
    source = data / "bazi-source-condition-reviews-v1.json"
    (tmp_path / source.name).write_bytes(source.read_bytes() + b" ")
    with pytest.raises(ValueError, match="散列"):
        condition_reviews(
            json.loads(parent_raw), tmp_path, hashlib.sha256(parent_raw).hexdigest()
        )

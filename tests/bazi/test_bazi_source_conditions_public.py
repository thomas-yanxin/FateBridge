"""All original source conditions remain distinct from actual model decisions."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.services.source_comparison import calculate_bazi_source_compare

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "src/fatebridge/data/reference/bazi-source-conditions.json"
PLAN = json.loads(DATA.read_text())


@pytest.mark.parametrize("row", PLAN["reviews"], ids=lambda r: r["review"]["case_id"])
def test_every_original_case_supplies_its_own_complete_source_conditions(row):
    result = calculate_bazi_source_compare(*row["review"]["pillars"])
    records = {r["reference_id"]: r for r in result["source_comparison"]["records"]}
    for binding in [{"reference_id": ref} for ref in row["reference_ids"]]:
        record = records[binding["reference_id"]]
        review = record["source_condition_review"]
        assert review == {
            **row["review"],
            "provenance": {
                "method_id": PLAN["method_id"],
                "condition_layer_sha256": hashlib.sha256(DATA.read_bytes()).hexdigest(),
            },
        }
    assert result["current_calculation"]["calculation_overridden"] is False
    assert result["source_comparison"]["new_independent_validation_credit"] == 0


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


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
        {"provenance": {"condition_layer_sha256": "0" * 64}},
        {"pillars": ["丙寅", "甲戌", "戊辰", "庚申"]},
    ],
)
def test_known_source_conditions_cannot_claim_other_text_or_adjudication(patch):
    from pydantic import ValidationError

    from fatebridge.core.output_source_conditions import SourceConditionReview

    base = deepcopy(
        next(r["review"] for r in PLAN["reviews"] if r["review"]["case_id"] == "ML-02")
    )
    SourceConditionReview.model_validate(base)
    with pytest.raises(ValidationError):
        SourceConditionReview.model_validate({**base, **patch})


def test_partial_readings_keep_only_supplied_facts_without_filling_unknowns():
    from fatebridge.core.output_source_conditions import SourceConditionReview

    row = next(
        r["review"] for r in PLAN["reviews"] if r["review"]["case_id"] == "ML-02"
    )
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
    identifier = [{"reference_id": ref} for ref in row["reference_ids"]][0][
        "reference_id"
    ]
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


def test_public_data_contains_source_conditions_without_private_answers():
    data = DATA.read_text()
    for key in ("expected_answer", "rubric", "actual_model_semantic_acceptance"):
        assert '"' + key + '"' not in data


def test_entire_layer_tampering_is_rejected(monkeypatch):
    from fatebridge.core import source_conditions

    source_conditions._published_plan.cache_clear()
    original = Path.read_bytes

    def altered(path):
        raw = original(path)
        return raw + b" " if path.name == source_conditions.DATA_NAME else raw

    try:
        with monkeypatch.context() as patch:
            patch.setattr(Path, "read_bytes", altered)
            with pytest.raises(ValueError, match="散列"):
                source_conditions._published_plan()
    finally:
        source_conditions._published_plan.cache_clear()

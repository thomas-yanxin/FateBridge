"""Provenance and identity gates must not turn annotation differences into passes."""

import copy
import gzip
import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "corpus_census_crosswalk", ROOT / "scripts/audit_bazi_corpus_census_crosswalk.py"
)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def old_row():
    return {
        "group": "observations",
        "id": "old",
        "pillars": ["甲子", "丙寅", "甲子", "甲子"],
        "expected_strength": "强",
        "label_status": "annotated_body_strength",
        "source_record": {"pdf_page": 10, "source_basis": "source wording"},
    }


def census_case():
    row = old_row()
    return {
        "case_id": "case",
        "literal_pillars": dict(zip(AUDIT.ORDER, row["pillars"])),
        "expected_daymaster_strength": None,
        "forbidden_daymaster_strengths": [],
        "source_text_layer": "Ren_commentary",
        "speaker_chain": ["任氏曰"],
        "claim_ids": ["claim"],
        "crosswalk_source_pages": [10],
    }


def walk(row=None, case=None, document=None):
    return AUDIT.crosswalk_row(
        old_row() if row is None else row,
        AUDIT.source_identity(
            {"source_sha256": AUDIT.LI1947} if document is None else document
        ),
        [census_case() if case is None else case],
    )


def test_model_prediction_and_biography_do_not_select_or_regrade_annotations():
    a = old_row()
    b = copy.deepcopy(a)
    a.update(actual_strength="弱", matches=False, assessment={"strength_level": "弱"})
    b.update(actual_strength="强", matches=True, assessment={"outcome": "successful"})
    assert walk(a) == walk(b)
    assert (
        walk(a)["annotation_review"]
        == "old_exact_census_no_exact_annotation_review_required"
    )
    assert not walk(a)["source_label_adjudicated_or_changed"]


@pytest.mark.parametrize(
    "document,status",
    [
        ({"source_sha256": AUDIT.ZIPING}, "different_book_no_source_identity_join"),
        ({"source": {"pdf_pages": [10]}}, "book_identity_not_confirmed"),
        (
            {"overlap_source_hashes": {"other": AUDIT.LI1947}},
            "book_identity_not_confirmed",
        ),
        (
            {
                "source_sha256": AUDIT.LI1947,
                "source": {"full_pdf_sha256": AUDIT.ZIPING},
            },
            "book_identity_not_confirmed",
        ),
    ],
)
def test_same_pillars_and_page_number_do_not_identify_a_book(document, status):
    result = walk(document=document)
    assert result["join_status"] == status
    assert result["confirmed_candidate_count"] == 0
    assert len(result["literal_candidates"]) == 1


def test_all_duplicate_candidates_retained_without_choosing_the_first():
    cases = [census_case(), census_case()]
    cases[1]["case_id"] = "other"
    result = AUDIT.crosswalk_row(
        old_row(), AUDIT.source_identity({"source_sha256": AUDIT.LI1947}), cases
    )
    assert result["confirmed_candidate_count"] == 2
    assert result["annotation_review"] == "identity_not_unique_or_confirmed"
    assert [c["census_case_id"] for c in result["literal_candidates"]] == [
        "case",
        "other",
    ]


@pytest.mark.parametrize(
    "change,status",
    [
        ("missing_pages", "case_pdf_pages_not_supplied"),
        ("different_page", "literal_candidates_outside_case_pdf_pages_review_required"),
        ("one_glyph", "no_exact_literal_candidate"),
        ("partial", "no_exact_literal_candidate"),
    ],
)
def test_missing_identity_evidence_is_not_guessed(change, status):
    row, case = old_row(), census_case()
    if change == "missing_pages":
        row["source_record"] = {"printed_pages": [10]}
    elif change == "different_page":
        case["crosswalk_source_pages"] = [11]
    elif change == "one_glyph":
        case["literal_pillars"]["hour"] = "丙子"
    else:
        case["literal_pillars"]["hour"] = None
    assert walk(row, case)["join_status"] == status


@pytest.mark.parametrize("value", [None, True, 0, "10"])
def test_bad_pdf_locators_are_rejected(value):
    row = old_row()
    row["source_record"]["pdf_page"] = value
    with pytest.raises(ValueError, match="locator"):
        walk(row)


@pytest.mark.parametrize(
    "old,new,forbidden,expected",
    [
        ("强", "强", [], "same_exact_annotation"),
        ("强", "弱", [], "different_exact_annotations_review_required"),
        ("强", None, ["强"], "old_exact_excluded_by_census_bound_review_required"),
        (None, "弱", [], "old_unknown_census_exact_no_label_transfer"),
        (None, None, [], "neither_has_exact_annotation"),
    ],
)
def test_exact_bounded_and_unknown_statements_remain_distinct(
    old, new, forbidden, expected
):
    case = census_case()
    case.update(
        expected_daymaster_strength=new, forbidden_daymaster_strengths=forbidden
    )
    assert AUDIT.compare_annotations(old, case) == expected


def test_invalid_old_label_is_rejected_even_without_any_candidate():
    row = old_row()
    row["expected_strength"] = "successful"
    with pytest.raises(ValueError, match="Invalid old"):
        AUDIT.crosswalk_row(row, AUDIT.source_identity({}), [])


def test_full_frozen_join_preserves_all_records_and_original26_objects(tmp_path):
    study = ROOT / "docs/validation/bazi-corpus-census-crosswalk-v1"
    # Replay the exact pre-formula evidence. Current canonical integration is
    # separately checked against all558cases/1380claims in the formula tests.
    manifest = json.loads((study / "verification-inputs-first.json").read_text())
    with zipfile.ZipFile(study / "verification-inputs-first.zip") as archive:
        assert set(archive.namelist()) == set(manifest["files"])
        for relative, expected in manifest["files"].items():
            target = (tmp_path / relative).resolve()
            assert target.is_relative_to(tmp_path.resolve())
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(relative))
            assert AUDIT.digest(target) == expected
    result = AUDIT.audit(tmp_path, tmp_path / study.relative_to(ROOT))
    old = json.loads(
        gzip.decompress(
            (
                ROOT
                / "docs/validation/bazi-source-bounds-v1/corpus-frozen-first.json.gz"
            ).read_bytes()
        )
    )
    original = json.loads(
        gzip.decompress(
            (
                ROOT / "docs/validation/bazi-month-duty-scan-source-corpus-v1.json.gz"
            ).read_bytes()
        )
    )
    census = json.loads((study / "census-before-first.json").read_text())
    assert [r["source_record"] for g in old["groups"].values() for r in g["rows"]] == [
        r["old_source_record"] for r in result["rows"]
    ]
    assert len(result["rows"]) == 367
    assert [
        r["original_object"] for r in result["original26_disagreements"]
    ] == original["all_distinct_disagreements"]
    assert len(result["original26_disagreements"]) == 26
    actual_cases = [
        {k: v for k, v in c.items() if k != "crosswalk_source_pages"}
        for c in result["census_cases_with_origin_pages"]
    ]
    assert actual_cases == census["resolved_source_cases"]
    assert result["census_source_claims"] == census["resolved_source_claims"]
    assert len(result["census_source_claims"]) == 1380
    assert not result["model_predictions_used_for_join_or_annotation_comparison"]
    assert not result["new_labels_adopted"] and not result["original26_gate_closed"]

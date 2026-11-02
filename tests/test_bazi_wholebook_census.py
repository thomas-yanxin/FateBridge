"""Synthetic integrity attacks; these fixtures are not classical case evidence."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/audit_bazi_wholebook_census.py"
SPEC = importlib.util.spec_from_file_location("census_audit", SCRIPT)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def bound(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False))
    path.with_suffix(".sha256").write_text(AUDIT.sha(path))


@pytest.fixture
def census(tmp_path):
    study = tmp_path / "study"
    study.mkdir()
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"synthetic source, not a classical edition")
    protocol = {
        "source_pdf": "source.pdf",
        "source_pdf_sha256": AUDIT.sha(pdf),
        "complete_physical_page_range": [1, 3],
    }
    bound(study / "protocol.json", protocol)
    bound(
        study / "page-inventory-before-review.json",
        {
            "pages": [{"pdf_page": p} for p in range(1, 4)],
            "source_pdf_sha256": AUDIT.sha(pdf),
        },
    )
    bound(
        study / "source-layer-addendum-before-cases.json",
        {
            "parent_protocol_sha256": AUDIT.sha(study / "protocol.json"),
            "allowed_layers": ["preface"],
        },
    )
    (study / "image").write_bytes(b"synthetic page image")
    page = {
        "pdf_page": 1,
        "image": "image",
        "image_sha256": AUDIT.sha(study / "image"),
        "source_text_layer": "preface",
        "page_case_and_rule_scan_complete": True,
        "literal_cases": [],
        "technical_rule_claims": [],
    }
    batch = {
        "protocol_sha256": AUDIT.sha(study / "protocol.json"),
        "source_pdf_sha256": AUDIT.sha(pdf),
        "strength_or_candidate_evaluation_performed": False,
        "page_order": [1, 2],
        "pages": [page, dict(copy.deepcopy(page), pdf_page=2)],
    }
    bound(study / "review-batch-0001.json", batch)
    return tmp_path, study, batch


def test_clean_partial_collection_never_allows_comparison(census):
    root, study, _ = census
    result = AUDIT.audit(study, root)
    assert result["collection_integrity_passed"]
    assert result["reviewed_pages"] == 2 and result["next_page"] == 3
    assert not result["candidate_evaluation_allowed"]
    assert not result["whole_book_collection_frozen"]


@pytest.mark.parametrize("page_numbers", [[1, 3], [1, 1], [2, 1]])
def test_gaps_duplicates_and_reordering_rejected(census, page_numbers):
    root, study, batch = census
    batch["page_order"] = page_numbers
    for row, number in zip(batch["pages"], page_numbers):
        row["pdf_page"] = number
    bound(study / "review-batch-0001.json", batch)
    with pytest.raises(ValueError, match="Pages skipped, repeated or reordered"):
        AUDIT.audit(study, root)


@pytest.mark.parametrize(
    "field", ["whole_book_collection_complete", "candidate_evaluation_allowed"]
)
def test_premature_progress_claim_rejected(census, field):
    root, study, _ = census
    progress = {
        "reviewed_pages": [1, 2],
        "whole_book_collection_complete": False,
        "candidate_evaluation_allowed": False,
    }
    progress[field] = True
    bound(study / "progress-first.json", progress)
    with pytest.raises(ValueError):
        AUDIT.audit(study, root)


@pytest.mark.parametrize(
    ("subject", "context", "allowed"),
    [
        ("壬印", "natal", False),
        ("daymaster", "later_luck", False),
        ("daymaster", "natal", True),
    ],
)
def test_body_label_requires_same_natal_subject(census, subject, context, allowed):
    root, study, batch = census
    batch["pages"][0]["technical_rule_claims"] = [
        {
            "claim_id": "SYNTHETIC",
            "source_text_layer": "preface",
            "anchor": "synthetic judgment",
            "assertion_subject": subject,
            "judgment_context": context,
            "expected_daymaster_strength": "弱",
            "forbidden_daymaster_strengths": [],
        }
    ]
    batch["pages"][0]["literal_cases"] = [
        {
            "case_id": "SYNTHETIC",
            "source_text_layer": "preface",
            "literal_pillars": {"year": None, "month": None, "day": None, "hour": None},
            "expected_daymaster_strength": "弱",
            "forbidden_daymaster_strengths": [],
            "claim_ids": ["SYNTHETIC"],
            "body_judgment_claim_ids": ["SYNTHETIC"],
        }
    ]
    bound(study / "review-batch-0001.json", batch)
    if allowed:
        result = AUDIT.audit(study, root)
        assert result["exact_body_labels"] == 1
        assert not result["candidate_evaluation_allowed"]
    else:
        with pytest.raises(ValueError, match="Other actor or later-luck"):
            AUDIT.audit(study, root)


def test_source_and_image_changes_rejected(census):
    root, study, _ = census
    (study / "image").write_bytes(b"changed image")
    with pytest.raises(ValueError, match="Page image changed"):
        AUDIT.audit(study, root)
    (root / "source.pdf").write_bytes(b"changed edition")
    with pytest.raises(ValueError, match="Source PDF changed"):
        AUDIT.audit(study, root)


def test_complete_page_count_still_requires_freeze(census):
    root, study, batch = census
    batch["pages"].append(dict(copy.deepcopy(batch["pages"][0]), pdf_page=3))
    batch["page_order"].append(3)
    bound(study / "review-batch-0001.json", batch)
    result = AUDIT.audit(study, root)
    assert result["all_physical_pages_scanned"]
    assert not result["candidate_evaluation_allowed"]
    bound(
        study / "collection-freeze.json",
        {
            "protocol_sha256": AUDIT.sha(study / "protocol.json"),
            "source_pdf_sha256": AUDIT.sha(root / "source.pdf"),
            "batches_sha256": {
                "review-batch-0001.json": AUDIT.sha(study / "review-batch-0001.json")
            },
            "remaining_transcription_uncertainties": [],
        },
    )
    assert AUDIT.audit(study, root)["candidate_evaluation_allowed"]


@pytest.mark.parametrize("uncertainty_source", ["page", "full_progress"])
def test_empty_freeze_cannot_hide_retained_transcription_uncertainty(
    census, uncertainty_source
):
    root, study, batch = census
    batch["pages"].append(dict(copy.deepcopy(batch["pages"][0]), pdf_page=3))
    batch["page_order"].append(3)
    if uncertainty_source == "page":
        batch["pages"][0]["uncertainties"] = ["Synthetic illegible source glyph"]
    bound(study / "review-batch-0001.json", batch)
    if uncertainty_source == "full_progress":
        bound(
            study / "progress-first.json",
            {
                "reviewed_pages": [1, 2, 3],
                "whole_book_collection_complete": False,
                "candidate_evaluation_allowed": False,
                "unresolved_items_retained": ["Synthetic undecided source attribution"],
            },
        )
    bound(
        study / "collection-freeze.json",
        {
            "protocol_sha256": AUDIT.sha(study / "protocol.json"),
            "source_pdf_sha256": AUDIT.sha(root / "source.pdf"),
            "batches_sha256": {
                "review-batch-0001.json": AUDIT.sha(study / "review-batch-0001.json")
            },
            "remaining_transcription_uncertainties": [],
        },
    )
    with pytest.raises(ValueError, match="Retained source uncertainty"):
        AUDIT.audit(study, root)


def attach_metadata_resolution(census):
    root, study, batch = census
    batch["pages"].append(dict(copy.deepcopy(batch["pages"][0]), pdf_page=3))
    batch["page_order"].append(3)
    batch["pages"][0]["retained_metadata"] = {"group_label": "uncertain first reading"}
    batch["pages"][0]["uncertainties"] = ["Synthetic marginal group glyph"]
    bound(study / "review-batch-0001.json", batch)
    warning = {
        "source_kind": "page",
        "original_document": "review-batch-0001.json",
        "original_document_sha256": AUDIT.sha(study / "review-batch-0001.json"),
        "pdf_page": 1,
        "warning_index": 0,
        "item": "Synthetic marginal group glyph",
    }
    warning["warning_id"] = hashlib.sha256(
        json.dumps(
            warning, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    evidence = study / "transcription-evidence/crop.png"
    evidence.parent.mkdir()
    evidence.write_bytes(b"synthetic crop, not source-image certification")
    resolution = {
        "resolution_id": "SYNTHETIC-METADATA",
        "kind": "page_metadata_transcription",
        "original_warnings": [warning],
        "original_batch": "review-batch-0001.json",
        "original_batch_sha256": AUDIT.sha(study / "review-batch-0001.json"),
        "pdf_page": 1,
        "image_sha256": batch["pages"][0]["image_sha256"],
        "field": "group_label",
        "first_value_retained": "uncertain first reading",
        "corrected_value": "synthetic legible reading",
        "anchor": "synthetic source label",
        "evidence": {
            "image": "transcription-evidence/crop.png",
            "image_sha256": AUDIT.sha(evidence),
            "pdf_page": 1,
            "parent_image_sha256": batch["pages"][0]["image_sha256"],
        },
    }
    document = {
        "protocol_sha256": AUDIT.sha(study / "protocol.json"),
        "source_pdf_sha256": AUDIT.sha(root / "source.pdf"),
        "resolutions": [resolution],
    }
    bound(study / "transcription-resolutions-first.json", document)
    return document, resolution


def freeze_with_metadata_resolution(root, study, result):
    bound(
        study / "collection-freeze.json",
        {
            "protocol_sha256": AUDIT.sha(study / "protocol.json"),
            "source_pdf_sha256": AUDIT.sha(root / "source.pdf"),
            "batches_sha256": result["batches_sha256"],
            "remaining_transcription_uncertainties": [],
            "transcription_resolution_documents_sha256": result[
                "transcription_resolution_documents_sha256"
            ],
            "transcription_warning_inventory_sha256": result[
                "transcription_warning_inventory_sha256"
            ],
            "resolved_page_metadata_sha256": result["resolved_page_metadata_sha256"],
        },
    )


def test_bound_metadata_resolution_keeps_first_records_and_noncertification(census):
    root, study, _ = census
    _, resolution = attach_metadata_resolution(census)
    first_batch = (study / "review-batch-0001.json").read_bytes()
    result = AUDIT.audit(study, root)
    assert result["transcription_warnings_retained"] == resolution["original_warnings"]
    assert result["remaining_transcription_warnings"] == []
    assert result["page_metadata_corrections"][0]["corrected_value"] == (
        "synthetic legible reading"
    )
    assert result["exact_body_labels"] == 0
    assert result["independent_annotation_review"] == "not_certified"
    assert result["semantic_annotation_correctness"] == "not_certified"
    assert (study / "review-batch-0001.json").read_bytes() == first_batch
    freeze_with_metadata_resolution(root, study, result)
    assert AUDIT.audit(study, root)["candidate_evaluation_allowed"]


@pytest.mark.parametrize(
    "attack",
    [
        "warning_identity",
        "warning_first_item",
        "batch",
        "page",
        "parent_image",
        "first_value",
        "body_grade_field",
        "unknown_disposition",
        "missing_crop",
        "crop_hash",
        "crop_parent",
        "crop_page",
        "crop_path_escape",
        "duplicate_warning",
        "duplicate_field",
        "protocol",
        "source_book",
        "hidden_grade_edit",
        "hidden_unknown_status",
        "boolean_page",
    ],
)
def test_metadata_resolution_binding_attacks_rejected(census, attack):
    root, study, _ = census
    document, resolution = attach_metadata_resolution(census)
    if attack == "warning_identity":
        resolution["original_warnings"][0]["warning_id"] = "forged"
    elif attack == "warning_first_item":
        resolution["original_warnings"][0]["item"] = "replaced first uncertainty"
    elif attack == "batch":
        resolution["original_batch_sha256"] = "forged"
    elif attack == "page":
        resolution["pdf_page"] = 2
    elif attack == "parent_image":
        resolution["image_sha256"] = "forged"
    elif attack == "first_value":
        resolution["first_value_retained"] = "replaced first reading"
    elif attack == "body_grade_field":
        resolution["field"] = "expected_daymaster_strength"
    elif attack == "unknown_disposition":
        resolution["kind"] = "unknown_but_treated_as_resolved"
    elif attack == "missing_crop":
        (study / "transcription-evidence/crop.png").unlink()
    elif attack == "crop_hash":
        resolution["evidence"]["image_sha256"] = "forged"
    elif attack == "crop_parent":
        resolution["evidence"]["parent_image_sha256"] = "forged"
    elif attack == "crop_page":
        resolution["evidence"]["pdf_page"] = 2
    elif attack == "crop_path_escape":
        resolution["evidence"]["image"] = "../source.pdf"
    elif attack == "duplicate_warning":
        resolution["original_warnings"].append(
            copy.deepcopy(resolution["original_warnings"][0])
        )
    elif attack == "duplicate_field":
        document["resolutions"].append(
            dict(copy.deepcopy(resolution), resolution_id="B")
        )
    elif attack == "protocol":
        document["protocol_sha256"] = "forged"
    elif attack == "source_book":
        document["source_pdf_sha256"] = "forged"
    elif attack == "hidden_grade_edit":
        resolution["expected_daymaster_strength"] = "强"
    elif attack == "hidden_unknown_status":
        resolution["status"] = "unknown"
    elif attack == "boolean_page":
        resolution["pdf_page"] = True
    bound(study / "transcription-resolutions-first.json", document)
    with pytest.raises(ValueError, match="Transcription resolution"):
        AUDIT.audit(study, root)


@pytest.mark.parametrize(
    "field",
    [
        "transcription_resolution_documents_sha256",
        "transcription_warning_inventory_sha256",
        "resolved_page_metadata_sha256",
    ],
)
def test_whole_book_freeze_binds_resolution_and_resolved_metadata(census, field):
    root, study, _ = census
    attach_metadata_resolution(census)
    result = AUDIT.audit(study, root)
    freeze_with_metadata_resolution(root, study, result)
    freeze = json.loads((study / "collection-freeze.json").read_text())
    del freeze[field]
    bound(study / "collection-freeze.json", freeze)
    with pytest.raises(ValueError, match="Whole-book freeze omitted transcription"):
        AUDIT.audit(study, root)


def test_one_bound_resolution_cannot_hide_another_uncertainty(census):
    root, study, batch = census
    attach_metadata_resolution(census)
    bound(
        study / "progress-first.json",
        {
            "reviewed_pages": [1, 2, 3],
            "whole_book_collection_complete": False,
            "candidate_evaluation_allowed": False,
            "unresolved_items_retained": ["Page2another unread glyph"],
        },
    )
    result = AUDIT.audit(study, root)
    assert len(result["transcription_warnings_retained"]) == 2
    assert len(result["remaining_transcription_warnings"]) == 1
    freeze_with_metadata_resolution(root, study, result)
    with pytest.raises(ValueError, match="Retained source uncertainty"):
        AUDIT.audit(study, root)


def attach_context(study, batch):
    batch["pages"][0]["literal_cases"] = [
        {
            "case_id": "UNLABELED",
            "source_text_layer": "preface",
            "literal_pillars": dict.fromkeys(["year", "month", "day", "hour"]),
            "expected_daymaster_strength": None,
            "forbidden_daymaster_strengths": [],
        }
    ]
    bound(study / "review-batch-0001.json", batch)
    context = {
        "protocol_sha256": AUDIT.sha(study / "protocol.json"),
        "source_pdf_sha256": AUDIT.sha(study.parent / "source.pdf"),
        "qualifications": [
            {
                "target_kind": "case",
                "target_id": "UNLABELED",
                "anchor": "synthetic source explicitly says after the term",
                "qualification": {"relation": "after"},
            }
        ],
    }
    bound(study / "source-context-first.json", context)
    return context


def test_source_qualification_requires_existing_target(census):
    root, study, batch = census
    context = attach_context(study, batch)
    result = AUDIT.audit(study, root)
    assert result["source_qualifications_retained"] == 1
    assert result["unknown_body_labels_retained"] == 1
    assert not result["candidate_evaluation_allowed"]
    context["qualifications"][0]["target_id"] = "NONEXISTENT"
    bound(study / "source-context-first.json", context)
    with pytest.raises(ValueError, match="qualification lost its target"):
        AUDIT.audit(study, root)


def test_full_freeze_cannot_drop_source_qualifications(census):
    root, study, batch = census
    batch["pages"].append(dict(copy.deepcopy(batch["pages"][0]), pdf_page=3))
    batch["page_order"].append(3)
    attach_context(study, batch)
    freeze = {
        "protocol_sha256": AUDIT.sha(study / "protocol.json"),
        "source_pdf_sha256": AUDIT.sha(root / "source.pdf"),
        "batches_sha256": {
            "review-batch-0001.json": AUDIT.sha(study / "review-batch-0001.json")
        },
        "remaining_transcription_uncertainties": [],
    }
    bound(study / "collection-freeze.json", freeze)
    with pytest.raises(ValueError, match="omitted source qualifications"):
        AUDIT.audit(study, root)
    freeze["context_documents_sha256"] = {
        "source-context-first.json": AUDIT.sha(study / "source-context-first.json")
    }
    bound(study / "collection-freeze.json", freeze)
    assert AUDIT.audit(study, root)["candidate_evaluation_allowed"]


def attach_reader_correction(study, batch):
    batch["pages"][0]["technical_rule_claims"] = [
        {
            "claim_id": "CORRECTABLE",
            "source_text_layer": "preface",
            "anchor": "synthetic source",
            "assertion_subject": "synthetic subject",
            "judgment_context": "natal",
            "retained_statement": "First reader paraphrase",
            "expected_daymaster_strength": None,
            "forbidden_daymaster_strengths": [],
        }
    ]
    bound(study / "review-batch-0001.json", batch)
    context = {
        "kind": "reader_transcription_correction_not_source_author_disagreement",
        "protocol_sha256": AUDIT.sha(study / "protocol.json"),
        "source_pdf_sha256": AUDIT.sha(study.parent / "source.pdf"),
        "source_pages": [1],
        "image_sha256": AUDIT.sha(study / "image"),
        "original_batch_sha256": AUDIT.sha(study / "review-batch-0001.json"),
        "qualifications": [
            {
                "target_kind": "claim",
                "target_id": "CORRECTABLE",
                "anchor": "synthetic correction anchor",
                "qualification": {
                    "field": "retained_statement",
                    "first_value_retained": "First reader paraphrase",
                    "corrected_value": "Revised reader paraphrase",
                },
            }
        ],
    }
    bound(study / "source-context-reader-first.json", context)
    return context


def test_reader_correction_keeps_original_and_exports_resolved_prose(census):
    root, study, batch = census
    attach_reader_correction(study, batch)
    original = (study / "review-batch-0001.json").read_bytes()
    result = AUDIT.audit(study, root)
    correction = result["source_prose_corrections"][0]
    assert correction["target_id"] == "CORRECTABLE"
    assert correction["first_value_retained"] == "First reader paraphrase"
    assert correction["corrected_value"] == "Revised reader paraphrase"
    assert (study / "review-batch-0001.json").read_bytes() == original
    assert result["exact_body_labels"] == 0
    assert not result["candidate_evaluation_allowed"]
    assert result["semantic_annotation_correctness"] == "not_certified"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("first_value_retained", "Unrelated first version"),
        ("field", "expected_daymaster_strength"),
        ("field", "source_text_layer"),
        ("corrected_value", "First reader paraphrase"),
        ("corrected_value", ["not a source prose string"]),
        ("original_batch_sha256", "0" * 64),
        ("source_pages", [2]),
        ("image_sha256", "0" * 64),
    ],
)
def test_reader_correction_rejects_unbound_or_relabelled_edits(census, field, value):
    root, study, batch = census
    context = attach_reader_correction(study, batch)
    if field in {"original_batch_sha256", "source_pages", "image_sha256"}:
        context[field] = value
    else:
        context["qualifications"][0]["qualification"][field] = value
    bound(study / "source-context-reader-first.json", context)
    with pytest.raises(ValueError, match="Reader correction"):
        AUDIT.audit(study, root)


def test_reader_correction_cannot_silently_replace_another_correction(census):
    root, study, batch = census
    context = attach_reader_correction(study, batch)
    bound(study / "source-context-reader-second.json", context)
    with pytest.raises(ValueError, match="Reader correction target repeated"):
        AUDIT.audit(study, root)


def test_complete_freeze_must_bind_resolved_reader_corrections(census):
    root, study, batch = census
    batch["pages"].append(dict(copy.deepcopy(batch["pages"][0]), pdf_page=3))
    batch["page_order"].append(3)
    attach_reader_correction(study, batch)
    result = AUDIT.audit(study, root)
    freeze = {
        "protocol_sha256": AUDIT.sha(study / "protocol.json"),
        "source_pdf_sha256": AUDIT.sha(root / "source.pdf"),
        "batches_sha256": result["batches_sha256"],
        "context_documents_sha256": result["context_documents_sha256"],
        "remaining_transcription_uncertainties": [],
    }
    bound(study / "collection-freeze.json", freeze)
    with pytest.raises(ValueError, match="omitted resolved reader corrections"):
        AUDIT.audit(study, root)
    freeze["resolved_source_claims_sha256"] = result["resolved_source_claims_sha256"]
    bound(study / "collection-freeze.json", freeze)
    assert AUDIT.audit(study, root)["candidate_evaluation_allowed"]

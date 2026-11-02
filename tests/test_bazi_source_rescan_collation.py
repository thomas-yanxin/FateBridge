"""Direct source-reading repairs and integrity attacks, not prediction samples."""

import copy
import hashlib
import importlib.util
import json
import runpy
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-source-rescan-collation-v1"
CENSUS = ROOT / "docs/validation/bazi-ditian-wholebook-census-v1"
OLD = ROOT / "docs/validation/bazi-census-input-claim-alignment-v1"
SPEC = importlib.util.spec_from_file_location(
    "rescan_census", ROOT / "scripts/audit_bazi_wholebook_census.py"
)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def read(path):
    return json.loads(path.read_text())


def bound(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    path.with_suffix(".sha256").write_text(AUDIT.sha(path) + "\n")


def deltas():
    fixture = (
        ROOT
        / "tests/fixtures/bazi_source_rescan_collation_v1/planned-deltas-first.json"
    )
    assert (
        AUDIT.sha(fixture)
        == "d6cb37fecde03817ef4478cd39bde9e3d3eaaa14ee2c7e4ec8a4aff32291cbd0"
    )
    return read(fixture)


def test_all7_preselected_questions_and_both_digital_witnesses_remain_visible():
    review = AUDIT.read_bound(STUDY / "seven-target-source-review-first.json")
    assert [r["original_page"] for r in review["rows"]] == [
        53,
        210,
        253,
        299,
        383,
        450,
        477,
    ]
    assert [r["candidate_leaf"] for r in review["rows"]] == [
        61,
        218,
        261,
        307,
        391,
        458,
        485,
    ]
    assert len({r["case_id"] for r in review["rows"]}) == 7
    for row in review["rows"]:
        assert AUDIT.sha(ROOT / row["original_image"]) == row["original_image_sha256"]
        assert AUDIT.sha(ROOT / row["candidate_image"]) == row["candidate_image_sha256"]
        assert not row["independent_expert_review"]
    assert not review["independent_edition_or_expert_credit"]
    assert review["full521_leaf_alignment_not_established"]
    raw = STUDY / "candidate-whole-first.djvu"
    assert raw.stat().st_size == 17912324
    assert (
        AUDIT.sha(raw)
        == "1d0a16f528ed3074cdefad33b2d2f9233a47199cf88a8b02001c897e16996e60"
    )
    assert (
        hashlib.sha1(raw.read_bytes()).hexdigest()
        == "e73a24aee3cfc28f22d39e795b13fe76a5a995ad"
    )


def test_exact_full_current_view_only_changes_two_source_fields_and_two_linked_references():
    before = AUDIT.read_bound(STUDY / "census-before-first.json")
    result = AUDIT.audit(CENSUS, ROOT)
    plan = deltas()
    expected_cases = copy.deepcopy(before["resolved_source_cases"])
    expected_claims = copy.deepcopy(before["resolved_source_claims"])
    for case in expected_cases:
        case.update(plan["case_patches"].get(case["case_id"], {}))
    for identity, patch in plan["claim_patches"].items():
        expected_claims[identity].update(patch)
    formula_path = (
        ROOT
        / "tests/fixtures/bazi_grouped_formula_positions_v1/expected-fields-first.json"
    )
    assert (
        AUDIT.sha(formula_path)
        == "e9bdfad8fdbfc0a01dba1d2277103a446b167b6106b2ba5f5f8913d89b2e16aa"
    )
    formulas = read(formula_path)
    for case in expected_cases:
        case.update(formulas["case_patches"].get(case["case_id"], {}))
    for identity, patch in formulas["claim_patches"].items():
        expected_claims[identity].update(patch)
    assert result["resolved_source_cases"] == expected_cases
    assert result["resolved_source_claims"] == expected_claims
    assert len(expected_cases) == 558 and len(expected_claims) == 1380
    assert (
        sum(
            a != b
            for a, b in zip(
                before["resolved_source_cases"], expected_cases, strict=True
            )
        )
        == 4
    )
    assert (
        sum(
            before["resolved_source_claims"][k] != v for k, v in expected_claims.items()
        )
        == 4
    )
    assert result["batches_sha256"] == before["batches_sha256"]
    assert (
        result["exact_body_labels"] == 26
        and result["unknown_body_labels_retained"] == 532
    )
    assert (
        result["transcription_warnings_retained"]
        == before["transcription_warnings_retained"]
    )
    assert (
        result["remaining_transcription_warnings"]
        == before["remaining_transcription_warnings"]
    )
    assert len(result["remaining_transcription_warnings"]) == 22
    assert (
        result["source_case_input_questions_retained"]
        == plan["original4_input_questions"]
    )
    assert len(result["source_case_input_question_resolutions"]) == 1
    assert (
        result["source_case_input_question_resolutions"][0]["original_question"]
        == plan["resolved_original_question"]
    )
    assert [q["case_id"] for q in result["remaining_case_input_questions"]] == plan[
        "remaining_question_ids"
    ]
    assert (
        not result["candidate_evaluation_allowed"]
        and not result["whole_book_collection_frozen"]
    )
    # The three other source conflicts and all unknown pillars/grades are exact.
    by_id = {c["case_id"]: c for c in result["resolved_source_cases"]}
    old = {c["case_id"]: c for c in before["resolved_source_cases"]}
    for identity in ["MAIN-C010", "MAIN-C219", "MAIN-C269", "MAIN-C368", "MAIN-C488"]:
        assert by_id[identity] == old[identity]
    assert not any(by_id["MAIN-C010"]["literal_pillars"].values())
    assert by_id["MAIN-C269"]["expected_daymaster_strength"] == "强"


def test_corrected_caption_and_hour_use_same_independent_references_without_historical_regrading():
    before = AUDIT.read_bound(STUDY / "census-before-first.json")
    current = AUDIT.audit(CENSUS, ROOT)
    a = {c["case_id"]: c for c in before["resolved_source_cases"]}
    b = {c["case_id"]: c for c in current["resolved_source_cases"]}
    script = runpy.run_path(
        str(ROOT / "scripts/audit_bazi_source_calendar_captions.py")
    )
    prior = ROOT / "docs/validation/bazi-source-calendar-caption-constraints-v1"
    profile = script["read_bound"](prior / "reference-profile-first.json")
    refs = script["read_bound"](prior / "reference-receipts-first.json")
    cycle = script["reference_cycle"](prior, refs, profile, ROOT)
    x = script["era_constraint"](
        a["MAIN-C159"]["source_metadata"]["source_caption_as_printed"],
        "癸巳",
        cycle,
        profile,
    )
    y = script["era_constraint"](
        b["MAIN-C159"]["source_metadata"]["source_caption_as_printed"],
        "癸巳",
        cycle,
        profile,
    )
    assert x["status"] == "year_caption_contradiction_even_with_adjacent_years"
    assert y["status"] == "not_disproved_by_conservative_year_set"
    assert y["nominal_era_year_ganzhi"] == "癸巳" and y["modern_birth_instant"] is None
    # Original failed report still records the erroneous first caption.
    old_report = read(prior / "assessment-third.json")
    assert (
        old_report["era_caption_rows"][0]["literal_caption_retained"]
        == "乾隆二十八年四月十八日辰時"
    )
    assert old_report["era_caption_rows"][0]["status"] == x["status"]
    relation = runpy.run_path(
        str(ROOT / "scripts/audit_bazi_census_pillar_consistency.py")
    )
    ref = read(
        ROOT / "docs/validation/bazi-census-pillar-consistency-v1/reference-first.json"
    )
    x = relation["assess_record"]({"case": a["MAIN-C457"]}, ref)
    y = relation["assess_record"]({"case": b["MAIN-C457"]}, ref)
    assert (
        "day_hour:mismatch_all_declared_profiles" in x["symbolic_assessment"]["flags"]
    )
    assert (
        "day_hour:mismatch_all_declared_profiles"
        not in y["symbolic_assessment"]["flags"]
    )


@pytest.fixture
def sandbox(tmp_path):
    root = tmp_path
    study = root / CENSUS.relative_to(ROOT)
    study.mkdir(parents=True)
    for directory, names in [
        (
            OLD,
            [
                "protocol-first.json",
                "all-original-cases-first.json",
                "all-original-claims-first.json",
            ],
        ),
        (
            STUDY,
            [
                "case-input-review-protocol-first.json",
                "all-original-cases-first.json",
                "all-original-claims-first.json",
                "case-input-corrections-from-images-first.json",
            ],
        ),
    ]:
        for name in names:
            p = directory / name
            out = root / p.relative_to(ROOT)
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, out)
            if p.with_suffix(".sha256").exists():
                shutil.copy2(p.with_suffix(".sha256"), out.with_suffix(".sha256"))
    documents = []
    case_origins, claim_origins = {}, {}
    for name in [
        "source-case-input-resolutions-v1.json",
        "source-case-input-resolutions-v2.json",
    ]:
        p = CENSUS / name
        document = read(p)
        documents.append(document)
        for edit in document["resolution_payload"]["case_resolutions"]:
            evidence = edit["source_evidence"]
            case_origins[edit["case_id"]] = {
                "pdf_page": evidence["pdf_page"],
                "batch": evidence["original_batch"],
                "batch_sha256": evidence["original_batch_sha256"],
                "image_sha256": evidence["image_sha256"],
            }
            image = CENSUS / evidence["image"]
            out = study / evidence["image"]
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(image, out)
            prior = ROOT / edit["prior_correction_document"]
            dest = root / prior.relative_to(ROOT)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(prior, dest)
            shutil.copy2(prior.with_suffix(".sha256"), dest.with_suffix(".sha256"))
        for review in document["resolution_payload"]["claim_reviews"]:
            claim_origins[review["claim_id"]] = case_origins[review["case_id"]]
    cases = read(OLD / "all-original-cases-first.json")
    raw_claims = {
        c["claim_id"]: c for c in read(OLD / "all-original-claims-first.json")
    }
    claims = read(OLD / "census-pre-overlay-third.json")["resolved_source_claims"]
    protocol_sha = AUDIT.sha(CENSUS / "protocol.json")
    pdf_sha = read(CENSUS / "protocol.json")["source_pdf_sha256"]

    def run(mutate=None):
        docs = copy.deepcopy(documents)
        protocol_path = root / docs[1]["review_protocol"]
        protocol = read(protocol_path)
        if mutate:
            mutate(docs[1]["resolution_payload"], protocol)
        # Rebind the envelopes, as the old source-integrity attack suite does.
        protocol["planned_payload_object_sha256"] = AUDIT.digest_value(
            docs[1]["resolution_payload"]
        )
        bound(protocol_path, protocol)
        docs[1]["review_protocol_sha256"] = AUDIT.sha(protocol_path)
        for name, document in zip(
            [
                "source-case-input-resolutions-v1.json",
                "source-case-input-resolutions-v2.json",
            ],
            docs,
            strict=True,
        ):
            bound(study / name, document)
        return AUDIT.resolve_case_input_alignment(
            cases,
            claims,
            case_origins,
            claim_origins,
            study,
            root,
            protocol_sha,
            pdf_sha,
            original_claims=raw_claims,
        )

    return run


def test_two_corrections_and_one_glyph_resolution_are_reproducible(sandbox):
    first = sandbox()
    assert sandbox() == first
    cases, claims, receipt = first
    assert len(cases) == 558 and len(claims) == 1380
    assert len(receipt["source_case_input_questions_retained"]) == 4
    assert len(receipt["remaining_case_input_questions"]) == 3
    assert len(receipt["source_case_input_question_resolutions"]) == 1


@pytest.mark.parametrize(
    "attack",
    [
        "caption_extra_metadata",
        "caption_remove_metadata",
        "caption_remove_field",
        "caption_add_field",
        "case_grade",
        "case_voice",
        "claim_grade",
        "claim_actor",
        "wrong_evidence",
        "wrong_first",
        "question_digest",
        "question_identity",
        "printed_conflict",
        "duplicate_resolution",
        "caption_question_resolution",
        "missing_same_document_correction",
    ],
)
def test_rebound_envelopes_do_not_authorize_other_metadata_labels_or_question_erasure(
    sandbox, attack
):
    def mutate(payload, protocol):
        edit = payload["case_resolutions"][0]
        review = payload["claim_reviews"][1]
        request = protocol["resolved_previous_glyph_questions"][0]
        if attack == "caption_extra_metadata":
            edit["corrected_fields"]["source_metadata"][
                "source_calendar_identity_not_resolved"
            ] = False
        elif attack == "caption_remove_metadata":
            edit["corrected_fields"]["source_metadata"].pop(
                "source_calendar_identity_not_resolved"
            )
        elif attack == "caption_remove_field":
            edit["corrected_fields"]["source_metadata"].pop("source_caption_as_printed")
        elif attack == "caption_add_field":
            edit["corrected_fields"]["source_metadata"][
                "birth_utc"
            ] = "1773-05-01T00:00:00Z"
        elif attack == "case_grade":
            edit["corrected_fields"]["expected_daymaster_strength"] = "强"
        elif attack == "case_voice":
            edit["corrected_fields"]["speaker_chain"] = ["new voice"]
        elif attack == "claim_grade":
            review["corrected_fields"]["expected_daymaster_strength"] = "弱"
        elif attack == "claim_actor":
            review["corrected_fields"]["assertion_subject"] = "daymaster"
        elif attack == "wrong_evidence":
            edit["source_evidence"]["image_sha256"] = "0" * 64
        elif attack == "wrong_first":
            edit["first_case_object"]["source_metadata"][
                "source_caption_as_printed"
            ] = "already corrected"
        elif attack == "question_digest":
            request["original_question_sha256"] = "0" * 64
        elif attack == "question_identity":
            request["original_question"]["case_id"] = "MAIN-C219"
        elif attack == "printed_conflict":
            request["original_question"]["kind"] = "printed_source_conflict"
            request["original_question_sha256"] = AUDIT.digest_value(
                request["original_question"]
            )
        elif attack == "duplicate_resolution":
            protocol["resolved_previous_glyph_questions"].append(copy.deepcopy(request))
        elif attack == "caption_question_resolution":
            request["case_id"] = "MAIN-C159"
        elif attack == "missing_same_document_correction":
            request["case_id"] = "MAIN-C219"

    with pytest.raises(ValueError):
        sandbox(mutate)

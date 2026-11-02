"""Source-input integrity and synthetic attacks, not predictive observations."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-census-input-claim-alignment-v1"
CENSUS = ROOT / "docs/validation/bazi-ditian-wholebook-census-v1"
SPEC = importlib.util.spec_from_file_location(
    "alignment_auditor", ROOT / "scripts/audit_bazi_wholebook_census.py"
)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def read(path):
    return json.loads(path.read_text())


def bind(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    path.with_suffix(".sha256").write_text(AUDIT.sha(path) + "\n")


def test_full_canonical_view_matches_source_read_inputs_and_claims():
    result = AUDIT.audit(CENSUS, ROOT)
    plan = read(STUDY / "planned-resolution-payload-first.json")
    baseline = read(STUDY / "census-pre-overlay-third.json")
    expected_cases = copy.deepcopy(baseline["resolved_source_cases"])
    expected_claims = copy.deepcopy(baseline["resolved_source_claims"])
    by_id = {c["case_id"]: c for c in expected_cases}
    for edit in plan["case_resolutions"]:
        by_id[edit["case_id"]].update(edit["corrected_fields"])
    for review in plan["claim_reviews"]:
        expected_claims[review["claim_id"]].update(review["corrected_fields"])
    # Later source-image review corrected one reader glyph, with the first
    # failure and original expectation retained in its prospective study.
    prose = (
        ROOT
        / "tests/fixtures/bazi_source_calendar_caption_constraints_v1/reader-correction-first.json"
    )
    assert (
        AUDIT.sha(prose)
        == "e07062816486139ddb64dc124895f4d2c731b4f952671e16c5f6d87babf88109"
    )
    correction = read(prose)
    assert (
        expected_claims[correction["claim_id"]][correction["field"]]
        == correction["first_value_retained"]
    )
    expected_claims[correction["claim_id"]][correction["field"]] = correction[
        "corrected_value"
    ]
    rescan_fixture = (
        ROOT
        / "tests/fixtures/bazi_source_rescan_collation_v1/planned-deltas-first.json"
    )
    assert (
        AUDIT.sha(rescan_fixture)
        == "d6cb37fecde03817ef4478cd39bde9e3d3eaaa14ee2c7e4ec8a4aff32291cbd0"
    )
    rescan = read(rescan_fixture)
    for identity, patch in rescan["case_patches"].items():
        by_id[identity].update(patch)
    for identity, patch in rescan["claim_patches"].items():
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
    for identity, patch in formulas["case_patches"].items():
        by_id[identity].update(patch)
    for identity, patch in formulas["claim_patches"].items():
        expected_claims[identity].update(patch)
    assert result["resolved_source_cases"] == expected_cases
    assert result["resolved_source_claims"] == expected_claims
    assert len(result["source_case_input_corrections"]) == 10
    assert len(result["source_case_claim_alignment_reviews"]) == 10
    assert (
        result["source_case_input_questions_retained"]
        == rescan["original4_input_questions"]
    )
    assert len(result["source_case_input_question_resolutions"]) == 1
    assert result["remaining_case_input_questions"] == [
        q
        for q in rescan["original4_input_questions"]
        if q != rescan["resolved_original_question"]
    ]
    assert result["literal_case_records"] == 558
    assert result["complete_literal_cases"] == 532
    assert result["raw_complete_literal_cases_retained"] == 530
    assert result["source_claim_records"] == 1380
    assert result["exact_body_labels"] == 26
    assert result["unknown_body_labels_retained"] == 532
    assert (
        result["transcription_warnings_retained"]
        == baseline["transcription_warnings_retained"]
    )
    assert (
        result["remaining_transcription_warnings"]
        == baseline["remaining_transcription_warnings"]
    )
    assert not result["candidate_evaluation_allowed"]
    assert not result["whole_book_collection_frozen"]
    for name in [
        "expected_daymaster_strength",
        "forbidden_daymaster_strengths",
        "claim_ids",
        "speaker_chain",
        "source_text_layer",
        "source_metadata",
        "uncertainties",
    ]:
        for current, first in zip(
            expected_cases, baseline["resolved_source_cases"], strict=True
        ):
            if name == "source_metadata" and current["case_id"] == "MAIN-C159":
                assert current[name] == rescan["case_patches"]["MAIN-C159"][name]
                assert {
                    k: v
                    for k, v in current[name].items()
                    if k != "source_caption_as_printed"
                } == {
                    k: v
                    for k, v in first[name].items()
                    if k != "source_caption_as_printed"
                }
            elif (
                name == "source_metadata"
                and current["case_id"] in formulas["case_patches"]
            ):
                assert (
                    current[name] == formulas["case_patches"][current["case_id"]][name]
                )
                restored = copy.deepcopy(current[name])
                restored.pop("literal_formula_position_provenance")
                restored["source_condition"] = first[name]["source_condition"]
                assert restored == first[name]
            else:
                assert current.get(name) == first.get(name)


def test_all_original_objects_and_previously_passing_error_remain_visible():
    plan = read(STUDY / "planned-resolution-payload-first.json")
    raw_cases = read(STUDY / "all-original-cases-first.json")
    raw_claims = read(STUDY / "all-original-claims-first.json")
    assert len(raw_cases) == 558 and len(raw_claims) == 1380
    assert all(e["first_case_object"] in raw_cases for e in plan["case_resolutions"])
    assert all(e["first_claim_object"] in raw_claims for e in plan["claim_reviews"])
    assert sum(bool(r["corrected_fields"]) for r in plan["claim_reviews"]) == 7
    assert (
        next(r for r in plan["claim_reviews"] if r["claim_id"] == "CENSUS-R559")[
            "corrected_fields"
        ]
        == {}
    )
    assert "MAIN-C514" in {c["case_id"] for c in plan["case_resolutions"]}


@pytest.fixture
def sandbox(tmp_path):
    study = tmp_path / CENSUS.relative_to(ROOT)
    review_dir = tmp_path / STUDY.relative_to(ROOT)
    study.mkdir(parents=True)
    review_dir.mkdir(parents=True)
    protocol = read(STUDY / "protocol-first.json")
    payload = read(STUDY / "planned-resolution-payload-first.json")
    for name in ["all-original-cases-first.json", "all-original-claims-first.json"]:
        (review_dir / name).write_bytes((STUDY / name).read_bytes())
    cases = read(review_dir / "all-original-cases-first.json")
    raw_claims = {
        c["claim_id"]: c for c in read(review_dir / "all-original-claims-first.json")
    }
    claims = read(STUDY / "census-pre-overlay-third.json")["resolved_source_claims"]
    case_origins, claim_origins = {}, {}
    for edit in payload["case_resolutions"]:
        evidence = edit["source_evidence"]
        target = study / evidence["image"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((CENSUS / evidence["image"]).read_bytes())
        case_origins[edit["case_id"]] = {
            "pdf_page": evidence["pdf_page"],
            "batch": evidence["original_batch"],
            "batch_sha256": evidence["original_batch_sha256"],
            "image_sha256": evidence["image_sha256"],
        }
        previous = tmp_path / edit["prior_correction_document"]
        previous.parent.mkdir(parents=True, exist_ok=True)
        previous.write_bytes((ROOT / edit["prior_correction_document"]).read_bytes())
        previous.with_suffix(".sha256").write_bytes(
            (ROOT / edit["prior_correction_document"])
            .with_suffix(".sha256")
            .read_bytes()
        )
    for review in payload["claim_reviews"]:
        claim_origins[review["claim_id"]] = case_origins[review["case_id"]]

    def execute(mutate=None):
        revised = copy.deepcopy(payload)
        if mutate:
            mutate(revised)
        # Rebind test payload hashes deliberately: protected-field checks must
        # reject these synthetic attacks independently of the hash checks.
        modified = copy.deepcopy(protocol)
        modified["planned_payload_object_sha256"] = AUDIT.digest_value(revised)
        modified["exact_case_ids"] = [x["case_id"] for x in revised["case_resolutions"]]
        modified["exact_claim_ids"] = [x["claim_id"] for x in revised["claim_reviews"]]
        review_path = review_dir / "protocol-first.json"
        bind(review_path, modified)
        bind(
            study / "source-case-input-resolutions-test.json",
            {
                "review_protocol": str(review_path.relative_to(tmp_path)),
                "review_protocol_sha256": AUDIT.sha(review_path),
                "resolution_payload": revised,
            },
        )
        result = AUDIT.resolve_case_input_alignment(
            cases,
            claims,
            case_origins,
            claim_origins,
            study,
            tmp_path,
            protocol["source_protocol_sha256"],
            protocol["source_pdf_sha256"],
            original_claims=raw_claims,
        )
        return result

    return execute


def test_resolver_retains_full_denominators_and_does_not_mutate_inputs(sandbox):
    cases, claims, metadata = sandbox()
    assert len(cases) == 558 and len(claims) == 1380
    assert len(metadata["source_case_input_corrections"]) == 8
    assert len(metadata["source_case_claim_alignment_reviews"]) == 8
    assert len(metadata["remaining_case_input_questions"]) == 4
    assert sandbox() == (cases, claims, metadata)


@pytest.mark.parametrize(
    "attack",
    [
        "case_grade",
        "case_voice",
        "claim_grade",
        "claim_voice",
        "claim_context",
        "missing_review",
        "wrong_link",
        "wrong_case_before",
        "wrong_claim_before",
        "incomplete_case",
        "actor_as_daymaster",
        "different_after_pillars",
        "non_literal_anchor",
        "duplicate_case",
        "duplicate_claim",
        "wrong_page",
    ],
)
def test_protected_fields_and_source_bindings_reject_rebound_attacks(sandbox, attack):
    def mutate(p):
        case = p["case_resolutions"][0]
        claim = p["claim_reviews"][0]
        if attack == "case_grade":
            case["corrected_fields"]["expected_daymaster_strength"] = "强"
        elif attack == "case_voice":
            case["corrected_fields"]["speaker_chain"] = ["new voice"]
        elif attack == "claim_grade":
            claim["corrected_fields"]["expected_daymaster_strength"] = "强"
        elif attack == "claim_voice":
            claim["corrected_fields"]["speaker_chain"] = ["new voice"]
        elif attack == "claim_context":
            claim["corrected_fields"]["judgment_context"] = "natal"
        elif attack == "missing_review":
            p["claim_reviews"].pop()
        elif attack == "wrong_link":
            claim["case_id"] = p["case_resolutions"][1]["case_id"]
        elif attack == "wrong_case_before":
            case["first_case_object"]["anchor"] = "different"
        elif attack == "wrong_claim_before":
            claim["first_claim_object"]["anchor"] = "different"
        elif attack == "incomplete_case":
            case["corrected_fields"]["literal_pillars"]["hour"] = None
        elif attack == "actor_as_daymaster":
            p["claim_reviews"][3]["corrected_fields"]["assertion_subject"] = "daymaster"
        elif attack == "different_after_pillars":
            case["corrected_fields"]["literal_pillars"]["hour"] = "甲子"
        elif attack == "non_literal_anchor":
            case["corrected_fields"]["anchor"] = "rewritten narrative"
        elif attack == "duplicate_case":
            p["case_resolutions"].append(copy.deepcopy(case))
        elif attack == "duplicate_claim":
            p["claim_reviews"].append(copy.deepcopy(claim))
        elif attack == "wrong_page":
            claim["source_evidence"]["pdf_page"] += 1

    with pytest.raises(ValueError):
        sandbox(mutate)


def test_unresolved_input_question_is_an_actual_freeze_gate(tmp_path, monkeypatch):
    # Exercise the canonical audit's freeze branch using full actual collection
    # data, while replacing only the freeze-file reads in this isolated call.
    expected = AUDIT.audit(CENSUS, ROOT)
    freeze = {
        "protocol_sha256": AUDIT.sha(CENSUS / "protocol.json"),
        "source_pdf_sha256": expected["source_pdf_sha256"],
        "batches_sha256": expected["batches_sha256"],
        "context_documents_sha256": expected["context_documents_sha256"],
        "resolved_source_claims_sha256": expected["resolved_source_claims_sha256"],
        "resolved_source_cases_sha256": expected["resolved_source_cases_sha256"],
        "source_case_input_resolution_documents_sha256": expected[
            "source_case_input_resolution_documents_sha256"
        ],
        "remaining_transcription_uncertainties": [],
    }
    real_exists, real_read = Path.exists, AUDIT.read_bound
    freeze_path = CENSUS / "collection-freeze.json"
    monkeypatch.setattr(
        Path, "exists", lambda p: True if p == freeze_path else real_exists(p)
    )
    monkeypatch.setattr(
        AUDIT,
        "read_bound",
        lambda p: copy.deepcopy(freeze) if p == freeze_path else real_read(p),
    )
    with pytest.raises(ValueError, match="Unresolved source-case input questions"):
        AUDIT.audit(CENSUS, ROOT)

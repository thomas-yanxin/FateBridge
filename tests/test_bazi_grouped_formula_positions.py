"""Printed ordered pairs are distinct from guessing an unknown source pillar."""

import copy
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-eight-input-source-review-v1"
CENSUS = ROOT / "docs/validation/bazi-ditian-wholebook-census-v1"
SPEC = importlib.util.spec_from_file_location(
    "grouped_formula_census", ROOT / "scripts/audit_bazi_wholebook_census.py"
)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


@pytest.mark.parametrize(
    "anchor,expected",
    [
        (
            "丙寅戊辰月日己卯癸卯年時",
            {"year": "己卯", "month": "丙寅", "day": "戊辰", "hour": "癸卯"},
        ),
        (
            "己卯己巳月日丙寅戊寅年時",
            {"year": "丙寅", "month": "己卯", "day": "己巳", "hour": "戊寅"},
        ),
    ],
)
def test_explicit_source_order_not_calendar_reconstruction(anchor, expected):
    assert AUDIT.parse_grouped_formula_positions(anchor) == expected


@pytest.mark.parametrize(
    "anchor",
    [
        "丙寅戊辰己卯癸卯",
        "丙寅戊辰月日己卯癸卯",
        "丙寅戊辰月日己卯癸卯年月",
        "丙寅戊辰年月己卯癸卯日時",
        "丙寅戊辰月日己卯未知年時",
        "若丙寅戊辰月日己卯癸卯年時",
        "丙寅戊辰月日己卯癸卯年時或甲子",
        "史姓四壬寅",
        "丙寅戊辰月日己卯癸卯年時\n",
    ],
)
def test_missing_conditional_or_unnamed_positions_are_not_completed(anchor):
    with pytest.raises(ValueError, match="explicitly name"):
        AUDIT.parse_grouped_formula_positions(anchor)


def before():
    return AUDIT.read_bound(STUDY / "census-before-first.json")


def apply(cases=None, claims=None, root=ROOT, study=CENSUS):
    old = before()
    return AUDIT.resolve_grouped_formula_positions(
        old["resolved_source_cases"] if cases is None else cases,
        old["resolved_source_claims"] if claims is None else claims,
        study,
        root,
        AUDIT.sha(CENSUS / "protocol.json"),
        old["source_pdf_sha256"],
    )


def test_only_two_cases_and_two_statements_change_no_strength_or_birth_inference():
    old = before()
    cases, claims, receipt = apply()
    changed = [
        a["case_id"]
        for a, b in zip(old["resolved_source_cases"], cases, strict=True)
        if a != b
    ]
    assert changed == ["MAIN-C332", "MAIN-C333"]
    assert [k for k, v in claims.items() if v != old["resolved_source_claims"][k]] == [
        "CENSUS-R945",
        "CENSUS-R946",
    ]
    for a, b in zip(old["resolved_source_cases"], cases, strict=True):
        assert a["expected_daymaster_strength"] == b["expected_daymaster_strength"]
        assert a["forbidden_daymaster_strengths"] == b["forbidden_daymaster_strengths"]
        for key in a.keys() - {"literal_pillars", "source_metadata"}:
            assert a[key] == b[key]
        if a["case_id"] in changed:
            meta = copy.deepcopy(b["source_metadata"])
            provenance = meta.pop("literal_formula_position_provenance")
            assert not provenance["historical_birth_moment_identified"]
            assert not provenance["strength_label_assigned"]
            meta["source_condition"] = a["source_metadata"]["source_condition"]
            assert meta == a["source_metadata"]
    for identity in ["CENSUS-R945", "CENSUS-R946"]:
        modified = copy.deepcopy(claims[identity])
        modified["retained_statement"] = old["resolved_source_claims"][identity][
            "retained_statement"
        ]
        assert modified == old["resolved_source_claims"][identity]
    assert receipt["raw_complete_literal_cases_retained"] == 530
    c010 = next(c for c in cases if c["case_id"] == "MAIN-C010")
    assert all(v is None for v in c010["literal_pillars"].values())


@pytest.mark.parametrize(
    "attack",
    [
        "missing_case",
        "unknown_case_anchor",
        "case_grade",
        "unrelated_claim",
        "source_actor",
    ],
)
def test_full_preimage_guard_rejects_changes_outside_the_two_formulas(attack):
    old = before()
    cases, claims = old["resolved_source_cases"], old["resolved_source_claims"]
    if attack == "missing_case":
        cases.pop()
    elif attack == "unknown_case_anchor":
        cases[0]["anchor"] = "丙寅戊辰月日己卯癸卯年時"
    elif attack == "case_grade":
        cases[-1]["expected_daymaster_strength"] = "强"
    elif attack == "unrelated_claim":
        claims[next(iter(claims))]["retained_statement"] = "replacement"
    else:
        cases[0]["speaker_chain"] = ["different voice"]
    with pytest.raises(ValueError, match="preimage"):
        apply(cases, claims)


def minimal_root(tmp_path):
    plan = AUDIT.read_bound(ROOT / AUDIT.GROUPED_FORMULA_PLAN)
    paths = [
        AUDIT.GROUPED_FORMULA_PLAN,
        plan["before_snapshot"]["path"],
        *plan["evidence"],
    ]
    binding = "docs/validation/bazi-ditian-wholebook-census-v1/source-formula-position-resolutions-v1.json"
    paths.append(binding)
    for relative in paths:
        p, q = ROOT / relative, tmp_path / relative
        q.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, q)
        if p.with_suffix(".sha256").exists():
            shutil.copy2(p.with_suffix(".sha256"), q.with_suffix(".sha256"))
    return tmp_path / "docs/validation/bazi-ditian-wholebook-census-v1"


@pytest.mark.parametrize(
    "attack", ["rebind_plan", "wrong_binding", "duplicate_document", "changed_image"]
)
def test_pinned_review_cannot_be_rebound_with_its_own_sidecar(tmp_path, attack):
    study = minimal_root(tmp_path)
    if attack == "changed_image":
        plan = AUDIT.read_bound(ROOT / AUDIT.GROUPED_FORMULA_PLAN)
        (tmp_path / next(iter(plan["evidence"]))).write_bytes(b"different pixels")
    elif attack == "duplicate_document":
        p = study / "source-formula-position-resolutions-extra.json"
        p.write_text("{}")
    else:
        p = (
            tmp_path / AUDIT.GROUPED_FORMULA_PLAN
            if attack == "rebind_plan"
            else study / "source-formula-position-resolutions-v1.json"
        )
        data = json.loads(p.read_text())
        if attack == "rebind_plan":
            data["resolutions"][0]["expected_pillars"]["year"] = "甲子"
        else:
            data["review_plan_sha256"] = "0" * 64
        p.write_text(json.dumps(data, ensure_ascii=False))
        p.with_suffix(".sha256").write_text(AUDIT.sha(p))
    with pytest.raises(ValueError):
        apply(root=tmp_path, study=study)


def test_current_full_census_remains_closed_with_all_original_failures():
    old = before()
    current = AUDIT.audit(CENSUS, ROOT)
    assert current["complete_literal_cases"] == 532
    assert current["raw_complete_literal_cases_retained"] == 530
    assert current["exact_body_labels"] == 26
    assert current["unknown_body_labels_retained"] == 532
    for key in [
        "source_case_input_questions_retained",
        "remaining_case_input_questions",
        "transcription_warnings_retained",
        "remaining_transcription_warnings",
    ]:
        assert current[key] == old[key]
    assert len(current["remaining_case_input_questions"]) == 3
    assert len(current["remaining_transcription_warnings"]) == 22
    assert not current["whole_book_collection_frozen"]
    assert not current["candidate_evaluation_allowed"]

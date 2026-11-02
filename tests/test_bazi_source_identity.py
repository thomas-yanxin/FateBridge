"""Documentary corrections must not improve strength scores or erase history."""

import gzip
import importlib.util
import json
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest

from fatebridge.core.source_identity import (
    NAME_NOTE,
    PARENT_SHA256,
    PLAN_SHA256,
    PUBLISHER_NOTE,
    build_identity_index,
    canonical_digest,
)
from fatebridge.services.source_comparison import calculate_bazi_source_compare

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_source_identity_v1"
FILES = ROOT / "docs/validation/bazi-source-identity-files-v1"
DATA = ROOT / "src/fatebridge/data/reference"


def load(name):
    return json.loads((DATA / name).read_text())


def plan():
    raw = (FIXTURE / "patch-plan-first.json").read_bytes()
    assert sha256(raw).hexdigest() == PLAN_SHA256
    return json.loads(raw)


def test_all367_records_only58_exact_documentary_changes_123known244unknown_retained():
    before = load("bazi-source-annotations-v7.json")
    after = load("bazi-source-annotations-v8.json")
    assert (
        sha256((DATA / "bazi-source-annotations-v7.json").read_bytes()).hexdigest()
        == PARENT_SHA256
    )
    patches = {p["reference_id"]: p for p in plan()["patches"]}
    assert len(patches) == 58
    for old, new in zip(before["records"], after["records"], strict=True):
        patch = patches.get(old["reference_id"])
        assert (old, new) == (patch["before"], patch["after"]) if patch else old == new
        assert old["pillars"] == new["pillars"]
        assert old["case_id"] == new["case_id"]
        assert (
            old["retained_strength_annotation"] == new["retained_strength_annotation"]
        )
    assert len(after["records"]) == 367 and after["literal_input_count"] == 321
    assert (
        sum(r["retained_strength_annotation"] is None for r in after["records"]) == 244
    )
    assert (
        sum(r["retained_strength_annotation"] is not None for r in after["records"])
        == 123
    )
    assert after["strength_constraints"] == before["strength_constraints"]


def test_printed_names_and_publisher_match_pinned_images_no_historical_identity_claim():
    records = {
        r["case_id"]: r for r in load("bazi-source-annotations-v8.json")["records"]
    }
    for identifier, pillars, name, grade in [
        (
            "ZP-PROSPECTIVE-17-MAO-HEAVY",
            ["壬寅", "戊申", "壬辰", "壬寅"],
            "馬參政",
            "强",
        ),
        (
            "ZP-PROSPECTIVE-18-MA-LIGHT",
            ["己巳", "癸酉", "癸未", "庚申"],
            "茅狀元",
            "弱",
        ),
    ]:
        row = records[identifier]
        assert (
            row["pillars"],
            row["name_as_printed"],
            row["retained_strength_annotation"],
        ) == (pillars, name, grade)
        revision = row["source_identity_revision"]
        correction = revision["name_correction"]
        assert correction["historical_person_identity_asserted"] is False
        assert correction["legacy_case_identifier_retained"] is True
        assert correction["source_pdf_page"] == 73
        assert (
            correction["source_image_sha256"]
            == sha256(
                (
                    ROOT
                    / "tests/fixtures/bazi_condition_evaluation_v1/model-inputs/primary/ziping-p73.png"
                ).read_bytes()
            ).hexdigest()
        )
        assert (
            revision["source_image_sha256"]
            == sha256(
                (
                    ROOT
                    / "docs/validation/bazi-condition-evaluation-files-v1/ziping-title-p1-first.png"
                ).read_bytes()
            ).hexdigest()
        )
        assert "上海世界图书馆发行" in row["source_reference"]["edition"]
        assert "世界书局发行" in revision["original_edition"]


def test_all367_complete_public_results_have_only_declared_documentary_diffs():
    patches = {p["reference_id"]: p for p in plan()["patches"]}
    index_sha = sha256(
        (DATA / "bazi-source-annotations-v8.json").read_bytes()
    ).hexdigest()
    count = 0
    after_source = FILES / "public-all367-source-first.jsonl.gz"
    assert (
        sha256(after_source.read_bytes()).hexdigest()
        == "09ea703d268ec5a138544041ea2e675862ae6584d5313f3b01037a99fce4d92e"
    )
    sealed_after = {
        r["reference_id"]: r
        for r in (json.loads(line) for line in gzip.open(after_source, "rt"))
    }
    assert len(sealed_after) == 367
    with gzip.open(FILES / "public-all367-before-first.jsonl.gz", "rt") as handle:
        for line in handle:
            case = json.loads(line)
            old = case["result"]
            expected = deepcopy(old)
            edited = named = False
            records = expected["source_comparison"]["records"]
            for i, row in enumerate(records):
                patch = patches.get(row["reference_id"])
                if patch is None:
                    continue
                retained_runtime = {
                    k: row[k]
                    for k in ["comparison", "bounded_strength_constraints"]
                    if k in row
                }
                assert canonical_digest(
                    {k: v for k, v in row.items() if k not in retained_runtime}
                ) == canonical_digest(patch["before"])
                records[i] = {**deepcopy(patch["after"]), **retained_runtime}
                edited = True
                named |= "name_as_printed" in patch["after"]
            expected["source_comparison"]["reference_index"].update(
                index_sha256=index_sha,
                data_revision="source_annotations_v8_witness_identity",
                source_identity_plan_sha256=PLAN_SHA256,
                total_registered_source_identity_revisions=58,
                total_registered_printed_name_corrections=2,
            )
            expected["summary"] += (PUBLISHER_NOTE if edited else "") + (
                NAME_NOTE if named else ""
            )
            sealed = sealed_after[case["reference_id"]]
            assert sealed["pillars"] == case["pillars"]
            actual = sealed["result"]
            assert canonical_digest(actual["current_calculation"]) == canonical_digest(
                old["current_calculation"]
            )
            assert canonical_digest(actual) == canonical_digest(expected), case[
                "reference_id"
            ]
            count += 1
    assert count == 367


@pytest.mark.parametrize(
    "fault",
    [
        "grade",
        "pillars",
        "case_id",
        "annotation",
        "publisher",
        "credit",
        "credit_bool",
        "name",
        "legacy_name",
        "identity",
        "name_page",
        "publisher_page_bool",
        "extra",
        "count",
        "missing",
        "duplicate",
    ],
)
def test_generator_rejects_unrelated_regrading_identity_or_type_changes(fault):
    parent = load("bazi-source-annotations-v7.json")
    proposal = deepcopy(plan())
    patch = next(p for p in proposal["patches"] if "name_as_printed" in p["after"])
    row = patch["after"]
    revision = row["source_identity_revision"]
    if fault == "grade":
        row["retained_strength_annotation"] = "中和"
    elif fault == "pillars":
        row["pillars"][0] = "甲子"
    elif fault == "case_id":
        row["case_id"] = "new"
    elif fault == "annotation":
        row["annotation_basis"] = "pretend source agrees"
    elif fault == "publisher":
        row["source_reference"]["edition"] = "another source"
    elif fault == "credit":
        revision["new_independent_validation_credit"] = 1
    elif fault == "credit_bool":
        revision["new_independent_validation_credit"] = False
    elif fault == "name":
        row["name_as_printed"] = "unknown"
    elif fault == "legacy_name":
        revision["name_correction"]["legacy_registered_name"] = "unknown"
    elif fault == "identity":
        revision["name_correction"]["historical_person_identity_asserted"] = True
    elif fault == "name_page":
        revision["name_correction"]["source_pdf_page"] = 72
    elif fault == "publisher_page_bool":
        revision["source_pdf_page"] = True
    elif fault == "extra":
        row["source_certified"] = True
    elif fault == "count":
        proposal["publisher_correction_count"] = 59
    elif fault == "missing":
        proposal["patches"].pop()
    else:
        proposal["patches"][-1] = deepcopy(proposal["patches"][0])
    with pytest.raises(ValueError):
        build_identity_index(parent, proposal, "0" * 64)


def test_generator_reproduces_both_artifacts_and_rejects_rebound_plan(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "source_identity_builder", ROOT / "scripts/build_bazi_source_index_v8.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.generate() == load("bazi-source-annotations-v8.json")
    assert (DATA / "bazi-source-witness-identity-v1.json").read_bytes() == (
        FIXTURE / "patch-plan-first.json"
    ).read_bytes()
    module.ROOT = tmp_path
    parent = tmp_path / "src/fatebridge/data/reference/bazi-source-annotations-v7.json"
    parent.parent.mkdir(parents=True)
    parent.write_bytes((DATA / parent.name).read_bytes())
    target = tmp_path / module.PLAN
    target.parent.mkdir(parents=True)
    target.write_text("{}")
    with pytest.raises(ValueError, match="protocol or parent"):
        module.generate()

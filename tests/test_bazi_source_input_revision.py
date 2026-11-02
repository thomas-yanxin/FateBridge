"""A source input repair must retain the population, unknowns and old failures."""

import gzip
import hashlib
import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.validation.bazi_source_corpus import (
    digest,
    load_registry,
    pillar_values,
    source_cases,
    strength_annotation,
)
from fatebridge.validation.bazi_source_inputs import (
    PLAN_PATH,
    PLAN_SHA256,
    source_documents,
)

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-corpus-input-revision-v1"
REGISTRY = ROOT / "tests/fixtures/bazi_source_corpus_v9/registry.json"
EXPECTED = {
    ("passage", "DTCW1947-TG-04"): ["己巳", "丁卯", "辛卯", "乙未"],
    ("prior_root_v4", "DTCW1947-GS-04"): ["己亥", "丙寅", "戊子", "甲寅"],
    ("prior_ganzhi", "GH-27"): ["壬寅", "丙午", "庚午", "庚辰"],
    ("prior_shape_bureau", "FJ-07"): ["戊寅", "甲寅", "甲辰", "丁卯"],
    ("complete_zhonghe_yuanliu_tongguan_v5", "YL-02"): ["辛丑", "癸巳", "戊申", "丙辰"],
    ("complete_zhonghe_yuanliu_tongguan_v5", "TG-04"): ["己巳", "丁卯", "辛卯", "乙未"],
}


def read_report(path):
    assert digest(path) == path.with_suffix(path.suffix + ".sha256").read_text().strip()
    return json.loads(gzip.decompress(path.read_bytes()))


def test_full_population_only_six_reviewed_inputs_change_unknowns_stay_unknown():
    registry = load_registry(ROOT, REGISTRY)
    documents, originals, receipt = source_documents(ROOT, registry)
    changed = set()
    assert len(documents) == 27
    assert sum(len(source_cases(d)) for d in documents.values()) == 367
    for group in documents:
        for before, after in zip(
            source_cases(originals[group]), source_cases(documents[group]), strict=True
        ):
            assert before["id"] == after["id"]
            assert strength_annotation(before) == strength_annotation(after)
            if before != after:
                key = group, before["id"]
                changed.add(key)
                assert pillar_values(after) == EXPECTED[key]
                assert strength_annotation(after) == (
                    "explicitly_unknown_body_strength",
                    None,
                )
                for stale in (
                    "variants",
                    "input_consistency",
                    "prior_exact_pillar_overlaps",
                    "fresh_gate_eligible",
                    "unseen_input",
                ):
                    assert stale not in after
                assert not after["source_input_revision"][
                    "source_strength_label_assigned"
                ]
    assert changed == EXPECTED.keys()
    assert len(receipt["changed_source_records"]) == 6
    assert receipt["new_independent_validation_credit"] == 0
    assert receipt["source_strength_labels_changed"] is False
    assert documents["prior_ganzhi"]["source_relative_force_statements"] == (
        originals["prior_ganzhi"]["source_relative_force_statements"]
    )
    for group, path in registry["groups"].items():
        assert json.loads((ROOT / path).read_text()) == originals[group]


def test_raw_v8_replays_all367_saved_assessments_without_source_revision():
    old = read_report(
        ROOT / "docs/validation/bazi-source-bounds-v1/corpus-frozen-first.json.gz"
    )
    raw = read_report(STUDY / "raw-v8-replay-first.json.gz")
    assert raw["source_input_revision"] is None
    assert raw["record_count"] == old["record_count"] == 367
    for group in old["groups"]:
        assert raw["groups"][group]["rows"] == old["groups"][group]["rows"]
    for field in (
        "local_and_negative_claims",
        "all_distinct_disagreements",
        "original_nineteen",
    ):
        assert raw[field] == old[field]


def test_all361_other_assessments_all_labels_and_claims_exact_no_pass_credit():
    raw = read_report(STUDY / "raw-v8-replay-first.json.gz")
    current = read_report(STUDY / "current-v9-replay-first.json.gz")
    unchanged = changed = annotated = 0
    for group in raw["groups"]:
        for before, after in zip(
            raw["groups"][group]["rows"], current["groups"][group]["rows"], strict=True
        ):
            assert after["original_source_record"] == before["source_record"]
            assert before["expected_strength"] == after["expected_strength"]
            assert before["matches"] == after["matches"]
            if (group, before["id"]) not in EXPECTED:
                copied = deepcopy(after)
                copied.pop("original_source_record")
                assert copied == before
                unchanged += 1
            else:
                assert after["pillars"] == EXPECTED[(group, before["id"])]
                assert after["matches"] is None
                assert after["assessment"] != before["assessment"]
                changed += 1
            annotated += before["expected_strength"] is not None
    assert (unchanged, changed, annotated) == (361, 6, 123)
    for field in (
        "local_and_negative_claims",
        "all_distinct_disagreements",
        "original_nineteen",
        "group_counts",
    ):
        assert current[field] == raw[field]
    assert len(current["all_distinct_disagreements"]) == 24
    assert current["record_count"] == 367
    assert current["input_index"]["distinct_four_pillar_inputs"] == 321
    assert current["source_labels_changed"] is False
    assert current["classical_acceptance_passed"] is False
    assert current["new_independent_cases"] == 0
    assert current["overall_score"] is None


def test_current_auditor_actually_uses_revision_not_only_saved_output():
    import fatebridge.validation.bazi_source_inputs as source_module
    from scripts.audit_bazi_source_corpus import audit

    assert Path(source_module.__file__).resolve() == (
        ROOT / "src/fatebridge/validation/bazi_source_inputs.py"
    )
    assert Path(audit.__code__.co_filename).resolve() == (
        ROOT / "scripts/audit_bazi_source_corpus.py"
    )
    result = audit()
    original = read_report(STUDY / "current-v9-replay-first.json.gz")
    reference = (
        ROOT
        / "tests/fixtures/architecture_refactor_v1/source-corpus-before-manifest.json"
    )
    assert (
        hashlib.sha256(reference.read_bytes()).hexdigest()
        == "3fed274529550529baa54938747d3aeda0e8e11f8de896b9cb4688ef42e2e976"
    )
    saved = json.loads(reference.read_bytes())
    for field in (
        "groups",
        "source_input_revision",
        "group_counts",
        "input_index",
        "local_and_negative_claims",
        "all_distinct_disagreements",
        "literal_input_consistency_flags",
        "original_nineteen",
    ):
        encoded = json.dumps(
            result[field],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        assert hashlib.sha256(encoded).hexdigest() == saved[field]
    assert result["source_drift"] == []


def minimal_root(tmp_path):
    registry = json.loads(REGISTRY.read_text())
    plan = json.loads((ROOT / PLAN_PATH).read_text())
    paths = set(registry["groups"].values()) | {PLAN_PATH, plan["parent_registry"]}
    for relative in paths:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    return registry, plan


@pytest.mark.parametrize(
    "attack", ["remove_group", "relabel", "alter_context", "drop_unknown"]
)
def test_entire_preimage_rejects_population_label_and_unrelated_metadata_drift(
    tmp_path, attack
):
    registry, _ = minimal_root(tmp_path)
    if attack == "remove_group":
        registry["groups"].pop("legacy")
    else:
        path = registry["groups"]["passage"]
        document = json.loads((tmp_path / path).read_text())
        if attack == "relabel":
            document["cases"][3]["expected_strength"] = "弱"
        elif attack == "alter_context":
            document["cases"][0]["annotation"] = "changed source context"
        else:
            document["cases"].pop(3)
        (tmp_path / path).write_text(json.dumps(document))
        registry["source_sha256"][path] = digest(tmp_path / path)
    with pytest.raises(ValueError, match="population|preimage"):
        source_documents(tmp_path, registry)


def test_replacing_review_and_its_own_hash_does_not_rebind_the_pinned_plan(tmp_path):
    registry, plan = minimal_root(tmp_path)
    plan["patches"][0]["after"]["expected_strength"] = "弱"
    p = tmp_path / PLAN_PATH
    p.write_text(json.dumps(plan))
    p.with_suffix(".sha256").write_text(digest(p) + "\n")
    registry["input_view"]["plan_sha256"] = digest(p)
    with pytest.raises(ValueError, match="pinned source review"):
        source_documents(tmp_path, registry)
    assert digest(ROOT / PLAN_PATH) == PLAN_SHA256


@pytest.mark.parametrize("witness", ["review", "cadal", "original"])
def test_changed_image_cannot_be_ignored_or_replaced_with_formula_repair(
    tmp_path, witness
):
    registry, plan = minimal_root(tmp_path)
    for relative in plan["evidence_sha256"]:
        p = tmp_path / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        target = (
            witness == "review"
            and relative.endswith("all8-direct-image-review-first.json")
            or witness == "cadal"
            and "cadal-leaf" in relative
            or witness == "original"
            and "page-images/" in relative
        )
        if target:
            p.write_bytes(b"different image reading or pixels")
            break
        shutil.copy2(ROOT / relative, p)
    with pytest.raises(ValueError, match="reading evidence changed"):
        source_documents(tmp_path, registry)


def test_partial_public_replay_cannot_claim_the_complete_current_view():
    from scripts.audit_bazi_clash_current import audit

    with pytest.raises(ValueError, match="retain all registered groups"):
        audit(
            {"legacy": "tests/fixtures/bazi-strength-reference.json"},
            source_view_registry=REGISTRY,
        )

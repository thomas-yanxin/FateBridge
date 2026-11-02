"""Restore source commentary without converting it into a source grade or quote."""

import gzip
import importlib.util
import json
import shutil
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest

from fatebridge.core.source_annotations import compare_registered_annotations
from fatebridge.services.source_comparison import calculate_bazi_source_compare

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-editorial-annotation-projection-v1"
DATA = ROOT / "src/fatebridge/data/reference"


def plan():
    return json.loads((STUDY / "protocol-first.json").read_text())


def test_all149_notes_follow_exact_source_fields_all218_other_records_exact():
    before = json.loads((DATA / "bazi-source-annotations-v6.json").read_text())
    after = json.loads((DATA / "bazi-source-annotations-v7.json").read_text())
    patches = {p["reference_id"]: p for p in plan()["patches"]}
    changed = known = 0
    for old, new in zip(before["records"], after["records"], strict=True):
        assert old["reference_id"] == new["reference_id"]
        if old == new:
            assert old["reference_id"] not in patches
            continue
        patch = patches[old["reference_id"]]
        assert (old, new) == (patch["before"], patch["after"])
        assert old["annotation_basis"] is old["retained_context"] is None
        source = patch["source_record"]
        assert (
            new["annotation_basis"] == new["retained_context"] == source["annotation"]
        )
        provenance = new["editorial_annotation_provenance"]
        value = json.loads((ROOT / provenance["registered_document"]).read_text())
        for part in provenance["source_field_pointer"].strip("/").split("/"):
            value = value[int(part)] if isinstance(value, list) else value[part]
        assert value == source["annotation"]
        assert sha256(value.encode()).hexdigest() == provenance["annotation_sha256"]
        assert provenance["is_verbatim_original_text"] is False
        assert provenance["strength_label_assigned_or_regraded"] is False
        assert provenance["new_independent_validation_credit"] == 0
        for key in old.keys() - {"annotation_basis", "retained_context"}:
            assert new[key] == old[key]
        known += old["retained_strength_annotation"] is not None
        changed += 1
    assert (changed, known, len(after["records"])) == (149, 52, 367)
    assert after["strength_constraints"] == before["strength_constraints"]
    for key in (
        "method_id",
        "registry_sha256",
        "literal_input_count",
        "input_reading_revision_count",
        "strength_constraint_count",
    ):
        assert after[key] == before[key]


def test_all367_historical_public_results_changed_only_qualified_notes_and_metadata():
    old = json.loads(
        gzip.decompress((STUDY / "public-before-first.json.gz").read_bytes())
    )
    declared = plan()
    patches = {p["reference_id"]: p for p in declared["patches"]}
    after_source = STUDY / "public-after-first.json.gz"
    assert (
        sha256(after_source.read_bytes()).hexdigest()
        == "96b0bc58b21e05c7aad3dac54ba53fe3606a41f38cbf22f9f82a27c056ed8e34"
    )
    after_rows = json.loads(gzip.decompress(after_source.read_bytes()))["rows"]
    sealed_after = {row["reference_id"]: row for row in after_rows}
    assert len(sealed_after) == len(old["rows"]) == 367
    negatives, unknowns, count = set(), 0, 0
    for case in old["rows"]:
        before = deepcopy(case["result"])
        sealed = sealed_after[case["reference_id"]]
        assert sealed["pillars"] == case["pillars"]
        after = deepcopy(sealed["result"])
        assert "error" not in after
        assert after["current_calculation"] == before["current_calculation"]
        new_comp, old_comp = after["source_comparison"], before["source_comparison"]
        notes = False
        for r, b in zip(new_comp["records"], old_comp["records"], strict=True):
            if b["reference_id"] in patches:
                p = patches[b["reference_id"]]
                for key in (
                    "annotation_basis",
                    "retained_context",
                    "editorial_annotation_provenance",
                ):
                    b[key] = p["after"][key]
                notes = True
            assert r == b
        metadata = new_comp.pop("reference_index")
        old_meta = old_comp.pop("reference_index")
        assert metadata["data_revision"] == "source_annotations_v7_editorial_projection"
        assert metadata["total_registered_editorial_annotations"] == 149
        for key in old_meta.keys() - {"index_sha256"}:
            assert metadata[key] == old_meta[key]
        assert new_comp == old_comp
        if notes:
            assert after["summary"].count(declared["summary_note"]) == 1
            assert (
                after["summary"].replace(declared["summary_note"], "", 1)
                == before["summary"]
            )
        else:
            assert after["summary"] == before["summary"]
        for key in after.keys() - {"source_comparison", "summary"}:
            assert after[key] == before[key]
        own = next(
            r for r in new_comp["records"] if r["reference_id"] == case["reference_id"]
        )
        if own["comparison"] == "differs":
            negatives.add(tuple(case["pillars"]))
        unknowns += own["retained_strength_annotation"] is None
        count += 1
    assert (count, unknowns, len(negatives)) == (367, 244, 24)


def test_all367_current_complete_results_match_before_dependency_repair():
    manifest = (
        ROOT
        / "tests/fixtures/architecture_refactor_v1/editorial367-before-manifest.json"
    )
    raw = manifest.read_bytes()
    assert (
        sha256(raw).hexdigest()
        == "d264e94b6fba8fda2b1c9d0b0ef11bf060be6feaed6c2968ac0a9dddbc31fb27"
    )
    data = json.loads(raw)
    assert (
        sha256((STUDY / "public-before-first.json.gz").read_bytes()).hexdigest()
        == data["source_sha256"]
    )
    assert len(data["rows"]) == 367
    for row in data["rows"]:
        current = calculate_bazi_source_compare(*row["pillars"])
        encoded = json.dumps(
            current,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        assert sha256(encoded).hexdigest() == row["business_sha256"]


def test_returned_editorial_provenance_cannot_poison_shared_index():
    pillars = dict(
        zip(
            ("year", "month", "day", "hour"),
            map(tuple, ["癸酉", "甲子", "丁卯", "丙午"]),
        )
    )
    first = compare_registered_annotations(pillars, "强")
    original = deepcopy(first)
    row = next(r for r in first["records"] if "editorial_annotation_provenance" in r)
    row["annotation_basis"] = "invented quote"
    row["editorial_annotation_provenance"]["is_verbatim_original_text"] = True
    assert compare_registered_annotations(pillars, "强") == original


@pytest.mark.parametrize(
    "fault",
    ["verbatim", "regrade", "credit", "case", "document", "bytes", "grade", "count"],
)
def test_runtime_rejects_changed_annotation_or_false_claims(tmp_path, fault):
    source = ROOT / "src/fatebridge/core/source_annotations.py"
    target = tmp_path / "fatebridge/core/source_annotations.py"
    target.parent.mkdir(parents=True)
    shutil.copy2(source, target)
    # Exercise the same eight frozen editorial-note faults in the current
    # versioned index. The original v7 fixture and first failures are retained.
    data = json.loads((DATA / "bazi-source-annotations-v8.json").read_text())
    row = next(r for r in data["records"] if "editorial_annotation_provenance" in r)
    p = row["editorial_annotation_provenance"]
    if fault == "verbatim":
        p["is_verbatim_original_text"] = True
    elif fault == "regrade":
        p["strength_label_assigned_or_regraded"] = True
    elif fault == "credit":
        p["new_independent_validation_credit"] = 1
    elif fault == "case":
        p["case_id"] = "different"
    elif fault == "document":
        p["registered_document"] = "different"
    elif fault == "bytes":
        row["annotation_basis"] += "tamper"
        row["retained_context"] += "tamper"
    elif fault == "grade":
        row["retained_strength_annotation"] = "弱"
    else:
        data["editorial_annotation_count"] -= 1
    dest = tmp_path / "fatebridge/data/reference/bazi-source-annotations-v8.json"
    dest.parent.mkdir(parents=True)
    dest.write_text(json.dumps(data))
    spec = importlib.util.spec_from_file_location("editorial_projection_fault", target)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(ValueError, match="编辑说明"):
        module._index()


def test_generator_reproduces_qualified_index_and_rejects_rebound_plan(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "editorial_projection_generator", ROOT / "scripts/build_bazi_source_index_v7.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.generate() == json.loads(
        (DATA / "bazi-source-annotations-v7.json").read_text()
    )
    module.ROOT = tmp_path
    p = tmp_path / module.PROTOCOL
    p.parent.mkdir(parents=True)
    p.write_text("{}")
    p.with_suffix(".sha256").write_text(sha256(p.read_bytes()).hexdigest() + "\n")
    with pytest.raises(ValueError, match="protocol changed"):
        module.generate()

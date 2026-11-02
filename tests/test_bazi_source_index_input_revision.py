"""Reviewed source inputs must reach public lookup without changing calculation."""

import gzip
import hashlib
import importlib.util
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core.source_annotations import compare_registered_annotations
from fatebridge.services.source_comparison import calculate_bazi_source_compare
from fatebridge.validation.bazi_source_corpus import digest
from tests.bazi_refactor_reference import assert_assessment_matches_before_repair

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-source-index-input-revision-v1"
PACKAGE = ROOT / "src/fatebridge/data/reference"


def data(name):
    return json.loads((PACKAGE / name).read_text())


def compressed(path):
    assert digest(path) == path.with_suffix(path.suffix + ".sha256").read_text().strip()
    return json.loads(gzip.decompress(path.read_bytes()))


def test_all367_index_records_only_six_pinned_readings_change_no_labels_or_bounds():
    plan = json.loads((STUDY / "protocol-first.json").read_text())
    assert digest(ROOT / plan["old_index"]) == plan["old_index_sha256"]
    old, new = [data(f"bazi-source-annotations-v{n}.json") for n in (5, 6)]
    patches = {p["reference_id"]: p for p in plan["patches"]}
    seen = set()
    for before, after in zip(old["records"], new["records"], strict=True):
        assert before["reference_id"] == after["reference_id"]
        assert (
            before["retained_strength_annotation"]
            == after["retained_strength_annotation"]
        )
        if before != after:
            patch = patches[before["reference_id"]]
            assert (before, after) == (patch["before"], patch["after"])
            assert after["retained_strength_annotation"] is None
            assert after["input_reading_revision"]["original_index_record"] == before
            assert (
                after["source_reference"]["registered_document_scope"]
                == "original_transcription_before_input_revision"
            )
            seen.add(before["reference_id"])
    assert seen == patches.keys()
    assert len(new["records"]) == 367
    assert new["strength_constraints"] == old["strength_constraints"]
    assert new["strength_constraint_count"] == 3
    assert (
        sum(r["retained_strength_annotation"] is not None for r in new["records"])
        == 123
    )
    assert new["literal_input_count"] == 321


def test_all367_current_source_inputs_retrieve_exact_row_and_same_full_assessment():
    saved = compressed(
        ROOT
        / "docs/validation/bazi-corpus-input-revision-v1/current-v9-replay-first.json.gz"
    )
    count = unknown = 0
    disagreements = set()
    for group in saved["groups"].values():
        for row in group["rows"]:
            result = calculate_bazi_source_compare(*row["pillars"])
            assert "error" not in result
            assert_assessment_matches_before_repair(
                row["pillars"], result["current_calculation"]["assessment"]
            )
            comp = result["source_comparison"]
            matched = next(
                r
                for r in comp["records"]
                if (r["group"], r["case_id"]) == (row["group"], row["id"])
            )
            assert matched["retained_strength_annotation"] == row["expected_strength"]
            assert matched["comparison"] == (
                "unadjudicated"
                if row["matches"] is None
                else "agrees" if row["matches"] else "differs"
            )
            if row["matches"] is False:
                disagreements.add(tuple(row["pillars"]))
            unknown += row["expected_strength"] is None
            assert comp["calculation_overridden"] is False
            assert comp["new_independent_validation_credit"] == 0
            count += 1
    assert (count, unknown, len(disagreements)) == (367, 244, 24)


def test_all_old367_inputs_still_calculate_identically_no_alias_of_retired_readings():
    before = compressed(STUDY / "public-before-first.json.gz")
    plan = json.loads((STUDY / "protocol-first.json").read_text())
    retired = {tuple(p["before"]["pillars"]) for p in plan["patches"]}
    reference = (
        ROOT
        / "tests/fixtures/architecture_refactor_v1/source-index373-before-manifest.json"
    )
    assert (
        hashlib.sha256(reference.read_bytes()).hexdigest()
        == "2eaf7a9b5658ffea9dc2943117e55ba1cd59293d07778c8166453f8fb2ec2a3a"
    )
    accepted = json.loads(reference.read_bytes())
    assert (
        digest(STUDY / "public-before-first.json.gz")
        == accepted["original_source_sha256"]
    )
    assert (
        len(accepted["rows"]["old367"]) == 367
        and len(accepted["rows"]["corrected6"]) == 6
    )
    for row, expected in zip(before["old367"], accepted["rows"]["old367"], strict=True):
        assert row["pillars"] == expected["pillars"]
        current = calculate_bazi_source_compare(*row["pillars"])
        raw = json.dumps(
            current,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        assert hashlib.sha256(raw).hexdigest() == expected["business_sha256"]
        if tuple(row["pillars"]) in retired:
            assert (
                current["source_comparison"]["status"] == "no_registered_literal_case"
            )
            assert current["source_comparison"]["records"] == []
    for row, expected in zip(
        before["corrected6"], accepted["rows"]["corrected6"], strict=True
    ):
        assert row["pillars"] == expected["pillars"]
        current = calculate_bazi_source_compare(*row["pillars"])
        raw = json.dumps(
            current,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        assert hashlib.sha256(raw).hexdigest() == expected["business_sha256"]
        comp = current["source_comparison"]
        assert comp["status"] == "unadjudicated_records_only"
        assert comp["agreeing_known_count"] == comp["differing_known_count"] == 0
        assert comp["full_original_text_conformance_certified"] is False
        assert "校读未补定强弱标签" in current["summary"]
        for record in comp["records"]:
            revision = record["input_reading_revision"]
            assert revision["source_strength_label_assigned"] is False
            assert revision["independent_edition_or_expert_review"] is False
            assert revision["new_independent_validation_credit"] == 0
        if row["reference_id"].endswith("TG-04"):
            assert comp["literal_match_count"] == 2


def test_corrected_record_full_provenance_is_not_mutable_via_returned_results():
    pillars = dict(
        zip(
            ("year", "month", "day", "hour"),
            map(tuple, ["己巳", "丁卯", "辛卯", "乙未"]),
        )
    )
    first = compare_registered_annotations(pillars, "弱")
    original = deepcopy(first)
    first["records"][0]["input_reading_revision"]["original_source_record"]["pillars"][
        2
    ] = "甲子"
    first["records"][0]["input_reading_revision"][
        "source_strength_label_assigned"
    ] = True
    assert compare_registered_annotations(pillars, "弱") == original


def test_generator_reproduces_packaged_index_with_original_protocol_guard(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "reviewed_index_generator", ROOT / "scripts/build_bazi_source_index_v6.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.generate() == data("bazi-source-annotations-v6.json")
    module.ROOT = tmp_path
    target = tmp_path / module.PROTOCOL
    target.parent.mkdir(parents=True)
    target.write_text("{}")
    with pytest.raises(ValueError, match="protocol changed"):
        module.generate()

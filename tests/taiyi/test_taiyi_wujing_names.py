"""Book conventions cannot be selected to improve an audit score."""

import copy
import json
import shutil

import pytest

from scripts.taiyi.audit_taiyi_wujing_facsimile import audit as native_audit
from scripts.taiyi.audit_taiyi_wujing_names import (
    CORPUS,
    ROOT,
    audit,
    compare,
    resolve_name,
    verify,
)


@pytest.fixture(scope="module")
def report():
    return audit()


@pytest.mark.parametrize("literal", verify()["unadjudicated_name_aliases"])
def test_unknown_aliases_are_not_guessed_from_other_books(literal):
    assert resolve_name(literal, verify())["value"] is None


def test_same_book_yin_yang_de_definitions_keep_the_conflict_and_suffix():
    profile = verify()
    assert resolve_name("陰德客目掩", profile)["value"] == "丑"
    assert resolve_name("陽德辰迫", profile)["value"] == "乾"
    assert resolve_name("陽德辰迫", profile)["unadjudicated_suffix"] == "辰迫"
    assert resolve_name("大族宮擊", profile)["value"] == "酉"
    assert profile["conflict_adjudicated"] is False


def test_full_cohort_and_original_results_are_retained(report):
    baseline = native_audit()
    assert report["original_v46_layer"] == baseline
    assert (
        report["current_actual_rule_profile"]
        == baseline["current_literal_layer"]["actual_rule_profile"]
    )
    assert len(report["old_differences_retained"]) == 45
    assert report["old_differences_retained"] == baseline["old_differences_retained"]
    assert report["required_observations"] == 1440
    assert len(report["source_rows"]) == 144
    assert all(len(r["comparisons"]) == 10 for r in report["source_rows"])
    for counts in report["field_totals"].values():
        assert (
            counts["required"]
            == sum(counts[k] for k in ("matching", "different", "unknown"))
            == 144
        )
    assert all(
        r["field"] in {"wenchang_palace", "shiji"}
        for r in report["source_reference_changes"]
    )
    assert report["conflict_adjudicated"] is False
    assert report["whole_classic_acceptance_passed"] is False
    assert report["new_dated_cases"] == report["new_model_calls"] == 0

    assert report["required_observations"] == 1440
    assert report["whole_classic_acceptance_passed"] is False


@pytest.mark.parametrize(
    "identifier,field",
    [("yang-48", "wenchang_palace"), ("yin-13", "shiji"), ("yang-25", "shiji")],
)
def test_recognizing_a_name_does_not_supply_a_missing_role(report, identifier, field):
    row = next(r for r in report["source_rows"] if r["id"] == identifier)
    item = next(c for c in row["comparisons"] if c["field"] == field)
    assert item["source_resolution"]["value"] is None
    assert item["comparison_status"] == "unknown"


def test_wrong_actual_cannot_change_the_source_value_or_original_result(report):
    baseline = copy.deepcopy(report["original_v46_layer"])
    row = next(r for r in baseline["source_rows"] if r["id"] == "yang-2")
    value = next(
        c
        for c in row["comparisons"]
        if c["original_comparison"]["actual_field"] == "wenchang_palace"
    )
    value["actual_value"] = "子"
    changed = compare(baseline, verify())
    row = next(r for r in changed["source_rows"] if r["id"] == "yang-2")
    item = next(c for c in row["comparisons"] if c["field"] == "wenchang_palace")
    assert item["source_resolution"]["value"] == "酉"
    assert item["actual_value"] == "子"
    assert item["comparison_status"] == "different"
    assert changed["original_v46_layer"] == report["original_v46_layer"]


def test_picking_the_other_book_to_fit_current_positions_is_rejected(report):
    profile = verify()
    next(r for r in profile["entries"] if r["name"] == "陰德")["position"] = "乾"
    with pytest.raises(ValueError, match="不能替换"):
        compare(report["original_v46_layer"], profile)


@pytest.mark.parametrize("mode", ["drop", "duplicate"])
def test_missing_or_duplicate_target_cannot_inflate_conformance(report, mode):
    current = copy.deepcopy(report["original_v46_layer"])
    rows = current["source_rows"]
    if mode == "drop":
        rows[0]["comparisons"].pop()
    else:
        rows[0] = copy.deepcopy(rows[1])
    with pytest.raises(ValueError, match="1440"):
        compare(current, verify())


@pytest.mark.parametrize("name", ["name-profile.json", "native-page145.png"])
def test_changed_source_is_rejected(tmp_path, name):
    corpus = tmp_path / "corpus"
    shutil.copytree(CORPUS, corpus)
    (corpus / name).write_bytes(b"changed")
    with pytest.raises(ValueError, match="指纹"):
        verify(corpus)

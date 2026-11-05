"""Complete independent source scope, contradictory facts, and unknown names."""

import shutil

import pytest

from scripts.audit_taiyi_wujing_cycles import (
    CORPUS,
    FIELDS,
    audit,
    source_data,
    source_value,
)


def test_complete_cycles_retain_every_target_including_differences_and_unknowns():
    report = audit()
    assert report["required_rows"] == report["audited_rows"] == 144
    assert report["required_observations"] == 1440
    assert set(report["field_totals"]) == set(FIELDS)
    for counts in report["field_totals"].values():
        assert counts["required"] == 144
        assert counts["matching"] + counts["different"] + counts["unknown"] == 144
    assert len(report["source_rows"]) == 144
    assert all(len(r["comparisons"]) == 10 for r in report["source_rows"])
    assert report["differences"] and report["unknowns"]
    assert report["whole_classic_acceptance_passed"] is False
    assert report["whole_annotation_conformance_assessed"] is False
    assert report["prior_jinjing_disagreements_resolved_by_switching_sources"] is False
    assert report["copied_source_blocks_counted_as_calculated_hits"] == 0
    assert report["new_dated_cases"] == 0


def test_scan_confirmed_yin_thirteen_count_and_general_are_not_made_consistent():
    report = audit()
    row = next(r for r in report["source_rows"] if r["id"] == "yin-13")
    fields = {r["source_observation"]["field"]: r for r in row["comparisons"]}
    assert fields["main_count"]["source_observation"]["value"] == 12
    general = fields["main_general"]
    assert general["source_observation"]["value"] == 6
    assert general["actual_value"] == 2
    assert general["comparison_status"] == "different"
    assert "主大將六宫" in row["source_block"]
    assert report["source_outcomes_applied"] is False


def test_eight_gates_delimiter_and_explicit_center_do_not_generate_a_general_from_count():
    data = source_data()
    row = next(r for r in data["rows"] if r["id"] == "yang-4")
    facts = {o["field"]: o for o in row["observations"]}
    count = facts["main_count"]
    assert count["value"] == 25
    assert count["source_occurrences"][0]["quote"] == "主算二十五八"
    assert count["source_occurrences"][0]["segmentation"]
    for field in ("main_general", "main_vice_general"):
        assert facts[field]["status"] == "literal_center"
        assert facts[field]["value"] == 5
        assert "不出中宮" in facts[field]["source_occurrences"][0]["quote"]


@pytest.mark.parametrize("name", ["五德", "大族", "大陽", "太陰", "大昊", "太昊"])
def test_unadjudicated_names_are_not_corrected_to_fit_runtime_positions(name):
    reference = source_data()["name_reference"]
    value = source_value(
        {"field": "shiji_name", "value": name, "status": "literal_text"}, reference
    )
    assert value["status"] == "not_resolved" and value["value"] is None


def test_name_position_comparison_does_not_accept_the_attached_condition():
    reference = source_data()["name_reference"]
    value = source_value(
        {"field": "wenchang_name", "value": "陰德主辰迫", "status": "literal_text"},
        reference,
    )
    assert value["value"] == "乾"
    assert value["unadjudicated_attached_text"] == "主辰迫"
    assert value["whole_annotation_conformance_assessed"] is False


def test_scan_confirmed_adjacent_repetition_stays_a_diagnostic_without_correction():
    report = audit()
    assert report["adjacent_source_pairs_considered"] == 142
    row = next(
        r
        for r in report["adjacent_literal_repetitions"]
        if r["source_ids"] == ["yin-55", "yin-56"]
    )
    assert row["different_wenchang_readings"] == ["吕申", "高叢"]
    assert row["identical_literal_fields"] == {
        "main_count": 16,
        "guest_count": 18,
        "main_general": 6,
        "main_vice_general": 8,
        "guest_general": 8,
        "guest_vice_general": 4,
        "shiji_name": "和德",
    }
    assert not row["is_error_adjudicated"]
    assert not row["source_or_runtime_values_replaced"]


@pytest.mark.parametrize(
    "name",
    [
        "manifest.json",
        "wujing-literal-cycles.json",
        "wujing-siku-yin.html",
        "wujing-cadal06047942.djvu",
        "wujing-cadal-page90.jpg",
        "name-reference.json",
        "name-reference-manifest.json",
        "facsimile-supplement.json",
        "cadal-native-page133.png",
        "facsimile-manifest.json",
    ],
)
def test_source_text_images_extraction_and_name_reference_remain_frozen(tmp_path, name):
    copied = tmp_path / "corpus"
    shutil.copytree(CORPUS, copied)
    (copied / name).write_bytes(b"changed")
    with pytest.raises(ValueError, match="指纹"):
        source_data(copied)

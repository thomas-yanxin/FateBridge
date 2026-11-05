"""Month-name evidence cannot reindex actual dates or repair another source."""

from copy import deepcopy

import pytest

from fatebridge.core import sukuyo_month_names as names
from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_commentarial_clock import commentarial_boundary_reference
from scripts.sukuyo.check_sukuyo_month_names import verify_primary


def reference():
    return commentarial_boundary_reference()["standalone_xuanying_reference"][
        "named_rizang_comparison"
    ]["month_name_reference"]


def test_twelve_explicit_named_months_keep_their_tang_labels():
    rows = reference()["Tang_named_month_annotations"]
    assert len(rows) == 12
    assert {r["named_month_literal"]: r["Tang_month_label"] for r in rows} == {
        "角月": 2,
        "氐月": 3,
        "心月": 4,
        "箕月": 5,
        "女月": 6,
        "室月": 7,
        "婁月": 8,
        "昴月": 9,
        "觜月": 10,
        "鬼月": 11,
        "星月": 12,
        "翼月": 1,
    }
    assert reference()["upper_annotation_and_lower_all12_same_named_anchors"]


def test_conditional_white_ninth_does_not_identify_xuanying_fortnight_or_exemplar():
    value = reference()
    row = value["conditional_white_ninth_comparison"]
    assert (row["textual_month"], row["fortnight"], row["day"]) == (1, "white", 9)
    assert row["hypothetical_T1299_month_label"] == 2
    assert row["mansion_literal"] == row["T1299_27_literal"] == "鬼"
    assert not value["interpretation_scope"]["Xuanying_fortnight_identified"]
    assert not value["interpretation_scope"]["actual_cited_exemplar_identified"]


def test_all330_rows_and_eighty_differences_remain_without_compound_emendation():
    value = reference()
    rows = value["all330_fixed_projection_rows"]
    assert len(rows) == 330
    assert sum(r["literal_equal"] for r in rows) == 250
    assert sum(not r["literal_equal"] for r in rows) == 80
    assert value["single_bull_counterexample"]["mansion_literal"] == "牛"
    assert value["single_bull_counterexample"]["T1299_27_literal"] == "女"
    assert [
        r["mansion_literal"]
        for r in rows
        if len(r["mansion_literal"]) > 1 and r["mansion_literal"] != "七星"
    ] == ["女虛", "牛女", "牛女", "牛女"]


def test_seven_star_literal_and_month8_narrative_do_not_become_repaired_cells():
    value = reference()
    missing = [
        r
        for r in value["rizang_explicit_endpoint_crosswalk"]
        if not r["literal_name_match"]
    ]
    assert len(missing) == 1 and missing[0]["rizang_endpoint_literal"] == "七星"
    assert missing[0]["Tang_month_by_exact_named_star"] is None
    assert not value["literal_name_differences_not_physical_differences"][
        "distinct_physical_mansion_proved"
    ]
    assert value["rizang_month8_narrative_anchor"][
        "narrative_not_full_explicit_fortnight_table"
    ]


def test_twelve_endpoint_offsets_are_diagnostics_not_a_selected_calendar():
    value = reference()
    assert [
        r["cyclic_label_offset"] for r in value["all12_cyclic_endpoint_diagnostics"]
    ] == list(range(12))
    assert all(len(r["rows"]) == 11 for r in value["all12_cyclic_endpoint_diagnostics"])
    assert not value["fixed_projection_rule"][
        "actual_month_year_leap_or_clock_conversion_established"
    ]


def test_changed_rizang_capture_cannot_reuse_month_name_binding():
    direct = commentarial_boundary_reference()["standalone_xuanying_reference"][
        "named_rizang_comparison"
    ]
    direct["source_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="日藏具名版本不一致"):
        names.month_name_reference(direct)


def test_changed_t1299_capture_cannot_reuse_month_name_binding(tmp_path, monkeypatch):
    path = tmp_path / "source.json"
    path.write_text('{"source_sha256":"changed"}')
    monkeypatch.setattr(names, "T1299_SOURCE", path)
    direct = {
        "source_sha256": "64d0dbf21d28e11d76488a2bf7ff0f651883f1f7d5d76392616b97da5d38ce17"
    }
    with pytest.raises(ValueError, match="T1299具名版本不一致"):
        names.month_name_reference(direct)


def test_detached_reference_cannot_repair_later_literal_source():
    value = reference()
    value["single_bull_counterexample"]["mansion_literal"] = "女"
    assert reference()["single_bull_counterexample"]["mansion_literal"] == "牛"


@pytest.mark.parametrize("civil,expected", [("2024-03-17", "井"), ("2024-03-18", "鬼")])
def test_current_host_month_is_not_shifted_again(civil, expected):
    calendar = calendar_mansion(civil, "12:00:00", "+08:00")
    before = deepcopy(calendar)
    evidence = day_evidence(calendar)
    assert calendar == before
    assert evidence["calendar"]["lunar_month"] == 2
    assert evidence["day_mansion"] == expected
    assert "不能因上述月名对应再给宿主月份加一" in evidence["reading_text"]
    assert "250字面相合、80不同" in evidence["reading_text"]


@pytest.mark.parametrize(
    "key", ["T21n1299.xml", "T13n0397.xml", "T2216-month-context.html"]
)
def test_actual_capture_substitution_is_rejected(tmp_path, key):
    path = tmp_path / "capture"
    path.write_bytes(b"substituted")
    with pytest.raises(ValueError, match="实际源文件字节指纹不一致"):
        verify_primary({key: path})


def test_offline_check_does_not_claim_actual_source_reading_or_date_conversion():
    checked = verify_primary()
    assert checked["actual_source_files_rechecked"] == []
    assert not checked["actual_date_conversion_or_cited_exemplar_certified"]

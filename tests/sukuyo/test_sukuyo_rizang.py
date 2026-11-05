"""Keep the named table, unresolved citation and actual calculation distinct."""

from copy import deepcopy

import pytest

from fatebridge.core import sukuyo_rizang as rizang
from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_commentarial_clock import commentarial_boundary_reference
from scripts.sukuyo.check_sukuyo_rizang import verify_primary


def reference():
    return commentarial_boundary_reference()["standalone_xuanying_reference"][
        "named_rizang_comparison"
    ]


@pytest.mark.parametrize(
    "month,half,day,expected",
    [
        (1, "white", 9, "鬼"),
        (2, "white", 7, "鬼"),
        (2, "white", 8, "柳"),
        (2, "white", 9, "星"),
        (2, "black", 9, "女"),
    ],
)
def test_named_edition_cells_keep_month_and_fortnight(month, half, day, expected):
    assert rizang.literal_cell(reference(), month, half, day) == expected


def test_compound_slots_are_not_silently_split_or_selected():
    value = reference()
    assert len(value["literal_slots"]) == 330
    assert rizang.literal_cell(value, 10, "white", 3) == "女虛"
    assert rizang.literal_cell(value, 5, "black", 2) == "牛女"
    assert rizang.literal_cell(value, 6, "white", 12) == "牛女"
    assert rizang.literal_cell(value, 7, "white", 9) == "牛女"
    with pytest.raises(ValueError, match="不能从相邻月"):
        rizang.literal_cell(value, 8, "white", 9)


def test_named_edition_is_not_certified_as_the_actual_cited_exemplar():
    value = reference()
    compared = value["xuanying_citation_comparison"]
    assert not compared["cited_fortnight_explicitly_stated"]
    assert not compared["cited_exemplar_identity_established"]
    assert not compared["citation_and_named_table_reconciled"]
    assert not value["interpretation_scope"]["applied_to_current_calendar"]
    assert not value["interpretation_scope"]["hinoo_half_mapping_established"]


def test_changed_xuanying_capture_cannot_inherit_old_comparison():
    direct = commentarial_boundary_reference()["standalone_xuanying_reference"]
    direct["capture_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="捕获版本不一致"):
        rizang.named_rizang_reference(direct)


def test_detached_source_view_cannot_change_later_output():
    first = reference()
    first["literal_slots"][0]["mansion_literal"] = "鬼"
    assert reference()["literal_slots"][0]["mansion_literal"] == "畢"


def test_table_conflict_does_not_move_the_modern_default_day_or_mansion():
    calendar = calendar_mansion("2024-03-17", "12:00:00", "+08:00")
    old = deepcopy(calendar)
    evidence = day_evidence(calendar)
    assert calendar == old
    assert evidence["day_mansion"] == "井"
    assert evidence["calendar"]["calendar_day_part"] is None
    text = evidence["reading_text"]
    assert "二月白七合鬼、白八合柳、白九合星" in text
    assert "二月黑九合女" in text
    assert "未把正月改成二月" in text
    assert "牛女、女虛复字槽原样保留" in text
    for cell in ("五月黑二牛女", "六月白十二牛女", "七月白九牛女", "十月白三女虛"):
        assert cell in text


def test_checker_rejects_substituted_capture(tmp_path):
    path = tmp_path / "source.xml"
    path.write_bytes(b"substituted")
    with pytest.raises(ValueError, match="字节指纹不一致"):
        verify_primary(path)


def test_offline_check_does_not_claim_to_read_actual_source():
    checked = verify_primary()
    assert checked["literal_slots_checked"] == 330
    assert not checked["actual_source_bytes_rechecked"]
    assert not checked["cited_exemplar_identified"]
    assert not checked["citation_reconciled"]

"""Direct print disagreement and unreadable characters remain separate."""

import pytest

from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_documentary import clock_position_reference
from fatebridge.core.sukuyo_special_days import special_day_evidence
from scripts.check_sukuyo_kyoto_enpo import verify_kyoto_enpo


def direct(name, weekday):
    result = special_day_evidence(
        name, weekday, weekday_basis="modern_utc_plus08_civil_midnight"
    )
    return result, result["direct_printed_comparisons"][1]


def test_sukuyo_enpo_selected_primary_bindings_and_failed_reads_remain_visible():
    report = verify_kyoto_enpo()
    assert report["errors"] == []
    assert report["accepted_mansion_readings"] == 20
    assert len(report["initial_generator_wrong_cells_retained"]) == 3
    assert report["actual_evidence_files_hashed"] == 0


@pytest.mark.parametrize("name,printed_labels", [("心", []), ("女", ["金刚峰"])])
def test_sukuyo_enpo_monday_girl_does_not_replace_taisho_heart(name, printed_labels):
    result, printed = direct(name, 1)
    assert printed["matched_labels"] == printed_labels
    lower = next(r for r in result["comparisons"] if r["witness"] == "lower_taisho")
    assert lower["matched_labels"] == (["金刚峰"] if name == "心" else [])
    assert not printed["applied_to_primary"]


@pytest.mark.parametrize("name", ["亢", "尾", "柳"])
def test_sukuyo_enpo_saturday_unknown_glyph_prevents_complete_label_claim(name):
    result, printed = direct(name, 6)
    assert printed["matched_labels"] == (["罗刹"] if name == "柳" else [])
    assert not printed["labels_complete_for_selected_day"]
    assert printed["disagrees_with_primary"] is None
    assert printed["unresolved_rows"][0]["mansion"] is None
    # The named 1897 print remains separately indexed and retains its tail.
    assert (
        result["direct_printed_comparisons"][0]["witness"]
        == "lower_wakita_1897_selected"
    )


def test_sukuyo_enpo_printed_stomach_does_not_resolve_taisho_unrecognized_mao():
    result, printed = direct("胃", 0)
    assert printed["matched_labels"] == ["罗刹"]
    lower = next(r for r in result["comparisons"] if r["witness"] == "lower_taisho")
    assert lower["unresolved_rows"][0]["literal_mansion"] == "冒"


def test_sukuyo_enpo_block_order_is_not_a_ming_witness_identification_or_clock():
    reference = clock_position_reference()["direct_japanese_print_reference"]
    assert reference["order_agrees_with_taisho_ming_position_operation"]
    assert reference["preceding_context"]["諸國_followed_by_一_visible"]
    assert not reference["identified_as_taisho_ming_witness"]
    assert reference["unresolved_glyphs"][0]["accepted"] is None
    assert reference["accepted_complete_diplomatic_transcription"] is None
    reference["unresolved_glyphs"].clear()
    assert clock_position_reference()["direct_japanese_print_reference"][
        "unresolved_glyphs"
    ]


def test_sukuyo_enpo_known_civil_time_keeps_ancient_clock_and_overlap_unselected():
    result = day_evidence(
        calendar_mansion(
            "1957-09-24",
            "06:30:00",
            calendar_profile="hinoo_t1299_host27",
            calendar_day_part="first_half",
        )
    )
    assert result["day_mansion"] is None
    assert result["calendar"]["candidate_su27s"] == ["角", "轸"]
    assert result["calendar_day"]["clock_evaluation_status"] == "not_computed"
    text = result["reading_text"]
    assert "酉／西未定" in text and "不能据位置相合就认定为大正【明】" in text
    assert "日宿未定，未作为确定标签" in text


def test_sukuyo_enpo_changed_actual_capture_rejected(tmp_path):
    (tmp_path / "kyoto-RB00017017-manifest.json").write_bytes(b"changed")
    with pytest.raises(ValueError, match="evidence bytes changed"):
        verify_kyoto_enpo(tmp_path)

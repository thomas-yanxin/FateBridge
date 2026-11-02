"""Position apparatus must not become new calendar or numeral rules."""

import pytest

from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_calendar_text import calendar_day_evidence
from fatebridge.core.sukuyo_documentary import clock_position_reference
from fatebridge.core.sukuyo_special_days import special_day_evidence
from scripts.check_sukuyo_clock_position import verify_clock_position


def test_sukuyo_clock_position_has_two_reciprocal_notes_for_one_operation():
    result = verify_clock_position()
    assert result["errors"] == [] and result["verified_cjk_counts"] == [248, 93]
    assert (
        result["paired_position_notes"] == 2
        and result["independent_position_operations"] == 1
    )
    reference = clock_position_reference()
    assert reference["adjacent_variant"]["base_literal"] == "一"
    assert reference["adjacent_variant"]["context_before_first_block_base"].endswith(
        "三方諸國一，"
    )
    assert reference["position_only_reconstruction"][
        "apparatus_indicated_block_order"
    ] == ["daybreak_eight_parts_93", "intervening_text", "lower_special_days_248"]
    assert not reference["position_only_reconstruction"]["full_ming_text_reconstructed"]


def test_sukuyo_clock_and_table_share_detached_position_evidence():
    first = calendar_day_evidence(1)["clock_doctrine"]["textual_position_reference"]
    second = special_day_evidence(
        "昴", 2, weekday_basis="modern_utc_plus08_civil_midnight"
    )["textual_position_reference"]
    assert first == second
    first["blocks"][0]["normalized_base_text"] = "changed"
    assert second == clock_position_reference()


@pytest.mark.parametrize(
    "date,primary,ming",
    [("2025-01-07", [], ["金刚峰"]), ("2025-04-22", ["金刚峰"], [])],
)
def test_sukuyo_lower_paragraph_position_does_not_replace_upper_weekday_variant(
    date, primary, ming
):
    day = day_evidence(calendar_mansion(date, "12:00:00"))
    special = day["special_day_evidence"]
    assert special["primary"]["matched_labels"] == primary
    assert (
        next(
            r for r in special["comparisons"] if r["witness"] == "upper_ming_apparatus"
        )["matched_labels"]
        == ming
    )
    assert not special["textual_position_reference"]["applied_to_primary_table"]
    assert day["calendar_day"]["clock_doctrine"]["day_parts"] == 8
    assert day["calendar_day"]["clock_doctrine"]["night_parts"] == 8


def test_sukuyo_position_does_not_fix_unidentified_lower_glyph_or_quoted_print():
    day = day_evidence(calendar_mansion("2025-01-09", "12:00:00"))
    lower = next(
        r
        for r in day["special_day_evidence"]["comparisons"]
        if r["witness"] == "lower_taisho"
    )
    assert lower["unresolved_rows"][0]["literal_mansion"] == "底"
    assert not lower["labels_complete_for_selected_day"]
    assert not day["calendar_day"]["clock_doctrine"]["textual_position_reference"][
        "position_only_reconstruction"
    ]["independent_ming_print_acquired"]


def test_sukuyo_position_does_not_resolve_hinoo_first_half_precedence():
    day = day_evidence(
        calendar_mansion(
            "1957-09-24",
            calendar_profile="hinoo_t1299_host27",
            calendar_day_part="first_half",
        )
    )
    assert day["day_mansion"] is None
    assert day["calendar"]["candidate_su27s"] == ["角", "轸"]
    assert day["calendar_day"]["clock_evaluation_status"] == "not_computed"
    assert not day["special_day_evidence"]["textual_position_reference"][
        "leap_short_month_priority_established"
    ]


@pytest.mark.parametrize("kind", ["xml", "legend"])
def test_sukuyo_changed_position_source_is_rejected(tmp_path, kind):
    path = tmp_path / kind
    path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="bytes changed"):
        verify_clock_position(
            **({"xml_path": path} if kind == "xml" else {"symbol_capture": path})
        )


def test_sukuyo_native_distinguishes_position_interchange_from_other_variant_types():
    text = day_evidence(calendar_mansion("2025-01-07", "12:00:00"))["reading_text"]
    assert "248字特殊日段" in text and "93字分时段" in text
    assert "一组位置异文，不是两个独立见证" in text
    assert "没有记八改六或删除分时段" in text
    assert "电子校记自身没有提供具名明本原页" in text
    assert "台大馆藏《永樂北藏》第一三〇册影印" in text
    assert "这不能认证它就是该校记所指的明本" in text

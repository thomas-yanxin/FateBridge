"""Keep the standalone entry, later gloss, variant and unresolved clock separate."""

from copy import deepcopy

import pytest

from fatebridge.core import sukuyo_xuanying as xuanying
from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_commentarial_clock import commentarial_boundary_reference
from scripts.check_sukuyo_xuanying import verify_primary
from tests.test_sukuyo_transports import (
    test_calendar_and_relations_across_all_real_transports as run_transport_check,
)


def test_standalone_entry_does_not_inherit_branches_from_later_nested_gloss():
    result = commentarial_boundary_reference()
    direct = result["standalone_xuanying_reference"]
    assert direct["selected_juan"] == 8
    assert direct["selected_locator"] == "C056n1163_p0945b10-14"
    assert "二月八日鬼宿合時" in direct["selected_literal"]
    assert "二月九日曙夜分属九日" in direct["selected_literal"]
    assert "寅" not in direct["selected_literal"]
    assert "卯" not in direct["selected_literal"]
    context = direct["T2216_context"]
    assert context["direct_quote_name_variant"]["C1163_literal"] == "佛星"
    assert context["direct_quote_name_variant"]["T2216_literal"] == "弗星"
    assert not context["cited_exemplar_identity_established"]
    assert not context["C1163_juan8_and_T2216_inline_9_17_note_reconciled"]
    assert not direct["applied_to_calendar_or_clock"]
    assert not direct["interpretation_scope"]["all_T2216_nested_originals_acquired"]


def test_facsimile_selected_fragments_do_not_complete_the_unaccepted_glyph():
    result = commentarial_boundary_reference()["standalone_xuanying_reference"]
    physical = result["facsimile_reference"]
    assert physical["pdf_pages"] == 302
    assert physical["selected_pdf_page_one_based"] == 92
    assert physical["visible_added_zhuang_page_label"] == "383"
    assert "夜分屬九日故也" in physical["selected_image_clear_fragments"]
    assert physical["glyph_before_night"]["accepted_unique_glyph"] is None
    assert not physical["same_physical_exemplar_as_C1163_or_T2216_proved"]
    assert not physical["full_text_collation_completed"]


def test_changed_commentary_cannot_inherit_the_old_entry_binding():
    reference = commentarial_boundary_reference()
    reference["sources"][0]["capture_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="注疏来源不一致"):
        xuanying.standalone_reference(reference)


def test_detached_output_cannot_change_later_reference():
    first = commentarial_boundary_reference()
    first["standalone_xuanying_reference"]["selected_literal"] = "寅時換日"
    first["standalone_xuanying_reference"]["facsimile_reference"]["glyph_before_night"][
        "accepted_unique_glyph"
    ] = "曙"
    again = commentarial_boundary_reference()["standalone_xuanying_reference"]
    assert "寅時" not in again["selected_literal"]
    assert (
        again["facsimile_reference"]["glyph_before_night"]["accepted_unique_glyph"]
        is None
    )


def test_complete_reading_keeps_explicit_half_and_both_leap_reconstructions():
    calendar = calendar_mansion(
        "0806-07-23",
        "23:59:00",
        "+09:00",
        calendar_basis="japanese_naoj_historical_utc09",
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part="first_half",
    )
    original = deepcopy(calendar)
    evidence = day_evidence(calendar)
    assert calendar == original
    assert evidence["calendar"]["candidate_su27s"] == ["星", "鬼"]
    assert evidence["day_mansion"] is None
    text = evidence["reading_text"]
    assert evidence["calendar"]["calendar_day_part"] == "first_half"
    assert "未写寅、卯钟界" in text
    assert "C1163作佛星，T2216此处作弗星" in text
    assert "章实等原本仍未取得" in text
    assert "夜字前一字的原图唯一字形未接纳" in text
    assert "所引音义、章实等原本尚未独立取得" not in text


@pytest.mark.parametrize("name", ["C1163", "T2216", "SINICA_PDF"])
def test_checker_rejects_substituted_actual_source_bytes(tmp_path, name):
    path = tmp_path / name
    path.write_bytes(b"different bytes")
    with pytest.raises(ValueError, match="字节指纹不一致"):
        verify_primary({name: path})


def test_offline_checker_does_not_claim_to_have_read_source_bytes():
    result = verify_primary()
    assert result["actual_captures_rechecked"] == []
    assert not result["facsimile_glyph_uniquely_accepted"]
    assert not result["historical_clock_or_hinoo_priority_established"]


def test_modern_default_reports_actual_null_half_and_three_source_identities():
    evidence = day_evidence(calendar_mansion("2024-03-17", "12:00:00", "+08:00"))
    assert evidence["calendar"]["calendar_day_part"] is None
    text = evidence["reading_text"]
    assert "calendar_day_part=null（未声明）" in text
    assert "中華大藏經（中華書局版）數位版" in text
    assert "弘教書院排印之高麗藏本影印" in text
    assert "尚未认证为同一实物，也未证明谱系独立" in text


def test_pair_retains_source_chain_and_unconstrained_matrix():
    from fatebridge.services.divination import calculate_sukuyo_compatibility

    result = calculate_sukuyo_compatibility(
        person1_date="0814-08-23",
        person1_time="00:01:00",
        person1_zone="+09:00",
        person1_calendar_day_part="first_half",
        person2_date="0806-07-23",
        person2_time="23:59:00",
        person2_zone="+09:00",
        person2_calendar_day_part="first_half",
        calendar_basis="japanese_naoj_historical_utc09",
        calendar_profile="hinoo_t1299_host27",
    )
    reference = result["standalone_xuanying_reference"]
    assert (
        reference == commentarial_boundary_reference()["standalone_xuanying_reference"]
    )
    assert not reference["applied_to_calendar_or_clock"]
    assert "未写寅、卯钟界" in result["summary"]
    assert "未移动历日或主宿" in result["summary"]
    assert result["candidate_relation_analysis"]["unconstrained_rows"]


@pytest.mark.parametrize("date", ["2024-03-17", "2024-09-25"])
def test_standalone_source_reference_across_all_real_transports(
    monkeypatch, capsys, date
):
    run_transport_check(
        monkeypatch,
        capsys,
        "suzhan",
        {"date": date, "time": "04:30:00", "zone": "+08:00"},
        [
            "sukuyo.calendar_day.clock_doctrine.commentarial_boundary_reference.standalone_xuanying_reference",
            "sukuyo.calendar",
            "sukuyo.day_mansion",
            "sukuyo.reading_text",
        ],
    )

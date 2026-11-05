"""Keep the selected print glyphs separate from electronic corrections."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core import sukuyo_printed_pages as source
from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from scripts.check_sukuyo_printed_pages import verify_primary

BEFORE = json.loads(
    (
        Path(__file__).parent / "data/sukuyo-printed-before-production-v71.json"
    ).read_bytes()
)


def reference():
    return source.printed_page_reference(
        BEFORE["expected_data"]["parent_witness_data_sha256"]
    )


@pytest.mark.parametrize("row", BEFORE["expected_data"]["root_selected_observations"])
def test_all_nine_before_code_selected_print_observations_retained(row):
    assert row in reference()["root_selected_observations"]


def test_new_page_evidence_is_not_all_printings_or_an_independent_manuscript():
    ref = reference()
    assert ref["raw_tiles_total"] == 330 and ref["initial_raw_tiles_total"] == 288
    assert len(ref["printed_frames"]) == 3
    assert sum(r["all_selected_level_tiles"] for r in ref["printed_frames"]) == 280
    assert not ref["acceptance_scope"]["independent_human_paleography_accepted"]
    assert not ref["acceptance_scope"][
        "calendar_day_boundary_half_or_precedence_changed"
    ]
    assert not any(
        r["maximum_resolution_whole_page_obtained"] for r in ref["printed_frames"]
    )


def test_changed_parent_or_print_bundle_is_rejected(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="版本不一致"):
        source.printed_page_reference("changed")
    changed = tmp_path / "changed.json"
    changed.write_text("{}")
    monkeypatch.setattr(source, "SOURCE", changed)
    with pytest.raises(ValueError, match="来源已改变"):
        reference()


def test_print_observations_are_detached_and_do_not_correct_source_history():
    first = reference()
    expected = deepcopy(first)
    first["root_selected_observations"][0]["root_selected_image_literal"] = "牟"
    assert reference() == expected


def test_native_delivery_preserves_same_calendar_and_explicitly_ages_the_old_flag():
    cal = calendar_mansion(
        "0806-07-23",
        "04:00:00",
        "+09:00",
        calendar_profile="hinoo_t1299_host27",
        calendar_basis="japanese_naoj_historical_utc09",
        calendar_day_part="first_half",
    )
    assert cal["candidate_su27s"] == ["星", "鬼"] and cal["natal_su27"] is None
    text = day_evidence(cal)["reading_text"]
    for term in (
        "根代理选读矣休多",
        "三十星",
        "完整第12层",
        "330块实际读回",
        "旧未核定标志描述v70取得状态",
    ):
        assert term in text


def test_offline_receipt_does_not_claim_actual_private_tiles_read():
    assert verify_primary()["raw_tile_files_actually_read"] == 0


def test_reinspection_retains_first_disagreements_and_metadata_erratum():
    supplement = reference()["followup_native_reference"]
    assert supplement["original_R1_and_A_unchanged"]
    assert (
        supplement["root_reinspection"]["T2465_half_glyph"]["accepted_new_literal"]
        is None
    )
    assert supplement["root_reinspection"]["T2465_half_glyph"][
        "current_uncertain_candidates"
    ] == ["己", "已"]
    assert supplement["metadata_erratum"]["actual_DZI_height"] == 5771
    assert not supplement["metadata_erratum"]["raw_ROI_receipt_rewritten"]
    assert (
        sum(
            r["all_tiles_read_and_hash_verified"]
            for r in supplement["additional_native_ROIs"]
        )
        == 42
    )


def test_printed_hinoo_passage_is_scoped_to_its_actual_profile():
    default = day_evidence(calendar_mansion("2025-03-04"))["reading_text"]
    assert "桧尾T78第30页所选印字" not in default
    assert "半字后己／已" not in default
    assert "宿曜T21第399页所选图段" in default
    hinoo = day_evidence(
        calendar_mansion(
            "0806-07-23",
            calendar_profile="hinoo_t1299_host27",
            calendar_basis="japanese_naoj_historical_utc09",
            calendar_day_part="first_half",
        )
    )["reading_text"]
    assert "桧尾T78第30页所选印字" in hinoo
    assert "半字后己／已" in hinoo

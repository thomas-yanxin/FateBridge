"""Retain every selected apparatus entry and its distinct textual layer."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core import sukuyo_calendar_witnesses as module
from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_fortnights import SOURCE as PARENT_SOURCE
from scripts.check_sukuyo_calendar_witnesses import verify_primary

BEFORE = json.loads(
    (
        Path(__file__).parent
        / "data/sukuyo-calendar-witnesses-before-production-v70.json"
    ).read_bytes()
)


def reference():
    raw = PARENT_SOURCE.read_bytes()
    return module.calendar_witness_reference(
        json.loads(raw), hashlib.sha256(raw).hexdigest()
    )


ROWS = [
    r
    for p in BEFORE["expected_data"]["all_five_selected_paragraphs"]
    for r in p["apparatus_entries"]
]


@pytest.mark.parametrize("row", ROWS)
def test_every_original_app_including_inline_notes_and_corresp_is_retained(row):
    paragraph = next(
        p
        for p in reference()["all_five_selected_paragraphs"]
        if p["paragraph_id"] == row["paragraph_id"]
    )
    assert row in paragraph["apparatus_entries"]


def test_complete_counts_and_body_readings_are_not_unemended_witnesses():
    value = reference()
    assert value["counts"] == {
        "selected_paragraphs": 5,
        "standoff_apparatus_entries": 75,
        "corresp_repeat_entries": 6,
        "inline_note_apparatus_entries": 5,
        "body_differs_from_reported_orig_entries": 6,
    }
    assert len(ROWS) == 75
    assert not value["interpretation_scope"]["CBETA_body_is_unemended_Taisho_main_text"]
    assert not value["interpretation_scope"]["source_priority_established"]
    assert not value["T1644_0196a12_digital_difference"][
        "actual_printed_glyph_adjudicated"
    ]
    assert value["T1644_0196a12_digital_difference"]["actual_SAT_main"] == "牟"
    assert value["T1644_0196a12_digital_difference"]["CBETA_reported_wit_orig"] == "矣"


@pytest.mark.parametrize("change", ["body", "note", "source", "missing", "parent"])
def test_revised_parent_text_notes_sources_and_missing_paragraphs_are_rejected(change):
    raw = PARENT_SOURCE.read_bytes()
    parent = json.loads(raw)
    digest = hashlib.sha256(raw).hexdigest()
    if change == "body":
        parent["selected_paragraphs"][0]["main_literal"] += "改"
    elif change == "note":
        parent["selected_paragraphs"][0]["publisher_note_layers"] = []
    elif change == "source":
        parent["actual_sources"]["T32n1644.xml"]["sha256"] = "changed"
    elif change == "missing":
        parent["selected_paragraphs"].pop()
    else:
        digest = "changed"
    with pytest.raises(ValueError, match="不一致"):
        module.calendar_witness_reference(parent, digest)


def test_altered_apparatus_bundle_is_not_silently_used(tmp_path, monkeypatch):
    source = tmp_path / "changed.json"
    source.write_text("{}")
    monkeypatch.setattr(module, "SOURCE", source)
    with pytest.raises(ValueError, match="来源已改变"):
        reference()


def test_caller_cannot_mutate_the_next_source_reading():
    first = reference()
    unchanged = deepcopy(first)
    first["all_six_body_vs_reported_orig_changes"][0]["reported_orig_literal"] = "改"
    assert reference() == unchanged


def test_native_explanation_delivers_layers_without_resolving_half_or_rule_priority():
    calendar = calendar_mansion(
        "0806-07-23",
        "04:00:00",
        "+09:00",
        calendar_basis="japanese_naoj_historical_utc09",
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part="first_half",
    )
    assert calendar["natal_su27"] is None
    # Bound to the retained source-only month-transition oracle, not a new
    # expectation inferred from the production answer under test.
    assert calendar["candidate_su27s"] == ["星", "鬼"]
    text = day_evidence(calendar)["reading_text"]
    for fragment in (
        "75条后置",
        "5条锚在行内注",
        "6条带corresp",
        "牟／所报【大】矣",
        "休／所报【大】林",
        "不同于该XML所报【大】矣",
    ):
        assert fragment in text
    assert "不能说SAT逐项认证六处" in text
    assert "未取得高丽藏新字节" in text


def test_native_witness_explanation_keeps_prospective_version_binding_and_gates():
    text = "\n".join(module.calendar_witness_lines(reference()))
    assert "结局发生前重新冻结并绑定本版来源、模型和解释" in text
    assert "旧版预测和旧版结局不能直接复用于新版认证" in text
    assert "弃权、失访及置信门槛不变" in text
    assert "真实样本仍为0" in text


def test_offline_check_does_not_claim_reacquired_actual_sources():
    result = verify_primary()
    assert result["apparatus_entries"] == 75
    assert result["actual_source_files_rechecked"] == []
    assert not result["independent_manuscript_or_day_boundary_acceptance"]

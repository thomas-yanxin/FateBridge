"""Native acquisition can close its gate without silently resolving other gates."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import sukuyo_witness_research as witnesses
from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from tests.test_sukuyo_witness_research import critical

ROOT = Path(__file__).resolve().parents[1]
FROZEN = json.loads(
    (ROOT / "tests/data/sukuyo-native-completion-before-code-v93.json").read_bytes()
)["expected_bundle"]


def test_later_completion_preserves_the_same_queue_and_historical_firsts():
    result = critical()
    old = result["image_witness_research"]
    prior = result["image_witness_native_followup"]
    current = result["image_witness_native_completion"]
    digest = current.pop("source_bundle_sha256")
    assert (
        digest == hashlib.sha256(witnesses.COMPLETION_SOURCE.read_bytes()).hexdigest()
    )
    assert current == FROZEN
    assert old["capture_summary"]["original_resolution_acquired"] == 0
    assert prior["capture_summary"]["union_acquired"] == 10
    members = current["unchanged_original17_verified_members"]
    assert len(members) == 17
    assert {(r["catalogue_id"], r["frame"]) for r in members} == {
        (r["catalogue_id"], r["frame"]) for r in prior["unchanged_old17_requirements"]
    }
    assert current["capture_summary"]["union_acquired"] == 17
    assert len(current["additional_timing_members_not_original17"]) == 2
    assert not current["capture_summary"]["additional_pages_in_original17_denominator"]
    assert [key for key, value in current["acceptance"].items() if value] == [
        "original17_image_acquisition"
    ]


def test_working_readings_and_feedback_do_not_rewrite_old_disagreements():
    result = critical()
    current = result["image_witness_native_completion"]
    timing = current["selected_timing"]
    assert timing["qualitative_dawn_to_next_weekday_handover_supported"]
    assert timing["next_day_glyph_working_reading"] == "曉"
    assert timing["canonical_evening_glyph"] is None
    assert timing["root_correction_feedback_exposed"]
    assert timing["root_failed_literals_not_adopted"] == ["即入夜", "入時"]
    assert not timing["source_claim_is_measured_predictive_accuracy"]
    colophon = current["NAGO075_selected_colophon"]
    assert colophon["volume_working_reading"] == "下卷"
    assert colophon["printed_character_count_working_reading"] == "八千四百二十字"
    assert colophon["cost_working_reading"] == "四兩九錢三分"
    assert not colophon["full_text_recounted"]
    assert (
        result["image_witness_research"]["nagoya_composite"]["volume_accepted_glyph"]
        is None
    )
    assert not result["image_witness_native_followup"]["naoj_count"][
        "applies_to_NAGO075"
    ]


@pytest.mark.parametrize("field", ["id", "source_bundle_sha256"])
def test_completion_cannot_bind_to_a_different_followup(field):
    prior = copy.deepcopy(critical()["image_witness_native_followup"])
    prior[field] = "changed"
    with pytest.raises(ValueError, match="此前后续参考不一致"):
        witnesses.native_completion_reference(prior)


def test_changed_facts_or_acceptance_are_rejected_before_delivery(
    tmp_path, monkeypatch
):
    altered = copy.deepcopy(FROZEN)
    altered["acceptance"]["leap_short_overlap_priority"] = True
    changed = tmp_path / "altered-completion.json"
    changed.write_text(json.dumps(altered, ensure_ascii=False))
    prior = critical()["image_witness_native_followup"]
    monkeypatch.setattr(witnesses, "COMPLETION_SOURCE", changed)
    with pytest.raises(ValueError, match="事实或接受状态改变"):
        witnesses.native_completion_reference(prior)


@pytest.mark.parametrize(
    "date,candidates,second",
    [("1903-06-25", ["鬼", "参"], "参"), ("1957-09-24", ["角", "轸"], "角")],
)
def test_new_dawn_evidence_keeps_overlap_uncertainty_and_known_second_half(
    date, candidates, second
):
    for part in (None, "first_half", "second_half"):
        result = calendar_mansion(
            date, calendar_profile="hinoo_t1299_host27", calendar_day_part=part
        )
        assert result["natal_su27"] == (second if part == "second_half" else None)
        assert result["candidate_su27s"] == (
            [] if part == "second_half" else candidates
        )
        assert result["status"] == ("computed" if part == "second_half" else "partial")
        text = day_evidence(result, "室", "travel")["reading_text"]
        assert "0／17" in text and "10／17" in text and "17／17" in text
        assert "原尺寸采集门通过" in text and "全本校勘门仍未通过" in text
        assert "明日曉時即次後曜當直" in text
        assert "现行计算未改用平明日界" in text
        assert "不是实测准确率" in text

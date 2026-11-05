"""Later native readings preserve the old failed capture and conditional rules."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_witness_research import (
    NATIVE_SOURCE,
    native_followup_reference,
)
from tests.sukuyo.test_sukuyo_witness_research import EXPECTED as ORIGINAL
from tests.sukuyo.test_sukuyo_witness_research import critical

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = json.loads(
    (ROOT / "tests/data/sukuyo-native-followup-before-code-v92.json").read_bytes()
)


def test_new_reference_matches_precode_observations_and_keeps_old_record_exact():
    result = critical()
    previous = result["image_witness_research"]
    assert {
        k: v for k, v in previous.items() if k != "source_bundle_sha256"
    } == ORIGINAL
    later = result["image_witness_native_followup"]
    assert (
        later.pop("source_bundle_sha256")
        == hashlib.sha256(NATIVE_SOURCE.read_bytes()).hexdigest()
    )
    assert later == REFERENCE["expected_bundle"]
    assert previous["capture_summary"]["original_resolution_acquired"] == 0
    assert later["capture_summary"]["union_acquired"] == 10
    assert len(later["unchanged_old17_requirements"]) == 17
    assert len(later["capture_summary"]["missing"]) == 7
    assert not any(later["acceptance"].values())


def test_mistaken_correction_and_disagreements_are_not_silently_overwritten():
    later = critical()["image_witness_native_followup"]
    count = later["naoj_count"]
    assert count["historical_root_first"] == "八千四百二十字"
    assert count["historical_root_correction"] == "八千四百一十字"
    assert count["selected_legacy_working_reading"] == "八千四百二十字"
    assert count["historical_correction_itself_misread"]
    assert not count["applies_to_NAGO075"]
    assert not count["same_physical_copy_accepted"]
    assert not count["independent_lineage_accepted"]
    shinpukuji = later["shinpukuji"]
    assert len(shinpukuji["half_phrase_role_firsts"]) == 3
    assert shinpukuji["half_phrase_canonical_glyph"] is None
    assert not shinpukuji["complete_selected_transcription_accepted"]
    assert shinpukuji["modern_day_boundary"] is None
    assert shinpukuji["modern_half_clock"] is None
    assert not shinpukuji["leap_short_overlap_priority_established"]


@pytest.mark.parametrize("field", ["id", "source_bundle_sha256"])
def test_later_reference_cannot_attach_to_another_old_source(field):
    altered = copy.deepcopy(critical()["image_witness_research"])
    altered[field] = "changed"
    with pytest.raises(ValueError, match="此前冻结参考不一致"):
        native_followup_reference(altered)


@pytest.mark.parametrize(
    "date,first_candidates,second_mansion",
    [("1903-06-25", ["鬼", "参"], "参"), ("1957-09-24", ["角", "轸"], "角")],
)
def test_new_images_do_not_resolve_overlap_but_do_not_erase_a_known_half(
    date, first_candidates, second_mansion
):
    for part in (None, "first_half", "second_half"):
        result = calendar_mansion(
            date, calendar_profile="hinoo_t1299_host27", calendar_day_part=part
        )
        if part == "second_half":
            assert result["status"] == "computed"
            assert result["natal_su27"] == second_mansion
            assert result["candidate_su27s"] == []
        else:
            assert result["status"] == "partial"
            assert result["natal_su27"] is None
            assert result["candidate_su27s"] == first_candidates
        text = day_evidence(result, "室", "travel")["reading_text"]
        assert "0／17" in text and "10／17" in text and "仍缺7张" in text
        assert "八千四百二十字" in text and "错改八千四百一十字" in text
        assert "本次更正此前更正" in text
        assert "未重新统计全文" in text


def test_default_profile_does_not_inherit_the_hinoo_image_followup():
    result = calendar_mansion("1903-06-25")
    assert result["profile_calculation"]["hinoo_source"] is None
    assert "后续冻结采集" not in day_evidence(result, "室", "travel")["reading_text"]

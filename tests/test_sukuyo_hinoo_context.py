"""Later working readings retain exact location, attribution and uncertainty."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import sukuyo_hinoo_context as context
from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_profiles import source_bundle
from tests.test_sukuyo_witness_research import critical

REFERENCE = json.loads(
    (
        Path(__file__).parent / "fixtures/sukuyo-hinoo-context-before-code-v95.json"
    ).read_bytes()
)["expected_bundle"]


def test_complete_context_matches_reference_frozen_before_production():
    actual = critical()["image_witness_context_followup"]
    assert (
        actual.pop("source_bundle_sha256")
        == hashlib.sha256(context.SOURCE.read_bytes()).hexdigest()
    )
    assert actual == REFERENCE
    assert len(actual["attributed_calendar_columns"]) == 24
    rows = {row["id"]: row for row in actual["qualified_comparisons"]}
    earlier = rows["antecedent_month_34_column6"]
    ending = rows["intercalary_month_34_column8"]
    assert earlier["generator_first_working_reading"] == "其十三月"
    assert earlier["reviewer_first_working_reading"] == "其十二月"
    assert ending["generator_first_working_reading"] == "閏十二月"
    assert ending["reviewer_first_working_reading"] == "閏十三月"
    assert ending["root_first_working_reading"] == "閏十二月"
    assert ending["root_after_feedback_working_reading"] == "閏十三月"
    pair = rows["regular_and_intercalary_35_column1"]
    assert pair["canonical_manuscript_reading"] is None
    assert pair["SAT_bound_text"] == "正十二月／傍十二月"
    assert pair["root_after_feedback_working_reading"] == "正十二月／傍十三月"
    assert not pair["ordinary_thirteenth_month_established"]
    assert rows["half_upper_35_column4"]["reviewer_candidates"] == ["已", "己", "也"]
    assert rows["half_lower_35_column5"]["reviewer_candidates"] == ["己", "已"]
    assert not rows["half_lower_35_column5"]["same_glyph_as_upper_established"]
    scope = actual["scope"]
    assert scope["new_v94_frames"] == [33, 36]
    assert not scope["new_frames_in_original17_denominator"]
    assert scope["daybreak_clock"] is None
    assert scope["hinoo_half_clock"] is None
    assert scope["leap_short_month_execution_priority"] is None
    assert not scope["calendar_policy_changed"]


@pytest.mark.parametrize("key", ["id", "source_bundle_sha256"])
def test_later_context_cannot_inherit_another_acquisition_record(key):
    previous = copy.deepcopy(critical()["image_witness_native_completion"])
    previous[key] = "different preceding record"
    taisho = source_bundle()["hinoo_addendum"]["downloaded_primary_edition"]
    with pytest.raises(ValueError, match="此前原尺寸记录"):
        context.context_reference(previous, taisho)


@pytest.mark.parametrize(
    "key",
    [
        "publisher_html_response_sha256",
        "downloaded_calendar_windows",
        "calendar_apparatus",
    ],
)
def test_manuscript_context_does_not_silently_follow_changed_SAT(key):
    previous = critical()["image_witness_native_completion"]
    taisho = copy.deepcopy(
        source_bundle()["hinoo_addendum"]["downloaded_primary_edition"]
    )
    taisho[key] = "different text or apparatus"
    with pytest.raises(ValueError, match="大正原文或校记"):
        context.context_reference(previous, taisho)


@pytest.mark.parametrize(
    "change", ["normalize_month", "merge_half_glyphs", "promote_feedback", "clock"]
)
def test_unreviewed_normalization_or_acceptance_changes_are_rejected(
    tmp_path, monkeypatch, change
):
    data = copy.deepcopy(REFERENCE)
    rows = {row["id"]: row for row in data["qualified_comparisons"]}
    if change == "normalize_month":
        rows["regular_and_intercalary_35_column1"][
            "SAT_bound_text"
        ] = "正十二月／傍十三月"
    elif change == "merge_half_glyphs":
        rows["half_lower_35_column5"]["same_glyph_as_upper_established"] = True
    elif change == "promote_feedback":
        data["scope"]["strict_blind_reading"] = True
    else:
        data["scope"]["hinoo_half_clock"] = "12:00"
    changed = tmp_path / "changed-context.json"
    changed.write_text(json.dumps(data, ensure_ascii=False))
    monkeypatch.setattr(context, "SOURCE", changed)
    previous = {
        "id": REFERENCE["previous_completion_id"],
        "source_bundle_sha256": REFERENCE["previous_completion_bundle_sha256"],
    }
    taisho = source_bundle()["hinoo_addendum"]["downloaded_primary_edition"]
    with pytest.raises(ValueError, match="读录阶段或未定范围"):
        context.context_reference(previous, taisho)


def test_native_text_delivers_differences_without_changing_known_results():
    calendar = calendar_mansion(
        "1957-09-24",
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part="second_half",
    )
    assert (
        calendar["status"],
        calendar["natal_su27"],
        calendar["candidate_su27s"],
    ) == ("computed", "角", [])
    text = day_evidence(calendar, "室", "travel")["reading_text"]
    for phrase in [
        "正十二月／傍十三月",
        "SAT绑定文字正十二月／傍十二月",
        "第6栏末其月数字",
        "左末栏另处",
        "反馈后更正不是独立首读",
        "未建立普通第十三月",
        "035第4栏",
        "第5栏",
        "没有先认定两处同字",
        "选区完整",
        "初一当日宿保留",
    ]:
        assert phrase in text
    assert (
        "image_witness_context_followup"
        in calendar["profile_calculation"]["hinoo_source"][
            "critical_calendar_reference"
        ]
    )


def test_default_profile_does_not_claim_manuscript_context():
    calendar = calendar_mansion("1957-09-24")
    assert calendar["profile_calculation"]["hinoo_source"] is None
    assert (
        "正十二月／傍十三月"
        not in day_evidence(calendar, "室", "travel")["reading_text"]
    )

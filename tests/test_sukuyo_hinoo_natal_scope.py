"""Source attribution must not promote a scholarly natal inference to a rule."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import sukuyo_hinoo_natal_scope as natal
from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_profiles import source_bundle
from tests.test_sukuyo_witness_research import critical

REFERENCE = json.loads(
    (
        Path(__file__).parent / "data/sukuyo-hinoo-natal-scope-before-code-v95.json"
    ).read_bytes()
)["expected_bundle"]


def test_official_scholarship_and_applicability_match_precode_reference():
    result = critical()["natal_half_application"]
    assert (
        result.pop("source_bundle_sha256")
        == hashlib.sha256(natal.SOURCE.read_bytes()).hexdigest()
    )
    assert result == REFERENCE
    scholar = result["scholarship"]
    assert (
        scholar["year"],
        scholar["printed_page"],
        scholar["chapter_pdf_page_one_based"],
    ) == (2017, 118, 51)
    application = result["application"]
    assert not application[
        "selected_T2465_clause_explicitly_assigns_natal_mansion_by_birth_half"
    ]
    assert application["daily_missing_day_assignment_still_interpretable"]
    assert not application["computed_status_proves_ancient_natal_applicability"]
    assert application["natal_use_status"] == "declared_research_profile_inference"
    assert not application["calendar_policy_or_values_changed"]


def test_later_inference_requires_the_actual_bound_meaning_reference():
    taisho = source_bundle()["hinoo_addendum"]["downloaded_primary_edition"]
    meanings = copy.deepcopy(critical()["calendar_clause_meanings"])
    meanings["source_bundle_sha256"] = "changed meaning"
    with pytest.raises(ValueError, match="当前句义参考"):
        natal.natal_scope_reference(meanings, taisho)


@pytest.mark.parametrize(
    "key",
    [
        "publisher_html_response_sha256",
        "downloaded_calendar_windows",
        "calendar_apparatus",
    ],
)
def test_natal_inference_does_not_inherit_another_primary_source(key):
    taisho = copy.deepcopy(
        source_bundle()["hinoo_addendum"]["downloaded_primary_edition"]
    )
    meanings = critical()["calendar_clause_meanings"]
    taisho[key] = "changed source or note"
    with pytest.raises(ValueError, match="大正原文或校记"):
        natal.natal_scope_reference(meanings, taisho)


@pytest.mark.parametrize(
    "change", ["promote_inference", "promote_computed", "no_daily_meaning", "clock"]
)
def test_reviewed_scope_cannot_silently_promote_or_erase_meaning(
    tmp_path, monkeypatch, change
):
    data = copy.deepcopy(REFERENCE)
    application = data["application"]
    key, value = {
        "promote_inference": (
            "selected_T2465_clause_explicitly_assigns_natal_mansion_by_birth_half",
            True,
        ),
        "promote_computed": (
            "computed_status_proves_ancient_natal_applicability",
            True,
        ),
        "no_daily_meaning": ("daily_missing_day_assignment_still_interpretable", False),
        "clock": ("modern_half_clock", "12:00"),
    }[change]
    application[key] = value
    file = tmp_path / "changed-natal-scope.json"
    file.write_text(json.dumps(data, ensure_ascii=False))
    meanings = critical()["calendar_clause_meanings"]
    taisho = source_bundle()["hinoo_addendum"]["downloaded_primary_edition"]
    monkeypatch.setattr(natal, "SOURCE", file)
    with pytest.raises(ValueError, match="本命适用推论"):
        natal.natal_scope_reference(meanings, taisho)


@pytest.mark.parametrize(
    "date,part,status,mansion,candidates",
    [
        ("1903-06-25", None, "partial", None, ["鬼", "参"]),
        ("1957-09-24", "second_half", "computed", "角", []),
    ],
)
def test_applicability_notice_preserves_known_and_conditional_results(
    date, part, status, mansion, candidates
):
    calendar = calendar_mansion(
        date, calendar_profile="hinoo_t1299_host27", calendar_day_part=part
    )
    assert (
        calendar["status"],
        calendar["natal_su27"],
        calendar["candidate_su27s"],
    ) == (status, mansion, candidates)
    text = day_evidence(calendar, "室", "travel")["reading_text"]
    assert "2017年莱顿大学论文第118页" in text
    assert "没有直接明说按出生前／后半判本命" in text
    assert "不抹去日分宿条文本身可解释的含义" in text
    assert "computed说明档案内计算确定" in text


def test_default_profile_does_not_inherit_hinoo_natal_inference():
    calendar = calendar_mansion("1957-09-24")
    assert calendar["profile_calculation"]["hinoo_source"] is None
    assert (
        "2017年莱顿大学论文"
        not in day_evidence(calendar, "室", "travel")["reading_text"]
    )

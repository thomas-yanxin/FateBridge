"""Contextual month meanings must stay bound to literal source and apparatus."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import sukuyo_hinoo_meanings as meanings
from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_profiles import source_bundle
from tests.sukuyo.test_sukuyo_witness_research import critical

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = json.loads(
    (ROOT / "tests/data/sukuyo-hinoo-meanings-before-code-v94.json").read_bytes()
)["expected_bundle"]


def test_meanings_match_precode_reference_and_distinguish_both_month_contexts():
    result = critical()["calendar_clause_meanings"]
    assert (
        result.pop("source_bundle_sha256")
        == hashlib.sha256(meanings.SOURCE.read_bytes()).hexdigest()
    )
    assert result == REFERENCE
    assert result["relative_month"]["example_lunar_month"] == 12
    assert result["relative_month"]["not_a_universal_first_lunar_month"]
    example = result["short_month_example"]
    assert (
        example["example_short_lunar_month"],
        example["example_following_lunar_month"],
    ) == (1, 2)
    assert example["next_first_day_ordinary_assignment_preserved"]
    halves = result["textual_halves"]
    assert halves["literal_fragments"] == ["半已上者", "半已下者"]
    assert halves["main_text_and_apparatus_not_merged"]
    assert halves["scholarly_interpretation"]["printed_page"] == 9
    assert halves["modern_half_clock"] is None
    assert halves["daybreak_clock"] is None
    assert not result["interaction"]["source_rule_priority_established"]
    assert not result["interaction"][
        "two_modern_reconstructions_are_two_explicit_source_algorithms"
    ]


@pytest.mark.parametrize(
    "key",
    [
        "publisher_html_response_sha256",
        "downloaded_calendar_windows",
        "calendar_apparatus",
    ],
)
def test_meanings_cannot_inherit_a_different_primary_text_or_apparatus(key):
    primary = copy.deepcopy(
        source_bundle()["hinoo_addendum"]["downloaded_primary_edition"]
    )
    primary[key] = "different text or note"
    with pytest.raises(ValueError, match="原文或校记不一致"):
        meanings.calendar_clause_meanings(primary)


def test_policy_or_meaning_changes_fail_closed(tmp_path, monkeypatch):
    data = copy.deepcopy(REFERENCE)
    data["textual_halves"]["modern_half_clock"] = "12:00"
    file = tmp_path / "changed-meanings.json"
    file.write_text(json.dumps(data, ensure_ascii=False))
    monkeypatch.setattr(meanings, "SOURCE", file)
    primary = source_bundle()["hinoo_addendum"]["downloaded_primary_edition"]
    with pytest.raises(ValueError, match="句义、出处或解释范围改变"):
        meanings.calendar_clause_meanings(primary)


@pytest.mark.parametrize(
    "date,part,status,mansion,candidates",
    [
        ("1903-06-25", "first_half", "partial", None, ["鬼", "参"]),
        ("1957-09-24", "second_half", "computed", "角", []),
    ],
)
def test_clarified_meanings_preserve_conditional_results_and_known_part(
    date, part, status, mansion, candidates
):
    result = calendar_mansion(
        date, calendar_profile="hinoo_t1299_host27", calendar_day_part=part
    )
    assert (result["status"], result["natal_su27"], result["candidate_su27s"]) == (
        status,
        mansion,
        candidates,
    )
    text = day_evidence(result, "室", "travel")["reading_text"]
    assert "其正月指相对于所举闰月的同名非闰月" in text
    assert "假令正月则具体举农历一月小" in text
    assert "初一当日宿也保留" in text
    assert "Kotyk 2022第9页" in text
    assert "不是现代12:00或平明钟时换算" in text
    assert "段落先后不构成已经确定的程序优先级" in text


def test_default_profile_does_not_claim_hinoo_clause_interpretation():
    result = calendar_mansion("1903-06-25")
    assert result["profile_calculation"]["hinoo_source"] is None
    assert "其正月指" not in day_evidence(result, "室", "travel")["reading_text"]

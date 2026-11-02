"""Whole-list prose claims need whole-list evidence and shared calculations."""

import json
from copy import deepcopy

import pytest

from fatebridge.core import sukuyo_general_days
from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_calendar_text import calendar_day_evidence
from scripts.check_sukuyo_general_days import verify_general_days


def test_prose_enumerations_check_all_sixty_classifications_and_paragraphs():
    report = verify_general_days()
    assert report["errors"] == []
    assert report["day_classifications_checked"] == 60
    assert report["selected_paragraphs_checked"] == 6


def test_whole_comparison_retains_both_sources_and_the_direction_of_differences():
    for day in (1, 9, 10, 16, 24, 25, 30):
        result = calendar_day_evidence(day)
        comparison = result["japanese_selected_reference"]
        reference = comparison["primary_general_day_reference"]
        assert [row["witness"] for row in reference["witnesses"]] == [
            "upper_prose",
            "lower_prose",
        ]
        for full, current, difference in zip(
            reference["witnesses"],
            comparison["primary_general_day_comparison"],
            comparison["full_favorable_membership_comparison"],
            strict=True,
        ):
            assert len(full["all_thirty_classifications"]) == 30
            assert (
                full["all_thirty_classifications"][day - 1]["assessment"]
                == current["primary_assessment"]
            )
            assert difference["primary_only_days"] == [10, 16, 25]
            assert difference["body_only_days"] == [9, 24]
            assert difference["symmetric_difference_days"] == [9, 10, 16, 24, 25]
            assert not difference["applied_to_primary_or_activities"]


def test_native_whole_list_comparison_follows_each_returned_witness(
    tmp_path, monkeypatch
):
    # Change only the upper source in a temporary file. A static five-day
    # sentence would now contradict its own current classification and list.
    data = json.loads(sukuyo_general_days.SOURCE.read_text())
    data["witnesses"][0]["favorable_lunar_days"].remove(10)
    altered = tmp_path / "altered.json"
    altered.write_text(json.dumps(data, ensure_ascii=False))
    monkeypatch.setattr(sukuyo_general_days, "SOURCE", altered)
    result = day_evidence(calendar_mansion("2024-06-15", "06:30:00"))
    text = result["reading_text"]
    assert "上卷散文一般吉日名单的差别为9、16、24、25日" in text
    assert "下卷散文一般吉日名单的差别为9、10、16、24、25日" in text
    assert result["calendar_day"]["classifications"][0]["assessment"] == "unlisted"
    assert verify_general_days()["errors"] == [
        ["upper_prose", "favorable_list"],
        ["upper_prose", 10, "classification"],
    ]


def test_general_day_reference_is_detached_and_invalid_days_are_rejected():
    first = sukuyo_general_days.general_day_evidence(10)
    original = deepcopy(first)
    first["reference"]["witnesses"][0]["favorable_lunar_days"].clear()
    first["reference"]["witnesses"][0]["all_thirty_classifications"][9][
        "assessment"
    ] = "unlisted"
    assert sukuyo_general_days.general_day_evidence(10) == original
    for day in (0, 31, True, 1.0, "1"):
        with pytest.raises(ValueError):
            sukuyo_general_days.general_day_evidence(day)


def test_primary_checker_rejects_changed_full_source(tmp_path):
    path = tmp_path / "changed.xml"
    path.write_text("changed")
    with pytest.raises(ValueError, match="full source bytes changed"):
        verify_general_days(path)

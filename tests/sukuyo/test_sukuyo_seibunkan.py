"""Primary-image reference, source binding, and unresolved calculations."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import sukuyo_seibunkan as later
from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_profiles import source_bundle
from tests.sukuyo.test_sukuyo_witness_research import critical

REFERENCE = json.loads(
    (
        Path(__file__).parents[1] / "data/sukuyo-seibunkan-before-code-v97.json"
    ).read_bytes()
)


def test_selected_print_matches_actual_reference_frozen_before_production():
    actual = critical()["later_seibunkan_comparison"]
    assert (
        actual.pop("source_bundle_sha256")
        == hashlib.sha256(later.SOURCE.read_bytes()).hexdigest()
    )
    assert actual == REFERENCE["expected_bundle"]
    assert later.seibunkan_lines(actual) == REFERENCE["expected_native_lines"]
    assert actual["natal_example"]["literal_result_mansion"] == "氏"
    assert actual["natal_example"]["modern_mansion_label_for_comparison"] == "氐"
    assert actual["weekday"]["middle_canonical_reading"] is None
    assert actual["leap_month"]["canonical_tail_reading"] is None
    assert not actual["table_layers"][
        "upper_table_same_as_criticized_figure_established"
    ]
    assert not actual["imprint_colophon_date_personally_verified"]


@pytest.mark.parametrize("change", ["literal_glyph", "calendar_priority"])
def test_unreviewed_glyph_normalization_or_rule_promotion_stops(
    tmp_path, monkeypatch, change
):
    data = copy.deepcopy(REFERENCE["expected_bundle"])
    if change == "literal_glyph":
        data["natal_example"]["literal_result_mansion"] = "氐"
    else:
        data["scope"]["leap_short_month_execution_priority"] = "repeat_first"
    changed = tmp_path / "changed-source.json"
    changed.write_text(json.dumps(data, ensure_ascii=False))
    old = critical()["calendar_clause_meanings"]
    taisho = source_bundle()["hinoo_addendum"]["downloaded_primary_edition"]
    monkeypatch.setattr(later, "SOURCE", changed)
    with pytest.raises(ValueError, match="原字、归属或未定"):
        later.seibunkan_reference(old, taisho)


@pytest.mark.parametrize("change", ["meanings", "taisho"])
def test_new_source_cannot_inherit_another_comparison_context(change):
    meanings = copy.deepcopy(critical()["calendar_clause_meanings"])
    taisho = copy.deepcopy(
        source_bundle()["hinoo_addendum"]["downloaded_primary_edition"]
    )
    if change == "meanings":
        meanings["source_bundle_sha256"] = "different meanings"
    else:
        taisho["downloaded_calendar_windows"] = []
    with pytest.raises(ValueError, match="句义绑定不一致"):
        later.seibunkan_reference(meanings, taisho)


@pytest.mark.parametrize(
    "date,part,expected",
    [
        ("1903-06-25", None, ("partial", None, ["鬼", "参"])),
        ("1903-06-25", "first_half", ("partial", None, ["鬼", "参"])),
        ("1957-09-24", "second_half", ("computed", "角", [])),
    ],
)
def test_positive_source_clause_does_not_resolve_unproven_overlap(date, part, expected):
    calendar = calendar_mansion(
        date, calendar_profile="hinoo_t1299_host27", calendar_day_part=part
    )
    assert (
        calendar["status"],
        calendar["natal_su27"],
        calendar["candidate_su27s"],
    ) == expected
    text = day_evidence(calendar, "室", "travel")["reading_text"]
    assert all(line in text for line in REFERENCE["expected_native_lines"])
    reference = calendar["profile_calculation"]["hinoo_source"][
        "critical_calendar_reference"
    ]["later_seibunkan_comparison"]
    assert reference["scope"]["hinoo_half_clock"] is None
    assert reference["scope"]["leap_short_month_execution_priority"] is None


def test_default_profile_does_not_adopt_later_book_policy():
    calendar = calendar_mansion("1957-09-24")
    assert calendar["profile_calculation"]["hinoo_source"] is None
    assert (
        "具名近代注释对照" not in day_evidence(calendar, "室", "travel")["reading_text"]
    )

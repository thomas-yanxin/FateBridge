"""Known sexagenary birth years support relative years without a century guess."""

import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.canping import liunian_series

ROOT = Path(__file__).parent / "fixtures/canping_relative_years_v1"
REFERENCE = json.loads((ROOT / "reference.json").read_text())
ARGS = REFERENCE["fixed_pillars"]
NUMBER_KEYS = {
    "numShun",
    "numNi",
    "shun",
    "ni",
    "ziRound",
    "verses",
    "dayunBranch",
    "dayunRange",
}


def test_explanatory_source_image_identity_is_fixed_separately_from_the_verse():
    for image in (REFERENCE["image"], REFERENCE["previous_verse_image"]):
        assert (
            hashlib.sha256((ROOT / image["file"]).read_bytes()).hexdigest()
            == image["sha256"]
        )
    assert REFERENCE["source_pdf"]["pdf_page"] == 64


@pytest.mark.parametrize("anchor", [None, 0])
def test_unknown_century_advances_known_ganzhi_without_inventing_calendar_year(anchor):
    series = liunian_series(**ARGS, birth_year=anchor)
    assert len(series["rows"]) == 120
    assert series["birth_pillar_year"] is None
    assert series["year_boundary"] == "relative_ganzhi_year_labels_only"
    assert all(row["year"] is None for row in series["rows"])
    for age, expected in REFERENCE["relative_years"].items():
        row = series["rows"][int(age) - 1]
        assert row["ganzhi"] == expected and row["taisuiBranch"] == expected[1]
    assert all("start_at" not in row and "end_at" not in row for row in series["rows"])


@pytest.mark.parametrize("anchor", [0, 1984])
def test_ages_before_explicit_first_period_have_no_number_text_or_substituted_luck_branch(
    anchor,
):
    rows = liunian_series(**ARGS, birth_year=anchor, end_age=4)["rows"]
    for row in rows[:2]:
        assert row["status"] == "not_started"
        assert not NUMBER_KEYS.intersection(row)
    assert rows[2]["status"] == "active" and rows[2]["dayunRange"] == "3-12"


@pytest.mark.parametrize(
    "expected", REFERENCE["manual_numbers"], ids=lambda row: str(row["age"])
)
def test_unknown_calendar_year_uses_actual_relative_taisui_not_birth_day(expected):
    row = liunian_series(**ARGS, birth_year=0)["rows"][expected["age"] - 1]
    assert (row["ganzhi"], row["taisuiBranch"], row["dayunBranch"]) == (
        expected["ganzhi"],
        expected["taisui"],
        expected["dayun"],
    )
    assert (row["numShun"], row["numNi"]) == (expected["num_shun"], expected["num_ni"])
    assert row["verses"]["selectionShun"]["number"] == expected["num_shun"]
    assert row["verses"]["selectionNi"]["number"] == expected["num_ni"]


def test_anchored_and_relative_rows_have_same_calculation_without_an_epoch_guess():
    relative = liunian_series(**ARGS, birth_year=0)
    anchored = liunian_series(**ARGS, birth_year=1984)
    assert all(
        {k: v for k, v in a.items() if k != "year"}
        == {k: v for k, v in b.items() if k != "year"}
        for a, b in zip(relative["rows"], anchored["rows"])
    )
    assert [row["year"] for row in anchored["rows"]] == list(range(1984, 2104))


def test_requested_late_age_slice_uses_birth_based_cycle_and_actual_luck_slot():
    series = liunian_series(**ARGS, start_age=13, end_age=13)
    assert len(series["rows"]) == 1
    row = series["rows"][0]
    assert row["ganzhi"] == "丙子" and row["dayunRange"] == "13-22"
    assert (row["numShun"], row["numNi"]) == (2409, 3009)


def test_explicit_relative_extension_beyond_default_horizon_remains_supported():
    row = liunian_series(**ARGS, start_age=121, end_age=121)["rows"][0]
    assert row["year"] is None and row["ganzhi"] == "甲子"
    assert row["dayunRange"] == "113-122" and row["dayunBranch"] == "丑"
    assert (row["numShun"], row["numNi"]) == (2207, 3207)


@pytest.mark.parametrize(
    "patch",
    [
        {"start_age": 0},
        {"start_age": 4, "end_age": 3},
        {"end_age": 0},
        {"qiyun_age": -1},
        {"qiyun_age": True},
        {"birth_year": False},
    ],
)
def test_invalid_age_ranges_or_boolean_anchors_do_not_silently_produce_a_schedule(
    patch,
):
    with pytest.raises(ValueError):
        liunian_series(**(ARGS | patch))

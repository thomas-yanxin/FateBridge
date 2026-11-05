"""Facsimile table, independent printed cumulative entries and exact edges."""

import hashlib
import json
from dataclasses import asdict
from fractions import Fraction as F
from pathlib import Path

import pytest

from fatebridge.core import guolao_classical as c
from fatebridge.core import guolao_historical as h

SOURCE_DIR = Path(__file__).parents[1] / "fixtures" / "guolao-purple-facsimile-v1"
SOURCE = json.loads((SOURCE_DIR / "reference.json").read_text())


def test_bundled_facsimiles_match_the_recorded_reviewed_bytes():
    for item in SOURCE["images"]:
        assert hashlib.sha256((SOURCE_DIR / item["path"]).read_bytes()).hexdigest() == (
            item["sha256"]
        )
    alternate = SOURCE["year_variants"]["alternate_scan"]
    assert (
        hashlib.sha256(
            (SOURCE_DIR / alternate["rendered_image"]).read_bytes()
        ).hexdigest()
        == alternate["rendered_image_sha256"]
    )
    # Both are visible in the facsimiles; the digital text was not the sole
    # source of this conflict. Preserve rather than choose the convenient year.
    assert SOURCE["year_variants"]["siku787_635"]["header"] == "万历乙亥岁"
    assert alternate["header"] == "万历己亥岁"


def test_printed_table_has_its_own_circle_not_a_normalized_shoushi_table():
    table = h.GUJIN_58_PURPLE
    assert table.circle_du == F("365.2564")
    assert table.widths_du[c.MANSIONS.index("虚")] == F("9.0064")
    assert c.SHOUSHI_1281.widths_du[c.MANSIONS.index("虚")] == F("9.0075")
    assert c.SHOUSHI_1281.circle_du - table.circle_du == F("0.0011")
    assert table.circle_du * 28 == F(SOURCE["period_days"])
    assert (c.SHOUSHI_1281.circle_du - table.circle_du) * 28 == F("0.0308")
    with pytest.raises(ValueError, match="未闭合"):
        c.HistoricalMansions("no_silent_emendation", F("365.2575"), table.widths_du)


def test_printed_28_cumulative_entries_and_the_column_offset_at_every_edge():
    epsilon = F(1, 10**12)
    origin = -F(SOURCE["offset_days"])
    entries = SOURCE["transcribed_interval_ends_days"]
    start = F()
    for i, item in enumerate(entries):
        end = F(item["end_phase_days"])
        current = h.purple_historical_position(origin + start)
        assert current.mansion == item["mansion"]
        assert current.degree_in_mansion_du == 0
        assert current.interval_end_days == end
        assert current.days_until_next_mansion == end - start
        before = h.purple_historical_position(origin + end - epsilon)
        assert before.mansion == item["mansion"]
        assert before.days_until_next_mansion == epsilon
        at = h.purple_historical_position(origin + end)
        assert at.mansion == entries[(i + 1) % 28]["mansion"]
        assert at.degree_in_mansion_du == 0
        assert current.next_mansion == at.mansion
        after = h.purple_historical_position(origin + end + epsilon)
        assert after.mansion == at.mansion
        assert after.degree_in_mansion_du == epsilon / 28
        assert (
            h.purple_historical_position(
                origin + start - h.GUJIN_58_PURPLE.circle_du * 28 * 19
            )
            == current
        )
        start = end


def test_original_worked_example_locates_bi_and_next_zi_without_a_modern_date():
    example = SOURCE["worked_example"]
    position = h.purple_historical_position(F(example["zhongji_days"]))
    assert position.phase_days == F(example["phase_days"])
    assert position.mansion == example["mansion"] == "毕"
    assert position.next_mansion == example["next_mansion"] == "觜"
    assert position.interval_start_days == F("4502.8592")
    assert position.interval_end_days == F(example["next_entry_phase_days"])
    assert position.days_until_next_mansion == F(example["days_until_next"])
    assert position.degree_in_mansion_du == F("401.7116") / 28
    assert "modern_longitude" not in asdict(position)
    assert not SOURCE["modern_epoch_calibrated"]
    assert not SOURCE["native_birth_model_changed"]


def test_undefined_input_units_are_rejected_instead_of_guessed():
    for wrong in [2451545.0, "116147.0196", 0, None, True]:
        with pytest.raises(TypeError, match="中积"):
            h.purple_historical_position(wrong)

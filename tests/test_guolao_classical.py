"""Primary-text examples and exact ancient-unit interval counterexamples."""

import json
import math
from fractions import Fraction as F
from pathlib import Path

import pytest

from fatebridge.core import guolao_classical as c
from fatebridge.core import guolao_moira


def test_luwei_hour_count_example_and_reverse_palace_example():
    # Volume 1 image 9: Sun 子, birth 酉, count to 卯 -> 午.
    assert c.life_branch("子", "酉", "卯") == "午"
    # The same image independently enumerates the twelve palaces for 命在寅.
    assert c.palace_branches("寅") == dict(zip(c.PALACES, "寅丑子亥戌酉申未午巳辰卯"))
    # These are changes of the stopping hour, never changes of the Sun's instant.
    assert c.life_branch("子", "酉", "辰") == "未"
    assert c.life_branch("子", "酉", "寅") == "巳"


@pytest.mark.parametrize(
    "edge,before,after",
    [
        (90.0, "卯", "寅"),
        (105.0, "寅", "卯"),
        (270.0, "卯", "辰"),
        (300.0, "辰", "卯"),
    ],
)
def test_declared_term_instant_policy_keeps_adjacent_floats(edge, before, after):
    assert c.counting_anchor(math.nextafter(edge, -math.inf)) == before
    assert c.counting_anchor(edge) == after
    assert c.counting_anchor(math.nextafter(edge, math.inf)) == after


def test_small_limit_is_reverse_counting_not_an_event_forecast():
    # Put birth-year 子 on life 寅; successive year branches run backwards.
    assert [c.small_limit_branch("寅", "子", y) for y in c.BRANCHES] == list(
        "寅丑子亥戌酉申未午巳辰卯"
    )
    assert c.small_limit_branch("午", "酉", "酉") == "午"
    assert c.small_limit_branch("午", "酉", "戌") == "巳"


def test_missing_life_degree_cannot_be_fabricated_from_discrete_palace():
    patterns = guolao_moira.calculate(
        {
            "life_sign_idx": 4,
            "god_signidx": {"岁驾": 4},
            "planet_signidx": {},
        }
    )
    names = {p["name"] for p in patterns}
    assert "命登岁驾" in names
    assert "命坐两歧" not in names
    for invalid in [-1, 12, True, 1.5]:
        with pytest.raises(ValueError, match="命宫索引"):
            guolao_moira.calculate({"life_sign_idx": invalid})


def test_shoushi_table_preserves_primary_circle_and_quadrant_subtotals():
    source = json.loads(
        (Path(__file__).parent / "fixtures" / "guolao-shoushi-source.json").read_text()
    )
    table = c.SHOUSHI_1281
    assert table.widths_du == tuple(map(F, source["ecliptic_widths_du"]))
    assert table.circle_du == F(source["circle_du"]) == F("365.2575")
    for i, subtotal in enumerate(source["quadrant_subtotals_du"]):
        assert sum(table.widths_du[i * 7 : (i + 1) * 7]) == F(subtotal)
    # The very narrow 觜 and fractional 虚 are materially different readings.
    assert table.widths_du[19] == F("0.05")
    assert table.widths_du[10] == F("9.0075")
    assert not source["modern_epoch_alignment_established"]
    assert not source["luwei_edition_table_emended"]


def test_every_historical_boundary_in_source_units_and_negative_wrap():
    table = c.SHOUSHI_1281
    epsilon = F(1, 10**8)
    start = F()
    for i, (name, width) in enumerate(zip(c.MANSIONS, table.widths_du)):
        assert table.locate(start) == (name, F())
        assert table.locate(start + epsilon) == (name, epsilon)
        assert table.locate(start - epsilon) == (
            c.MANSIONS[i - 1],
            table.widths_du[i - 1] - epsilon,
        )
        assert table.locate(start - table.circle_du * 17) == (name, F())
        start += width
    assert table.locate(table.circle_du) == ("角", F())
    with pytest.raises(TypeError, match="Fraction"):
        table.locate(12.87)
    with pytest.raises(ValueError, match="未闭合"):
        c.HistoricalMansions("do_not_normalize", F("365.25"), table.widths_du)


@pytest.mark.parametrize("invalid", ["", "子丑", "X"])
def test_invalid_branches_never_become_a_default(invalid):
    with pytest.raises(ValueError, match="地支"):
        c.life_branch("子", invalid, "卯")


def test_noble_tables_are_from_the_selected_edition_including_wu_exception():
    source = json.loads(
        (
            Path(__file__).parent / "fixtures" / "guolao-classical-source.json"
        ).read_text()
    )["transcription"]["nobles"]
    for stem in c.STEMS:
        branches = c.year_god_branches(stem, "辰")
        assert branches == {
            "天贵": source["day_tianyi"][stem],
            "玉贵": source["night_yutang"][stem],
            "岁驾": "辰",
        }
    assert c.year_god_branches("戊", "子") == {"天贵": "丑", "玉贵": "未", "岁驾": "子"}
    assert c.year_god_branches("甲", "子") == {"天贵": "未", "玉贵": "丑", "岁驾": "子"}
    # 戊 follows 庚 here, so swapping every value from the legacy table fails.
    for invalid in ("", "甲乙", "X"):
        with pytest.raises(ValueError, match="年干"):
            c.year_god_branches(invalid, "子")


def test_purple_cycle_replays_source_arithmetic_without_fitting_a_modern_epoch():
    source = json.loads(
        (Path(__file__).parent / "fixtures" / "guolao-purple-source.json").read_text()
    )
    example = source["worked_example"]
    result = c.purple_cycle_reference(F(example["zhongji_days"]))
    assert result["published_phase_days"] == F(example["published_phase_days"])
    assert F(example["next_zi_entry_days"]) - result["published_phase_days"] == F(
        example["days_until_zi_entry"]
    )
    assert result["corrected_period_days"] == F("10227.21")
    assert result["rounding_discrepancy_days"] == F("0.0308")
    assert result["corrected_period_experiment_phase_days"] == F("4904.232")
    epsilon = F(1, 10**12)
    base = -c.PURPLE_SOURCE_OFFSET_DAYS
    assert c.purple_cycle_reference(base)["published_phase_days"] == 0
    assert (
        c.purple_cycle_reference(base - epsilon)["published_phase_days"]
        == c.PURPLE_SOURCE_PERIOD_DAYS - epsilon
    )
    assert c.purple_cycle_reference(base + epsilon)["published_phase_days"] == epsilon
    assert (
        c.purple_cycle_reference(base - c.PURPLE_SOURCE_PERIOD_DAYS * 10)[
            "published_phase_days"
        ]
        == 0
    )
    assert not source["modern_longitude_epoch_calibrated"]
    with pytest.raises(TypeError, match="中积"):
        c.purple_cycle_reference(2451545.0)

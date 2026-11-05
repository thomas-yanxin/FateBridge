"""Original 318-year calculation; declared century-step policy stays explicit."""

import hashlib
import json
import runpy
import sys
from fractions import Fraction as F
from pathlib import Path

import pytest

from fatebridge.core.guolao_historical import shoushi_winter_cycle

SOURCE_DIR = Path(__file__).parents[1] / "fixtures" / "guolao-shoushi-accumulation-v1"
SOURCE = json.loads((SOURCE_DIR / "reference.json").read_text())


def test_original_318_year_middle_and_winter_day_reproduce_the_printed_example():
    image = SOURCE["image"]
    assert (
        hashlib.sha256((SOURCE_DIR / image["path"]).read_bytes()).hexdigest()
        == image["sha256"]
    )
    example = SOURCE["worked_example"]
    result = shoushi_winter_cycle(example["elapsed_years"])
    assert result.effective_year_days == F(example["effective_year_days"])
    assert result.zhongji_days == F(example["zhongji_days"])
    assert result.winter_cycle_days == F(example["winter_cycle_days"])
    assert result.winter_sexagenary_day == example["winter_sexagenary_day"]
    assert result.winter_fraction_of_day == F(example["winter_fraction_of_day"])
    # The constant-year and continuous-drift alternatives fail this example.
    assert result.zhongji_days != 318 * F("365.2425")
    assert result.zhongji_days != 318 * (F("365.2425") - F(318, 1000000))
    assert not SOURCE["modern_calendar_date_assigned"]
    assert not SOURCE["modern_epoch_calibrated"]


def test_epoch_day_and_declared_whole_century_step_are_exact():
    initial = shoushi_winter_cycle(0)
    assert initial.zhongji_days == 0
    assert initial.winter_cycle_days == F("55.06")
    assert initial.winter_sexagenary_day == "己未"
    for elapsed, year in [
        (99, "365.2425"),
        (100, "365.2424"),
        (199, "365.2424"),
        (200, "365.2423"),
    ]:
        value = shoushi_winter_cycle(elapsed)
        assert value.effective_year_days == F(year)
        assert value.zhongji_days == elapsed * F(year)


def test_upward_reconstruction_and_undefined_units_are_not_guessed():
    with pytest.raises(ValueError, match="上考"):
        shoushi_winter_cycle(-1)
    for bad in [True, 318.0, F(318), "318", None]:
        with pytest.raises(TypeError, match="距算"):
            shoushi_winter_cycle(bad)


def test_actual_offline_command_connects_elapsed_years_to_middle_and_mansion(
    monkeypatch, capsys
):
    script = Path(__file__).parents[2] / "scripts" / "audit_guolao_purple.py"
    monkeypatch.setattr(sys, "argv", [str(script), "--elapsed-years", "318"])
    assert runpy.run_path(str(script))["main"]() == 0
    value = json.loads(capsys.readouterr().out)
    assert value["input_kind"] == "source_elapsed_years_not_modern_calendar_year"
    assert F(value["zhongji_days_exact"]) == F("116147.0196")
    assert value["year_accumulation"]["winter_sexagenary_day"] == "丙午"
    assert value["printed_historical_table"]["mansion"] == "毕"
    assert value["printed_historical_table"]["next_mansion"] == "觜"
    assert not value["year_accumulation"]["modern_calendar_date_assigned"]
    assert value["modern_longitude"] is None

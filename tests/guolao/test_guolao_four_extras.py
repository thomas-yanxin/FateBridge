"""Facsimile arithmetic, opposite directions, rounded endpoints and CLI inputs."""

import hashlib
import json
import runpy
import sys
from fractions import Fraction as F
from pathlib import Path

import pytest

from fatebridge.core import guolao_four_extras as g
from fatebridge.core.guolao_historical import (
    GUJIN_58_PURPLE,
    purple_historical_position,
)

ROOT = Path(__file__).parents[2]
FIXTURE = Path(__file__).parents[1] / "fixtures/guolao-four-extras-source-v1"
SOURCE = json.loads((FIXTURE / "reference.json").read_text())
EXAMPLE = SOURCE["worked_example"]


def test_downloaded_full_pages_keep_original_fingerprints_and_review_scope():
    for image in SOURCE["images"]:
        assert hashlib.sha256((FIXTURE / image["path"]).read_bytes()).hexdigest() == (
            image["sha256"]
        )
    assert not SOURCE["source"]["independent_second_collator"]
    assert not SOURCE["accepted_modern_longitudes"]
    assert not SOURCE["accepted_fractional_degree_interpolation_for_new_tables"]


@pytest.mark.parametrize("key", ["purple", "apogee", "rahu", "ketu"])
def test_all_four_separate_original_worked_chains(key):
    value = g.four_extras_source_days(
        F(EXAMPLE["zhongji_days"]), winter_cycle_days=F(EXAMPLE["winter_cycle_days"])
    )["factors"][key]
    expected = EXAMPLE["factors"][key]
    for name in ["mansion", "next_mansion"]:
        assert value[name] == expected[name]
    for actual, reference in [
        ("phase_days_exact", "phase_days"),
        ("interval_end_days_exact", "next_entry_phase_days"),
        ("days_until_next_entry_exact", "days_until_next_entry"),
        ("next_entry_day_cycle_exact", "entry_day_cycle"),
    ]:
        assert F(value[actual]) == F(expected[reference])
    if expected["sum_days"] is not None:
        assert F(value["sum_days_exact"]) == F(expected["sum_days"])
    assert value["next_entry_sexagenary_day"] == expected["entry_sexagenary_day"]


@pytest.mark.parametrize("key", ["purple", "apogee", "rahu", "ketu"])
def test_every_printed_endpoint_and_either_side_follow_the_correct_direction(key):
    factor = SOURCE["offsets"][key]
    table = SOURCE["tables_transcribed"][factor["table"]]
    origin = -F(factor["offset_days"])
    epsilon = F(1, 10**12)
    start = F()
    for i, row in enumerate(table["intervals"]):
        end = F(row["end_phase_days"])
        current = g.four_extras_source_days(origin + start)["factors"][key]
        before = g.four_extras_source_days(origin + end - epsilon)["factors"][key]
        at = g.four_extras_source_days(origin + end)["factors"][key]
        after = g.four_extras_source_days(origin + end + epsilon)["factors"][key]
        following = table["intervals"][(i + 1) % 28]["mansion"]
        assert current["mansion"] == before["mansion"] == row["mansion"]
        assert F(current["interval_start_days_exact"]) == start
        assert F(current["interval_end_days_exact"]) == end
        assert F(before["days_until_next_entry_exact"]) == epsilon
        assert at["mansion"] == after["mansion"] == following
        assert at["entry_kind"] == table["entry_kind"]
        assert at["direction"] == table["direction"]
        assert at["next_entry_day_cycle_exact"] is None
        start = end


@pytest.mark.parametrize(
    "key,offset,endpoint,width,next_name",
    [
        ("apogee", "2384.1092", "84.8570", "9.59", "斗"),
        ("rahu", "1680.8602", "333.8539", "17.95", "心"),
    ],
)
def test_regenerating_the_table_from_rounded_rate_misplaces_a_printed_boundary(
    key, offset, endpoint, width, next_name
):
    record = g.four_extras_source_days(F(endpoint) - F(offset))["factors"][key]
    generated_end = F(width) * F(record["printed_days_per_historical_du_exact"])
    assert F(endpoint) < generated_end
    assert record["mansion"] == next_name
    # An implementation using generated_end as the first exit still says 箕/尾.
    assert record["degree_in_mansion_historical_du_exact"] is None


def test_node_half_period_is_a_source_day_shift_not_a_modern_longitude_rotation():
    middle = F(EXAMPLE["zhongji_days"])
    value = g.four_extras_source_days(middle)
    shifted = g.four_extras_source_days(middle + F("3396.7216"))["factors"]["rahu"]
    ketu = value["factors"]["ketu"]
    for name in [
        "mansion",
        "next_mansion",
        "phase_days_exact",
        "days_until_next_entry_exact",
    ]:
        assert shifted[name] == ketu[name]
    assert F(ketu["offset_days_exact"]) - F(
        value["factors"]["rahu"]["offset_days_exact"]
    ) == F("3396.7216")
    assert value["modern_longitudes"] is None


@pytest.mark.parametrize("middle", [F(), F("116147.0196"), F(-1, 10**9), F(-900000)])
def test_purple_reuses_existing_exact_table_and_new_tables_preserve_periodicity(middle):
    records = g.four_extras_source_days(middle)["factors"]
    purple = purple_historical_position(middle)
    assert records["purple"]["mansion"] == purple.mansion
    assert F(records["purple"]["degree_in_mansion_historical_du_exact"]) == (
        purple.degree_in_mansion_du
    )
    for key, record in records.items():
        repeated = g.four_extras_source_days(
            middle - 3 * F(record["period_days_exact"])
        )["factors"][key]
        for field in ["mansion", "phase_days_exact", "days_until_next_entry_exact"]:
            assert repeated[field] == record[field]


def test_entire_printed_tables_match_transcription_without_forcing_rate_closure():
    source = json.loads(g.DATA.read_bytes())
    assert source["tables"] == SOURCE["tables_transcribed"]
    assert source["factors"] == SOURCE["offsets"]
    for key in ["apogee", "nodes"]:
        table = source["tables"][key]
        rate = F(table["printed_days_per_du"])
        assert F(table["period_days"]) != GUJIN_58_PURPLE.circle_du * rate
    assert not source["period_or_widths_normalized"]


@pytest.mark.parametrize("bad", [0, True, "116147.0196", 2451545.0, None])
def test_raw_middle_requires_declared_exact_source_days(bad):
    with pytest.raises(TypeError, match="中积"):
        g.four_extras_source_days(bad)


@pytest.mark.parametrize("bad", [0, True, "42.0796", 42.0796])
def test_optional_winter_requires_declared_exact_cycle(bad):
    with pytest.raises(TypeError, match="冬至分"):
        g.four_extras_source_days(F(), winter_cycle_days=bad)


@pytest.mark.parametrize("bad", [F(-1, 10**10), F(60), F(2451545)])
def test_winter_is_a_day_cycle_not_a_julian_day(bad):
    with pytest.raises(ValueError, match="60"):
        g.four_extras_source_days(F(), winter_cycle_days=bad)


@pytest.mark.parametrize(
    "fault",
    ["missing", "reorder", "nonmonotonic", "closure", "entry_kind", "half_period"],
)
def test_damaged_source_table_fails_closed(tmp_path, monkeypatch, fault):
    source = json.loads(g.DATA.read_bytes())
    table = source["tables"]["nodes"]
    if fault == "missing":
        table["intervals"].pop()
    elif fault == "reorder":
        table["intervals"][0]["mansion"] = "箕"
    elif fault == "nonmonotonic":
        table["intervals"][1]["end_phase_days"] = "1"
    elif fault == "closure":
        table["period_days"] = "6793"
    elif fault == "entry_kind":
        table["entry_kind"] = "initial_degree"
    else:
        source["half_node_period_days"] = "3396"
    path = tmp_path / "source.json"
    path.write_text(json.dumps(source))
    monkeypatch.setattr(g, "DATA", path)
    with pytest.raises(ValueError):
        g.four_extras_source_days(F())


def _command(monkeypatch, capsys, args):
    script = ROOT / "scripts/guolao/audit_guolao_four_extras.py"
    monkeypatch.setattr(sys, "argv", [str(script), *args])
    assert runpy.run_path(str(script))["main"]() == 0
    return json.loads(capsys.readouterr().out)


@pytest.mark.parametrize(
    "args",
    [["--elapsed-years", "318"], ["--source-year", "1599"], ["--winter-year", "1598"]],
)
def test_actual_cli_year_paths_reproduce_all_four_worked_mansion_entries(
    monkeypatch, capsys, args
):
    value = _command(monkeypatch, capsys, args)
    assert value["elapsed_years"] == 318
    for key, expected in EXAMPLE["factors"].items():
        assert value["factors"][key]["mansion"] == expected["mansion"]
        assert (
            value["factors"][key]["next_entry_sexagenary_day"]
            == expected["entry_sexagenary_day"]
        )
    for flag in [
        "modern_epoch_calibrated",
        "modern_calendar_date_assigned",
        "used_in_native_birth_chart",
        "gujin58_header_variants_resolved",
    ]:
        assert value[flag] is False


def test_explicit_middle_and_winter_cli_matches_year_arithmetic(monkeypatch, capsys):
    direct = _command(
        monkeypatch,
        capsys,
        ["--zhongji-days", "116147.0196", "--winter-cycle-days", "42.0796"],
    )
    year = _command(monkeypatch, capsys, ["--elapsed-years", "318"])
    year.pop("elapsed_years")
    assert direct == year


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["--source-year", "1280"],
        ["--elapsed-years", "318", "--winter-cycle-days", "0"],
        ["--source-year", "1599", "--winter-year", "1598"],
        ["--zhongji-days", "1/0"],
        ["--zhongji-days", "NaN"],
        ["--zhongji-days", "0", "--winter-cycle-days", "60"],
    ],
)
def test_cli_rejects_missing_conflicting_or_invalid_operands(monkeypatch, capsys, args):
    with pytest.raises(SystemExit) as exc:
        _command(monkeypatch, capsys, args)
    assert exc.value.code == 2
    assert not capsys.readouterr().out

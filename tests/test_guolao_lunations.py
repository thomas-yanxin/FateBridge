"""Distinct epoch constants, original mean-month chains and date counterexamples."""

import hashlib
import json
import runpy
import sys
from fractions import Fraction as F
from pathlib import Path

import pytest

from fatebridge.core import guolao_lunations as l

ROOT = Path(__file__).parents[1]
FIXTURE = Path(__file__).parent / "fixtures/guolao-source-lunations-v1"
SOURCE = json.loads((FIXTURE / "reference.json").read_text())
EXAMPLE = SOURCE["worked_example"]


def test_reviewed_artifacts_and_named_parameters_match_source_transcription():
    for artifact in SOURCE["artifacts"]:
        assert hashlib.sha256(
            (FIXTURE / artifact["path"]).read_bytes()
        ).hexdigest() == (artifact["sha256"])
    data = json.loads(l.DATA.read_bytes())
    assert data["profiles"] == SOURCE["profiles_transcribed"]
    assert data["gujin58_month_table"] == SOURCE["month_table_transcribed"]
    assert not SOURCE["second_independent_collator"]
    assert all(
        row["png_bytes_equal"] for row in SOURCE["nlc166_extraction_render_check"]
    )


@pytest.mark.parametrize("key", ["purple", "apogee", "rahu", "ketu"])
def test_all_four_original_month_remainders_and_mean_conjunction_cycles(key):
    example = EXAMPLE["factors"][key]
    value = l.source_mean_lunation(
        F(EXAMPLE["zhongji_days"]), F(example["wait_days"]), profile_id=l.GUJIN
    )
    assert F(value["runyu_days_exact"]) == F(EXAMPLE["runyu_days"])
    assert F(value["runyu_plus_event_days_exact"]) == F(example["sum_days"])
    assert value["mean_lunation_index"] == example["lunation_index"]
    assert value["unintercalated_table_slot_label"] == example["printed_month"]
    assert F(value["days_since_mean_conjunction_exact"]) == F(
        example["mean_month_elapsed_days"]
    )
    assert F(value["mean_conjunction_day_cycle_exact"]) == F(
        example["mean_new_moon_cycle_days"]
    )
    assert value["lunar_date"] is None


def test_yuanshi_runying_is_not_silently_substituted_into_gujin_worked_example():
    g = l.source_mean_lunation(F(EXAMPLE["zhongji_days"]), F(), profile_id=l.GUJIN)
    y = l.source_mean_lunation(F(EXAMPLE["zhongji_days"]), F(), profile_id=l.YUANSHI)
    assert F(g["runying_days_exact"]) == F("20.2050")
    assert F(y["runying_days_exact"]) == F("20.1850")
    assert F(g["runyu_days_exact"]) == F("23.402331")
    assert F(y["runyu_days_exact"]) == F("23.382331")
    assert y["unintercalated_table_slot_label"] is None


def test_epoch_constant_mixing_can_change_the_month_count_at_a_boundary():
    event = F("6.128262")
    g = l.source_mean_lunation(F(EXAMPLE["zhongji_days"]), event, profile_id=l.GUJIN)
    y = l.source_mean_lunation(F(EXAMPLE["zhongji_days"]), event, profile_id=l.YUANSHI)
    assert g["mean_lunation_index"] == 1
    assert F(g["days_since_mean_conjunction_exact"]) == 0
    assert y["mean_lunation_index"] == 0
    assert F(y["days_since_mean_conjunction_exact"]) == F("29.510593")


def test_runyu_difference_wraps_rather_than_always_being_positive_point_zero_two():
    g = l.source_mean_lunation(F("9.34"), F(), profile_id=l.GUJIN)
    y = l.source_mean_lunation(F("9.34"), F(), profile_id=l.YUANSHI)
    assert F(g["runyu_days_exact"]) - F(y["runyu_days_exact"]) == F("-29.510593")


def test_twelve_printed_month_table_boundaries_and_either_side_are_exact():
    epsilon = F(1, 10**12)
    base = F(EXAMPLE["zhongji_days"])
    runyu = F(EXAMPLE["runyu_days"])
    for row in SOURCE["month_table_transcribed"][1:]:
        event = F(row["cumulative_days"]) - runyu
        before = l.source_mean_lunation(base, event - epsilon, profile_id=l.GUJIN)
        at = l.source_mean_lunation(base, event, profile_id=l.GUJIN)
        after = l.source_mean_lunation(base, event + epsilon, profile_id=l.GUJIN)
        assert before["mean_lunation_index"] == row["lunation_index"] - 1
        assert (
            at["mean_lunation_index"]
            == after["mean_lunation_index"]
            == row["lunation_index"]
        )
        assert at["unintercalated_table_slot_label"] == row["unintercalated_slot_label"]
        assert F(at["days_since_mean_conjunction_exact"]) == 0
        assert F(after["days_since_mean_conjunction_exact"]) == epsilon


def test_beyond_printed_table_is_not_wrapped_into_an_invented_lunar_month():
    value = l.source_mean_lunation(F(), F(500), profile_id=l.GUJIN)
    assert value["mean_lunation_index"] > 11
    assert value["unintercalated_table_slot_label"] is None
    assert value["lunar_date"] is None
    assert not value["intercalation_reconstructed"]


def test_neither_mean_fraction_shortcut_can_reproduce_all_printed_lunar_days():
    values = l.gujin_four_extras_lunations(F(EXAMPLE["zhongji_days"]))["factors"]
    assert values["apogee"]["unaccepted_day_diagnostics"]["floor_elapsed_plus_one"] == 7
    assert EXAMPLE["factors"]["apogee"]["printed_day"] == 8
    assert (
        values["purple"]["unaccepted_day_diagnostics"]["midnight_difference_plus_one"]
        == 26
    )
    assert EXAMPLE["factors"]["purple"]["printed_day"] == 25
    assert all(value["lunar_date"] is None for value in values.values())
    assert not l.gujin_four_extras_lunations(F(EXAMPLE["zhongji_days"]))[
        "printed_calendar_dates_used_as_algorithm_outputs"
    ]


@pytest.mark.parametrize("field", ["middle", "event"])
@pytest.mark.parametrize("bad", [0, True, "1", 2451545.0, None])
def test_exact_units_are_required(field, bad):
    with pytest.raises(TypeError, match="Fraction"):
        l.source_mean_lunation(
            bad if field == "middle" else F(),
            bad if field == "event" else F(),
            profile_id=l.GUJIN,
        )


@pytest.mark.parametrize("middle,event", [(F(-1), F()), (F(), F(-1))])
def test_lower_reckoning_does_not_infer_upward_or_prior_event_policy(middle, event):
    with pytest.raises(ValueError, match="非负"):
        l.source_mean_lunation(middle, event, profile_id=l.GUJIN)


@pytest.mark.parametrize("profile", [None, "shoushi", "auto", 1, []])
def test_profile_must_be_explicitly_named(profile):
    with pytest.raises(ValueError, match="具名"):
        l.source_mean_lunation(F(), F(), profile_id=profile)


@pytest.mark.parametrize(
    "fault", ["missing_month", "changed_cumulative", "invalid_runying"]
)
def test_damaged_source_data_fails_without_repairing_the_printed_table(
    tmp_path, monkeypatch, fault
):
    value = json.loads(l.DATA.read_bytes())
    if fault == "missing_month":
        value["gujin58_month_table"].pop()
    elif fault == "changed_cumulative":
        value["gujin58_month_table"][2]["cumulative_days"] = "60"
    else:
        value["profiles"][l.GUJIN]["runying_days"] = "30"
    path = tmp_path / "source.json"
    path.write_text(json.dumps(value))
    monkeypatch.setattr(l, "DATA", path)
    with pytest.raises(ValueError):
        l.source_mean_lunation(F(), F(), profile_id=l.GUJIN)


def _command(monkeypatch, capsys, script, args):
    path = ROOT / "scripts" / script
    monkeypatch.setattr(sys, "argv", [str(path), *args])
    assert runpy.run_path(str(path))["main"]() == 0
    return capsys.readouterr().out


@pytest.mark.parametrize(
    "args",
    [
        ["--elapsed-years", "318"],
        ["--source-year", "1599"],
        ["--winter-year", "1598"],
        ["--zhongji-days", "116147.0196"],
        ["--zhongji-days", "116147.0196", "--winter-cycle-days", "42.0796"],
    ],
)
def test_real_cli_opt_in_connects_all_four_mean_months_without_civil_dates(
    monkeypatch, capsys, args
):
    value = json.loads(
        _command(
            monkeypatch,
            capsys,
            "audit_guolao_four_extras.py",
            [*args, "--include-mean-lunations"],
        )
    )
    audit = value.pop("mean_lunation_audit")
    old = json.loads(_command(monkeypatch, capsys, "audit_guolao_four_extras.py", args))
    assert value == old
    assert audit["profile_id"] == l.GUJIN
    assert not audit["comparison_replaces_gujin_parameters"]
    for key, expected in EXAMPLE["factors"].items():
        assert (
            audit["factors"][key]["mean_lunation_index"] == expected["lunation_index"]
        )
        assert audit["factors"][key]["lunar_date"] is None


@pytest.mark.parametrize(
    "args",
    [
        ["--zhongji-days", "116147.0196", "--winter-cycle-days", "0"],
        ["--zhongji-days", "-1"],
    ],
)
def test_opt_in_rejects_mixed_clock_operands_and_unreconstructed_upward_policy(
    monkeypatch, capsys, args
):
    with pytest.raises(SystemExit) as error:
        _command(
            monkeypatch,
            capsys,
            "audit_guolao_four_extras.py",
            [*args, "--include-mean-lunations"],
        )
    assert error.value.code == 2
    assert not capsys.readouterr().out

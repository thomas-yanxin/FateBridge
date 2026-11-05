"""Rotation must derive TT with the same policy as the physical clock."""

import json
from pathlib import Path

import pytest

from fatebridge.core import astro_models as rotation
from fatebridge.core.astro import runtime
from fatebridge.core.astro.iers_ut1 import c04_table, use_ut1_source
from tests.reference_data import verify_source_files

FIXTURE = Path(__file__).parent / "data/astro/rotation_tt_policy"
PROTOCOL = json.loads((FIXTURE / "protocol.json").read_text())
ANCHORS = json.loads((FIXTURE / "boundary-anchors.json").read_text())


def test_native_policy_controls_are_sealed_and_not_independent_observations():
    verify_source_files(FIXTURE)
    assert len(PROTOCOL["cases"]) == 26
    assert not PROTOCOL["production_imports"]
    assert PROTOCOL["known_lead_not_blind"]


@pytest.mark.parametrize("row", PROTOCOL["cases"], ids=lambda r: r["id"])
def test_rotation_nutation_uses_the_physical_clock_tt(row, monkeypatch):
    actual = runtime.swe.calc
    tt_arguments = []

    def observed(tt, body, *args, **kwargs):
        if body == runtime.swe.ECL_NUT:
            tt_arguments.append(tt)
        return actual(tt, body, *args, **kwargs)

    monkeypatch.setattr(runtime.swe, "calc", observed)
    with use_ut1_source("swiss_delta_t"):
        rotation._standard_correction(runtime.swe, row["ut1"])
    assert len(tt_arguments) == 1
    assert (
        abs(tt_arguments[0] - row["tt"]) * 86400
        <= PROTOCOL["tt_epoch_tolerance_seconds"]
    )


@pytest.mark.parametrize("row", PROTOCOL["cases"], ids=lambda r: r["id"])
def test_model_choice_and_phase_anchor_follow_the_same_tt(row, monkeypatch):
    # Return the argument itself so branch choice cannot hide behind a tiny
    # difference between the two sidereal formulae.
    monkeypatch.setattr(rotation, "_standard_correction", lambda module, ut1: ut1)
    with use_ut1_source("swiss_delta_t"):
        actual = rotation._correction(runtime.swe, row["ut1"])
    expected = (
        row["ut1"]
        if row["expected_model"] == 3
        else ANCHORS[0 if row["tt"] < 2451545 else 1]["ut1"]
    )
    assert abs(actual - expected) * 86400 <= PROTOCOL["tt_epoch_tolerance_seconds"]


def test_selected_c04_supplies_its_own_tt_without_a_default_delta_t(monkeypatch):
    table = c04_table()
    sample = table.samples[-1]
    actual = runtime.swe.calc
    arguments = []

    def observed(tt, body, *args, **kwargs):
        if body == runtime.swe.ECL_NUT:
            arguments.append(tt)
        return actual(tt, body, *args, **kwargs)

    monkeypatch.setattr(runtime.swe, "calc", observed)
    with use_ut1_source("iers_c04"):
        rotation._standard_correction(runtime.swe, sample.ut1)
    assert arguments == [sample.tt]

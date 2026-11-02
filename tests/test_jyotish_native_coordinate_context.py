"""Retain every expanded frame and poisoned-cache challenge at the same epoch."""

import json
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.compressed_ephemeris import (
    audit_compressed_endpoints,
    coordinate_context_evidence,
)
from tests.test_jyotish_segment_motion import full_files
from tests.test_jyotish_sources import data18, restore_runtime  # noqa: F401

MATERIAL = json.loads(
    (
        Path(__file__).parent / "fixtures/jyotish-native-context-challenge.json"
    ).read_text()
)


@pytest.mark.parametrize(
    "epoch", MATERIAL["epochs"], ids=["planet_file_end", "moon_file_end"]
)
@pytest.mark.parametrize("body", MATERIAL["bodies"])
@pytest.mark.parametrize("operation", ["calc", "calc_ut"])
@pytest.mark.parametrize("form", MATERIAL["forms"])
def test_all_native_components_agree_after_private_context_preselection(
    data18, epoch, body, operation, form
):
    directory = full_files(data18)
    native = e.swe
    flags = (
        native.FLG_SWIEPH
        | {
            "tropical_speed": native.FLG_SPEED,
            "sidereal_speed": native.FLG_SPEED | native.FLG_SIDEREAL,
            "equatorial": native.FLG_EQUATORIAL,
            "icrf_xyz": native.FLG_XYZ
            | native.FLG_ICRS
            | native.FLG_J2000
            | native.FLG_EQUATORIAL,
            "speed3": native.FLG_SPEED3,
        }[form]
    )
    tt = epoch["julian_day_tt"]
    instant = tt if operation == "calc" else epoch["julian_day_ut1"]
    states = []
    with e.preserve_ephemeris_path():
        for condition in MATERIAL["conditions"]:
            native.set_ephe_path(str(directory))
            native.set_sid_mode(native.SIDM_LAHIRI, 0, 0)
            if condition == "warm":
                native.calc(tt + 0.75, getattr(native, body.upper()), flags)
            elif condition == "unmanaged_same_epoch":
                getattr(native, operation)(
                    instant, getattr(native, body.upper()), flags
                )
            with audit_compressed_endpoints():
                values, returned = e.ephemeris_call(
                    operation, instant, getattr(native, body.upper()), flags
                )
                context = coordinate_context_evidence()
            assert e.ephemeris_model_from_retflag(returned) == "swieph"
            assert context["physical_jd_tt"] == tt
            assert context["input_julian_day"] == instant
            assert context["physical_instant_shifted"] is False
            assert context["private_native_cache_reset"] is True
            assert context["original_native_state"] is None
            states.append((values, returned))
    assert states[0] == states[1] == states[2]

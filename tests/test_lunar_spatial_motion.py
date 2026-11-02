"""Frozen pre-edit raw-DE441/AD arithmetic, partial-rate and transport evidence."""

import hashlib
import json
import math
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.astro import ephemeris, lunar_motion
from fatebridge.utils.errors import EphemerisSourceError
from tests.test_jyotish_sources import restore_runtime  # noqa: F401

REFERENCE_PATH = (
    Path(__file__).with_name("fixtures") / "lunar-spatial-source-reference-v1.json"
)
REFERENCE = json.loads(REFERENCE_PATH.read_text())
NATIVE_REFERENCE_PATH = REFERENCE_PATH.with_name(
    "lunar-spatial-native-arithmetic-v1.json"
)
NATIVE_REFERENCE = json.loads(NATIVE_REFERENCE_PATH.read_text())
AS = 180 / math.pi * 3600


def test_reference_identity_and_all_unfavorable_rows_remain_visible():
    assert hashlib.sha256(REFERENCE_PATH.read_bytes()).hexdigest() == (
        "651c707ed6f940460049e9c4ece9d44caf7ffa39365c93949fa1a8bbabf72ea5"
    )
    assert len(REFERENCE["cases"]) == 64
    assert len({r["job_id"] for r in REFERENCE["cases"]}) == 16
    assert REFERENCE["summary"]["spatial_only_reduces_total_error_rows"] == 22
    assert (
        sum(
            not r["spatial_only_reduces_total_error"]
            for r in REFERENCE["stage_results"]
        )
        == 10
    )
    assert REFERENCE["summary"]["new_physical_reference_passes"] == 0
    assert hashlib.sha256(NATIVE_REFERENCE_PATH.read_bytes()).hexdigest() == (
        "bc61c7277e02fab8ff7083669b6d9c95dee4369b85662fc4c8512e5a4e072afa"
    )
    # These exact-native replay failures are preserved, not counted as passes.
    assert NATIVE_REFERENCE["summary"]["native_C_order_position_failures"] == 34
    assert NATIVE_REFERENCE["summary"]["native_C_order_speed_failures"] == 47


@pytest.mark.parametrize(
    "row",
    REFERENCE["cases"] + NATIVE_REFERENCE["cases"],
    ids=lambda r: f'{r["job_id"]}:{r["clock"]}:{r["frame"]}',
)
def test_spatial_jacobian_and_replacement_against_independent_forward_ad(row):
    apparent, spatial = lunar_motion.aberration_position_jvp(
        row["position"], row["relative_velocity"], row["observer_beta"]
    )
    correction = lunar_motion.aberration_spatial_correction(
        row["position"], row["relative_velocity"], row["observer_beta"]
    )
    radius = math.hypot(*row["apparent_position"])
    limit = REFERENCE["consumer_error_line_arcsec_per_day"]
    assert math.dist(apparent, row["apparent_position"]) / radius * AS <= limit
    assert math.dist(spatial, row["expected_spatial_jvp"]) / radius * AS <= limit
    assert (
        math.dist(correction, row["expected_spatial_correction"]) / radius * AS <= limit
    )
    # A missing spatial term must fail at least some of this fixed cohort.
    assert all(math.isfinite(v) for v in correction)


@pytest.mark.parametrize("case", ["short", "nan", "superluminal", "zero_position"])
def test_invalid_spatial_inputs_are_rejected(case):
    position, velocity, beta = (
        [1.0, 2.0, 3.0],
        [0.01, 0.02, 0.03],
        [0.0001, 0.0002, 0.0003],
    )
    if case == "short":
        velocity.pop()
    elif case == "nan":
        velocity[0] = math.nan
    elif case == "superluminal":
        beta[0] = 2.0
    else:
        position = [0.0, 0.0, 0.0]
    with pytest.raises(EphemerisSourceError):
        lunar_motion.aberration_spatial_correction(position, velocity, beta)


EPOCHS = [
    r
    for r in REFERENCE["cases"]
    if r["clock"] == "same_numeric_tdb_control" and r["frame"] == "ICRF"
]


@pytest.mark.parametrize("row", EPOCHS, ids=lambda r: r["job_id"])
def test_native_all_original_epochs_keep_positions_and_separate_partial_terms(row):
    e.configure_ephemeris_path(str(Path(__file__).resolve().parents[1] / "ephe"))
    tt = row["epoch"]["jd_tt_binary64"]
    context = {}
    corrected, model = ephemeris._swisseph_planet_state(
        "Moon", tt, julian_day_tt=tt, motion_metadata=context
    )
    raw, raw_model = ephemeris._swisseph_planet_state(
        "Moon", tt, julian_day_tt=tt, correct_motion=False
    )
    assert model == raw_model == "swieph"
    for name in ("longitude", "latitude", "distance"):
        if name in raw:
            assert corrected[name] == raw[name]
    assert corrected["longitude_speed_native"] == raw["longitude_speed"]
    assert corrected["longitude_speed"] == (
        corrected["longitude_speed_native"]
        + corrected["longitude_speed_light_time_correction"]
        + corrected["longitude_speed_spatial_aberration_correction"]
        + corrected.get("longitude_speed_lunar_source_remainder_correction", 0.0)
        + corrected["longitude_speed_rotation_correction"]
        + corrected.get("longitude_speed_analytic_frame_correction", 0.0)
    )
    policy = context["lunar_light_time"]
    assert policy["method_id"] == "fatebridge_lunar_fixed_frame_source_derivative_v3"
    assert policy["spatial_aberration"]["status"] == "applied"
    assert policy["spatial_aberration"]["observer_beta_held_fixed"] is True
    assert (
        policy["spatial_aberration"]["longitude_speed_correction"]
        == corrected["longitude_speed_spatial_aberration_correction"]
    )
    assert (
        "Complete moving-frame derivatives, native binary identity" in policy["scope"]
    )
    from fatebridge.core.astro.native_motion import context_motion
    from fatebridge.core.local_techniques.otherbu import _motion_snapshot_line

    motion = context_motion(
        "Moon",
        {"Moon": corrected["longitude_speed"]},
        {"Moon": model},
        "tropical_ecliptic_of_date",
        corrected,
    )
    line = _motion_snapshot_line({"id": "Moon", "motion": motion})
    assert (
        f"空间光行差修正 {corrected['longitude_speed_spatial_aberration_correction']} 度/日"
        in line
    )
    assert (
        f"月球固定框架源导数余项 {corrected['longitude_speed_lunar_source_remainder_correction']} 度/日"
        in line
    )

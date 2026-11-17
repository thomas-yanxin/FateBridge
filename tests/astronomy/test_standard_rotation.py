"""Independent published-IERS arithmetic; no physical frame certification."""

import gzip
import hashlib
import json
import math
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime
from fatebridge.core.astro import runtime
from fatebridge.core.astro.iers_ut1 import use_ut1_source
from fatebridge.core.astro.reference_frames import (
    iau_equatorial_frame,
    native_equatorial_frame,
)
from fatebridge.core.astro_models import frame_gast, iers2010_gast

REFERENCE = json.loads(
    gzip.decompress(
        (
            Path(__file__).parents[1] / "data/rotation_iers2010_v1/reference.json.gz"
        ).read_bytes()
    )
)
FRAME_REFERENCE = json.loads(
    gzip.decompress(
        (
            Path(__file__).parents[1] / "data/rotation_frame_v1/reference.json.gz"
        ).read_bytes()
    )
)
PHYSICAL_REFERENCE = json.loads(
    gzip.decompress(
        (
            Path(__file__).parents[1] / "data/earth_attitude_v1/reference.json.gz"
        ).read_bytes()
    )
)


def test_published_decimal_expression_is_no_worse_than_common_input_ERFA():
    assert REFERENCE["production_imported"] is False
    assert REFERENCE["precision_decimal_digits"] == 90
    assert REFERENCE["original_gast_gate_arcseconds"] == 0.001
    assert REFERENCE["IERS_source_sha256"] == (
        "a5c690b277108e35d88df9cc20fea4120dfbc10a81444bb41b15cf9c6edcd6cb"
    )
    assert hashlib.sha256(REFERENCE["generator_source"].encode()).hexdigest() == (
        REFERENCE["generator_sha256"]
    )
    rows = REFERENCE["rows"]
    assert len(rows) == 514
    assert {(row["index"], row["input_family"]) for row in rows} == {
        (index, family)
        for index in REFERENCE["reference_plan"]["high_precision_control_indices"]
        for family in ("IAU_inputs", "native_inputs")
    }
    with localcontext() as context:
        context.prec = 90
        for row in rows:
            actual = iers2010_gast(
                row["jd_ut1"],
                row["jd_tt"],
                row["nutation_longitude_degrees"],
                row["mean_obliquity_degrees"],
            )
            errors = []
            for value in (actual, row["ERFA_common_gast_degrees"]):
                difference = Decimal.from_float(value) - Decimal(
                    row["published_expression_gast_degrees"]
                )
                if difference > 180:
                    difference -= 360
                elif difference < -180:
                    difference += 360
                errors.append(abs(difference) * 3600)
            assert errors[0] <= Decimal("0.001"), row
            assert errors[0] <= errors[1], (row, errors)


def test_same_NPB_origins_and_ERA_are_no_worse_than_common_input_ERFA():
    reference = FRAME_REFERENCE
    assert reference["production_imported"] is False
    assert reference["precision_decimal_digits"] == 90
    assert reference["original_gate_arcsec"] == 0.001
    assert len(reference["parsed_S06_terms"]) == 66
    assert hashlib.sha256(reference["generator_source"].encode()).hexdigest() == (
        reference["generator_sha256"]
    )
    rows = reference["rows"]
    assert len(rows) == 514
    assert sum(r["degree_format_limited_vs_native_radian"] for r in rows) == 4
    assert {(r["index"], r["input_family"]) for r in rows} == {
        (i * 146100 // 256, family)
        for i in range(257)
        for family in ("native", "full_IAU")
    }
    with localcontext() as context:
        context.prec = 90
        for row in rows:
            matrix = tuple(tuple(r) for r in row["NPB"])
            actual = frame_gast(row["jd_ut1"], row["jd_tt"], matrix)
            assert 0 <= actual < 360
            errors = []
            for value in (actual, row["ERFA_common_gast_degrees"]):
                difference = Decimal.from_float(value) - Decimal(
                    row["ideal_gast_degrees"]
                )
                if difference > 180:
                    difference -= 360
                elif difference < -180:
                    difference += 360
                errors.append(abs(difference) * 3600)
            assert errors[0] <= Decimal("0.001"), row
            assert errors[0] <= errors[1], (row, errors)


def test_native_frame_matches_original_author_C_axes_and_boundary_shortcuts():
    reference = FRAME_REFERENCE
    assert reference["native_clock_source"]["production_imported"] is False
    assert reference["native_clock_source"]["source_library_sha256"] == (
        reference["frame_input_metadata"]["source_library_sha256"]
    )
    clocks = reference["native_clock_rows"]
    boundaries = reference["native_frame_boundary_rows"]
    assert len(clocks) == 257 and len(boundaries) == 18
    for row in clocks + boundaries:
        _, epsilon, dpsi, deps = row["native_ECL_NUT"]
        actual = native_equatorial_frame(row["jd_tt"], epsilon, dpsi, deps)
        expected = row["native_NPB"] if "native_NPB" in row else row["NPB"]
        for column in range(3):
            chord = math.sqrt(
                math.fsum(
                    (actual[i][column] - expected[i][column]) ** 2 for i in range(3)
                )
            )
            assert math.degrees(2 * math.asin(chord / 2)) * 3600 <= 0.001, row


def test_managed_rotation_uses_matching_frame_and_clock_without_ephemeris_files(
    monkeypatch, tmp_path
):
    rows = PHYSICAL_REFERENCE["epochs"]
    assert len(rows) == 257
    previous = ephemeris_runtime.configured_ephemeris_path()
    try:
        with monkeypatch.context() as patch, use_ut1_source("swiss_delta_t"):
            patch.setenv("SE_EPHE_PATH", str(tmp_path))
            ephemeris_runtime.configure_ephemeris_path(str(tmp_path))
            for row in rows:
                actual = ephemeris_runtime.ephemeris_call("sidtime", row["jd_ut1"]) * 15
                error = (
                    abs(math.remainder(actual - row["SOFA_GAST_degrees"], 360)) * 3600
                )
                assert error <= 0.001, row
    finally:
        ephemeris_runtime.configure_ephemeris_path(previous or "")


def test_physical_equator_matches_unmodified_official_SOFA_axes():
    data = gzip.decompress(
        (
            Path(__file__).parents[1] / "data/earth_attitude_v1/reference.json.gz"
        ).read_bytes()
    )
    assert hashlib.sha256(data).hexdigest() == (
        "d4c935492bf7a2fe04995515588194f4586e77086a4636b21aea7393016fb2f7"
    )
    reference = PHYSICAL_REFERENCE
    assert reference["production_imported"] is False
    assert reference["gate_arcseconds"] == 0.001
    assert reference["epoch_count"] == len(reference["epochs"]) == 257
    for name, source in reference["generator_sources"].items():
        assert (
            hashlib.sha256(source.encode()).hexdigest()
            == reference["generator_hashes"][name]
        )
    for row in reference["epochs"]:
        actual = iau_equatorial_frame(row["jd_tt"])
        expected = row["SOFA_NPB"]
        for column in range(3):
            chord = math.sqrt(
                math.fsum(
                    (actual[i][column] - expected[i][column]) ** 2 for i in range(3)
                )
            )
            assert math.degrees(2 * math.asin(chord / 2)) * 3600 <= 0.001, row


def test_selected_house_kernels_share_the_physical_pole_and_source_ecliptic(
    monkeypatch,
):
    """Common frozen Sun input isolates geometry from ephemeris availability."""
    reference = PHYSICAL_REFERENCE
    cases = reference["house_cases"]
    assert len(cases) == reference["house_case_count"] == 6624
    assert len({case["house_code"] for case in cases}) == 23
    actual_call = ephemeris_runtime.ephemeris_call
    epoch = reference["epochs"][0]

    def common_source(operation, *args, **kwargs):
        if operation == "calc" and args[1] == runtime.swe.SUN:
            assert args[0] == epoch["jd_tt"]
            assert args[2] == runtime.swe.FLG_SWIEPH | runtime.swe.FLG_EQUATORIAL
            return (
                (*epoch["source_equatorial_Sun"], 0.0, 0.0, 0.0),
                runtime.swe.FLG_SWIEPH | runtime.swe.FLG_EQUATORIAL,
            )
        return actual_call(operation, *args, **kwargs)

    monkeypatch.setattr(ephemeris_runtime, "ephemeris_call", common_source)
    with runtime.preserve_ephemeris_path(), use_ut1_source("swiss_delta_t"):
        runtime.swe.set_sid_mode(runtime.swe.SIDM_LAHIRI, 0, 0)
        for case in cases:
            epoch = reference["epochs"][case["epoch"]]
            args = (
                "houses_ex",
                epoch["jd_ut1"],
                case["latitude"],
                case["longitude"],
                case["house_code"].encode(),
                runtime.swe.FLG_SIDEREAL if case["sidereal"] else 0,
            )
            if case["original_return_code"] < 0:
                with pytest.raises(runtime.swe.Error):
                    common_source(*args, _julian_day_tt=epoch["jd_tt"])
                continue
            cusps, angles = common_source(*args, _julian_day_tt=epoch["jd_tt"])
            actual = (*cusps, *angles)
            assert len(actual) == len(case["values"]) == 20
            assert (
                max(
                    abs(math.remainder(value - expected, 360)) * 3600
                    for value, expected in zip(actual, case["values"])
                )
                <= reference["gate_arcseconds"]
            ), case

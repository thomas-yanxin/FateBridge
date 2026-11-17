"""Independent ERFA primitives and native source-frame reduction witnesses."""

import hashlib
import json
import math
from pathlib import Path

import pytest

from fatebridge.core.astro import reference_frames

REFERENCE = json.loads(
    (
        Path(__file__).parents[1] / "fixtures/native-longterm-frame-reference-v1.json"
    ).read_text()
)
AUTHOR_FRAME = json.loads(
    (
        Path(__file__).parents[1] / "fixtures/native-source-frame-reference-v1.json"
    ).read_text()
)


def test_native_frame_reference_preserves_all_frozen_author_cases():
    assert AUTHOR_FRAME["production_imported"] is False
    assert AUTHOR_FRAME["source_commit"] == "696bda432298d482d27e67a0cf1238920301a7dd"
    assert AUTHOR_FRAME["physical_accuracy_or_continuous_domain_certified"] is False
    assert AUTHOR_FRAME["coordinate_model_gate"] == "1e-10"
    expected = {
        (epoch, frame)
        for epoch in AUTHOR_FRAME["case_plan"]["epochs"]
        for frame in AUTHOR_FRAME["case_plan"]["frames"]
    }
    assert len(expected) == len(AUTHOR_FRAME["rows"]) == 734
    assert {(row["jd_tt"], row["frame"]) for row in AUTHOR_FRAME["rows"]} == expected
    generator = (
        Path(__file__).parents[2] / "scripts/astronomy/build_native_frame_reference.py"
    )
    assert (
        hashlib.sha256(generator.read_bytes()).hexdigest()
        == AUTHOR_FRAME["generator_sha256"]
    )


@pytest.mark.parametrize("sidereal", [False, True])
def test_native_frame_composition_matches_original_C_unit_axis_operations(sidereal):
    for row in AUTHOR_FRAME["rows"]:
        if (row["frame"] == "lahiri") != sidereal:
            continue
        true_epsilon, mean_epsilon, psi, deps = row["ECL_NUT_degrees"]
        matrix = reference_frames.mm(
            reference_frames.ecliptic_rotation(
                math.radians(mean_epsilon if sidereal else true_epsilon)
            )[0],
            reference_frames.native_equatorial_frame(
                row["jd_tt"],
                mean_epsilon,
                0.0 if sidereal else psi,
                0.0 if sidereal else deps,
            ),
        )
        if sidereal:
            angle = math.radians(row["mean_Lahiri_ayanamsa_degrees"])
            c, s = math.cos(angle), math.sin(angle)
            matrix = reference_frames.mm(
                ((c, s, 0.0), (-s, c, 0.0), (0.0, 0.0, 1.0)), matrix
            )
        for actual, expected_row in zip(
            matrix, row["original_C_ICRS_to_display_matrix"]
        ):
            assert actual == pytest.approx(expected_row, abs=1e-10, rel=0), (
                row["jd_tt"],
                row["frame"],
            )


@pytest.mark.parametrize("row", REFERENCE["rows"], ids=lambda row: str(row["jd_tt"]))
def test_longterm_precession_and_frame_bias_match_independent_erfa(row):
    assert REFERENCE["production_imported"] is False
    actual, _ = reference_frames.precession(row["jd_tt"])
    for actual_row, expected_row in zip(actual, row["erfa_mean_j2000_precession"]):
        assert actual_row == pytest.approx(expected_row, abs=2e-14, rel=0)
    for actual_row, expected_row in zip(
        reference_frames.icrs_to_mean_j2000(), row["erfa_iau2006_bias"]
    ):
        assert actual_row == pytest.approx(expected_row, abs=1e-15, rel=0)


@pytest.mark.parametrize("row", REFERENCE["rows"], ids=lambda row: str(row["jd_tt"]))
def test_native_ecliptic_reduction_matches_independent_coordinates(row):
    actual = reference_frames.native_apparent_ecliptic(
        row["input_icrs_vector"], row["jd_tt"]
    )
    assert actual == pytest.approx(
        row["expected_apparent_ecliptic_vector"], abs=1e-12, rel=0
    )
    longitude = math.degrees(math.atan2(actual[1], actual[0])) % 360
    error = math.remainder(longitude - row["native_apparent_longitude_degrees"], 360)
    assert abs(error) * 3600 < 1e-7

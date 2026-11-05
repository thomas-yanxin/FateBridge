"""Unchanged vector-plane references qualify the integrated R/C provider."""

import gzip
import hashlib
import json
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pytest
from mpmath import mp

from fatebridge.core.astro import house_positions
from fatebridge.core.astro.house_positions import EclipticHouseProjection
from fatebridge.core.astro.house_projection_precision import RC_PLANE_PROJECTION_METHOD
from fatebridge.core.predictive.native_chart import build_native_subject
from fatebridge.utils.errors import EphemerisSourceError

FIXTURE = Path(__file__).parents[1] / "data/astro/house_projection_precision"
MODELS = json.loads((FIXTURE / "inputs.json").read_text())["cases"]


def test_all_frozen_plane_phase_and_membership_probes():
    assert (
        hashlib.sha256((FIXTURE / "inputs.json").read_bytes()).hexdigest()
        == "722c9c5924a97552b92342e1768ad7ffd4a05487b4afb41f7436bbf051f9333a"
    )
    assert (
        hashlib.sha256((FIXTURE / "reference.jsonl.gz").read_bytes()).hexdigest()
        == "111ab78c0fee6aa03069a84f49b7ca63ea922fc21f08635750b99bfcc9e023ed"
    )
    projectors = {
        (m["id"], code): EclipticHouseProjection(
            m["armc"], m["latitude"], m["obliquity"], code.encode()
        )
        for m in MODELS
        for code in ("R", "C")
    }
    count = 0
    failures = []
    with gzip.open(FIXTURE / "reference.jsonl.gz", "rt") as stream:
        for line in stream:
            row = json.loads(line)
            actual = projectors[row["model_id"], row["code"]].position(row["longitude"])
            error = (
                abs(
                    ((actual - 1) * 30 - float(row["shifted_phase_degrees"]) + 180)
                    % 360
                    - 180
                )
                * 3600
            )
            if error > 1 or math.floor(actual) != row["house"]:
                failures.append((row["id"], actual, error, row["house"]))
            count += 1
    assert count == 53568
    assert not failures, failures[:20]
    for projection in projectors.values():
        metadata = projection.metadata()
        assert metadata["method"] == RC_PLANE_PROJECTION_METHOD
        assert len(metadata["precision"]["checks"]) == 48
        for check in metadata["precision"]["checks"]:
            assert check["house"] == math.floor(check["delivered_position"])
            assert check["working_decimal_digits"] == [80, 120]
        assert metadata["precision"]["maximum_physical_error_arcseconds"] is None


def test_contexts_and_record_lists_are_private():
    m = MODELS[0]
    initial = mp.prec

    def solve(_):
        projection = EclipticHouseProjection(
            m["armc"], m["latitude"], m["obliquity"], b"R"
        )
        result = projection.position(182.51339850163603)
        return result, projection.metadata()

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(solve, range(16)))
    assert all(result == results[0] for result in results)
    assert mp.prec == initial
    assert all(len(result[1]["precision"]["checks"]) == 1 for result in results)


def test_precision_failure_is_not_an_unregistered_reason_or_a_default_house(
    monkeypatch,
):
    def fail(**kwargs):
        raise ArithmeticError("injected convergence failure")

    monkeypatch.setattr(house_positions, "checked_house_plane_position", fail)
    m = MODELS[0]
    with pytest.raises(EphemerisSourceError) as raised:
        EclipticHouseProjection(
            m["armc"], m["latitude"], m["obliquity"], b"R"
        ).position(0.0)
    assert raised.value.reason == "house_projection_precision_unavailable"
    assert raised.value.as_result()["status_code"] == 503


def test_regiomontanus_geographic_pole_is_still_an_open_method_boundary():
    projection = EclipticHouseProjection(15.0, 90.0, 23.4, b"R")
    native = house_positions.runtime.ephemeris_call(
        "house_pos", 15.0, 90.0, 23.4, (45.0, 0.0), b"R"
    )
    assert projection.position(45.0) == native
    metadata = projection.metadata()
    assert metadata["method"] == house_positions.NATIVE_PROJECTION_METHOD
    assert (
        metadata["precision"]["status"]
        == "native_geographic_pole_convention_not_requalified"
    )
    assert metadata["precision"]["checks"][0]["working_decimal_digits"] == []


@pytest.mark.parametrize("code", ["R", "C"])
def test_derived_point_projection_uses_original_tropical_input_before_display_rotation(
    code,
):
    case = MODELS[0]
    subjects = [
        build_native_subject(
            name="derived frame numerical control",
            local_datetime=datetime(case["year"], 1, 1, 0, 30, tzinfo=timezone.utc),
            longitude=case["longitude"],
            latitude=case["latitude"],
            timezone_name="UTC",
            house_system=code,
            zodiac_type=zodiac,
        )
        for zodiac in ["Tropic", "Sidereal"]
    ]
    assert subjects[0].medium_coeli.house == subjects[1].medium_coeli.house
    traces = [
        s.calculation_basis["house_position_projection"]["precision"]["checks"]
        for s in subjects
    ]
    assert [r["tropical_longitude"] for r in traces[0]] == [
        r["tropical_longitude"] for r in traces[1]
    ]
    assert [r["delivered_position"] for r in traces[0]] == [
        r["delivered_position"] for r in traces[1]
    ]

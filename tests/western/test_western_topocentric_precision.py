"""Frozen vector references qualify the unclipped, scalar T inverse."""

import gzip
import hashlib
import json
import math
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

import pytest
from mpmath import mp

from fatebridge.core.astro import house_positions
from fatebridge.core.astro.house_positions import EclipticHouseProjection
from fatebridge.core.astro.topocentric_precision import TOPOCENTRIC_PROJECTION_METHOD
from fatebridge.utils.errors import EphemerisSourceError

FIXTURE = Path(__file__).parents[1] / "data/astro/topocentric_precision"
MODELS = json.loads((FIXTURE / "inputs.json").read_text())["cases"]
BY_ID = {m["id"]: m for m in MODELS}
BOUNDARIES = json.loads((FIXTURE / "candidate-boundary-reference.json").read_text())[
    "rows"
]
BOUNDARY_MODELS = {
    m["id"]: m
    for m in json.loads((FIXTURE / "candidate-boundary-inputs.json").read_text())[
        "cases"
    ]
}


def phase_error(position, row):
    return (
        abs(((position - 1) * 30 - float(row["phase_degrees"]) + 180) % 360 - 180)
        * 3600
    )


@lru_cache(maxsize=1)
def legacy_references():
    """Expected values come only from the sealed pre-production vector file."""
    result = {}
    with gzip.open(FIXTURE / "reference.jsonl.gz", "rt") as stream:
        for row in map(json.loads, stream):
            if row["probe"].startswith("legacy-query-") and row["status"] == "defined":
                model = BY_ID[row["model_id"]]
                key = (
                    model["latitude"],
                    model["armc"],
                    model["obliquity"],
                    row["longitude"],
                )
                if key in result:
                    assert result[key]["phase_degrees"] == row["phase_degrees"]
                result[key] = row
    return result


@lru_cache(maxsize=1)
def clamp_references():
    result = {}
    with gzip.open(FIXTURE / "reference.jsonl.gz", "rt") as stream:
        for row in map(json.loads, stream):
            model = BY_ID[row["model_id"]]
            if model.get("origin") == "predeclared_native_clamp_boundary" and row[
                "probe"
            ].startswith("fixed-"):
                result[(model["latitude"], model["armc"], row["longitude"])] = row
    return result


@pytest.mark.parametrize("latitude", [-89.9999, -89.999999, 89.9999, 89.999999])
def test_original_latitude_is_used_beyond_the_native_plateau(latitude):
    armc = 120.0 if latitude > 0 else 300.0
    values = []
    native = []
    for lat in (math.copysign(89.999, latitude), latitude):
        projection = EclipticHouseProjection(armc, lat, 23.4392911, b"T")
        value = projection.position(30.0)
        row = clamp_references()[(lat, armc, 30.0)]
        assert phase_error(value, row) <= 1 and math.floor(value) == row["house"]
        check = projection._precision_records[0]
        assert check["topocentric_branch"]["geographic_latitude_used"] == lat
        values.append(value)
        native.append(check["native_position"])
    assert native[0] == native[1]  # Controlled demonstration of the old clip.
    assert abs(values[0] - values[1]) * 30 * 3600 > 1


def test_all_frozen_t_phase_membership_and_branch_probes():
    assert (
        hashlib.sha256((FIXTURE / "inputs.json").read_bytes()).hexdigest()
        == "e56bc0807d88f1cc58cad7f3df1ca7bda25ae773e31d66a66d1bc3abd325a633"
    )
    assert (
        hashlib.sha256((FIXTURE / "reference.jsonl.gz").read_bytes()).hexdigest()
        == "6577fa04a4f9b96c403bfc76e72ae9bdbf68faabe0616fab30ce8fe4b5467035"
    )
    projectors = {
        m["id"]: EclipticHouseProjection(m["armc"], m["latitude"], m["obliquity"], b"T")
        for m in MODELS
    }
    counts = Counter()
    failures = []
    with gzip.open(FIXTURE / "reference.jsonl.gz", "rt") as stream:
        for row in map(json.loads, stream):
            projection = projectors[row["model_id"]]
            actual = projection.position(row["longitude"])
            counts[row["status"]] += 1
            check = projection._precision_records[-1]
            if row["status"] != "defined":
                assert actual == check["native_position"]
                assert check["working_decimal_digits"] == []
                continue  # Retained conventions are not numerical passes.
            branch = check["topocentric_branch"]
            assert check["tropical_longitude"] == row["longitude"]
            if phase_error(actual, row) > 1 or math.floor(actual) != row["house"]:
                failures.append(
                    (row["id"], actual, row["house"], phase_error(actual, row))
                )
            assert branch["above_horizon"] == row["above_horizon"]
            assert branch["reflected_western"] == row["reflected_western"]
            assert branch["root_selection"] == row["root_selection"]
            assert (
                branch["geographic_latitude_used"] == BY_ID[row["model_id"]]["latitude"]
            )
            assert branch["latitude_clamped"] is False
            assert len(branch["candidate_root_degrees"]) == len(
                row["candidate_root_degrees"]
            )
            assert check["working_decimal_digits"] == [80, 120]
    assert counts == {
        "defined": 61056,
        "native_geographic_pole_convention_not_requalified": 2208,
    }
    assert not failures, failures[:20]
    for model_id, projection in projectors.items():
        metadata = projection.metadata()
        assert metadata["precision"]["maximum_physical_error_arcseconds"] is None
        if abs(BY_ID[model_id]["latitude"]) == 90:
            assert metadata["method"] == house_positions.NATIVE_PROJECTION_METHOD
            assert (
                metadata["precision"]["status"]
                == "native_geographic_pole_convention_not_requalified"
            )
            assert metadata["precision"]["latitude_clamped"] is None
        else:
            assert metadata["method"] == TOPOCENTRIC_PROJECTION_METHOD
            assert metadata["precision"]["latitude_clamped"] is False


@pytest.mark.parametrize(
    "row", BOUNDARIES, ids=lambda r: f"{r['model_id']}-{r['longitude']}"
)
def test_exact_endpoint_alternatives_are_retained_and_selected_explicitly(row):
    model = BOUNDARY_MODELS[row["model_id"]]
    projection = EclipticHouseProjection(
        model["armc"], model["latitude"], model["obliquity"], b"T"
    )
    actual = projection.position(row["longitude"])
    assert phase_error(actual, row) <= 1 and math.floor(actual) == row["house"]
    metadata = projection.metadata()
    branch = metadata["precision"]["checks"][0]["topocentric_branch"]
    assert branch["root_selection"] == row["root_selection"]
    assert branch["selected_root_degrees"] == float(row["selected_root_degrees"])
    assert branch["candidate_root_degrees"] == [
        float(x) for x in row["candidate_root_degrees"]
    ]
    assert branch["candidate_positions"] == row["candidate_positions"]
    assert metadata["precision"]["status"] == (
        "supplied_model_checked_with_boundary_candidates"
        if len(row["candidate_positions"]) > 1
        else "supplied_model_checked"
    )


def test_private_precision_contexts_and_records():
    initial = mp.prec

    def solve(_):
        projection = EclipticHouseProjection(30.0, 89.999999, 23.4392911, b"T")
        return projection.position(60.0), projection.metadata()

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(solve, range(16)))
    assert all(r == results[0] for r in results)
    assert mp.prec == initial
    assert all(len(r[1]["precision"]["checks"]) == 1 for r in results)


def test_t_precision_failure_is_a_registered_source_error(monkeypatch):
    def fail(**kwargs):
        raise ArithmeticError("injected T inverse failure")

    monkeypatch.setattr(house_positions, "checked_topocentric_position", fail)
    with pytest.raises(EphemerisSourceError) as caught:
        EclipticHouseProjection(30.0, 89.999999, 23.4392911, b"T").position(60.0)
    assert caught.value.reason == "house_projection_precision_unavailable"
    assert caught.value.as_result()["status_code"] == 503

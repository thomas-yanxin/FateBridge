"""Frozen independent source allocation and exact final-scalar arithmetic."""

import gzip
import hashlib
import json
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.astrology_tables import SIGNS
from fatebridge.core.jyotish import GRAHAS, divisional_chart
from fatebridge.core.jyotish_kala import nathonnatha
from fatebridge.core.jyotish_mean import mean_longitudes
from fatebridge.core.jyotish_vargas import (
    varga_coordinates,
    varga_longitude,
    varga_sign,
)

FIXTURE = Path(__file__).parents[1] / "data/jyotish_varga_flint_v1"
RAW = gzip.decompress((FIXTURE / "source.json.gz").read_bytes())
REFERENCE = json.loads(RAW)
DIVISIONS = (1, 2, 3, 7, 9, 10, 12, 30)
COMPLEMENT_FIXTURE = Path(__file__).parents[1] / "data/jyotish_complement_flint_v1"
COMPLEMENT_RAW = gzip.decompress((COMPLEMENT_FIXTURE / "source.json.gz").read_bytes())
COMPLEMENT_REFERENCE = json.loads(COMPLEMENT_RAW)


def test_frozen_reference_integrity_and_complete_declared_scope():
    assert (
        hashlib.sha256(RAW).hexdigest()
        == (FIXTURE / "source.json.sha256").read_text().strip()
    )
    provenance = REFERENCE["provenance"]
    assert provenance["python_flint"] == "0.9.0"
    assert provenance["flint"] == "3.6.0"
    assert provenance["reference_imports_project"] is False
    assert provenance["uses_fraction_or_fmpq_float"] is False
    assert (
        provenance["source_table_sha256"]
        == hashlib.sha256((FIXTURE / "source-tables.json").read_bytes()).hexdigest()
    )
    assert (
        provenance["criteria_sha256"]
        == hashlib.sha256((FIXTURE / "criteria.json").read_bytes()).hexdigest()
    )
    for name, count in (("development", 13498), ("validation", 1280)):
        data = REFERENCE["datasets"][name]
        assert data["divisions"] == list(DIVISIONS)
        assert len(data["cases"]) == count


@pytest.mark.parametrize("dataset", ["development", "validation"])
@pytest.mark.parametrize("division", DIVISIONS)
def test_every_frozen_component_matches_independent_reference(dataset, division):
    for row in REFERENCE["datasets"][dataset]["cases"]:
        encoded = row["value"]
        value = (
            float.fromhex(encoded["hex"])
            if encoded["kind"] == "float"
            else Fraction(int(encoded["numerator"]), int(encoded["denominator"]))
        )
        expected = row["expected"][str(division)]
        sign, degree = varga_coordinates(value, division)
        assert sign == expected["sign"], row["id"]
        assert varga_sign(value, division) == expected["sign"], row["id"]
        assert (None if degree is None else degree.hex()) == expected[
            "degree_hex"
        ], row["id"]
        if division == 30:
            with pytest.raises(ValueError, match="D30"):
                varga_longitude(value, division)
        else:
            assert (
                varga_longitude(value, division).hex() == expected["longitude_hex"]
            ), row["id"]


@pytest.mark.parametrize("function", [varga_coordinates, varga_longitude, varga_sign])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_inputs_remain_explicit_errors(function, value):
    for division in DIVISIONS:
        with pytest.raises(ValueError, match="有限"):
            function(value, division)


@pytest.mark.parametrize("function", [varga_coordinates, varga_longitude, varga_sign])
@pytest.mark.parametrize("division", [-1, 0, 4, 60])
def test_unsupported_divisions_never_fall_back(function, division):
    with pytest.raises(ValueError, match="D1"):
        function(23.0, division)


@pytest.mark.parametrize("division", DIVISIONS)
def test_real_chart_consumer_preserves_original_counterexample(division):
    row = next(
        row
        for row in REFERENCE["datasets"]["development"]["cases"]
        if row["id"] == "development-23"
    )
    value = float.fromhex(row["value"]["hex"])
    expected = row["expected"][str(division)]
    chart = divisional_chart(
        {"ascendant": value, "longitudes": dict.fromkeys(GRAHAS, value)}, division
    )
    for point in (chart["ascendant"], *chart["planets"]):
        assert point["sign"] == SIGNS[expected["sign"]]
        assert (
            None if point["longitude"] is None else point["longitude"].hex()
        ) == expected["longitude_hex"]
    if division == 30:
        assert all(
            point["degree_in_sign"] is None
            for point in (chart["ascendant"], *chart["planets"])
        )


def test_frozen_complement_reference_integrity_and_complete_scope():
    assert (
        hashlib.sha256(COMPLEMENT_RAW).hexdigest()
        == (COMPLEMENT_FIXTURE / "source.json.sha256").read_text().strip()
    )
    provenance = COMPLEMENT_REFERENCE["provenance"]
    assert provenance["python_flint"] == "0.9.0"
    assert provenance["flint"] == "3.6.0"
    assert provenance["imports_product"] is False
    assert provenance["uses_fraction_or_fmpq_float_for_expected"] is False
    criteria_raw = (COMPLEMENT_FIXTURE / "criteria.json").read_bytes()
    assert hashlib.sha256(criteria_raw).hexdigest() == provenance["criteria_sha256"]
    criteria = json.loads(criteria_raw)
    for name, expected in criteria["source_sha256"].items():
        assert hashlib.sha256((COMPLEMENT_FIXTURE / name).read_bytes()).hexdigest() == (
            expected
        )
    for family, development_count in (("mean", 12067), ("natha", 10716)):
        for dataset, count in (
            ("development", development_count),
            ("validation", 2000),
        ):
            data = COMPLEMENT_REFERENCE["families"][family][dataset]
            assert data["family"] == family and data["dataset"] == dataset
            assert len(data["cases"]) == count
            assert count == criteria["inputs"][family + "_" + dataset]["cases"]


@pytest.mark.parametrize("family", ["mean", "natha"])
@pytest.mark.parametrize("dataset", ["development", "validation"])
def test_all_exact_complements_match_independent_reference(family, dataset):
    for row in COMPLEMENT_REFERENCE["families"][family][dataset]["cases"]:
        actual = (
            mean_longitudes(float.fromhex(row["jd_hex"]))
            if family == "mean"
            else nathonnatha(
                float.fromhex(row["meridian_hex"]),
                float.fromhex(row["sun_ra_hex"]),
            )
        )
        assert {name: value.hex() for name, value in actual.items()} == row[
            "expected_hex"
        ], row["id"]

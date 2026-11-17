"""Fixed independent Arb/FLINT arithmetic reference; no native astronomy needed."""

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.human_design_interval_geometry import (
    _add,
    _Arithmetic,
    _ceil,
    _divide_integer,
    _neg,
    _scale,
    _sub,
)
from fatebridge.core.human_design_solar_projection import nominal_solar_projection


@pytest.fixture(scope="module")
def reference():
    folder = Path(__file__).resolve().parents[1] / "data/human_design_interval_flint_v1"
    raw = gzip.decompress((folder / "source.json.gz").read_bytes())
    digest = hashlib.sha256(raw).hexdigest()
    assert digest == (folder / "source.json.sha256").read_text().strip()
    assert digest == "a11c3956c08a62adb4dfc8ec7a43ce809c798c126a703d63c06c30c0c32b0d67"
    return json.loads(raw)


def test_all354_arb_geometry_values_and_classifications(reference):
    rows = reference["geometry"]
    assert len(rows) == 354
    assert sum(row["analytic_degenerate_glue"] is not None for row in rows) == 66
    for row in rows:
        actual = nominal_solar_projection(row["sun"], row["target"])
        for key, expected in row["rounded_hex"].items():
            assert actual[key].hex() == expected, (row["id"], key)
        assert actual["projection_relation"] == row["relation"], row["id"]
        assert actual["physical_accuracy_certified"] is False


def test_all320_flint_exact_interval_primitive_cases(reference):
    rows = reference["primitives"]
    assert len(rows) == 320
    for row in rows:
        arithmetic = _Arithmetic(row["bits"])
        a, b = tuple(row["a"]), tuple(row["b"])
        n, d, factor = (row[key] for key in ("n", "d", "factor"))
        actual = {
            "ceil": _ceil(n, d),
            "add": _add(a, b),
            "neg": _neg(a),
            "sub": _sub(a, b),
            "scale": _scale(a, factor),
            "divide_integer": _divide_integer(a, d),
            "rational": arithmetic.rational(n, d),
            "multiply": arithmetic.multiply(a, b),
            "square": arithmetic.square(a),
            "divide": arithmetic.divide(a, b),
            # The frozen reference explicitly restricts sqrt to this domain.
            "sqrt": arithmetic.sqrt((max(0, a[0]), max(0, a[1]))),
        }
        assert len(actual) == len(row["expected"]) == 11
        for key, expected in row["expected"].items():
            observed = actual[key]
            assert (
                list(observed) if isinstance(observed, tuple) else observed
            ) == expected, (
                row["id"],
                key,
            )

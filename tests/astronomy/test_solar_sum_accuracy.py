"""Exact sums of rounded terms; original orbit and author gates stay separate."""

import ast
import gzip
import hashlib
import inspect
import json
import math
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core import analytic_solar, de440_solar

FIXTURE = Path(__file__).parents[1] / "fixtures/meihua_sum_v75"


def exact_sum(terms):
    total = Fraction(0)
    for value in terms:
        total += Fraction(value)
    return float(total)


def model_evaluation(reference):
    values = []
    for row in reference["longitudes"]:
        day, fraction = [float.fromhex(x) for x in row["parts"]]
        values.append(
            {
                "parts": row["parts"],
                "de440_parts": de440_solar.solar_longitude_parts(day, fraction),
                "de440_scalar": de440_solar.solar_longitude(day + fraction),
                "analytic_scalar": analytic_solar.solar_longitude(day + fraction),
            }
        )
    return {
        "longitudes": values,
        "root": de440_solar.longitude_crossing_tt_parts(345.0, 2451604.5, 2451615.5),
    }


def test_frozen_exact_term_corpus_is_not_a_production_generated_expected_value() -> (
    None
):
    freeze = json.loads((FIXTURE / "reference-freeze.json").read_text())
    raw = (FIXTURE / "exact-term-sums.json.gz").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "2658166b3bbb953aeb844557adce5d3269593c65c15ea37ce9287c0eff9a4558"
    )
    assert hashlib.sha256(gzip.decompress(raw)).hexdigest() == (
        "65b26f34a41ba1c51568a2f2a6fbfe0f2f7c09528869c96d8bd193b51ce44248"
    )
    assert freeze["before_production_modification"]
    assert not freeze["rational_expected_values_from_production"]
    assert freeze["real_trace_distinct_operand_sets"] == 5069
    assert freeze["literal_controls"] == 33
    assert freeze["required_records"] == 5102
    assert freeze["new_real_outcomes"] == 0


def test_actual_model_sums_match_exact_terms_and_keep_analytic_outputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reference = json.loads((FIXTURE / "reference-model-outputs.json").read_text())[
        "reference"
    ]
    accurate = math.fsum
    modules = (analytic_solar, de440_solar)
    paths = {str(Path(module.__file__).resolve()) for module in modules}
    seen = set()

    def checked(values):
        terms = list(values)
        result = accurate(terms)
        caller = inspect.currentframe().f_back
        filename = str(Path(caller.f_code.co_filename).resolve())
        if filename in paths:
            assert result == exact_sum(terms)
            seen.add((filename, caller.f_lineno))
        else:
            pass
        return result

    def version_dependent_sum(*args, **kwargs):
        raise AssertionError("Solar terms must not inherit interpreter-dependent sum")

    for module in modules:
        monkeypatch.setattr(module, "sum", version_dependent_sum, raising=False)
    monkeypatch.setattr(math, "fsum", checked)
    actual = model_evaluation(reference)
    # Keep the original arguments and unchanged analytic model outputs. The
    # historical DE440 raw snapshot is retained; independent source controls
    # own record selection and interpolation accuracy after operator changes.
    assert [(row["parts"], row["analytic_scalar"]) for row in actual["longitudes"]] == [
        (row["parts"], row["analytic_scalar"]) for row in reference["longitudes"]
    ]
    required = set()
    for filename in paths:
        for node in ast.walk(ast.parse(Path(filename).read_text())):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "math"
                and node.func.attr == "fsum"
            ):
                required.add((filename, node.lineno))
            else:
                pass
    assert seen == required

"""Exact sums of rounded terms; original orbit and author gates stay separate."""

import ast
import gzip
import hashlib
import inspect
import json
import math
from fractions import Fraction
from pathlib import Path

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


def test_frozen_exact_term_corpus_is_not_a_production_generated_expected_value():
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


def test_all_frozen_real_terms_and_cancellation_controls_match_exact_rationals():
    rows = json.loads(
        gzip.decompress((FIXTURE / "exact-term-sums.json.gz").read_bytes())
    )
    assert len(rows) == 5102
    for row in rows:
        terms = [float.fromhex(row["start_hex"])] + [
            float.fromhex(value) for value in row["terms_hex"]
        ]
        expected = float.fromhex(row["expected_hex"])
        assert exact_sum(terms) == expected
        assert math.fsum(terms) == expected


def test_actual_model_sums_match_exact_terms_and_keep_original_raw_outputs(monkeypatch):
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
        return result

    def version_dependent_sum(*args, **kwargs):
        raise AssertionError("Solar terms must not inherit interpreter-dependent sum")

    for module in modules:
        monkeypatch.setattr(module, "sum", version_dependent_sum, raising=False)
    monkeypatch.setattr(math, "fsum", checked)
    assert model_evaluation(reference) == reference
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
    assert len(required) == 15  # Thirteen reviewed sites and two existing split sums.
    assert seen == required

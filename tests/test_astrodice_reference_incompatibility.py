"""A floating infeasible flag never replaces an exact contradiction."""

import subprocess
import sys
from fractions import Fraction as F

import pytest

from scripts.astrodice_reference_infeasibility import (
    METHOD,
    matrix_digest,
    verify_incompatibility,
)


def witness():
    a, b = [[F(1)], [F(-1)]], [F(0), F(-1)]
    return (
        a,
        b,
        {
            "method_id": METHOD,
            "status": "exact_infeasibility_witness",
            "matrix_sha256": matrix_digest(a, b),
            "support_indices": [0, 1],
            "weights": ["1/2", "1/2"],
            "contradiction_bound": "-1/2",
        },
    )


def test_nonnegative_weighted_sum_proves_zero_less_than_a_negative_bound():
    a, b, c = witness()
    assert verify_incompatibility(a, b, c) == F(-1, 2)


@pytest.mark.parametrize(
    "field,value",
    [
        ("weights", ["-1/2", "3/2"]),
        ("weights", ["1/2", "1/4"]),
        ("support_indices", [0, 0]),
        ("support_indices", [0, 2]),
        ("contradiction_bound", "0"),
        ("status", "solver_said_infeasible"),
        ("matrix_sha256", "changed"),
    ],
)
def test_forged_or_numerical_only_contradictions_are_rejected(field, value):
    a, b, c = witness()
    c[field] = value
    with pytest.raises(ValueError):
        verify_incompatibility(a, b, c)


def test_a_feasible_system_cannot_accept_a_resealed_false_witness():
    a, _, c = witness()
    b = [F(1), F(0)]
    c["matrix_sha256"] = matrix_digest(a, b)
    with pytest.raises(ValueError, match="strictly negative"):
        verify_incompatibility(a, b, c)


def test_changed_variable_coefficients_cannot_be_hidden_by_a_new_matrix_digest():
    _, b, c = witness()
    a = [[F(2)], [F(-1)]]
    c["matrix_sha256"] = matrix_digest(a, b)
    with pytest.raises(ValueError, match="annihilate"):
        verify_incompatibility(a, b, c)


def test_certificate_guards_remain_active_under_python_optimization():
    code = "from scripts.astrodice_reference_infeasibility import verify_incompatibility;verify_incompatibility([[1],[-1]],[0,-1],{'status':'solver_said_infeasible'})"
    r = subprocess.run(
        [sys.executable, "-O", "-c", code], capture_output=True, text=True
    )
    assert r.returncode != 0 and "ValueError" in r.stderr

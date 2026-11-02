"""Exact Farkas witnesses for incompatible reference-model inequalities.

SciPy only proposes a nonnegative combination. Acceptance checks rational
annihilation and a strictly negative bound. This certifies incompatibility of
the declared model/printing constraints, never an astronomical cause or truth.
"""

import hashlib
import json
from fractions import Fraction as F
from itertools import combinations

from scripts.astrodice_interval_reference import solve

METHOD = "exact_farkas_reference_incompatibility_v1"


def matrix_digest(a, b):
    if not a or not a[0] or len(a) != len(b) or any(len(r) != len(a[0]) for r in a):
        raise ValueError("Invalid reference constraint dimensions")
    content = {"a": [[str(F(x)) for x in r] for r in a], "b": [str(F(v)) for v in b]}
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()


def verify_incompatibility(a, b, certificate):
    if (
        certificate.get("method_id") != METHOD
        or certificate.get("status") != "exact_infeasibility_witness"
        or certificate.get("matrix_sha256") != matrix_digest(a, b)
    ):
        raise ValueError("Farkas certificate identity changed")
    indices = certificate["support_indices"]
    weights = list(map(F, certificate["weights"]))
    if (
        not indices
        or len(indices) != len(weights)
        or len(set(indices)) != len(indices)
        or any(type(i) is not int or not 0 <= i < len(a) for i in indices)
        or any(w < 0 for w in weights)
        or sum(weights, F(0)) != 1
    ):
        raise ValueError("Invalid nonnegative Farkas combination")
    if any(
        sum((w * F(a[i][j]) for i, w in zip(indices, weights)), F(0)) != 0
        for j in range(len(a[0]))
    ):
        raise ValueError("Farkas combination does not annihilate the variables")
    contradiction = sum((w * F(b[i]) for i, w in zip(indices, weights)), F(0))
    if contradiction >= 0 or contradiction != F(certificate["contradiction_bound"]):
        raise ValueError("No exact strictly negative Farkas contradiction")
    return contradiction


def find_incompatibility(a, b):
    from scipy.optimize import linprog

    digest = matrix_digest(a, b)
    n = len(a[0])
    result = linprog(
        [float(v) for v in b],
        A_eq=[[float(row[j]) for row in a] for j in range(n)] + [[1.0] * len(a)],
        b_eq=[0.0] * n + [1.0],
        bounds=(0, None),
        method="highs",
        options={
            "primal_feasibility_tolerance": 1e-9,
            "dual_feasibility_tolerance": 1e-9,
        },
    )
    if not result.success:
        return {
            "status": "diagnostic_solver_unresolved",
            "solver_status": result.status,
            "message": result.message,
            "matrix_sha256": digest,
        }
    candidates = sorted(range(len(a)), key=lambda i: result.x[i], reverse=True)[
        : min(12, len(a))
    ]
    for support in combinations(candidates, n + 1):
        equations = [[F(a[i][j]) for i in support] for j in range(n)] + [
            [F(1)] * (n + 1)
        ]
        try:
            weights = solve(equations, [F(0)] * n + [F(1)])
        except ValueError:
            continue
        if any(w < 0 for w in weights):
            continue
        bound = sum((w * F(b[i]) for i, w in zip(support, weights)), F(0))
        if bound >= 0:
            continue
        certificate = {
            "method_id": METHOD,
            "status": "exact_infeasibility_witness",
            "matrix_sha256": digest,
            "support_indices": list(support),
            "weights": list(map(str, weights)),
            "contradiction_bound": str(bound),
        }
        verify_incompatibility(a, b, certificate)
        return certificate
    return {
        "status": "no_exact_infeasibility_witness_found",
        "matrix_sha256": digest,
        "solver_status": result.status,
    }

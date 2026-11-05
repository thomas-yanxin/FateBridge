"""Exact Farkas witnesses for incompatible reference-model inequalities.

SciPy only proposes a nonnegative combination. Acceptance checks rational
annihilation and a strictly negative bound. This certifies incompatibility of
the declared model/printing constraints, never an astronomical cause or truth.
"""

import hashlib
import json
from fractions import Fraction as F

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

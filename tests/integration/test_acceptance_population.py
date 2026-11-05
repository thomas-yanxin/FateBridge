"""A green subset, changed reference, duplicate, or unknown cannot pass a gate."""

import pytest
from pydantic import ValidationError

from fatebridge.validation.acceptance import (
    GateObservation,
    GateProtocol,
    evaluate_gate,
)


def protocol():
    return GateProtocol(
        gate_id="fixed-three",
        method_id="synthetic",
        axis="numerical",
        reference_sha256="a" * 64,
        case_ids=("pass", "fail", "missing"),
        comparison="absolute_error_le",
        tolerance=2,
        unit="arcseconds",
        scope="independent hand-computed comparison vectors",
    )


def observed(name, error=None, reference="a" * 64):
    return GateObservation(case_id=name, error=error, reference_sha256=reference)


def test_all_rows_and_reference_identity_are_required():
    p = protocol()
    rows = (observed("pass", 1), observed("fail", 3), observed("missing", None))
    r = evaluate_gate(p, rows)
    assert r["status"] == "failed" and r["denominator"] == 3
    assert r["failures"] == ["fail"] and r["unresolved"] == ["missing"]
    subset = evaluate_gate(p, rows[:1])
    assert subset["status"] == "failed" and subset["missing"] == ["fail", "missing"]
    wrong = evaluate_gate(
        p, (observed("pass", 0, "b" * 64), observed("fail", 0), observed("missing", 0))
    )
    assert wrong["status"] == "failed" and wrong["wrong_reference"] == ["pass"]


def test_duplicates_unknowns_and_unregistered_cases_do_not_become_passes():
    p = protocol()
    good = tuple(observed(k, 0) for k in p.case_ids)
    assert evaluate_gate(p, good)["status"] == "passed"
    assert evaluate_gate(p, (*good, good[0]))["duplicates"] == ["pass"]
    assert evaluate_gate(p, (*good, observed("extra", 0)))["status"] == "failed"
    unknown = evaluate_gate(p, (good[0], good[1], observed("missing")))
    assert unknown["population_complete"] and unknown["status"] == "unresolved"


@pytest.mark.parametrize("error", [-1, float("nan"), float("inf")])
def test_nonphysical_error_values_are_rejected(error):
    with pytest.raises(ValidationError):
        observed("pass", error)

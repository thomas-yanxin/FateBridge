"""Transport comparisons retain every current numerical and source fact."""

import math

import pytest

from tests.output_facts import canonical_json


def test_current_facts_ignore_only_execution_receipts():
    payload = {
        "value": 1.0,
        "provenance": {"source": "primary"},
        "generated_at": "source-edition-date",
        "run_metadata": {"run_id": "first", "duration_ms": 1},
    }
    other = {**payload, "run_metadata": {"run_id": "second", "duration_ms": 2}}
    assert canonical_json(payload) == canonical_json(other)
    for field, replacement in (
        ("value", math.nextafter(1.0, math.inf)),
        ("provenance", {"source": "different"}),
        ("generated_at", "different-edition"),
    ):
        assert canonical_json(payload) != canonical_json(
            {**payload, field: replacement}
        )


@pytest.mark.parametrize("value", [math.inf, -math.inf, math.nan])
def test_nonfinite_current_facts_are_rejected(value):
    with pytest.raises(ValueError):
        canonical_json({"coordinate": value})

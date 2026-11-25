"""Actual India physical directions, same epoch, sealed JPL/ERFA reference."""

from pathlib import Path

import pytest

from scripts.jyotish.audit_jyotish_endpoints import audit
from tests.unit_test.fixtures.jyotish_sources import (  # noqa: F401
    data18,
    full_files,
    restore_runtime,
)

REFERENCE = Path(__file__).parents[1] / "fixtures/jyotish-endpoint-reference.json"


@pytest.mark.parametrize(
    "name,rows",
    [
        ("jyotish-endpoint-reference.json", 8),
        ("jyotish-endpoint-extended-reference.json", 6),
    ],
)
def test_actual_domain_endpoint_directions_match_independent_reference(
    data18, name: str, rows: int
) -> None:
    directory = full_files(data18)
    result = audit(REFERENCE.with_name(name), directory)
    assert result["expected_rows"] == result["passed_rows"] == rows
    assert all(row["same_physical_epoch"] for row in result["rows"])
    assert result["status"] == "passed"
    assert result["position_line_arcsec"] == 2.0

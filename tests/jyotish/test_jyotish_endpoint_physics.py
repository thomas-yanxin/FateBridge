"""Actual India physical directions, same epoch, sealed JPL/ERFA reference."""

from pathlib import Path

import pytest

from scripts.jyotish.audit_jyotish_endpoints import audit
from tests.jyotish.test_jyotish_segment_motion import full_files
from tests.jyotish.test_jyotish_sources import data18, restore_runtime  # noqa: F401

REFERENCE = Path(__file__).parents[1] / "fixtures/jyotish-endpoint-reference.json"


@pytest.mark.parametrize(
    "name,rows",
    [
        ("jyotish-endpoint-reference.json", 8),
        ("jyotish-endpoint-extended-reference.json", 6),
    ],
)
def test_actual_domain_endpoint_directions_match_independent_reference(
    data18, name, rows
):
    directory = full_files(data18)
    result = audit(REFERENCE.with_name(name), directory)
    assert result["expected_rows"] == result["passed_rows"] == rows
    assert all(row["same_physical_epoch"] for row in result["rows"])
    assert result["status"] == "passed"
    assert result["position_line_arcsec"] == 2.0

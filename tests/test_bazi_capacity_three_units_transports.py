"""All newly registered primary-source records survive each public transport."""

import json
from pathlib import Path

import pytest

from tests.test_bazi_source_comparison_transports import (
    rest,
)
from tests.test_bazi_source_comparison_transports import (
    test_same_literal_comparison_full_and_published_view_on_three_surfaces as check_surfaces,
)

REFERENCE = (
    Path(__file__).resolve().parent
    / "fixtures/bazi_capacity_three_units_v1/reference.json"
)
CASES = json.loads(REFERENCE.read_text())["cases"]


@pytest.mark.parametrize("project", [False, True])
@pytest.mark.parametrize("case", CASES, ids=lambda r: r["id"])
def test_complete_new_source_units_on_rest_mcp_cli(
    case, project, rest, tmp_path, capsys
):
    expected = (
        "unadjudicated_records_only"
        if case["expected_strength"] is None
        else "agrees_with_known_annotations"
    )
    check_surfaces(project, case["pillars"], expected, rest, tmp_path, capsys)

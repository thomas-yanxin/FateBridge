"""All newly registered primary-source records survive each public transport."""

import json
from pathlib import Path

import pytest

from tests.bazi.test_bazi_source_comparison_transports import (
    test_same_literal_comparison_full_and_published_view_on_three_surfaces as check_surfaces,
)
from tests.evaluation.test_agentic_nested_outputs import rest as _shared_rest

REFERENCE = Path(__file__).resolve().parents[1] / "data/bazi/complete-units-source.json"
CASES = json.loads(REFERENCE.read_text())["cases"]


rest = _shared_rest


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

"""Current Mei Hua geometry, source words and three-state conditions."""

import json
from pathlib import Path

import pytest

from fatebridge.services.divination import calculate_meihua_analysis
from tests.support.meihua_current_components import assert_current_components

CASES = json.loads(
    (Path(__file__).parents[1] / "data/meihua/time_component_inputs.json").read_bytes()
)


@pytest.mark.parametrize("row", CASES)
def test_current_components_match_literal_geometry_and_truth_tables(row):
    assert_current_components(calculate_meihua_analysis(**row["input"]))

"""Published default evidence and summaries carry their own computed qualifiers."""

import json
from pathlib import Path

import pytest

from fatebridge.application.examples import suggested_fields
from tests.support.transports import SPECS

FIXTURE = Path(__file__).parents[1] / "fixtures/meihua_summary_fidelity_v1"
POLICY = json.loads((FIXTURE / "composition-policy.json").read_text())


@pytest.mark.parametrize("tool", ["meihua_cast", "meihua_analysis"])
@pytest.mark.parametrize("view", [None, "reading"])
def test_default_reading_view_contains_complete_qualification(tool, view):
    fields = suggested_fields(SPECS[tool], view=view)
    if tool == "meihua_analysis" and view is None:
        # The compact time card carries the exact combined qualification in
        # summary; the complete reading card still carries every source fact.
        assert fields.count("summary") == 1
        assert not any(
            field.startswith("interpretation.seasonal_qualification.")
            for field in fields
        )
        fields = suggested_fields(SPECS[tool], view="reading")
    assert fields.count("interpretation.seasonal_qualification") == 1

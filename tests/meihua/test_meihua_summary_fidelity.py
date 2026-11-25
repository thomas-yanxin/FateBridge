"""Published default evidence and summaries carry their own computed qualifiers."""

import pytest

from fatebridge.application.examples import suggested_fields
from tests.support.transports import SPECS


@pytest.mark.parametrize("tool", ["meihua_cast", "meihua_analysis"])
def test_first_view_and_seasonal_evidence(tool: str) -> None:
    spec = SPECS[tool]
    first_fields = suggested_fields(spec)
    assert first_fields == suggested_fields(spec, view="general")
    assert first_fields is not None
    assert first_fields.count("summary") == 1
    assert not any(
        field.startswith("interpretation.seasonal_qualification")
        for field in first_fields
    )
    for view in ("reading", "strength"):
        fields = suggested_fields(spec, view=view)
        assert fields is not None
        assert fields.count("interpretation.seasonal_qualification") == 1

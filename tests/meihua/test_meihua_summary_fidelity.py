"""The first response carries the summary and deeper cards carry seasonal evidence."""

import pytest

from fatebridge.application.examples import suggested_fields
from tests.support.transports import SPECS


@pytest.mark.parametrize("tool", ["meihua_cast", "meihua_analysis"])
def test_complete_seasonal_qualification_remains_available(tool):
    spec = SPECS[tool]
    fields = suggested_fields(spec)
    assert fields.count("summary") == 1
    assert not any(
        field.startswith("interpretation.seasonal_qualification") for field in fields
    )
    for view in ("reading", "strength"):
        assert (
            suggested_fields(spec, view=view).count(
                "interpretation.seasonal_qualification"
            )
            == 1
        )

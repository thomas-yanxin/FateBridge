"""Clock evidence survives the existing snapshot export policies."""

import pytest

from tests.test_agentic_nested_outputs import inputs
from tests.test_bazi_birth_seconds import BASE, SPECS


@pytest.mark.parametrize(
    "spec", [s for s in SPECS if s.key != "analyze_destiny"], ids=lambda s: s.key
)
def test_every_existing_snapshot_export_keeps_the_known_clock_receipt(spec):
    request = spec.request_model.model_validate(
        {**inputs(spec), **BASE, "birth_minute": 20, "birth_second": 59}
    )
    service, args, kwargs = spec.bind(request)
    result = service(*args, **kwargs)
    assert "error" not in result
    assert "1990-05-15T10:20:59+00:00" in result["snapshot_text"]
    assert "1990-05-15T10:20:59+00:00" in result["snapshot_export"]["export_text"]
    assert "不认证" in result["snapshot_export"]["export_text"]

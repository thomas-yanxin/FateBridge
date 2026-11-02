"""Typed runtime source errors retain their class before generic ValueError."""

import pytest

from fatebridge.application import execution
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import EphemerisSourceError


@pytest.mark.parametrize("include_metadata", [False, True])
@pytest.mark.parametrize("typed_source", [False, True])
def test_dispatch_preserves_source_failure_and_plain_input_error_semantics(
    monkeypatch, include_metadata, typed_source
):
    spec = next(s for s in CATALOG if s.key == "fengshui_xuankong_natal")
    request = spec.request_model.model_validate(
        {
            "house": {"facing_degrees": 180, "north_reference": "magnetic"},
            "period": {
                "basis": "construction_completion",
                "effective_event_year": 1800,
                "evidence": "Synthetic dispatcher test",
            },
        }
    )

    def failed(*args):
        if typed_source:
            raise EphemerisSourceError("solar_de440_invalid")
        raise ValueError("private raw input details must not be echoed")

    monkeypatch.setattr(execution, "execute_spec", failed)
    result = execution.execute_tool(spec, request, include_metadata=include_metadata)
    assert "run_metadata" not in result
    assert "private raw input" not in str(result)
    assert result["retryable"] is False
    if typed_source:
        assert result["error_code"] == "ephemeris_source_inconsistent"
        assert result["status_code"] == 503
        assert result["issues"] == [
            {"path": "runtime.ephemeris_data", "code": "solar_de440_invalid"}
        ]
    else:
        assert result["error_code"] == "validation_error"

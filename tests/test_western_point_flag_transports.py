"""Wrong reference-point flags produce source errors on every public surface."""

import asyncio
import json

import pytest

from fatebridge.core.astro import runtime
from tests.test_agentic_nested_outputs import SPECS, call_cli, native, rest


@pytest.mark.parametrize("zodiac", ["Tropic", "Sidereal"])
def test_wrong_native_point_is_not_published_as_a_normal_horary(
    zodiac, monkeypatch, rest, tmp_path, capsys
):
    original = runtime.ephemeris_call
    swe = runtime.swe
    calls = []

    def changed(operation, *args, **kwargs):
        result = original(operation, *args, **kwargs)
        if operation == "calc" and args[1] == swe.SATURN:
            values, flags = result
            calls.append(flags)
            return values, flags | 1048576
        return result

    monkeypatch.setattr(runtime, "ephemeris_call", changed)
    spec = SPECS["astro_horary"]
    payload = dict(
        question_year=2026,
        question_month=9,
        question_day=19,
        question_hour=0,
        timezone_name="UTC",
        longitude=0,
        latitude=40,
        ut1_source="iers_c04",
        zodiac_type=zodiac,
        category="career",
    )
    http = rest.post(spec.rest_path, json=payload)
    assert http.status_code == 503
    expected = http.json()
    code, cli = call_cli(spec, payload, tmp_path, capsys)
    protocol = asyncio.run(native(spec, payload))
    assert code == 1 and protocol.is_error
    mcp = json.loads(protocol.content[0].text)
    assert len(calls) >= 3
    for value in [expected, cli, mcp]:
        assert value["error_code"] == "ephemeris_source_inconsistent"
        assert value["retryable"] is False
        assert value["issues"] == expected["issues"]
        assert "coordinate_contract_changed" in json.dumps(value["issues"])
        assert "horary" not in value

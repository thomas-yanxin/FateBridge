"""Required divination clocks cannot silently become a midnight chart."""

import asyncio

import pytest

from tests.test_agentic_nested_outputs import SPECS, call_cli, native, rest


@pytest.mark.parametrize(
    "key,options",
    [
        ("sixyao", {"method": "time"}),
        ("sixyao", {"method": "coin", "seed": 42}),
        ("sixyao", {"coins": [6, 7, 8, 9, 7, 8]}),
        ("sixyao", {"gua_code": "111111"}),
        ("sanshiunited", {}),
    ],
)
@pytest.mark.parametrize("clock", ["", "   "])
def test_empty_required_clock_fails_on_every_transport(
    key, options, clock, rest, tmp_path, capsys
):
    spec = SPECS[key]
    payload = {"date": "2026-02-10", "time": clock, **options}
    response = rest.post(spec.rest_path, json=payload)
    code, local = call_cli(spec, payload, tmp_path, capsys)
    protocol = asyncio.run(native(spec, payload))
    assert response.status_code == 400 and code == 1 and protocol.is_error
    for output in [response.json(), local, protocol.structured_content]:
        assert output["error_code"] == "validation_error"
        assert "time" in output["error"]
        assert "run_metadata" not in output

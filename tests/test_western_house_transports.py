"""The Equal-MC definition and Chinese name agree on all actual transports."""

import asyncio

import pytest

from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest
from tests.test_western_accuracy import BIRTH


@pytest.mark.parametrize("key", ["astro_chart", "astro_chart13"])
def test_equal_mc_tenth_cusp_and_canonical_label_on_all_transports(
    key, rest, tmp_path, capsys
):
    spec = SPECS[key]
    payload = {**BIRTH, "hsys": 8}
    response = rest.post(
        spec.rest_path, json=payload, params={"response_char_limit": 0}
    )
    code, cli = call_cli(
        spec, payload, tmp_path, capsys, flags=["--response-char-limit", "0"]
    )
    mcp = asyncio.run(native(spec, payload))
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    assert (
        business(response.json()) == business(cli) == business(mcp.structured_content)
    )
    for result in [response.json(), cli, mcp.structured_content]:
        assert (
            result["chart_profile"]["house_system_label_zh"]
            == "天顶为第10宫宫头的等宫制"
        )
        assert result["houses"][9]["cusp_longitude"] == pytest.approx(
            result["angles"]["midheaven"]["longitude"], abs=1e-10
        )
        assert "天顶为第10宫宫头的等宫制" in result["snapshot_text"]
        assert "天顶为10宫中点等宫制" not in result["snapshot_text"]

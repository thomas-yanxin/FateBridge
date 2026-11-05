"""The comprehensive tool is distinct from the standard chart and9topics."""

import asyncio

import pytest

from fatebridge.core import de440_solar
from fatebridge.utils.errors import EphemerisSourceError
from tests.support.transports import SPECS, business, call_cli, inputs, native


@pytest.mark.parametrize("project", [False, True])
def test_comprehensive_default_source_matches_its_actual_mcp_and_cli_surfaces(
    project,
    monkeypatch,
    tmp_path,
    capsys,
):
    monkeypatch.delenv("FATEBRIDGE_SOLAR_TERM_MODEL", raising=False)
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    spec = SPECS["analyze_destiny"]
    assert spec.rest_path is None
    payload = {**inputs(spec), "use_true_solar_time": False}
    opts = dict(include_snapshot_text=False, response_char_limit=0)
    flags = ["--include-snapshot-text", "false", "--response-char-limit", "0"]
    if project:
        opts.update(fields=["calendar_context"], strict_fields=True)
        flags += ["--fields", "calendar_context", "--strict-fields", "true"]
    mcp = asyncio.run(native(spec, payload, **opts))
    code, cli = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    assert not mcp.is_error and code == 0
    assert business(mcp.structured_content) == business(cli)
    for result in [mcp.structured_content, cli]:
        term = result["calendar_context"]["current_solar_term"]
        assert term["resolution_provider"] == "jpl_de440"
        assert term["ephemeris_model"] == de440_solar.MODEL_ID
        assert (
            de440_solar.MODEL_ID
            in result["run_metadata"]["provenance"]["ephemeris_model"]
        )


def test_comprehensive_default_data_failure_cannot_return_a_complete_report(
    monkeypatch,
    tmp_path,
    capsys,
):
    def unavailable():
        raise EphemerisSourceError("solar_de440_invalid")

    monkeypatch.delenv("FATEBRIDGE_SOLAR_TERM_MODEL", raising=False)
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.setattr(de440_solar, "_profile", unavailable)
    spec = SPECS["analyze_destiny"]
    payload = {**inputs(spec), "use_true_solar_time": False}
    mcp = asyncio.run(native(spec, payload))
    code, cli = call_cli(spec, payload, tmp_path, capsys)
    assert mcp.is_error and code != 0
    assert cli["error_code"] == "ephemeris_source_inconsistent"
    assert cli["retryable"] is False
    assert "four_pillars" not in cli

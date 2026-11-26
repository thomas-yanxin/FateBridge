"""The comprehensive tool is distinct from the standard chart and9topics."""

import asyncio
from pathlib import Path

import pytest

from fatebridge.core import almanac, de440_solar
from fatebridge.core.bazi.calendar import BaZiCalendar
from fatebridge.utils.errors import EphemerisSourceError
from tests.support.transports import SPECS, business, call_cli, inputs, native


@pytest.mark.parametrize("project", [False, True])
def test_comprehensive_default_source_matches_its_actual_mcp_and_cli_surfaces(
    project: bool,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("FATEBRIDGE_SOLAR_TERM_MODEL", raising=False)
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    almanac.get_solar_terms_for_year.cache_clear()
    spec = SPECS["bazi_overview"]
    assert spec.rest_path == "/api/bazi/overview"
    payload = {**inputs(spec), "use_true_solar_time": False}
    opts = dict(detail="audit")
    flags = ["--detail", "audit"]
    if project:
        opts.update(fields=["calendar_context"])
        flags += ["--fields", "calendar_context"]
    else:
        pass
    mcp = asyncio.run(native(spec, payload, **opts))
    code, cli = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    assert not mcp.is_error and code == 0
    assert business(mcp.structured_content) == business(cli)
    for result in [mcp.structured_content, cli]:
        term = result["calendar_context"]["current_solar_term"]
        assert term["resolution_provider"] == "jpl_de440"
        assert term["ephemeris_model"] == de440_solar.MODEL_ID
        assert result["run_metadata"]["engine_is_approximate"] is False


def test_comprehensive_default_data_failure_cannot_return_a_complete_report(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def unavailable():
        raise EphemerisSourceError("solar_de440_invalid")

    monkeypatch.delenv("FATEBRIDGE_SOLAR_TERM_MODEL", raising=False)
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    almanac.get_solar_terms_for_year.cache_clear()
    BaZiCalendar._get_four_pillars_cached.cache_clear()
    monkeypatch.setattr(de440_solar, "_profile", unavailable)
    spec = SPECS["bazi_overview"]
    payload = {**inputs(spec), "use_true_solar_time": False}
    mcp = asyncio.run(native(spec, payload))
    code, cli = call_cli(spec, payload, tmp_path, capsys)
    assert mcp.is_error and code != 0
    assert cli["error_code"] == "ephemeris_source_inconsistent"
    assert cli["retryable"] is False
    assert "four_pillars" not in cli

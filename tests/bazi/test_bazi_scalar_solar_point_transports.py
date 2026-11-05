"""Actual analytic/SPK roots keep explicit point semantics on public transports."""

from pathlib import Path

import pytest

from tests.bazi.test_bazi_tt_utc_exact_transports import check_terms
from tests.support.transports import AS_OF, SPECS, business, inputs
from tests.support.transports import rest as _shared_rest
from tests.support.transports import surface_calls

rest = _shared_rest


@pytest.mark.parametrize("mode", ["analytic", "spk"])
@pytest.mark.parametrize("key", ["bazi_birth", "dayun_analysis", "timing_analysis"])
@pytest.mark.parametrize("project", [False, True])
def test_scalar_root_point_facts_agree_on_rest_mcp_cli(
    mode, key, project, monkeypatch, tmp_path, surface_calls
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    if mode == "spk":
        monkeypatch.setenv(
            "FATEBRIDGE_SOLAR_SPK_FILE",
            str(Path(__file__).resolve().parents[2] / "ephe/solar-de440.bsp"),
        )
    spec = SPECS[key]
    payload = {
        **inputs(spec),
        "birth_year": 2001,
        "birth_month": 6,
        "birth_day": 15,
        "birth_hour": 10,
        "birth_minute": 30,
        "birth_second": 21,
        "birth_timezone": "Asia/Shanghai",
        "use_true_solar_time": False,
    }
    options = {"as_of": AS_OF, "response_char_limit": 0, "include_snapshot_text": False}
    flags = [
        "--as-of",
        AS_OF,
        "--response-char-limit",
        "0",
        "--include-snapshot-text",
        "false",
    ]
    path = "bazi_birth.calendar_context" if key == "bazi_birth" else "calendar_context"
    if project:
        options.update(fields=[path], strict_fields=True)
        flags += ["--fields", path, "--strict-fields", "true"]
    response, mcp, code, cli = surface_calls(
        spec, payload, params=options, options=options, flags=flags, cli_first=False
    )
    assert response.status_code == 200 and not mcp.is_error and code == 0, response.text
    results = [response.json(), mcp.structured_content, cli]
    for result in results:
        assert business(result) == business(results[0])
        assert check_terms(result) > 0
        spec.output_model.model_validate(result)
        calendar = (
            result["bazi_birth"]["calendar_context"]
            if key == "bazi_birth"
            else result["calendar_context"]
        )
        term = calendar["current_solar_term"]
        assert term["resolution_provider"] == (
            "jpl_spk" if mode == "spk" else "fatebridge_analytic"
        )
        details = term["solar_model_details"]
        assert (
            details["numerical_epoch_representation"] == "explicit_ieee_float_tt_point"
        )
        assert details["scalar_jd_scope"] == "exact_value_of_selected_ieee_float"
        assert details["accuracy_certified"] is False

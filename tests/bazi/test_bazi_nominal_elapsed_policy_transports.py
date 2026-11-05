"""The same declared nominal clock scale survives full and projected delivery."""

import pytest

from tests.support.transports import SPECS, business
from tests.support.transports import rest as _shared_rest
from tests.support.transports import surface_calls

DECLARATIONS = {
    "elapsed_scale": "nominal_utc_label_seconds",
    "leap_second_policy": "not_counted",
}


rest = _shared_rest


@pytest.mark.parametrize("tool", ["timing_analysis", "dayun_analysis"])
@pytest.mark.parametrize("project", [False, True])
def test_dayun_duration_scale_survives_rest_mcp_and_cli(tool, project, surface_calls):
    spec = SPECS[tool]
    payload = {
        "birth_year": 2016,
        "birth_month": 12,
        "birth_day": 31,
        "birth_hour": 23,
        "birth_minute": 59,
        "birth_second": 59,
        "birth_timezone": "UTC",
        "gender": "男",
        "use_true_solar_time": False,
        "analysis_year": 2026,
        "analysis_month": 10,
        "analysis_day": 25,
    }
    prefix = "dayun_analysis." if tool == "timing_analysis" else ""
    path = prefix + "timing_context.timeline.start_details"
    options = {"response_char_limit": 0, "include_snapshot_text": False}
    flags = ["--response-char-limit", "0", "--include-snapshot-text", "false"]
    if project:
        options.update(fields=[path], strict_fields=True)
        flags += ["--fields", path, "--strict-fields", "true"]
    http, protocol, code, cli = surface_calls(
        spec, payload, params=options, options=options, flags=flags, cli_first=False
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0
    results = [http.json(), protocol.structured_content, cli]
    for result in results:
        assert business(result) == business(results[0])
        spec.output_model.model_validate(result)
        dayun = result["dayun_analysis"] if tool == "timing_analysis" else result
        details = dayun["timing_context"]["timeline"]["start_details"]
        assert {k: details[k] for k in DECLARATIONS} == DECLARATIONS
        assert details["elapsed_seconds"] > 0

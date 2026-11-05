"""Confirmed fixed-second offsets survive actual Bazi and timing transports."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from tests.bazi.test_bazi_birth_seconds import SPECS
from tests.evaluation.test_agentic_nested_outputs import business, call_cli, native
from tests.evaluation.test_agentic_nested_outputs import rest as _shared_rest

SELECTED = [
    s for s in SPECS if s.key in {"bazi_birth", "timing_analysis", "dayun_analysis"}
]


rest = _shared_rest


@pytest.mark.parametrize("spec", SELECTED, ids=lambda s: s.key)
@pytest.mark.parametrize(
    "label,seconds", [("UTC+00:19:32", 1172), ("GMT-00:44:30", -2670)]
)
@pytest.mark.parametrize("project", [False, True])
def test_fixed_second_offset_is_exact_and_does_not_certify_civil_record(
    spec, label, seconds, project, rest, tmp_path, capsys
):
    values = dict(
        birth_year=1965,
        birth_month=8,
        birth_day=26,
        birth_hour=19,
        birth_minute=34,
        gender="男",
        birth_timezone=label,
        use_true_solar_time=False,
    )
    options = {
        "as_of": "2000-01-01T00:00:00Z",
        "response_char_limit": 0,
        "include_snapshot_text": False,
    }
    flags = [
        "--as-of",
        options["as_of"],
        "--response-char-limit",
        "0",
        "--include-snapshot-text",
        "false",
    ]
    if project:
        prefix = "bazi_birth." if spec.key == "bazi_birth" else ""
        fields = [prefix + "calendar_context.birth_time_input"]
        options.update(fields=fields, strict_fields=True)
        flags += ["--fields", *fields, "--strict-fields", "true"]
    mcp = asyncio.run(native(spec, values, **options))
    code, cli = call_cli(spec, values, tmp_path, capsys, flags=flags)
    response = rest.post(spec.rest_path, json=values, params=options)
    assert not mcp.is_error and code == 0 and response.status_code == 200, response.text
    outputs = [mcp.structured_content, cli, response.json()]
    for result in outputs:
        assert business(result) == business(outputs[0])
        body = result["bazi_birth"] if spec.key == "bazi_birth" else result
        receipt = body["calendar_context"]["birth_time_input"]
        instant = datetime(1965, 8, 26, 19, 34, tzinfo=timezone.utc) - timedelta(
            seconds=seconds
        )
        assert (
            datetime.fromisoformat(receipt["nominal_civil_datetime"]).astimezone(
                timezone.utc
            )
            == instant
        )
        assert receipt["omitted_components"] == ["second"]
        assert receipt["calculation_defaults"] == {"second": 0}
        assert receipt["observed_precision_certified"] is False
        assert receipt["uncertainty_interval"] is None
        spec.output_model.model_validate(result)

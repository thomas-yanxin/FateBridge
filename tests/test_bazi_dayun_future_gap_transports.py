"""Actual transports preserve initial, internal and configured-final states."""

import asyncio

import pytest

from fatebridge.application.examples import suggested_fields
from tests.test_agentic_nested_outputs import business, call_cli, native, rest
from tests.test_bazi_birth_seconds import SPECS
from tests.test_bazi_dayun_future_gaps import INITIAL, LATER

RANGE_SPECS = [s for s in SPECS if s.key in {"timing_analysis", "dayun_analysis"}]


@pytest.mark.parametrize("row", [INITIAL[0], *LATER], ids=lambda row: row["id"])
@pytest.mark.parametrize("spec", RANGE_SPECS, ids=lambda s: s.key)
@pytest.mark.parametrize("project", [False, True])
def test_future_gap_states_reach_full_and_published_views(
    row, spec, project, rest, tmp_path, capsys
):
    values = {**row["input"], "birth_time_uncertainty_minutes": 1}
    options = {
        "as_of": row["analysis_at"],
        "include_snapshot_text": True,
        "response_char_limit": 0,
    }
    flags = [
        "--as-of",
        row["analysis_at"],
        "--include-snapshot-text",
        "true",
        "--response-char-limit",
        "0",
    ]
    if project:
        fields = suggested_fields(spec, view="birth_time_sensitivity")
        options.update(fields=fields, strict_fields=True)
        flags += ["--fields", *fields, "--strict-fields", "true"]
    mcp = asyncio.run(native(spec, values, **options))
    code, cli = call_cli(spec, values, tmp_path, capsys, flags=flags)
    response = rest.post(spec.rest_path, json=values, params=options)
    assert not mcp.is_error and code == 0 and response.status_code == 200, response.text
    outputs = [mcp.structured_content, cli, response.json()]
    for result in outputs:
        assert business(result) == business(outputs[0])
        sensitivity = result["birth_time_sensitivity"]
        actual = {
            (p["status"], p["period"]) for p in sensitivity["current_dayun_candidates"]
        }
        if "expected_current_candidates" in row:
            assert sorted(actual) == [
                tuple(p) for p in row["expected_current_candidates"]
            ]
        else:
            assert sorted({p[0] for p in actual}) == row["expected_statuses"]
        event = sensitivity["dayun_event_analysis"]
        assert any(e["kind"] == "dayun_future_civil_gap_end" for e in event["events"])
        assert event["future_clock_scan"]["forward_gap_count"] == 1
        assert event["continuous_completeness_certified"] is False
        assert event["physical_precision_certified"] is False
        assert (
            sensitivity["sample_count"]
            == sum(p["sample_count"] for p in sensitivity["pillars_candidates"])
            == 3
        )
        spec.output_model.model_validate(result)
        if not project:
            assert "未来跳时" in result["snapshot_text"]
            assert (
                "计算覆盖期数不是寿命估计" in result["snapshot_export"]["export_text"]
            )
            if any(p[0] == "before_dayun" for p in actual):
                assert "尚未起运" in result["snapshot_text"]
            if any(p[0] == "beyond_calculation" for p in actual):
                assert "超出已配置期数" in result["snapshot_text"]

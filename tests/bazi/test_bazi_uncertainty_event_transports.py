"""Actual full and published uncertainty views retain event-only candidates."""

import asyncio

import pytest

from fatebridge.application.examples import suggested_fields
from tests.bazi.test_bazi_birth_seconds import SPECS
from tests.bazi.test_bazi_uncertainty_events import KNOWN
from tests.support.transports import AS_OF, business, call_cli, native
from tests.support.transports import rest as _shared_rest

ROW = next(r for r in KNOWN if r["input"]["birth_year"] >= 2000)
RANGE_SPECS = [s for s in SPECS if s.key in {"timing_analysis", "dayun_analysis"}]


rest = _shared_rest


@pytest.mark.parametrize("spec", RANGE_SPECS, ids=lambda s: s.key)
@pytest.mark.parametrize("project", [False, True])
def test_actual_range_tools_and_published_view_include_all_event_candidates(
    spec, project, rest, tmp_path, capsys
):
    values = {
        **ROW["input"],
        "gender": "男",
        "birth_time_uncertainty_minutes": 1,
        "analysis_year": 2026,
        "analysis_month": 1,
        "analysis_day": 1,
        "analysis_hour": 12,
    }
    options = {"include_snapshot_text": True, "response_char_limit": 0}
    flags = ["--include-snapshot-text", "true", "--response-char-limit", "0"]
    if project:
        fields = suggested_fields(spec, view="birth_time_sensitivity")
        assert fields and "birth_time_sensitivity" in fields
        options.update(fields=fields, strict_fields=True)
        flags += ["--fields", *fields, "--strict-fields", "true"]
    mcp = asyncio.run(native(spec, values, **options))
    code, cli = call_cli(spec, values, tmp_path, capsys, flags=flags)
    response = rest.post(
        spec.rest_path, json=values, params={"as_of": AS_OF, **options}
    )
    assert not mcp.is_error and code == 0 and response.status_code == 200, response.text
    outputs = [mcp.structured_content, cli, response.json()]
    for result in outputs:
        assert business(result) == business(outputs[0])
        sensitivity = result["birth_time_sensitivity"]
        candidates = sensitivity["pillars_candidates"]
        assert len(candidates) == 3
        assert (
            sum(r["sample_count"] for r in candidates)
            == sensitivity["sample_count"]
            == 3
        )
        only_events = [r for r in candidates if r["sample_count"] == 0]
        assert len(only_events) == 1 and only_events[0]["event_probe_count"] > 0
        assert sensitivity["additional_event_probe_count"] > 0
        assert (
            sensitivity["event_analysis"]["continuous_completeness_certified"] is False
        )
        assert (
            sensitivity["boundary_range_scope"]
            == "minute_grid_natal_and_dayun_event_probe_envelope"
        )
        spec.output_model.model_validate(result)
        if not project:
            assert "本命四柱候选数：3" in result["snapshot_text"]
            assert "无分钟样本的事件候选也须保留" in result["snapshot_text"]
            assert (
                "全部连续候选、交运状态与边界极值仍未认证"
                in result["snapshot_export"]["export_text"]
            )

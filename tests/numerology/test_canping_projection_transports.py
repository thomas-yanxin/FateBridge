"""Actual REST, FastMCP and CLI agree on the complete projected schedule."""

import pytest
from jsonschema import Draft202012Validator

from tests.support.transports import SPECS, business, projected_outputs
from tests.support.transports import rest as shared_rest

rest = shared_rest


@pytest.mark.parametrize(
    "mode,method,full",
    [
        ("de440", "bazi_appendix_v1", False),
        ("de440", "bazi_continuous_v1", True),
        ("analytic", "bazi_appendix_v1", True),
        ("analytic", "bazi_continuous_v1", False),
    ],
)
def test_complete_projection_and_selected_receipts_on_three_surfaces(
    monkeypatch, mode, method, full, rest, tmp_path, capsys
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    spec = SPECS["canping"]
    payload = dict(
        date="2200-05-15",
        time="09:00",
        zone="UTC",
        gender="男",
        use_true_solar_time=False,
        dayun_method=method,
        analysis_datetime="2300-01-01T12:00:00Z",
    )
    fields = [
        "canping_timing",
        "liunian_series" if full else "liunian_series.solar_context",
        "numerology_evidence.rule_trace",
        "snapshot_text",
    ]
    outputs = projected_outputs(spec, payload, fields, rest, tmp_path, capsys)
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for result in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        timing, series = result["canping_timing"], result["liunian_series"]
        selected = timing["selected"]
        assert (selected["year"], selected["ganzhi"]) == (2299, "己卯")
        assert selected["year_start_boundary"]["year"] == 2299
        assert selected["year_end_boundary"]["year"] == 2300
        context = series["solar_context"]
        assert context == timing["solar_year_context"]
        assert context["boundary_count"] == 121 and context["horizon_years"] == 120
        assert context["de440_projection_profile_used"] is (mode == "de440")
        trace = next(
            r
            for r in result["numerology_evidence"]["rule_trace"]
            if r["rule_id"] == "canping_actual_lichun_dependencies"
        )
        assert trace["facts"] == context
        if full:
            assert len(series["rows"]) == 120 and len(series["year_boundaries"]) == 121
        assert "[参平年序·实际立春来源]" in result["snapshot_text"]

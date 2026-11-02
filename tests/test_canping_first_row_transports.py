"""Actual adapters retain first-row facts and reject inconsistent summaries."""

from copy import deepcopy

import pytest

from fatebridge.application.examples import evidence_views
from tests.numerology_clock_input_fixture_compat import upgrade_prior_clock_input
from tests.test_agentic_nested_outputs import SPECS, business
from tests.test_agentic_nested_outputs import rest as shared_rest
from tests.test_canping_first_row import FAULTS, REFERENCES
from tests.test_canping_receipt_binding_transports import return_frozen_output
from tests.test_heluo_poem_transports import run_three

rest = shared_rest


@pytest.mark.parametrize("unrelated_projection", [False, True])
def test_empty_actual_sequence_cannot_publish_nonempty_summary(
    unrelated_projection, monkeypatch, rest, tmp_path, capsys
):
    row = REFERENCES[0]
    out = upgrade_prior_clock_input(row["output"], row["arguments"]["time"])
    out["canping_timing"]["first_row"] = deepcopy(out["dayun"][0])
    out["dayun"] = []
    return_frozen_output(monkeypatch, out)
    fields = ["analysis_type"] if unrelated_projection else ["canping_timing.first_row"]
    response, code, cli, mcp = run_three(
        SPECS["canping"], row["arguments"], fields, rest, tmp_path, capsys
    )
    assert response.status_code == 503 and code == 1 and mcp.is_error
    for result in [response.json(), cli, mcp.structured_content]:
        assert result["error_code"] == "numerology_source_inconsistent"
        assert result["retryable"] is False


@pytest.fixture(autouse=True)
def native_model(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", "/tmp/fatebridge-heluo-fiftysecond/empty-ephe")


@pytest.mark.parametrize(
    "profile", ["bazi_appendix_v1", "bazi_continuous_v1", "legacy_minggong_v1"]
)
def test_actual_policy_view_retains_original_first_row_on_every_adapter(
    profile, rest, tmp_path, capsys
):
    row = next(r for r in REFERENCES if r["arguments"]["dayun_method"] == profile)
    spec = SPECS["canping"]
    response, code, cli, mcp = run_three(
        spec,
        row["arguments"],
        evidence_views(spec)["timing_policy"]["fields"],
        rest,
        tmp_path,
        capsys,
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    outputs = [response.json(), cli, mcp.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for out in outputs:
        spec.output_model.model_validate(out)
        timing = out["canping_timing"]
        assert timing["first_row"] == row["expected_first_row"]
        assert "dayun" not in out
        if profile == "legacy_minggong_v1":
            assert timing["first_period"] is None
        else:
            assert timing["first_row"] == timing["first_period"]


@pytest.mark.parametrize("summary", ["first_row", "first_period"])
@pytest.mark.parametrize("path,value", FAULTS)
@pytest.mark.parametrize("unrelated_projection", [False, True])
def test_wrong_actual_summary_is_rejected_before_projection_on_all_adapters(
    summary, path, value, unrelated_projection, monkeypatch, rest, tmp_path, capsys
):
    row = next(
        r for r in REFERENCES if r["arguments"]["dayun_method"] == "bazi_appendix_v1"
    )
    out = upgrade_prior_clock_input(row["output"], row["arguments"]["time"])
    out["canping_timing"]["first_row"] = deepcopy(out["dayun"][0])
    target = out["canping_timing"][summary]
    keys = path.split(".")
    for key in keys[:-1]:
        target = target[key]
    target[keys[-1]] = value
    return_frozen_output(monkeypatch, out)
    fields = ["analysis_type"] if unrelated_projection else ["canping_timing.first_row"]
    response, code, cli, mcp = run_three(
        SPECS["canping"], row["arguments"], fields, rest, tmp_path, capsys
    )
    assert response.status_code == 503 and code == 1 and mcp.is_error
    for result in [response.json(), cli, mcp.structured_content]:
        assert result["error_code"] == "numerology_source_inconsistent"
        assert result["retryable"] is False
        assert (
            result["issues"][0]["code"] == "runtime_canping_schedule_binding_conflict"
        )

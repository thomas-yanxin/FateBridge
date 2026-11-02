"""Actual adapters reject injected internal conflicts before field projection.

Service output is replaced with frozen real baseline results to isolate output
validation. These are transport fault probes, not fresh calendar calculations.
"""

from copy import deepcopy
from dataclasses import replace

import pytest

import fatebridge.application.execution as execution
from tests.test_agentic_nested_outputs import SPECS, business
from tests.test_agentic_nested_outputs import rest as shared_rest
from tests.test_canping_receipt_binding import BASELINES, corrupt_output, label
from tests.test_heluo_poem_transports import run_three

rest = shared_rest


def return_frozen_output(monkeypatch, output):
    original = execution.execute_spec

    def bound_output(spec, request):
        if spec.key == "canping":
            spec = replace(spec, bind=lambda _: (lambda: deepcopy(output), (), {}))
        return original(spec, request)

    monkeypatch.setattr(execution, "execute_spec", bound_output)


@pytest.mark.parametrize("row", BASELINES, ids=label)
@pytest.mark.parametrize("summary_only", [False, True])
def test_normal_frozen_receipts_survive_both_projection_shapes(
    row, summary_only, rest, tmp_path, capsys, monkeypatch
):
    return_frozen_output(monkeypatch, row["output"])
    fields = (
        ["canping_timing.schedule_basis.summary"]
        if summary_only
        else ["canping_timing.schedule_basis", "snapshot_text"]
    )
    response, code, cli, mcp = run_three(
        SPECS["canping"], row["input"], fields, rest, tmp_path, capsys
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    outputs = [response.json(), cli, mcp.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for out in outputs:
        SPECS["canping"].output_model.model_validate(out)
        b = out["canping_timing"]["schedule_basis"]
        assert (
            b["summary"] == row["output"]["canping_timing"]["schedule_basis"]["summary"]
        )
        if summary_only:
            assert set(b) == {"summary"}


@pytest.mark.parametrize(
    "row", [r for r in BASELINES if r["input"]["zone"] == "Asia/Shanghai"], ids=label
)
@pytest.mark.parametrize(
    "kind", ["summary", "role", "trace", "snapshot", "clock_context"]
)
@pytest.mark.parametrize("unrelated_field", [False, True])
def test_injected_conflicts_are_source_errors_on_all_three_adapters(
    row, kind, unrelated_field, rest, tmp_path, capsys, monkeypatch
):
    return_frozen_output(monkeypatch, corrupt_output(row, kind))
    fields = ["analysis_type"] if unrelated_field else ["canping_timing.schedule_basis"]
    response, code, cli, mcp = run_three(
        SPECS["canping"], row["input"], fields, rest, tmp_path, capsys
    )
    assert response.status_code == 503 and code == 1 and mcp.is_error
    for out in [response.json(), cli, mcp.structured_content]:
        assert out["error_code"] == "numerology_source_inconsistent"
        assert out["retryable"] is False
        assert out["issues"] == [
            {
                "path": "runtime.numerology_sources",
                "code": "runtime_canping_schedule_binding_conflict",
            }
        ]


@pytest.mark.parametrize(
    "row", [r for r in BASELINES if r["input"]["zone"] == "Asia/Shanghai"], ids=label
)
@pytest.mark.parametrize("unrelated_field", [False, True])
def test_conflict_after_execution_receipt_keeps_the_specific_source_error(
    row, unrelated_field, rest, tmp_path, capsys, monkeypatch
):
    from fatebridge.services import run_metadata

    return_frozen_output(monkeypatch, row["output"])
    original = run_metadata.attach_run_metadata

    def late_conflict(*args, **kwargs):
        result = original(*args, **kwargs)
        result["canping_timing"]["schedule_basis"][
            "summary"
        ] = "本次未来交运时刻已经无条件确定。"
        return result

    monkeypatch.setattr(run_metadata, "attach_run_metadata", late_conflict)
    fields = ["analysis_type"] if unrelated_field else ["canping_timing.schedule_basis"]
    response, code, cli, mcp = run_three(
        SPECS["canping"], row["input"], fields, rest, tmp_path, capsys
    )
    assert response.status_code == 503 and code == 1 and mcp.is_error
    for out in [response.json(), cli, mcp.structured_content]:
        assert out["error_code"] == "numerology_source_inconsistent"
        assert out["issues"][0]["code"] == "runtime_canping_schedule_binding_conflict"

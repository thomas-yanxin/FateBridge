"""Original text, numerical identity and request-bound receipts are independent."""

import gzip
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.application.execution import execute_spec, execute_tool
from fatebridge.core.numerology_clock_input import (
    clock_input_representation,
    require_clock_input_binding,
)
from fatebridge.core.numerology_inputs import CLOCK_POLICY_ID, require_birth_clock
from fatebridge.core.output_numerology import NumerologyBirthClock, NumerologyClockInput
from tests.evaluation.test_agentic_nested_outputs import SPECS, business
from tests.evaluation.test_agentic_nested_outputs import rest as shared_rest
from tests.numerology.test_heluo_poem_transports import run_three

rest = shared_rest
F = Path(__file__).parents[1] / "fixtures/numerology_clock_input_v1"
REFERENCE = json.loads((F / "reference.json").read_bytes())
BASE = dict(
    date="2000-05-15", time="09:00", zone="UTC", gender="男", use_true_solar_time=False
)


@pytest.fixture(autouse=True)
def native_model(monkeypatch, tmp_path):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path / "empty-ephe"))


@pytest.mark.parametrize("row", REFERENCE["rows"], ids=lambda r: r["input"])
def test_independent_lexical_vectors_and_partial_projections(row):
    assert clock_input_representation(row["input"]) == row["expected"]
    assert clock_input_representation("  " + row["input"] + "  ") == row["expected"]
    NumerologyClockInput.model_validate(row["expected"])
    for k, v in row["expected"].items():
        projected = NumerologyClockInput.model_validate({k: v})
        assert projected.model_fields_set == {k}


@pytest.mark.parametrize("value", REFERENCE["invalid"])
@pytest.mark.parametrize("key", ["heluo", "canping"])
def test_original_unknown_and_invalid_time_rejections_stay_in_force(value, key):
    with pytest.raises((ValueError, TypeError)):
        clock_input_representation(value)
    with pytest.raises(ValidationError):
        SPECS[key].request_model.model_validate({**BASE, "time": value})


@pytest.mark.parametrize("row", REFERENCE["rows"], ids=lambda r: r["input"])
@pytest.mark.parametrize("key", ["heluo", "canping"])
def test_request_retains_original_components_while_numeric_parser_stays_canonical(
    row, key
):
    request = SPECS[key].request_model.model_validate({**BASE, "time": row["input"]})
    assert request.time == row["input"]
    assert require_birth_clock(request.time) == row["expected"]["normalized_clock"]


@pytest.mark.parametrize(
    "change",
    [
        {"observed_precision_certified": True},
        {"observed_precision_certified": 0},
        {"uncertainty_interval": {"seconds": 30}},
        {"calculation_defaults": {"second": False}},
        {"calculation_defaults": {"second": 1}},
        {"fractional_digits": True},
        {"supplied_components": ["hour", "hour"]},
        {"supplied_components": ["hour", "minute", "second"]},
        {"scope": "已认证实际精度"},
        {"statement": "出生已精确至秒"},
    ],
)
def test_text_does_not_certify_physical_precision_or_fabricate_components(change):
    with pytest.raises(ValidationError):
        NumerologyClockInput.model_validate(
            {**REFERENCE["rows"][0]["expected"], **change}
        )


@pytest.fixture(scope="module", params=["heluo", "canping"])
def complete_result(request):
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
        spec = SPECS[request.param]
        parsed = spec.request_model.model_validate(BASE)
        result = execute_spec(spec, parsed)
        assert "error" not in result
        return spec, parsed, result


def test_actual_result_and_same_clock_trace_are_bound_to_original_request(
    complete_result,
):
    _, request, result = complete_result
    before = deepcopy(result)
    require_clock_input_binding(result, requested_time=request.time)
    NumerologyBirthClock.model_validate(result["numerology_evidence"]["birth_clock"])
    assert result == before


@pytest.mark.parametrize(
    "fault", ["missing", "trace", "snapshot", "normalized", "civil", "all_copies"]
)
def test_forgery_is_rejected_against_actual_request_before_any_projection(
    complete_result, fault
):
    spec, request, result = complete_result
    bad = deepcopy(result)
    clock = bad["numerology_evidence"]["birth_clock"]
    trace = next(
        r["facts"]
        for r in bad["numerology_evidence"]["rule_trace"]
        if r["rule_id"] == CLOCK_POLICY_ID
    )
    if fault == "missing":
        del clock["input_representation"]
    elif fault == "trace":
        trace["input_representation"]["supplied_text"] = "09:00:00"
    elif fault == "snapshot":
        bad["snapshot_text"] = bad["snapshot_text"].replace(
            clock["input_representation"]["statement"], "所给出生时间已认证至秒。"
        )
    elif fault == "normalized":
        bad["input_normalized"]["time"] = "09:00:01"
    elif fault == "civil":
        clock["civil_datetime"] = clock["civil_datetime"].replace(
            "09:00:00", "09:00:01"
        )
    else:
        # Same numerical instant and internally consistent output copies. Only
        # the independently retained original request exposes the false claim.
        forged = deepcopy(REFERENCE["rows"][2]["expected"])
        old = clock["input_representation"]["statement"]
        clock["input_representation"] = deepcopy(forged)
        trace["input_representation"] = deepcopy(forged)
        bad["snapshot_text"] = bad["snapshot_text"].replace(old, forged["statement"])
        NumerologyBirthClock.model_validate(clock)
    mocked = replace(spec, bind=lambda _: (lambda: bad, (), {}))
    error = execute_tool(mocked, request)
    assert error["error_code"] == "numerology_source_inconsistent"
    assert error["status_code"] == 503 and error["retryable"] is False
    assert error["issues"][0]["code"] == "runtime_numerology_clock_input_conflict"


@pytest.mark.parametrize("key", ["heluo", "canping"])
@pytest.mark.parametrize("clock", ["09:00", "09:00:00", "09:00:00.123400"])
def test_original_components_survive_actual_three_local_adapters(
    key, clock, rest, tmp_path, capsys
):
    fields = [
        "input_normalized.time",
        "numerology_evidence.birth_clock.input_representation",
    ]
    response, code, cli, mcp = run_three(
        SPECS[key], {**BASE, "time": clock}, fields, rest, tmp_path, capsys
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    outputs = [response.json(), cli, mcp.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    expected = next(r["expected"] for r in REFERENCE["rows"] if r["input"] == clock)
    assert (
        response.json()["numerology_evidence"]["birth_clock"]["input_representation"]
        == expected
    )

"""Full execution requires real anchors; partial output reading stays legal."""

import asyncio
import gzip
import json
import sys
import types
from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import pytest

import fatebridge.application.execution as execution
from fatebridge.core.output_bazi_anchors import (
    BAZI_ANCHOR_TOOLS,
    require_complete_bazi_anchors,
)
from tests.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    native,
)
from tests.test_agentic_nested_outputs import rest as _rest_fixture

rest = _rest_fixture
ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_complete_anchors_v1"
TOOLS = tuple(
    ["analyze_destiny", "bazi_birth"]
    + [
        "bazi_" + t
        for t in (
            "career",
            "wealth",
            "health",
            "children",
            "education",
            "personality",
            "relatives",
            "marriage",
            "romance",
        )
    ]
)


def read(path):
    return json.loads(gzip.decompress(path.read_bytes()))


@lru_cache(maxsize=1)
def baseline():
    return read(FIXTURE / "baseline-first.json.gz")


@lru_cache(maxsize=1)
def controls():
    return read(FIXTURE / "counterexamples-first.json.gz")["controls"]


@lru_cache(maxsize=1)
def old_validator():
    source = read(FIXTURE / "before-source.json.gz")[
        "src/fatebridge/application/execution.py"
    ]
    name = "_pre_bazi_complete_execution"
    module = types.ModuleType(name)
    sys.modules[name] = module
    exec(compile(source, "pre_bazi_complete_execution.py", "exec"), module.__dict__)
    return module.__dict__["validate_output"]


@pytest.mark.parametrize("index", range(143))
def test_all_first_accepted_absence_controls_are_rejected_in_full_execution(index):
    case = controls()[index]
    assert case["old_full_validator_accepted"]
    spec = SPECS[case["tool"]]
    old_validator()(spec, case["payload"])
    with pytest.raises(execution.OutputContractError, match="完整八字"):
        execution.validate_output(spec, case["payload"])


def test_all86_original_branch_payloads_remain_valid_without_any_value_change():
    assert len(baseline()["rows"]) == 86 and set(TOOLS) == BAZI_ANCHOR_TOOLS
    for row in baseline()["rows"]:
        assert not row["is_error"]
        before = deepcopy(row["result"])
        execution.validate_output(SPECS[row["tool"]], row["result"])
        assert row["result"] == before


def test_partial_and_historical_models_are_not_made_full_execution_models():
    for tool in TOOLS:
        spec = SPECS[tool]
        spec.output_model.model_validate({})
        partial = {key: {} for key in spec.required_output_fields}
        spec.output_model.model_validate(partial)
        with pytest.raises(execution.OutputContractError):
            execution.validate_output(spec, partial)


def test_supported_unknowns_and_empty_observations_survive_complete_validation():
    for row in baseline()["rows"]:
        execution.validate_output(SPECS[row["tool"]], row["result"])
        if row["tool"] == "bazi_marriage" and row["variant"] == "unknown_gender":
            value = row["result"]["marriage_analysis"]
            assert value["marriage_quality"]["score"] is None
            assert set(value["spouse_star"]["alternatives"]) == {"male", "female"}
        if row["variant"] == "manual_timing":
            ctx = row["result"][row["tool"].removeprefix("bazi_") + "_analysis"][
                "timing_context"
            ]
            assert (
                ctx["source"] == "explicit_pillar_overrides"
                and "analysis_datetime" not in ctx
            )
        if row["tool"] == "analyze_destiny" and row["variant"].startswith(
            "solar_cross_"
        ):
            ctx = row["result"]["calendar_context"]
            assert (
                ctx["lunar_calendar"] is None
                and ctx["lunar_calendar_support"]["supported"] is False
            )


def test_error_envelopes_and_other_domain_guards_keep_their_own_contract():
    for tool in TOOLS:
        malformed = {"error": "无效输入", "error_code": "validation_error"}
        with pytest.raises(old_validator().__globals__["OutputContractError"]):
            old_validator()(SPECS[tool], malformed)
        with pytest.raises(execution.OutputContractError):
            execution.validate_output(SPECS[tool], malformed)
        execution.validate_output(
            SPECS[tool],
            {"error": "无效输入", "error_code": "validation_error", "retryable": False},
        )
    require_complete_bazi_anchors("sixyao", {})


def test_full_output_guard_never_calls_any_birth_or_strength_solver(monkeypatch):
    import fatebridge.services.birth_context as context
    from fatebridge.core.elements import ElementAnalysis

    def forbidden(*args, **kwargs):
        raise AssertionError("Full-output validation compares supplied facts only")

    monkeypatch.setattr(ElementAnalysis, "analyze_day_master_strength", forbidden)
    monkeypatch.setattr(context, "build_birth_computation_context", forbidden)
    for row in baseline()["rows"]:
        execution.validate_output(SPECS[row["tool"]], row["result"])


def base(tool):
    return next(
        r for r in baseline()["rows"] if r["tool"] == tool and r["variant"] == "base"
    )


def projection(tool):
    if tool == "analyze_destiny":
        return "day_master.stem"
    if tool == "bazi_birth":
        return "bazi_birth.four_pillars.day.stem"
    return tool.removeprefix("bazi_") + "_analysis.evidence_chain.method_id"


@pytest.mark.parametrize("tool", TOOLS)
def test_actual_supported_surfaces_preserve_healthy_partial_projection(
    tool, rest, tmp_path, capsys
):
    spec = SPECS[tool]
    payload = base(tool)["arguments"]
    path = projection(tool)
    opts = dict(
        as_of=AS_OF,
        fields=[path],
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
    )
    protocol = asyncio.run(native(spec, payload, **opts))
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            path,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    assert not protocol.is_error and code == 0
    assert business(protocol.structured_content) == business(cli)
    if spec.rest_path is not None:
        http = rest.post(spec.rest_path, json=payload, params=opts)
        assert http.status_code == 200 and business(http.json()) == business(cli)
    else:
        assert tool == "analyze_destiny"
    spec.output_model.model_validate(business(cli))


@pytest.mark.parametrize("tool", TOOLS)
def test_all_supported_surfaces_reject_empty_complete_business_before_projection(
    tool, rest, monkeypatch, tmp_path, capsys
):
    spec = SPECS[tool]
    payload = base(tool)["arguments"]
    path = projection(tool)
    bad = next(
        c["payload"]
        for c in controls()
        if c["tool"] == tool and c["kind"] == "empty_business"
    )
    original = execution.execute_spec

    def corrupt(actual, parsed):
        if actual.key == tool:
            actual = replace(actual, bind=lambda _: (lambda: deepcopy(bad), (), {}))
        return original(actual, parsed)

    monkeypatch.setattr(execution, "execute_spec", corrupt)
    opts = dict(
        as_of=AS_OF, fields=[path], strict_fields=True, include_snapshot_text=False
    )
    protocol = asyncio.run(native(spec, payload, **opts))
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            path,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ],
    )
    assert protocol.is_error and code == 1 and cli["error_code"] == "internal_error"
    assert protocol.structured_content["error_code"] == "internal_error"
    if spec.rest_path is not None:
        http = rest.post(spec.rest_path, json=payload, params=opts)
        assert http.status_code == 500 and http.json()["error_code"] == "internal_error"

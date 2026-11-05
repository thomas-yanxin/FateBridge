"""Seasonal explanations and partial views must follow their available anchors."""

import asyncio
import copy
import importlib.util
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import pytest
from pydantic import ValidationError

import fatebridge.application.execution as execution
from fatebridge.core.output_chinese import JinkouCourse
from tests.evaluation.test_agentic_nested_outputs import (
    AS_OF,
    REST_POST_CASES,
    SPECS,
    call_cli,
    native,
    rest,
)

ROOT = Path(__file__).resolve().parents[2]
MODULE = importlib.util.spec_from_file_location(
    "seasonal_binding", ROOT / "scripts/ren/audit_jinkou_seasonal_binding.py"
)
assert MODULE and MODULE.loader
AUDIT = importlib.util.module_from_spec(MODULE)
MODULE.loader.exec_module(AUDIT)
REF = AUDIT.reference()
FAULTS = [
    f"{course}_{operation}_basis"
    for course in ("main", "annual")
    for operation in ("forged", "missing", "null")
]
SPEC = SPECS["jinkou"]
PAYLOAD = {
    **REST_POST_CASES[SPEC.rest_path](),
    "birth_year_ganzhi": "甲子",
    "year_fate_age": 43,
    "gender": "男",
}


@lru_cache(maxsize=1)
def output():
    fn, args, kw = SPEC.bind(SPEC.request_model.model_validate(PAYLOAD))
    return fn(*args, **kw)


def test_primary_25_cells_keep_month_duration_and_daily_rules_unresolved():
    from fatebridge.core.metaphysics.jinkou_seasonal import seasonal_power

    for season, states in REF["seasons"].items():
        for month in REF["configured_months"][season]:
            for element, expected in zip(REF["elements"], states):
                assert seasonal_power(month, element) == expected
    assert not REF["whole_month_classical_acceptance"]
    assert not REF["daily_five_states_adjudicated"]
    assert not REF["comprehensive_use_adjudicated"] and not REF["goal_complete"]


@pytest.mark.parametrize("fault", FAULTS)
def test_full_main_and_annual_basis_is_required_and_calculation_bound(fault):
    with pytest.raises(execution.OutputContractError):
        execution.validate_output(SPEC, AUDIT.corrupt(output(), fault))


@pytest.mark.parametrize("fault", ["seasonal_power", "basis", "invalid_month"])
def test_partial_course_uses_its_present_month_anchor(fault):
    with pytest.raises(ValidationError):
        JinkouCourse.model_validate(AUDIT.corrupt(output(), "sparse_" + fault))


@pytest.mark.parametrize("fault", FAULTS)
@pytest.mark.parametrize("project", [False, True])
def test_contradictory_explanation_is_rejected_before_projection_on_three_ports(
    fault, project, rest, monkeypatch, tmp_path, capsys
):
    bad = AUDIT.corrupt(output(), fault)
    original = execution.execute_spec

    def broken(spec, request):
        if spec.key == SPEC.key:
            spec = replace(spec, bind=lambda _: (lambda: copy.deepcopy(bad), (), {}))
        return original(spec, request)

    monkeypatch.setattr(execution, "execute_spec", broken)
    params = {"as_of": AS_OF, "response_char_limit": 0}
    opts = {}
    flags = ["--response-char-limit", "0"]
    if project:
        params.update(fields="analysis_type", strict_fields="true")
        opts.update(fields=["analysis_type"], strict_fields=True)
        flags += ["--fields", "analysis_type", "--strict-fields", "true"]
    http = rest.post(SPEC.rest_path, json=PAYLOAD, params=params)
    protocol = asyncio.run(native(SPEC, PAYLOAD, **opts))
    code, cli = call_cli(SPEC, PAYLOAD, tmp_path, capsys, flags=flags)
    assert http.status_code == 500 and protocol.is_error and code == 1
    assert cli["error_code"] == "internal_error"


def test_projection_does_not_invent_missing_month_or_five_state_values():
    for value in (
        {},
        {"rows": [{"seasonal_power": "旺"}]},
        {"overview": {"power_basis": None}},
        {
            "qi_evidence": {"month_building_branch": "寅"},
            "rows": [{"element": "木", "seasonal_power": None}],
        },
    ):
        assert (
            JinkouCourse.model_validate(value).model_dump(exclude_unset=True) == value
        )


@pytest.mark.parametrize("project", [False, True])
def test_correct_main_and_annual_explanations_survive_three_ports(
    project, rest, tmp_path, capsys
):
    fields = ["jinkou.overview.power_basis", "jinkou.rows", "jinkou.year_fate.course"]
    params = [("as_of", AS_OF), ("response_char_limit", "0")]
    flags = ["--response-char-limit", "0"]
    opts = {}
    if project:
        params += [("fields", f) for f in fields] + [("strict_fields", "true")]
        flags += ["--fields", *fields, "--strict-fields", "true"]
        opts.update(fields=fields, strict_fields=True)
    http = rest.post(SPEC.rest_path, json=PAYLOAD, params=params)
    protocol = asyncio.run(native(SPEC, PAYLOAD, **opts))
    code, cli = call_cli(SPEC, PAYLOAD, tmp_path, capsys, flags=flags)
    assert http.status_code == 200 and not protocol.is_error and code == 0
    expected = output()["jinkou"]
    for body in (http.json(), protocol.structured_content, cli):
        assert (
            body["jinkou"]["overview"]["power_basis"]
            == expected["overview"]["power_basis"]
        )
        assert body["jinkou"]["rows"] == expected["rows"]
        assert body["jinkou"]["year_fate"]["course"] == expected["year_fate"]["course"]

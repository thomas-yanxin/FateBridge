"""Separate 神将建旺 from phase strength, earth seats and comprehensive use."""

import asyncio
import copy
import importlib.util
import json
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import pytest
from pydantic import ValidationError

import fatebridge.application.execution as execution
from fatebridge.core.output_chinese import JinkouQiEvidence
from scripts.ren.audit_ren_classical import observe_jinkou
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
    "month_building_audit", ROOT / "scripts/ren/audit_jinkou_month_building.py"
)
assert MODULE and MODULE.loader
AUDIT = importlib.util.module_from_spec(MODULE)
MODULE.loader.exec_module(AUDIT)
REF = AUDIT.reference()
FAULTS = json.loads((AUDIT.CORPUS / "protocol.json").read_text())["faults"]
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


@pytest.mark.parametrize("case", REF["symbolic_cases"], ids=lambda c: c["id"])
def test_symbolic_source_contrasts_reach_the_actual_board(case):
    board = observe_jinkou(case)
    assert [board["rows"][i]["content"] for i in (1, 2)] == [
        case["expected_god"],
        case["expected_general"],
    ]
    checks = board["qi_evidence"]["month_building_checks"]
    assert [c["position"] for c in checks] == ["贵神", "将神"]
    assert [c["matched"] for c in checks] == case["expected_matched"]
    assert board["use_evidence"]["comprehensive_position"] is None


def test_main_and_annual_keep_their_own_month_building_inputs():
    body = output()
    for board in (body["jinkou"], body["jinkou"]["year_fate"]["course"]):
        qi = board["qi_evidence"]
        assert [c["branch"] for c in qi["month_building_checks"]] == [
            board["rows"][i]["content"] for i in (1, 2)
        ]
        assert qi["month_building_scan_sha256"] == REF["source_sha256"]
        assert qi["month_building_pdf_page"] == 111
        assert (
            qi["month_building_basis"] in body["snapshot_text"]
            or board is not body["jinkou"]
        )


def test_existing_complete_service_cannot_accept_a_fabricated_new_layer():
    bad = copy.deepcopy(output())
    month = bad["jinkou"]["qi_evidence"]["month_building_branch"]
    bad["jinkou"]["qi_evidence"]["month_building_checks"] = [
        dict(position=p, branch=month, month_building_branch=month, matched=False)
        for p in ("贵神", "将神")
    ]
    with pytest.raises(execution.OutputContractError):
        execution.validate_output(SPEC, bad)


def test_all_branch_triples_keep_the_complete_source_and_failure_denominator():
    report = AUDIT.audit()
    assert report["identities_match"] and report["symbolic_matched_count"] == 4
    assert (
        report["triple_count"] == 1728 and report["position_comparison_count"] == 3456
    )
    assert report["failure_count"] == 0 and not report["failures"]
    assert not report["god_advance_or_retreat_adjudicated"]
    assert not report["daily_five_states_adjudicated"]
    assert not report["comprehensive_use_adjudicated"] and not report["goal_complete"]
    assert report["independent_historical_or_reality_events"] == 0


@pytest.mark.parametrize("annual", [False, True])
@pytest.mark.parametrize("fault", FAULTS)
@pytest.mark.parametrize("project", [False, True])
def test_wrong_or_missing_new_evidence_fails_before_projection_on_all_ports(
    annual, fault, project, rest, monkeypatch, tmp_path, capsys
):
    bad = AUDIT.corrupt(output(), fault, annual)
    with pytest.raises(execution.OutputContractError):
        execution.validate_output(SPEC, bad)
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


@pytest.mark.parametrize("project", [False, True])
def test_actual_three_ports_keep_the_same_main_and_annual_month_evidence(
    project, rest, tmp_path, capsys
):
    fields = [
        "jinkou.qi_evidence",
        "jinkou.year_fate.course.qi_evidence",
        "jinkou.ruleset",
    ]
    params = [("as_of", AS_OF), ("response_char_limit", "0")]
    opts = {}
    flags = ["--response-char-limit", "0"]
    if project:
        params += [("fields", f) for f in fields] + [("strict_fields", "true")]
        flags += ["--fields", *fields, "--strict-fields", "true"]
        opts.update(fields=fields, strict_fields=True)
    http = rest.post(SPEC.rest_path, json=PAYLOAD, params=params)
    protocol = asyncio.run(native(SPEC, PAYLOAD, **opts))
    code, cli = call_cli(SPEC, PAYLOAD, tmp_path, capsys, flags=flags)
    assert http.status_code == 200 and not protocol.is_error and code == 0
    for body in (http.json(), protocol.structured_content, cli):
        assert body["jinkou"]["qi_evidence"] == output()["jinkou"]["qi_evidence"]
        assert (
            body["jinkou"]["year_fate"]["course"]["qi_evidence"]
            == output()["jinkou"]["year_fate"]["course"]["qi_evidence"]
        )


def test_sparse_source_and_month_checks_validate_present_anchors_without_filling():
    value = {
        "month_building_branch": "寅",
        "month_building_checks": [
            dict(
                position="贵神", branch="寅", month_building_branch="寅", matched=False
            )
        ],
    }
    with pytest.raises(ValidationError):
        JinkouQiEvidence.model_validate(value)
    with pytest.raises(ValidationError):
        JinkouQiEvidence.model_validate({"month_building_scan_sha256": "0" * 64})
    for value in (
        {},
        {"month_building_checks": None},
        {"month_building_branch": "寅", "month_building_checks": [{"matched": None}]},
    ):
        assert (
            JinkouQiEvidence.model_validate(value).model_dump(exclude_unset=True)
            == value
        )

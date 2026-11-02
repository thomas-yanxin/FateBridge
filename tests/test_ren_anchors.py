"""Calculation anchors must survive cross-board swaps and full-output deletion."""

import asyncio
import copy
import importlib.util
import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

import fatebridge.application.execution as execution
from tests.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    native,
    rest,
)

ROOT = Path(__file__).resolve().parents[1]
MODULE = importlib.util.spec_from_file_location(
    "ren_anchor_audit", ROOT / "scripts/audit_ren_anchors.py"
)
assert MODULE and MODULE.loader
AUDIT = importlib.util.module_from_spec(MODULE)
MODULE.loader.exec_module(AUDIT)
REFERENCE = AUDIT.reference()
FAULTS = REFERENCE["faults"]
COMPLETENESS = AUDIT.completeness_reference()


@pytest.fixture(scope="module")
def outputs():
    return AUDIT.results(REFERENCE)


def test_predeclared_value_and_deletion_denominators_stay_separate():
    result = AUDIT.audit()
    assert result["predeclared_fault_count"] == result["rejected_fault_count"] == 36
    assert result["separately_frozen_completeness_fault_count"] == 6
    assert len(result["completeness_checks"]) == 6
    assert result["fault_rejection_passed"] and result["completeness_rejection_passed"]
    assert result["valid_tool_count"] == 4
    assert result["new_classical_cases"] == result["new_empirical_outcomes"] == 0
    assert result["classical_acceptance_passed"] is result["goal_complete"] is False


@pytest.mark.parametrize("change", ["edit", "missing", "extra"])
def test_anchor_reference_inventory_and_labels_are_immutable(tmp_path, change):
    target = tmp_path / "corpus"
    shutil.copytree(AUDIT.CORPUS, target)
    if change == "edit":
        p = target / "faults.json"
        d = json.loads(p.read_text())
        d["faults"].pop()
        p.write_text(json.dumps(d))
    elif change == "missing":
        (target / "provenance.json").unlink()
    else:
        (target / "extra.json").write_text("{}")
    with pytest.raises(ValueError, match="Frozen anchor"):
        AUDIT.reference(target)


def assert_broken_on_three_ports(
    spec, bad, project, rest, monkeypatch, tmp_path, capsys
):
    original = execution.execute_spec

    def broken(actual, request):
        if actual.key == spec.key:
            actual = replace(
                actual, bind=lambda _: (lambda: copy.deepcopy(bad), (), {})
            )
        return original(actual, request)

    monkeypatch.setattr(execution, "execute_spec", broken)
    options = {}
    params = dict(as_of=AS_OF, response_char_limit=0)
    flags = ["--response-char-limit", "0"]
    if project:
        params.update(fields="analysis_type", strict_fields="true")
        options.update(fields=["analysis_type"], strict_fields=True)
        flags += ["--fields", "analysis_type", "--strict-fields", "true"]
    payload = REFERENCE["payloads"][spec.key]
    http = rest.post(spec.rest_path, json=payload, params=params)
    protocol = asyncio.run(native(spec, payload, **options))
    code, result = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    assert http.status_code == 500 and protocol.is_error and code == 1
    assert result["error_code"] == "internal_error"


@pytest.mark.parametrize("fault", FAULTS, ids=lambda f: f["tool"] + "-" + f["id"])
@pytest.mark.parametrize("project", [False, True])
def test_cross_board_and_calendar_faults_fail_before_projection(
    fault, project, outputs, rest, monkeypatch, tmp_path, capsys
):
    valid, donor = outputs
    spec = SPECS[fault["tool"]]
    bad = AUDIT.corrupt(valid[spec.key], fault, donor)
    with pytest.raises(ValidationError):
        spec.output_model.model_validate(bad)
    assert_broken_on_three_ports(
        spec, bad, project, rest, monkeypatch, tmp_path, capsys
    )


@pytest.mark.parametrize(
    "fault", COMPLETENESS, ids=lambda f: f["tool"] + "-" + f["path"]
)
@pytest.mark.parametrize("project", [False, True])
def test_full_service_cannot_delete_anchors_to_evade_conditional_guard(
    fault, project, outputs, rest, monkeypatch, tmp_path, capsys
):
    valid, _ = outputs
    spec = SPECS[fault["tool"]]
    bad = AUDIT.remove_anchor(valid[spec.key], fault["path"])
    # Public projected models intentionally accept absent fields. The service
    # completeness layer must reject deletion before any transport projects it.
    spec.output_model.model_validate(bad)
    with pytest.raises(execution.OutputContractError):
        execution.validate_output(spec, bad)
    assert_broken_on_three_ports(
        spec, bad, project, rest, monkeypatch, tmp_path, capsys
    )


@pytest.mark.parametrize("key", REFERENCE["payloads"])
@pytest.mark.parametrize("project", [False, True])
def test_valid_full_and_anchored_projections_still_agree_on_all_ports(
    key, project, rest, tmp_path, capsys
):
    spec = SPECS[key]
    payload = REFERENCE["payloads"][key]
    prefix = "subresults.liureng_gods." if key == "sanshiunited" else ""
    fields = [
        prefix + "four_pillars.day",
        prefix + "liureng.xun_head",
        prefix + "liureng.life_stages.day_stem",
    ]
    if key == "jinkou":
        fields += ["jinkou.rows", "jinkou.stem_relations", "jinkou.overview"]
    params = [("as_of", AS_OF), ("response_char_limit", "0")]
    options = {}
    flags = ["--response-char-limit", "0"]
    if project:
        params += [("fields", f) for f in fields] + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ]
        options.update(fields=fields, strict_fields=True, include_snapshot_text=False)
        flags += [
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ]
    http = rest.post(spec.rest_path, json=payload, params=params)
    protocol = asyncio.run(native(spec, payload, **options))
    code, result = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert (
        business(http.json())
        == business(protocol.structured_content)
        == business(result)
    )
    for data in [http.json(), protocol.structured_content, result]:
        spec.output_model.model_validate(data)


@pytest.mark.parametrize(
    "key,value",
    [
        ("jinkou", {"jinkou": {"stem_relations": {"day_stem": "乙"}}}),
        ("jinkou", {"four_pillars": {"day": {"stem": "乙"}}}),
        (
            "jinkou",
            {
                "jinkou": {
                    "rows": [{"label": n} for n in ["人元", "贵神", "将神", "地分"]]
                }
            },
        ),
        ("liureng_gods", {"liureng": {"life_stages": {"day_stem": "乙"}}}),
        ("liureng_runyear", {"runyear": {"year_fate": {"day_ganzhi": "乙丑"}}}),
        (
            "sanshiunited",
            {"subresults": {"liureng_gods": {"four_pillars": {"day": {"stem": "乙"}}}}},
        ),
    ],
)
def test_public_sparse_models_do_not_invent_missing_anchors(key, value):
    assert (
        SPECS[key].output_model.model_validate(value).model_dump(exclude_unset=True)
        == value
    )


def test_complete_gate_is_scoped_to_the_four_ren_tool_families():
    from fatebridge.core.output_ren_anchors import require_complete_ren_anchors

    require_complete_ren_anchors("taiyi", {})
    require_complete_ren_anchors("qimen", {})

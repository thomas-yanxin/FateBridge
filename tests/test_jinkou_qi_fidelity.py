"""Reject contradictory qi prose and sparse facts on the actual public paths."""

import asyncio
import copy
import hashlib
import json
import shutil
from dataclasses import replace

import pytest
from pydantic import ValidationError

import fatebridge.application.execution as execution
from fatebridge.core.output_chinese import JinkouCourse, JinkouQiEvidence
from scripts.audit_jinkou_qi_fidelity import CORPUS, audit, reference
from tests.test_agentic_nested_outputs import AS_OF, business, call_cli, native, rest
from tests.test_jinkou_branch_breaks import PAYLOAD, SPEC, course, native_solar, raw

FAULTS = {
    "basis": "月建子、将神丑相距0支，所选月建条文：建旺；日支午属水，生将神金。",
    "scope": "完整日下五态和综合用神均已唯一裁定，成功概率100%。",
    "source_url": "https://invalid.example/fabricated-classic",
    "source_section": "并不存在的整本认证",
}


def test_independent_month_day_and_combined_cohorts():
    result = audit()
    assert result["month_matrix_count"] == result["day_matrix_count"] == 144
    assert result["combined_count"] == 1728 and result["finite_facts_passed"]
    assert not result["daily_five_states_adjudicated"]
    assert not result["comprehensive_use_adjudicated"]
    data = reference()
    assert sum(c["month_qi_label"] is None for c in data["month_matrix"]) == 84
    assert sum(c["day_generates_general"] for c in data["day_matrix"]) == 28


@pytest.mark.parametrize("change", ["page", "reference", "joint"])
def test_original_reading_cannot_be_rewritten_with_its_manifest(tmp_path, change):
    target = tmp_path / "qi"
    shutil.copytree(CORPUS, target)
    name = "page-112.jpg" if change == "page" else "reference.json"
    path = target / name
    path.write_bytes(path.read_bytes() + b" ")
    if change == "joint":
        manifest = json.loads((target / "freeze.json").read_text())
        manifest[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        (target / "freeze.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Frozen qi reference"):
        reference(target)


@pytest.mark.parametrize(
    "value",
    [
        {},
        {"month_qi_label": None},
        {"month_building_branch": None, "month_offset": None},
        {"day_branch": None, "day_generates_general": None},
        {"jiangshen_branch": "子"},
        {"month_offset": 3, "month_qi_label": None},
    ],
)
def test_sparse_views_keep_omitted_or_unknown_facts(value):
    assert (
        JinkouQiEvidence.model_validate(value).model_dump(exclude_unset=True) == value
    )


@pytest.mark.parametrize(
    "value",
    [
        {"month_building_branch": "亥", "jiangshen_branch": "子", "month_offset": 0},
        {
            "month_building_branch": "丑",
            "jiangshen_branch": "子",
            "month_qi_label": "进气相",
        },
        {"month_offset": 3, "month_qi_label": "建旺"},
        {"month_offset": 3, "month_qi_status": "matched_excerpt"},
        {"month_offset": True},
        {"month_offset": 12},
        {"month_offset": -1},
        {"day_branch": "子", "day_element": "火"},
        {"jiangshen_branch": "辰", "jiangshen_element": "木"},
        {"day_branch": "子", "jiangshen_branch": "寅", "day_generates_general": False},
        {
            "day_element": "火",
            "jiangshen_element": "土",
            "day_generates_general": False,
        },
        {"day_generates_general": 1},
        {"month_building_branch": None, "month_offset": 0},
        {"day_branch": None, "day_generates_general": False},
        {"jiangshen_branch": None, "jiangshen_element": "水"},
    ],
)
def test_sparse_views_reject_only_present_contradictions(value):
    with pytest.raises(ValidationError):
        JinkouQiEvidence.model_validate(value)


@pytest.mark.parametrize("key", list(FAULTS))
def test_trace_only_views_check_own_text_metadata_and_computed_anchors(key):
    trace = copy.deepcopy(
        next(
            t
            for t in raw()["jinkou"]["rule_trace"]
            if t["rule_id"] == "jinkou.month_day_qi"
        )
    )
    trace["result"][key] = FAULTS[key]
    with pytest.raises(ValidationError):
        JinkouCourse.model_validate(dict(rule_trace=[trace]))
    if key in ("source_url", "source_section"):
        trace["result"][key] = raw()["jinkou"]["qi_evidence"][key]
        trace[key] = FAULTS[key]
        with pytest.raises(ValidationError):
            JinkouCourse.model_validate(dict(rule_trace=[trace]))


@pytest.mark.parametrize("role", ["primary", "natal_course", "year_fate"])
@pytest.mark.parametrize("project", [False, True])
@pytest.mark.parametrize("key", list(FAULTS))
def test_wrong_deterministic_text_is_rejected_before_projection_on_three_ports(
    role, project, key, rest, monkeypatch, tmp_path, capsys
):
    bad = copy.deepcopy(raw())
    board = course(bad, role)
    board["qi_evidence"][key] = FAULTS[key]
    for trace in board["rule_trace"]:
        if trace["rule_id"] == "jinkou.month_day_qi":
            trace["result"][key] = FAULTS[key]
    with pytest.raises(execution.OutputContractError):
        execution.validate_output(SPEC, bad)
    original = execution.execute_spec

    def broken(spec, request):
        if spec.key == "jinkou":
            spec = replace(spec, bind=lambda _: (lambda: copy.deepcopy(bad), (), {}))
        return original(spec, request)

    monkeypatch.setattr(execution, "execute_spec", broken)
    params = dict(as_of=AS_OF, response_char_limit="0")
    flags, options = ["--response-char-limit", "0"], {}
    if project:
        params.update(fields="analysis_type", strict_fields="true")
        flags += ["--fields", "analysis_type", "--strict-fields", "true"]
        options = dict(fields=["analysis_type"], strict_fields=True)
    http = rest.post(SPEC.rest_path, json=PAYLOAD, params=params)
    protocol = asyncio.run(native(SPEC, PAYLOAD, **options))
    code, cli = call_cli(SPEC, PAYLOAD, tmp_path, capsys, flags=flags)
    assert http.status_code == 500 and protocol.is_error and code == 1
    assert cli["error_code"] == "internal_error"


@pytest.mark.parametrize("project", [False, True])
def test_valid_unchanged_qi_is_preserved_across_three_ports(
    project, rest, tmp_path, capsys
):
    fields = [
        "jinkou.qi_evidence",
        "jinkou.natal_course.course.qi_evidence",
        "jinkou.year_fate.course.qi_evidence",
    ]
    params = [("as_of", AS_OF), ("response_char_limit", "0")]
    flags, options = ["--response-char-limit", "0"], {}
    if project:
        params += [("fields", f) for f in fields] + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ]
        flags += [
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ]
        options = dict(fields=fields, strict_fields=True, include_snapshot_text=False)
    http = rest.post(SPEC.rest_path, json=PAYLOAD, params=params)
    protocol = asyncio.run(native(SPEC, PAYLOAD, **options))
    code, cli = call_cli(SPEC, PAYLOAD, tmp_path, capsys, flags=flags)
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    assert (
        business(http.json()) == business(cli) == business(protocol.structured_content)
    )
    for body in (http.json(), cli, protocol.structured_content):
        for role in ("primary", "natal_course", "year_fate"):
            assert (
                course(body, role)["qi_evidence"] == course(raw(), role)["qi_evidence"]
            )


def test_shared_helper_cannot_be_its_own_independent_month_oracle(monkeypatch):
    import fatebridge.core.metaphysics.jinkou_qi as production

    original = production.month_qi_facts

    def wrong(month, general):
        result = original(month, general)
        result["month_offset"] = (result["month_offset"] + 1) % 12
        return result

    monkeypatch.setattr(production, "month_qi_facts", wrong)
    result = audit()
    assert not result["finite_facts_passed"]
    assert len(result["month_failures"]) == 144
    assert len(result["combined_failures"]) == 1728

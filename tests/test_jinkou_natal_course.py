"""Full, separately anchored natal courses from confirmed natal inputs."""

import asyncio
import copy
import json
from dataclasses import replace
from functools import lru_cache

import pytest

import fatebridge.application.execution as execution
from scripts.audit_jinkou_natal_course import CORPUS, observe, reference
from scripts.audit_ren_classical import observe_jinkou
from tests.test_agentic_nested_outputs import AS_OF, SPECS, call_cli, native, rest

REF = reference()
PROTOCOL = json.loads((CORPUS / "protocol.json").read_text())
SPEC = SPECS["jinkou"]


@lru_cache(maxsize=8)
def output(which=0):
    payload = dict(PROTOCOL["public_payload"], **PROTOCOL["natal_inputs"][which])
    fn, args, kw = SPEC.bind(SPEC.request_model.model_validate(payload))
    return fn(*args, **kw)


@pytest.mark.parametrize("case", REF["cases"], ids=lambda x: x["id"])
def test_manual_symbolic_positions_then_new_derived_course(case):
    ordinary = observe_jinkou(dict(case, ground=case["natal"]))
    # The six handwritten expectations are checked before the new API call.
    if case["diurnal"] == (case["hour"] in "卯辰巳午未申"):
        assert [r["content"] for r in ordinary["rows"]] == case["expected"]
    value = observe(case)
    assert value["source_sha256"] == REF["source_sha256"]
    assert value["source_url"] == REF["source_url"] and value["original_pdf_pages"] == [
        168,
        169,
    ]
    assert [r["content"] for r in value["course"]["rows"]] == case["expected"]
    assert value["course"]["overview"]["di_fen_source"] == "natal_branch_derived_course"
    assert not value["course_ground_is_observed"]
    assert "natal_course" not in value["course"] and "year_fate" not in value["course"]


@pytest.mark.parametrize("which", range(4))
def test_natal_course_needs_only_confirmed_natal_fact_not_age_or_gender(which):
    value = output(which)["jinkou"]
    natal = value["natal_course"]
    assert value["overview"]["di_fen"] == "酉"
    assert value["year_fate"]["course"] is None
    if which < 3:
        assert natal["status"] == "calculated" and natal["natal_branch"] == "子"
        assert natal["course"]["overview"]["di_fen"] == "子"
        assert [r["content"] for r in natal["course"]["rows"]] == list("甲亥未子")
    else:
        assert natal["status"] == "missing_inputs" and natal["course"] is None
        assert natal["natal_branch"] is None


def corrupt(value, fault):
    bad = copy.deepcopy(value)
    main = bad["jinkou"]
    n = main["natal_course"]
    child = n["course"]
    if fault == "wrong_branch":
        n["natal_branch"] = "丑"
    elif fault == "wrong_source":
        n["natal_branch_source"] = "explicit_birth_year_ganzhi"
    elif fault == "wrong_birth_year":
        n["birth_year_ganzhi"] = "甲丑"
    elif fault == "wrong_ground":
        child["overview"]["di_fen"] = "丑"
    elif fault == "observed_ground_claim":
        n["course_ground_is_observed"] = True
    elif fault == "missing_child":
        n["course"] = None
    elif fault == "invented_child":
        n["status"] = "missing_inputs"
    elif fault == "wrong_human":
        child["rows"][0]["content"] = "乙"
    elif fault == "wrong_general":
        child["rows"][2]["content"] = "子"
    elif fault == "changed_month_general":
        child["overview"]["month_general"]["branch"] = "子"
    elif fault == "changed_diurnal":
        child["overview"]["is_diurnal"] = False
    elif fault == "wrong_day":
        child["calendar_policy"]["effective_day_ganzhi"] = "乙丑"
    elif fault == "wrong_trace":
        next(
            t
            for t in main["rule_trace"]
            if t["rule_id"] == "jinkou.natal_branch_course"
        )["result"]["natal_branch"] = "丑"
    elif fault == "missing_wrapper":
        del main["natal_course"]
    elif fault == "wrong_scan":
        n["source_sha256"] = "0" * 64
    elif fault == "recursive_course":
        child["natal_course"] = {"course": {}}
    else:
        raise ValueError(fault)
    return bad


@pytest.mark.parametrize("fault", PROTOCOL["faults"])
@pytest.mark.parametrize("project", [False, True])
def test_natal_facts_and_full_child_reject_corruption_before_projection(
    fault, project, rest, monkeypatch, tmp_path, capsys
):
    bad = corrupt(output(), fault)
    with pytest.raises(execution.OutputContractError):
        execution.validate_output(SPEC, bad)
    original = execution.execute_spec

    def broken(spec, request):
        if spec.key == "jinkou":
            spec = replace(spec, bind=lambda _: (lambda: copy.deepcopy(bad), (), {}))
        return original(spec, request)

    monkeypatch.setattr(execution, "execute_spec", broken)
    payload = dict(PROTOCOL["public_payload"], natal_branch="子")
    params = {"as_of": AS_OF, "response_char_limit": 0}
    opts = {}
    flags = ["--response-char-limit", "0"]
    if project:
        params.update(fields="analysis_type", strict_fields="true")
        opts.update(fields=["analysis_type"], strict_fields=True)
        flags += ["--fields", "analysis_type", "--strict-fields", "true"]
    http = rest.post(SPEC.rest_path, json=payload, params=params)
    mcp = asyncio.run(native(SPEC, payload, **opts))
    code, cli = call_cli(SPEC, payload, tmp_path, capsys, flags=flags)
    assert (
        http.status_code == 500
        and mcp.is_error
        and code == 1
        and cli["error_code"] == "internal_error"
    )


@pytest.mark.parametrize("project", [False, True])
def test_three_ports_deliver_full_separate_natal_course(
    project, rest, tmp_path, capsys
):
    payload = dict(PROTOCOL["public_payload"], natal_branch="子")
    fields = ["four_pillars", "jinkou.overview", "jinkou.natal_course"]
    params = [("as_of", AS_OF), ("response_char_limit", "0")]
    opts = {}
    flags = ["--response-char-limit", "0"]
    if project:
        params += [("fields", p) for p in fields] + [("strict_fields", "true")]
        opts.update(fields=fields, strict_fields=True)
        flags += ["--fields", *fields, "--strict-fields", "true"]
    http = rest.post(SPEC.rest_path, json=payload, params=params)
    mcp = asyncio.run(native(SPEC, payload, **opts))
    code, cli = call_cli(SPEC, payload, tmp_path, capsys, flags=flags)
    assert http.status_code == 200 and not mcp.is_error and code == 0
    for body in [http.json(), mcp.structured_content, cli]:
        assert body["jinkou"]["natal_course"] == output()["jinkou"]["natal_course"]
        assert body["jinkou"]["overview"]["di_fen"] == "酉"
    if not project:
        assert "[京本本命另课]" in http.json()["snapshot_text"]


def test_both_natal_and_annual_courses_coexist_without_recursion():
    payload = dict(
        PROTOCOL["public_payload"],
        birth_year_ganzhi="甲子",
        year_fate_age=20,
        gender="男",
    )
    fn, args, kw = SPEC.bind(SPEC.request_model.model_validate(payload))
    value = fn(*args, **kw)
    execution.validate_output(SPEC, value)
    main = value["jinkou"]
    assert main["natal_course"]["course"]["overview"]["di_fen"] == "子"
    assert (
        main["year_fate"]["course"]["overview"]["di_fen"] == main["year_fate"]["branch"]
    )
    assert main["overview"]["di_fen"] == "酉"


def test_sparse_natal_views_preserve_absence_and_explicit_unknown():
    from fatebridge.core.output_chinese import Jinkou, JinkouNatalCourse

    for value in [{}, {"natal_branch": None}, {"status": "calculated"}]:
        assert (
            JinkouNatalCourse.model_validate(value).model_dump(exclude_unset=True)
            == value
        )
    value = {"natal_course": {"natal_branch": None}}
    assert Jinkou.model_validate(value).model_dump(exclude_unset=True) == value


@pytest.mark.parametrize(
    "field", ["course_ground_is_observed", "birth_year_calendar_boundary_verified"]
)
@pytest.mark.parametrize("bad", [True, 0, 1])
def test_partial_natal_flags_cannot_invent_observation_or_certification(field, bad):
    from pydantic import ValidationError

    from fatebridge.core.output_chinese import JinkouNatalCourse

    with pytest.raises(ValidationError):
        JinkouNatalCourse.model_validate({field: bad})


def test_natal_course_does_not_claim_comprehensive_judgement():
    from pydantic import ValidationError

    from fatebridge.core.output_chinese import JinkouNatalCourse

    with pytest.raises(ValidationError):
        JinkouNatalCourse.model_validate({"comprehensive_judgement": "已认证大吉"})


@pytest.mark.parametrize("section", ["京本本命另课", "京本行年另课"])
def test_both_derived_courses_are_registered_and_individually_exportable(
    section, rest, tmp_path, capsys
):
    payload = dict(
        PROTOCOL["public_payload"], natal_branch="子", selected_sections=[section]
    )
    http = rest.post(
        SPEC.rest_path, json=payload, params={"as_of": AS_OF, "response_char_limit": 0}
    )
    mcp = asyncio.run(native(SPEC, payload))
    code, cli = call_cli(SPEC, payload, tmp_path, capsys)
    assert http.status_code == 200 and not mcp.is_error and code == 0
    for body in [http.json(), mcp.structured_content, cli]:
        e = body["snapshot_export"]
        assert e["unknown_detected_sections"] == []
        assert [s["title"] for s in e["sections"] if s["included"]] == [section]
        assert e["export_text"].startswith("[" + section + "]")

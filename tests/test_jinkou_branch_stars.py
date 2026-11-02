"""Selected Jingben calendar anchors, branch identities and honest scope."""

import asyncio
import copy
import json
import shutil
from dataclasses import replace

import pytest
from pydantic import ValidationError

import fatebridge.application.execution as execution
from fatebridge.application.examples import evidence_views
from fatebridge.core.metaphysics.jinkou_branch_stars import branch_stars
from fatebridge.core.output_chinese import Jinkou
from fatebridge.core.output_jinkou_branch_stars import (
    JinkouBranchStars,
    require_complete_branch_stars,
)
from scripts.audit_jinkou_branch_stars import CORPUS, reference
from tests.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    native,
    rest,
)
from tests.test_jinkou_natal import raw
from tests.test_ren_transports import PAYLOAD

REF = reference()
SPEC = SPECS["jinkou"]


def value(case=None):
    c = case or REF["synthetic_cases"][0]
    return branch_stars(
        year_branch=c["year"],
        month_branch=c["month"],
        day_ganzhi=c["day"],
        input_branches=dict(zip(("贵神", "将神", "地分"), c["branches"])),
    )


@pytest.mark.parametrize("c", REF["synthetic_cases"], ids=lambda c: c["id"])
def test_predeclared_original_target_examples(c):
    result = value(c)
    JinkouBranchStars.model_validate(result)
    observed = {
        v["id"]: v["matched_day"] if v["id"] == "tianshe" else v["matched_positions"]
        for v in result["checks"]
    }
    assert observed == c["expected"]
    assert result["comprehensive_effect"] is None
    assert result["complete_classical_conformance"] is False


def test_month_horse_is_distinct_from_day_horse_and_soil_strength_profile():
    v = value()
    assert v["day_ganzhi"] == "甲申" and v["month_building_branch"] == "寅"
    assert next(c["target"] for c in v["checks"] if c["id"] == "yima") == "申"
    assert value(REF["synthetic_cases"][1])["season_partition"] == "春"
    assert value(REF["synthetic_cases"][-1])["season_partition"] == "冬"


@pytest.mark.parametrize("fault", ["edit", "delete", "extra"])
def test_frozen_source_and_denominators_cannot_be_replaced(tmp_path, fault):
    d = tmp_path / "copy"
    shutil.copytree(CORPUS, d)
    if fault == "edit":
        p = d / "reference.json"
        v = json.loads(p.read_text())
        v["yima_anchor"] = "day_branch"
        p.write_text(json.dumps(v))
    elif fault == "delete":
        (d / "source-pages.pdf").unlink()
    else:
        (d / "unregistered.txt").write_text("extra")
    with pytest.raises((ValueError, FileNotFoundError), match="Frozen|No such file"):
        reference(d)


@pytest.mark.parametrize(
    "fault",
    [
        "day_horse",
        "soil_season",
        "year_direction",
        "day_stem_only",
        "god_earth",
        "prune",
        "duplicate",
        "positions",
        "true",
        "zero",
        "effect",
    ],
)
def test_copresent_facts_do_not_allow_conflated_targets(fault):
    v = copy.deepcopy(value())
    if fault == "day_horse":
        v["checks"][2]["target"] = "寅"
    elif fault == "soil_season":
        v["season_partition"] = "夏"
    elif fault == "year_direction":
        v["checks"][4]["target"] = "戌"
    elif fault == "day_stem_only":
        v["checks"][-1]["matched_day"] = True
    elif fault == "god_earth":
        v["input_branches"]["贵神"] = "戌"
    elif fault == "prune":
        v["checks"].pop()
    elif fault == "duplicate":
        v["checks"][1] = v["checks"][0]
    elif fault == "positions":
        v["checks"][2]["matched_positions"] *= 2
    elif fault == "true":
        v["complete_classical_conformance"] = True
    elif fault == "zero":
        v["complete_classical_conformance"] = 0
    else:
        v["comprehensive_effect"] = "保证成功"
    with pytest.raises(ValidationError):
        JinkouBranchStars.model_validate(v)


def test_sparse_views_retain_only_requested_facts_and_validate_known_context():
    v = value()
    partial = {"checks": v["checks"], "month_building_branch": "寅"}
    assert (
        JinkouBranchStars.model_validate(partial).model_dump(exclude_unset=True)
        == partial
    )
    partial["month_building_branch"] = "卯"
    with pytest.raises(ValidationError):
        JinkouBranchStars.model_validate(partial)
    assert JinkouBranchStars.model_validate(
        {"input_branches": {"贵神": "申"}}
    ).model_dump(exclude_unset=True) == {"input_branches": {"贵神": "申"}}


@pytest.mark.parametrize(
    "star,target", [("tianma", "卯"), ("yima", "卯"), ("tianshe", "乙丑")]
)
def test_omitted_calendar_does_not_allow_targets_absent_from_the_named_rule(
    star, target
):
    checks = copy.deepcopy(value()["checks"])
    next(c for c in checks if c["id"] == star)["target"] = target
    with pytest.raises(ValidationError):
        JinkouBranchStars.model_validate({"checks": checks})


@pytest.mark.parametrize(
    "fault", ["missing", "trace", "duplicate_trace", "forged_trace", "prune"]
)
def test_complete_result_retains_all_explanation_dependencies(fault):
    b = json.loads(json.dumps(raw()["jinkou"]))
    trace = next(
        t for t in b["rule_trace"] if t["rule_id"] == "jinkou.jingben_branch_stars"
    )
    if fault == "missing":
        b.pop("branch_stars")
    elif fault == "trace":
        b["rule_trace"].remove(trace)
    elif fault == "duplicate_trace":
        b["rule_trace"].append(copy.deepcopy(trace))
    elif fault == "forged_trace":
        trace["result"]["year_branch"] = "子"
    else:
        b["branch_stars"]["checks"].pop()
    with pytest.raises(ValueError):
        require_complete_branch_stars(b)


def test_published_view_on_real_rest_native_mcp_and_cli(rest, tmp_path, capsys):
    fields = evidence_views(SPEC)["branch_stars"]["fields"]
    payload = dict(PAYLOAD, di_fen="酉")
    opts = dict(fields=fields, strict_fields=True, include_snapshot_text=False)
    h = rest.post(
        SPEC.rest_path,
        json=payload,
        params=[
            ("as_of", AS_OF),
            ("response_char_limit", "0"),
            ("include_snapshot_text", "false"),
            ("strict_fields", "true"),
            *[("fields", f) for f in fields],
        ],
    )
    m = asyncio.run(native(SPEC, payload, **opts))
    code, c = call_cli(
        SPEC,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    assert h.status_code == 200 and not m.is_error and code == 0
    assert business(h.json()) == business(m.structured_content) == business(c)
    assert c["jinkou"]["ruleset"]["version"] == "1.16.0"
    for body in [h.json(), m.structured_content, c]:
        SPEC.output_model.model_validate(body)


@pytest.mark.parametrize("fault", ["missing", "wrong_year", "trace"])
@pytest.mark.parametrize("project", [False, True])
def test_domain_faults_fail_on_all_ports_before_projection(
    fault, project, rest, monkeypatch, tmp_path, capsys
):
    bad = json.loads(json.dumps(raw()))
    b = bad["jinkou"]
    v = b["branch_stars"]
    t = next(
        t for t in b["rule_trace"] if t["rule_id"] == "jinkou.jingben_branch_stars"
    )
    if fault == "missing":
        b.pop("branch_stars")
    elif fault == "trace":
        b["rule_trace"].remove(t)
    else:
        v = branch_stars(
            year_branch="子" if v["year_branch"] != "子" else "丑",
            month_branch=v["month_building_branch"],
            day_ganzhi=v["day_ganzhi"],
            input_branches=v["input_branches"],
        )
        b["branch_stars"] = v
        t["result"] = copy.deepcopy(v)
    original = execution.execute_spec

    def broken(actual, request):
        if actual.key == "jinkou":
            actual = replace(
                actual, bind=lambda _: (lambda: copy.deepcopy(bad), (), {})
            )
        return original(actual, request)

    monkeypatch.setattr(execution, "execute_spec", broken)
    params = {"as_of": AS_OF, "response_char_limit": 0}
    opts = {}
    flags = ["--response-char-limit", "0"]
    if project:
        params.update(fields="analysis_type", strict_fields="true")
        opts.update(fields=["analysis_type"], strict_fields=True)
        flags += ["--fields", "analysis_type", "--strict-fields", "true"]
    h = rest.post(SPEC.rest_path, json=PAYLOAD, params=params)
    m = asyncio.run(native(SPEC, PAYLOAD, **opts))
    code, c = call_cli(SPEC, PAYLOAD, tmp_path, capsys, flags=flags)
    assert h.status_code == 500 and m.is_error and code == 1
    assert c["error_code"] == "internal_error"


def test_snapshot_reports_each_actual_target_and_match_without_invented_effect():
    b = raw()
    v = b["jinkou"]["branch_stars"]
    for c in v["checks"]:
        anchor_label = {
            "month_building": "月建",
            "year_branch": "年支",
            "season_and_day": "四季与占日",
        }[c["category"]]
        status = (
            ("符合占日" if c["matched_day"] else "未合占日")
            if c["target_kind"] == "day_ganzhi"
            else "本支相同位置：" + ("、".join(c["matched_positions"]) or "无")
        )
        assert (
            f"{c['name']}：目标{c['target']}，依据{anchor_label}，{status}；原PDF{c['original_pdf_page']}。"
            in b["snapshot_text"]
        )
    assert v["scope"] in b["snapshot_text"]


def test_star_body_cannot_borrow_god_occupied_position():
    request = SPEC.request_model.model_validate(dict(PAYLOAD, di_fen="子"))
    fn, args, kwargs = SPEC.bind(request)
    b = fn(*args, **kwargs)["jinkou"]
    earth = b["overview"]["guishen"]["earth_branch"]
    assert earth != b["branch_stars"]["input_branches"]["贵神"]
    b["branch_stars"]["input_branches"]["贵神"] = earth
    with pytest.raises(ValidationError):
        Jinkou.model_validate(b)

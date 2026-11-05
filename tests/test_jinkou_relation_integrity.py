"""Same-course Jingben facts, with original source failures left untouched."""

import copy
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.application.execution import validate_output
from fatebridge.core.output_chinese import Jinkou, JinkouRelations
from tests.test_agentic_nested_outputs import SPECS, rest
from tests.test_ren_anchors import assert_broken_on_three_ports
from tests.test_ren_classical_depth import AUDIT

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/jinkou_relation_integrity_v1"
PIN = "a522ad91924073b0a74bbfd22e71270a2d33f16d5cb6b7337ef3826c042129dc"
SPEC = SPECS["jinkou"]


def reference():
    assert hashlib.sha256((CORPUS / "freeze.json").read_bytes()).hexdigest() == PIN
    frozen = json.loads((CORPUS / "freeze.json").read_text())
    assert {p.name for p in CORPUS.iterdir()} == {*frozen["files"], "freeze.json"}
    assert all(
        hashlib.sha256((CORPUS / n).read_bytes()).hexdigest() == h
        for n, h in frozen["files"].items()
    )
    return json.loads((CORPUS / "reference.json").read_text())


def board():
    return AUDIT.observe_jinkou(dict(day="丙申", hour="丑", ground="巳", general="子"))


FAULTS = (
    "absolute_matches",
    "absolute_phase",
    "absolute_class",
    "absolute_page",
    "absolute_roles",
    "absolute_prune",
    "absolute_duplicate",
    "defeat_matches",
    "defeat_target",
    "defeat_position",
    "defeat_phase_coherent",
    "defeat_seat_coherent",
    "defeat_prune",
    "defeat_duplicate",
    "calendar_matches",
    "calendar_role",
    "calendar_reference",
    "calendar_branch",
    "calendar_prune",
    "calendar_duplicate",
    "source_hash",
    "source_variants",
    "false_certificate",
    "trace_only",
    "trace_duplicate",
    "trace_source",
    "alternate_year_coherent",
    "alternate_hour_coherent",
    "alternate_god_coherent",
    "trace_bad_shape",
)


def damage(value, fault):
    result = copy.deepcopy(value)
    # Domain output shares objects with its trace. JSON transport does not;
    # detach here so trace-only faults actually leave the body intact.
    result["relations"] = copy.deepcopy(value["relations"])
    rel = result["relations"]
    absolute = rel["si_jue"]["checks"]
    defeats = rel["si_bai"]["checks"]
    calendar = rel["calendar"]["checks"]
    if fault == "absolute_matches":
        for c in absolute:
            c["matched"] = not c["matched"]
    elif fault == "absolute_phase":
        absolute[0]["element"] = "金"
    elif fault == "absolute_class":
        absolute[1]["classification"] = "正绝"
    elif fault == "absolute_page":
        absolute[0]["original_pdf_page"] = 110
    elif fault == "absolute_roles":
        absolute[0]["left_position"] = "贵神"
    elif fault == "absolute_prune":
        absolute.pop()
    elif fault == "absolute_duplicate":
        absolute[1] = copy.deepcopy(absolute[0])
    elif fault == "defeat_matches":
        for c in defeats:
            c["matched"] = not c["matched"]
    elif fault == "defeat_target":
        defeats[0]["bai_branch"] = "寅"
    elif fault == "defeat_position":
        defeats[0]["position"] = "地分"
    elif fault == "defeat_phase_coherent":
        c = defeats[0]
        c["element"] = "水" if c["element"] != "水" else "火"
        c["bai_branch"] = {"水": "酉", "火": "卯"}[c["element"]]
        c["matched"] = c["seat_branch"] == c["bai_branch"]
        c["basis"] = (
            f"{c['position']}{c['element']}临地分{c['seat_branch']}；本节{c['element']}败在{c['bai_branch']}"
        )
    elif fault == "defeat_seat_coherent":
        for c in defeats:
            c["seat_branch"] = "子" if c["seat_branch"] != "子" else "午"
            c["matched"] = c["seat_branch"] == c["bai_branch"]
            c["basis"] = (
                f"{c['position']}{c['element']}临地分{c['seat_branch']}；本节{c['element']}败在{c['bai_branch']}"
            )
    elif fault == "defeat_prune":
        defeats.pop()
    elif fault == "defeat_duplicate":
        defeats[1] = copy.deepcopy(defeats[0])
    elif fault == "calendar_matches":
        for c in calendar:
            c["matched"] = not c["matched"]
    elif fault == "calendar_role":
        next(c for c in calendar if c["rule_id"] == "day_build")["position"] = "贵神"
    elif fault == "calendar_reference":
        calendar[0]["reference_branch"] = (
            "丑" if calendar[0]["reference_branch"] != "丑" else "午"
        )
    elif fault == "calendar_branch":
        calendar[0]["branch"] = "亥" if calendar[0]["branch"] != "亥" else "午"
    elif fault == "calendar_prune":
        calendar.pop()
    elif fault == "calendar_duplicate":
        calendar[1] = copy.deepcopy(calendar[0])
    elif fault == "source_hash":
        rel["source_sha256"] = "0" * 64
    elif fault == "source_variants":
        rel["transcription_variants"][0]["scan_element"] = "水"
    elif fault == "false_certificate":
        rel["complete_classical_conformance"] = True
    elif fault in {
        "alternate_year_coherent",
        "alternate_hour_coherent",
        "alternate_god_coherent",
    }:
        from fatebridge.core.metaphysics.common import branch_element_text
        from fatebridge.core.metaphysics.jinkou_relations import structural_relations

        rows = copy.deepcopy(result["rows"])
        year = rel["calendar"]["year_branch"]
        hour = result["definition_evidence"]["hour_branch"]
        if fault == "alternate_year_coherent":
            year = "子" if year != "子" else "午"
        if fault == "alternate_hour_coherent":
            hour = "子" if hour != "子" else "午"
        if fault == "alternate_god_coherent":
            rows[1]["content"] = "酉" if rows[1]["content"] != "酉" else "午"
            rows[1]["element"] = branch_element_text(rows[1]["content"])
        n = rel["si_jue"]["natal"]
        rel = structural_relations(
            rows,
            year_branch=year,
            day_branch=rel["calendar"]["day_branch"],
            hour_branch=hour,
            natal_branch=n["right_branch"],
            natal_branch_source=n["input_source"],
        )
        result["relations"] = rel
    elif fault == "trace_only":
        pass
    elif fault == "trace_duplicate":
        pass
    elif fault == "trace_source":
        pass
    elif fault == "trace_bad_shape":
        pass
    else:
        raise ValueError(fault)
    trace = next(
        t for t in result["rule_trace"] if t["rule_id"] == "jinkou.jingben_relations"
    )
    if fault == "trace_only":
        trace["result"]["calendar"]["checks"][0]["matched"] = not trace["result"][
            "calendar"
        ]["checks"][0]["matched"]
    elif fault == "trace_duplicate":
        result["rule_trace"].append(copy.deepcopy(trace))
    elif fault == "trace_source":
        trace["source_section"] = "未核对的另外一部原典"
    elif fault == "trace_bad_shape":
        trace["result"]["calendar"] = "不是结构关系对象"
    else:
        trace["result"] = copy.deepcopy(rel)
    return result


def test_reference_keeps_existing_source_rules_and_open_daily_gap():
    ref = reference()
    old = ROOT / "tests/fixtures/jinkou_relations_v1/reference.json"
    assert hashlib.sha256(old.read_bytes()).hexdigest() == ref["old_reference_sha256"]
    assert ref["si_bai_scope"]
    assert "does not provide" in ref["daily_strength_gap"]["adjudication"]
    assert len(ref["si_jue"]) == 4 and len(ref["calendar_rules"]) == 4


@pytest.mark.parametrize("fault", FAULTS)
def test_bad_matches_and_coherent_fabrications_cannot_enter_a_complete_course(fault):
    original = board()
    Jinkou.model_validate(original)
    with pytest.raises(ValidationError):
        Jinkou.model_validate(damage(original, fault))


@pytest.mark.parametrize("group", ["si_jue", "si_bai", "calendar"])
def test_known_local_inputs_do_not_allow_inverted_matches_without_a_whole_course(group):
    value = copy.deepcopy(board()["relations"])
    for c in value[group]["checks"]:
        c["matched"] = not c["matched"]
    with pytest.raises(ValidationError):
        JinkouRelations.model_validate(value)


def test_sparse_facts_stay_sparse_but_known_day_build_scope_is_enforced():
    value = {"calendar": {"year_branch": "子"}}
    assert JinkouRelations.model_validate(value).model_dump(exclude_unset=True) == value
    value = {"si_bai": {"checks": [dict(position=p) for p in ("人元", "贵神", "将神")]}}
    assert JinkouRelations.model_validate(value).model_dump(exclude_unset=True) == value
    invalid = {
        "calendar": {
            "checks": copy.deepcopy(board()["relations"]["calendar"]["checks"])
        }
    }
    row = next(c for c in invalid["calendar"]["checks"] if c["rule_id"] == "day_build")
    row["position"] = "贵神"
    with pytest.raises(ValidationError):
        JinkouRelations.model_validate(invalid)


def test_equivalent_unique_catalog_order_is_not_a_new_rule():
    value = board()
    value["relations"] = copy.deepcopy(value["relations"])
    for node in [
        value["relations"],
        next(
            t["result"]
            for t in value["rule_trace"]
            if t["rule_id"] == "jinkou.jingben_relations"
        ),
    ]:
        for group in ["si_jue", "si_bai", "calendar"]:
            node[group]["checks"] = list(reversed(node[group]["checks"]))
    Jinkou.model_validate(value)


@pytest.mark.parametrize("kind", ["si_jue", "si_bai", "calendar"])
@pytest.mark.parametrize("verdict", [False, True])
def test_explicit_missing_input_cannot_claim_a_positive_or_negative_verdict(
    kind, verdict
):
    from fatebridge.core.output_chinese import (
        JinkouBaiCheck,
        JinkouCalendarCheck,
        JinkouJueCheck,
    )

    model = {
        "si_jue": JinkouJueCheck,
        "si_bai": JinkouBaiCheck,
        "calendar": JinkouCalendarCheck,
    }[kind]
    row = copy.deepcopy(board()["relations"][kind]["checks"][0])
    row[
        {
            "si_jue": "right_branch",
            "si_bai": "seat_branch",
            "calendar": "reference_branch",
        }[kind]
    ] = None
    row["matched"] = verdict
    with pytest.raises(ValidationError):
        model.model_validate(row)
    # Absence in a projection is different from an explicitly missing input.
    assert model.model_validate({"matched": verdict}).model_dump(
        exclude_unset=True
    ) == {"matched": verdict}


@pytest.mark.parametrize(
    "fault",
    ["calendar_matches", "absolute_phase", "defeat_seat_coherent", "trace_only"],
)
@pytest.mark.parametrize("project", [False, True])
def test_inconsistent_relations_fail_on_real_protocol_paths_before_projection(
    fault, project, monkeypatch, rest, tmp_path, capsys
):
    from tests.fixtures.surface_payloads import REST_POST_CASES

    fn, args, kw = SPEC.bind(
        SPEC.request_model.model_validate(REST_POST_CASES[SPEC.rest_path]())
    )
    value = fn(*args, **kw)
    value["jinkou"] = damage(value["jinkou"], fault)
    with pytest.raises(ValidationError):
        SPEC.output_model.model_validate(value)
    assert_broken_on_three_ports(
        SPEC, value, project, rest, monkeypatch, tmp_path, capsys
    )


@pytest.mark.parametrize("group", ["si_jue", "si_bai", "calendar"])
def test_whole_service_cannot_hide_all_relation_checks_from_body_and_trace(group):
    from fatebridge.application.execution import OutputContractError
    from tests.fixtures.surface_payloads import REST_POST_CASES

    fn, args, kw = SPEC.bind(
        SPEC.request_model.model_validate(REST_POST_CASES[SPEC.rest_path]())
    )
    value = copy.deepcopy(fn(*args, **kw))
    value["jinkou"]["relations"] = copy.deepcopy(value["jinkou"]["relations"])
    value["jinkou"]["relations"][group].pop("checks")
    for trace in value["jinkou"]["rule_trace"]:
        if trace["rule_id"] == "jinkou.jingben_relations":
            trace["result"][group].pop("checks")
    with pytest.raises(OutputContractError):
        validate_output(SPEC, value)


@pytest.mark.parametrize("course", ["natal_course", "year_fate"])
@pytest.mark.parametrize("fault", ["calendar_matches", "defeat_seat_coherent"])
@pytest.mark.parametrize("project", [False, True])
def test_derived_courses_keep_their_own_relation_facts(
    course, fault, project, monkeypatch, rest, tmp_path, capsys
):
    source = json.loads(
        (ROOT / "tests/fixtures/jinkou_year_course_v1/reference.json").read_text()
    )
    payload = dict(source["calendar"], gender="男", is_diurnal=True)
    fn, args, kw = SPEC.bind(SPEC.request_model.model_validate(payload))
    value = copy.deepcopy(fn(*args, **kw))
    SPEC.output_model.model_validate(value)
    child = value["jinkou"][course]["course"]
    assert child is not None
    value["jinkou"][course]["course"] = damage(child, fault)
    with pytest.raises(ValidationError):
        SPEC.output_model.model_validate(value)
    assert_broken_on_three_ports(
        SPEC, value, project, rest, monkeypatch, tmp_path, capsys
    )

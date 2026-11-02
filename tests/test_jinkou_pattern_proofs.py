"""Complete premise traces, independent arithmetic and preserved source failures."""

import asyncio
import copy
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from types import ModuleType

import pytest
from pydantic import ValidationError

from fatebridge.application.execution import OutputContractError, validate_output
from fatebridge.core.metaphysics.jinkou_patterns import patterns_from_symbols
from fatebridge.core.output_ren_patterns import JinkouPatterns
from tests.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    native,
    rest,
)
from tests.test_ren_anchors import assert_broken_on_three_ports

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/jinkou_pattern_proofs_v1"
PIN = "8a810e86e2607d650af1d7088e7dcae83ff18b128f8b642d794a1f6f340c4d31"
SPEC = SPECS["jinkou"]


def reference():
    assert hashlib.sha256((CORPUS / "freeze.json").read_bytes()).hexdigest() == PIN
    frozen = json.loads((CORPUS / "freeze.json").read_text())
    assert {p.name for p in CORPUS.iterdir()} == {*frozen["files"], "freeze.json"}
    assert all(
        hashlib.sha256((CORPUS / n).read_bytes()).hexdigest() == h
        for n, h in frozen["files"].items()
    )
    ref = json.loads((CORPUS / "reference.json").read_text())
    assert all(
        hashlib.sha256((ROOT / n).read_bytes()).hexdigest() == h
        for n, h in ref["old_source_pins"].items()
    )
    return ref


def recognized(symbols, day):
    return patterns_from_symbols(
        [
            dict(label=p, content=s)
            for p, s in zip(("人元", "贵神", "将神", "地分"), symbols, strict=True)
        ],
        day_ganzhi=day,
    )


def assert_logic(value):
    assert value["condition_logic"] == "any_of_all_v1"
    facts = {f["id"]: f for f in value["condition_facts"]}
    assert len(facts) == len(value["condition_facts"])
    referenced = set()
    for row in value["evaluations"]:
        groups = row["condition_groups"]
        if row["matched"] is None:
            assert groups is None
            continue
        assert groups and all(groups)
        result = any(
            all(facts[t["fact_id"]]["matched"] is t["expected"] for t in g)
            for g in groups
        )
        assert result is row["matched"]
        referenced.update(t["fact_id"] for group in groups for t in group)
    assert referenced == set(facts)
    JinkouPatterns.model_validate(value)


def test_whole_catalog_premises_are_available_for_positive_negative_and_unknown():
    ref = reference()
    value = recognized(["甲", "子", "辰", "申"], "甲子")
    assert_logic(value)
    assert len(value["evaluations"]) == 64
    assert sum(v["condition_groups"] is not None for v in value["evaluations"]) == 58
    assert [
        v["id"] for v in value["evaluations"] if v["condition_groups"] is None
    ] == ref["unknown_ids"]


@pytest.mark.parametrize("case", reference()["cases"], ids=lambda c: c["id"])
def test_four_book_conflicts_explain_the_actual_failed_operands_without_repair(case):
    value = recognized(case["symbols"], case["day"])
    assert_logic(value)
    row = next(r for r in value["evaluations"] if r["id"] == case["id"])
    fact = next(f for f in value["condition_facts"] if f["id"] == case["failed_fact"])
    assert row["matched"] is case["expected_match"] is False
    assert fact["matched"] is False
    for k, v in case["operands"].items():
        assert (
            fact["reference"] if k == "house_branches" else fact["operands"][k]
        ) == v


def test_disjunction_negation_and_all_premises_survive_earlier_failure():
    value = recognized(["甲", "子", "丑", "寅"], "甲子")
    assert_logic(value)
    rows = {r["id"]: r for r in value["evaluations"]}
    facts = {f["id"]: f for f in value["condition_facts"]}
    assert facts["trine"]["matched"] is False
    assert all(
        t["fact_id"] in facts for g in rows["P03"]["condition_groups"] for t in g
    )
    assert any(
        t["expected"] is False for g in rows["P03"]["condition_groups"] for t in g
    )
    assert len(rows["P24"]["condition_groups"]) == 2
    assert len(rows["P28"]["condition_groups"]) == 4
    assert len(rows["P33"]["condition_groups"]) == 2


def test_mathematical_equal_phase_and_equal_branch_remain_different():
    value = recognized(["庚", "巳", "辰", "戌"], "甲子")
    facts = {f["id"]: f for f in value["condition_facts"]}
    assert facts["same:J:D"]["matched"] is True
    assert facts["equal_branch:J:D"]["matched"] is False
    assert facts["clash:J:D"]["matched"] is True


def test_complete_old_fields_still_equal_frozen_implementation_for_all_source_cases():
    from fatebridge.core.metaphysics.jinkou import GUISHEN_IDENTITIES
    from scripts.audit_jinkou_patterns import literal_rows, load_reference

    old = ModuleType("fatebridge.core.metaphysics._pattern_before_v59")
    old.__package__ = "fatebridge.core.metaphysics"
    exec(
        compile((CORPUS / "before.py").read_text(), str(CORPUS / "before.py"), "exec"),
        old.__dict__,
    )
    for case in load_reference()["cases"]:
        rows = literal_rows(case, GUISHEN_IDENTITIES)
        actual = recognized([r["content"] for r in rows], case["day"] or "甲子")
        expected = old.structural_patterns(rows, day_ganzhi=case["day"] or "甲子")
        actual.pop("condition_logic")
        actual.pop("condition_facts")
        for row in actual["evaluations"]:
            row.pop("condition_groups")
        assert actual == expected


@lru_cache(maxsize=1)
def complete():
    payload = dict(
        analysis_year=2026,
        analysis_month=4,
        analysis_day=8,
        analysis_hour=9,
        analysis_minute=30,
        analysis_timezone="Asia/Shanghai",
        use_true_solar_time=False,
        di_fen="酉",
        birth_year_ganzhi="甲午",
        gender="男",
        year_fate_age=20,
        is_diurnal=True,
    )
    fn, args, kw = SPEC.bind(SPEC.request_model.model_validate(payload))
    value = fn(*args, **kw)
    validate_output(SPEC, value)
    return value, payload


def course(value, which):
    board = value["jinkou"]
    return (
        board
        if which == "primary"
        else board["natal_course" if which == "natal" else which]["course"]
    )


FAULTS = (
    "missing_facts",
    "missing_groups",
    "wrong_result",
    "wrong_operands",
    "wrong_reference",
    "wrong_requirement",
    "duplicate_fact",
    "missing_fact",
    "unused_fact",
    "invent_unknown",
    "borrow_other_course",
    "trace_only",
)


def damaged(which, fault):
    value = json.loads(json.dumps(complete()[0]))
    board = course(value, which)
    patterns = board["patterns"]
    trace = next(
        t for t in board["rule_trace"] if t["rule_id"] == "jinkou.structural_patterns"
    )
    if fault == "missing_facts":
        patterns.pop("condition_facts")
    elif fault == "missing_groups":
        for row in patterns["evaluations"]:
            row.pop("condition_groups")
    elif fault == "wrong_result":
        patterns["condition_facts"][0]["matched"] = not patterns["condition_facts"][0][
            "matched"
        ]
    elif fault == "wrong_operands":
        fact = next(f for f in patterns["condition_facts"] if f["id"] == "same:H:G")
        fact["operands"]["source_symbol"] = (
            "甲" if fact["operands"]["source_symbol"] != "甲" else "乙"
        )
    elif fault == "wrong_reference":
        patterns["condition_facts"][0]["reference"] = ["子"]
    elif fault == "wrong_requirement":
        patterns["evaluations"][0]["condition_groups"][0][0]["expected"] = False
    elif fault == "duplicate_fact":
        patterns["condition_facts"].append(
            copy.deepcopy(patterns["condition_facts"][0])
        )
    elif fault == "missing_fact":
        patterns["condition_facts"].pop()
    elif fault == "unused_fact":
        other = copy.deepcopy(patterns["condition_facts"][0])
        other["id"] = "unused"
        patterns["condition_facts"].append(other)
    elif fault == "invent_unknown":
        patterns["evaluations"][51]["condition_groups"] = copy.deepcopy(
            patterns["evaluations"][0]["condition_groups"]
        )
    elif fault == "borrow_other_course":
        other = course(value, "year_fate" if which != "year_fate" else "primary")
        assert other["patterns"]["condition_facts"] != patterns["condition_facts"]
        patterns["condition_facts"] = copy.deepcopy(
            other["patterns"]["condition_facts"]
        )
    elif fault == "trace_only":
        trace["result"]["condition_facts"][0]["matched"] = not trace["result"][
            "condition_facts"
        ][0]["matched"]
        return value
    else:
        raise AssertionError(fault)
    trace["result"] = copy.deepcopy(patterns)
    return value


@pytest.mark.parametrize("which", ["primary", "natal", "year_fate"])
@pytest.mark.parametrize("fault", FAULTS)
def test_each_complete_course_rejects_forged_or_missing_proofs(which, fault):
    with pytest.raises(OutputContractError):
        validate_output(SPEC, damaged(which, fault))


@pytest.mark.parametrize("project", [False, True])
def test_proof_failure_is_rejected_on_all_three_ports_before_projection(
    project, rest, monkeypatch, tmp_path, capsys
):
    value, payload = complete()
    assert value
    assert_broken_on_three_ports(
        SPEC,
        damaged("natal", "missing_facts"),
        project,
        rest,
        monkeypatch,
        tmp_path,
        capsys,
    )


def test_positive_complete_and_sparse_proofs_preserve_omission():
    from fatebridge.core.output_ren_patterns import JinkouPatternFact

    value, _ = complete()
    for which in ("primary", "natal", "year_fate"):
        assert_logic(course(value, which)["patterns"])
    for partial in (
        {"matched": False},
        {"description": "仅描述"},
        {"operation": "trine"},
    ):
        obj = JinkouPatternFact.model_validate(partial)
        assert obj.model_dump(exclude_unset=True) == partial
    with pytest.raises(ValidationError):
        JinkouPatternFact.model_validate({"matched": 0})
    with pytest.raises(ValidationError):
        JinkouPatternFact.model_validate(
            {"operation": "control", "operands": {}, "matched": False}
        )


def missing_reference():
    folder = ROOT / "tests/fixtures/jinkou_pattern_missing_inputs_v1"
    assert (
        hashlib.sha256((folder / "freeze.json").read_bytes()).hexdigest()
        == "d4b2f40f4e17f8539ad37162af7458e9ab8a17a1dfdf94c216b91d0df33c35e8"
    )
    freeze = json.loads((folder / "freeze.json").read_text())
    assert {p.name for p in folder.iterdir()} == set(freeze["files"]) | {"freeze.json"}
    assert all(
        hashlib.sha256((folder / n).read_bytes()).hexdigest() == h
        for n, h in freeze["files"].items()
    )
    return json.loads((folder / "reference.json").read_text())


def test_missing_raw_stems_are_unknown_while_defined_gate_rules_stay_known():
    from fatebridge.core.metaphysics.jinkou_patterns import structural_patterns
    from scripts.audit_jinkou_gate_roles import synthetic_rows

    ref = missing_reference()
    rows = synthetic_rows(*ref["symbols"][1:])
    old = ModuleType("fatebridge.core.metaphysics._pattern_missing_before_v59")
    old.__package__ = "fatebridge.core.metaphysics"
    exec(
        compile((CORPUS / "before.py").read_text(), str(CORPUS / "before.py"), "exec"),
        old.__dict__,
    )
    previous = old.structural_patterns(rows, day_ganzhi=ref["day_ganzhi"])
    assert all(
        next(v for v in previous["evaluations"] if v["id"] == pid)["matched"] is False
        for pid in ref["expected_unknown_rules"]
    )
    actual = structural_patterns(rows, day_ganzhi=ref["day_ganzhi"])
    ledger = {v["id"]: v for v in actual["evaluations"]}
    assert [
        v["id"] for v in ledger.values() if v["status"] == "input_unavailable"
    ] == ref["expected_unknown_rules"]
    for pid in ref["expected_unknown_rules"]:
        assert ledger[pid]["matched"] is None and ledger[pid]["condition_groups"]
    for pid, expected in ref["expected_still_known"].items():
        assert ledger[pid]["matched"] is expected
    assert actual["evaluated_rule_count"] == 56
    assert len(actual["unresolved"]) == 8
    assert ledger["P52"]["status"] == "unresolved_definition"
    assert next(f for f in actual["condition_facts"] if f["id"] == "three_wonders")[
        "operands"
    ]["stems"] == ["戊", None, None]
    JinkouPatterns.model_validate(actual)


@pytest.mark.parametrize("case", missing_reference()["truth_cases"])
def test_unknown_propagation_obeys_frozen_three_valued_logic(case):
    from fatebridge.core.metaphysics.jinkou_pattern_proofs import evaluate_groups

    facts = {}
    groups = []
    for i, group in enumerate(case["groups"]):
        clause = []
        for j, value in enumerate(group):
            identity = f"{i}:{j}"
            facts[identity] = value
            clause.append(dict(fact_id=identity, expected=True))
        groups.append(clause)
    assert evaluate_groups(groups, facts) is case["result"]
    assert evaluate_groups([[dict(fact_id="a", expected=False)]], {"a": None}) is None


@pytest.mark.parametrize("project", [False, True])
def test_positive_proofs_on_three_ports_full_and_strict_projection(
    project, rest, tmp_path, capsys
):
    _, payload = complete()
    params = {"as_of": AS_OF, "response_char_limit": 0}
    options = {}
    flags = ["--response-char-limit", "0"]
    if project:
        fields = [
            "jinkou.patterns",
            "jinkou.natal_course.course.patterns",
            "jinkou.year_fate.course.patterns",
        ]
        params.update(fields=fields, strict_fields=True)
        options = dict(fields=fields, strict_fields=True)
        flags.extend(["--fields", *fields])
        flags.extend(["--strict-fields", "true"])
    response = rest.post(SPEC.rest_path, json=payload, params=params)
    protocol = asyncio.run(native(SPEC, payload, **options))
    code, cli = call_cli(SPEC, payload, tmp_path, capsys, flags=flags)
    assert response.status_code == 200 and not protocol.is_error and code == 0
    assert (
        business(response.json())
        == business(protocol.structured_content)
        == business(cli)
    )
    for which in ["primary", "natal", "year_fate"]:
        assert_logic(course(cli, which)["patterns"])


@pytest.mark.asyncio
async def test_complete_proof_payload_is_retrieved_from_the_same_run_without_recalculation(
    monkeypatch,
):
    from fastmcp import Client

    import fatebridge.application.execution as execution
    from fatebridge.mcp_server import create_mcp_app

    original = execution.execute_spec
    calls = []

    def count(spec, request):
        if spec.key == "jinkou":
            calls.append(spec.key)
        return original(spec, request)

    monkeypatch.setattr(execution, "execute_spec", count)
    _, payload = complete()
    calls.clear()
    async with Client(create_mcp_app()) as client:
        response = await client.call_tool(
            "jinkou",
            {
                **payload,
                "as_of": AS_OF,
                "fields": None,
                "include_snapshot_text": False,
                "response_char_limit": 6000,
            },
        )
        assert not response.is_error
        inline = response.structured_content
        delivery = inline["result_delivery"]
        pieces = []
        uri = delivery["first_page_uri"]
        while uri:
            page = json.loads((await client.read_resource(uri))[0].text)
            pieces.append(page["text"])
            uri = page["next_uri"]
    text = "".join(pieces)
    retrieved = json.loads(text)
    assert (
        len(pieces) > 1
        and hashlib.sha256(text.encode()).hexdigest() == delivery["sha256"]
    )
    assert retrieved["run_metadata"]["run_id"] == inline["run_metadata"]["run_id"]
    assert (
        retrieved["run_metadata"]["business_output_sha256"]
        == inline["run_metadata"]["business_output_sha256"]
    )
    assert calls == ["jinkou"]
    for which in ["primary", "natal", "year_fate"]:
        assert_logic(course(retrieved, which)["patterns"])

"""Transmission selection, branch kin and new source layers remain distinct."""

import asyncio
import copy
import importlib.util
import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

import fatebridge.application.execution as execution
from fatebridge.core.metaphysics.liureng_transmission_relations import (
    transmission_relations,
)
from fatebridge.core.output_liuren_transmission_relations import (
    LiurenTransmissionRelations,
)
from tests.evaluation.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    native,
    rest,
)

ROOT = Path(__file__).resolve().parents[2]
MOD = importlib.util.spec_from_file_location(
    "transmission_audit", ROOT / "scripts/ren/audit_liuren_transmission_relations.py"
)
assert MOD and MOD.loader
AUDIT = importlib.util.module_from_spec(MOD)
MOD.loader.exec_module(AUDIT)
RULES, CASES = AUDIT.reference()
PAYLOADS = json.loads((ROOT / "tests/fixtures/ren_anchors_v1/faults.json").read_text())[
    "payloads"
]


def raw(key):
    spec = SPECS[key]
    fn, args, kw = spec.bind(spec.request_model.model_validate(PAYLOADS[key]))
    return fn(*args, **kw)


def test_literal_and_synthetic_evidence_have_separate_denominators():
    r = AUDIT.audit()
    assert r["engineering_checks_passed"]
    assert r["literal_god_phase_anchors"] == 12 and r["literal_trine_anchors"] == 4
    assert (
        len(r["literal_control_examples"]) == 4
        and r["synthetic_god_branch_pairs_matched"] == 144
    )
    assert (
        len(r["synthetic_named_contexts"]) == 10
        and r["synthetic_trine_contexts_matched"] == 240
    )
    assert (
        r["new_historical_events"] == 0
        and r["goal_complete"] is r["full_classical_conformance"] is False
    )


@pytest.mark.parametrize("change", ["edit", "missing", "extra", "prune"])
def test_frozen_readings_and_counterexamples_cannot_drift(tmp_path, change):
    p = tmp_path / "corpus"
    shutil.copytree(AUDIT.CORPUS, p)
    if change in {"edit", "prune"}:
        q = p / "synthetic-cases.json"
        v = json.loads(q.read_text())
        if change == "edit":
            v["cases"][0]["must_match"] = []
        else:
            v["cases"].pop()
        q.write_text(json.dumps(v))
    elif change == "missing":
        (p / "source-pages.pdf").unlink()
    else:
        (p / "extra.json").write_text("{}")
    with pytest.raises(ValueError, match="Frozen transmission-relation"):
        AUDIT.reference(p)


@pytest.mark.parametrize("case", CASES["cases"], ids=lambda c: c["id"])
def test_independently_handwritten_symbolic_conditions(case):
    v = transmission_relations(
        **AUDIT.context(case["day"], case["branches"], uppers=case["lesson_uppers"])
    )
    LiurenTransmissionRelations.model_validate(v)
    flags = {r["id"]: r["matched"] for r in v["rules"]}
    assert all(flags[i] for i in case["must_match"])
    assert all(not flags[i] for i in case["must_not_match"])


def test_god_spirit_and_nominal_trine_never_replace_branch_kin():
    v = transmission_relations(
        **AUDIT.context("甲子", ["子", "寅", "丑"], ["贵人", "朱雀", "玄武"])
    )
    a, b, c = v["rows"]
    assert (
        a["god_element"] == "土"
        and a["element"] == "水"
        and a["day_relation"] == "父母"
        and a["war"] == "外战"
    )
    assert (
        c["god_element"] == "水"
        and c["element"] == "土"
        and c["day_relation"] == "妻财"
        and c["war"] == "内战"
    )
    v = transmission_relations(**AUDIT.context("甲子", ["亥", "卯", "未"]))
    t = next(t for t in v["trines"] if t["branches_complete"])
    assert t["nominal_element"] == "木" and t["nominal_day_relation"] == "兄弟"
    assert [r["day_relation"] for r in v["rows"]] == ["父母", "兄弟", "妻财"]
    assert t["transformation_confirmed"] is v["comprehensive_judgement"] is None


def test_duplicate_trine_members_and_earth_branches_do_not_invent_a_trine():
    for branches in (["巳", "酉", "酉"], ["辰", "戌", "丑"]):
        v = transmission_relations(**AUDIT.context("甲子", branches))
        assert not any(t["branches_complete"] for t in v["trines"])


@pytest.mark.parametrize(
    "key", ["liureng_gods", "liureng_runyear", "jinkou", "sanshiunited"]
)
@pytest.mark.parametrize("project", [False, True])
def test_four_families_deliver_same_source_layers_on_three_ports(
    key, project, rest, tmp_path, capsys
):
    spec = SPECS[key]
    fields = [
        "liureng.transmission_relations",
        "liureng.three_transmissions",
        "liureng.four_lessons",
        "liureng.ruleset",
    ]
    params = [("as_of", AS_OF), ("response_char_limit", "0")]
    flags = ["--response-char-limit", "0"]
    options = {}
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
        options.update(fields=fields, strict_fields=True, include_snapshot_text=False)
    http = rest.post(spec.rest_path, json=PAYLOADS[key], params=params)
    protocol = asyncio.run(native(spec, PAYLOADS[key], **options))
    code, cli = call_cli(spec, PAYLOADS[key], tmp_path, capsys, flags=flags)
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert (
        business(http.json()) == business(protocol.structured_content) == business(cli)
    )
    for body in (http.json(), protocol.structured_content, cli):
        spec.output_model.model_validate(body)
        Draft202012Validator(spec.output_model.model_json_schema()).validate(body)
        board = body["liureng"]
        e = board["transmission_relations"]
        assert board["ruleset"]["version"] == "1.16.0"
        assert len(e["rows"]) == 3 and len(e["rules"]) == 9 and len(e["trines"]) == 4
        assert (
            e["comprehensive_judgement"] is None
            and not e["complete_classical_conformance"]
        )
        for r in e["rows"]:
            original = board["three_transmissions"][r["position"]]
            assert (r["branch"], r["god"], r["day_relation"]) == (
                original["branch"],
                original["god"],
                original["relation"],
            )


@pytest.mark.parametrize("kind", ["phase", "day", "transformation", "ledger"])
@pytest.mark.parametrize("key", ["liureng_gods", "jinkou"])
@pytest.mark.parametrize("project", [False, True])
def test_false_source_layers_fail_before_unrelated_projection(
    kind, key, project, rest, monkeypatch, tmp_path, capsys
):
    spec = SPECS[key]
    bad = raw(key)
    e = bad["liureng"]["transmission_relations"]
    if kind == "phase":
        e["rows"][0]["god_element"] = next(
            p for p in "木火土金水" if p != e["rows"][0]["god_element"]
        )
    elif kind == "day":
        e["day_ganzhi"] = "甲子"
    elif kind == "transformation":
        e["trines"][0]["transformation_confirmed"] = True
    else:
        e["rules"][0]["matched"] = not e["rules"][0]["matched"]
        e["matched_rule_ids"] = [r["id"] for r in e["rules"] if r["matched"]]
    with pytest.raises(ValidationError):
        spec.output_model.model_validate(bad)
    original = execution.execute_spec

    def broken(actual, request):
        if actual.key == key:
            actual = replace(
                actual, bind=lambda _: (lambda: copy.deepcopy(bad), (), {})
            )
        return original(actual, request)

    monkeypatch.setattr(execution, "execute_spec", broken)
    params = {"as_of": AS_OF, "response_char_limit": 0}
    options = {}
    flags = ["--response-char-limit", "0"]
    if project:
        params.update(fields="analysis_type", strict_fields="true")
        options.update(fields=["analysis_type"], strict_fields=True)
        flags += ["--fields", "analysis_type", "--strict-fields", "true"]
    http = rest.post(spec.rest_path, json=PAYLOADS[key], params=params)
    protocol = asyncio.run(native(spec, PAYLOADS[key], **options))
    code, cli = call_cli(spec, PAYLOADS[key], tmp_path, capsys, flags=flags)
    assert (
        http.status_code == 500
        and protocol.is_error
        and code == 1
        and cli["error_code"] == "internal_error"
    )


@pytest.mark.parametrize("field", ["rows", "rules", "trines", "day_ganzhi"])
def test_complete_gate_keeps_source_dependencies_while_partial_models_allow_omission(
    field,
):
    spec = SPECS["liureng_gods"]
    bad = raw("liureng_gods")
    del bad["liureng"]["transmission_relations"][field]
    spec.output_model.model_validate(bad)
    with pytest.raises(execution.OutputContractError):
        execution.validate_output(spec, bad)


def test_standalone_null_projections_preserve_unknowns():
    v = {"comprehensive_judgement": None, "equivalent_three_empty_adjudicated": None}
    assert (
        LiurenTransmissionRelations.model_validate(v).model_dump(exclude_unset=True)
        == v
    )


@pytest.mark.parametrize(
    "value",
    [
        {"god": "贵人", "god_element": "木"},
        {"branch": "子", "element": "土"},
        {"god_element": "火", "element": "金", "war": "内战"},
        {"god_element": "火", "element": "金", "war": None},
        {"god_element": "水", "element": "火", "god_to_spirit": "受克"},
    ],
)
def test_projected_rows_reject_contradictions_when_own_anchors_present(value):
    from fatebridge.core.output_liuren_transmission_relations import (
        TransmissionRelationRow,
    )

    with pytest.raises(ValidationError):
        TransmissionRelationRow.model_validate(value)

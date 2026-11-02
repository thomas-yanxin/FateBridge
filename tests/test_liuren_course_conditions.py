"""Frozen source clauses, discriminators, same-board guards and real ports."""

import asyncio
import copy
import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

import fatebridge.application.execution as execution
from fatebridge.core.metaphysics.liureng_course_conditions import (
    course_conditions,
    course_conditions_trace,
)
from fatebridge.core.output_liuren_course_conditions import LiurenCourseConditions
from fatebridge.core.output_ren_anchors import require_complete_ren_anchors
from scripts.audit_liuren_course_conditions import (
    CORPUS,
    audit,
    reference,
    transmissions,
)
from tests.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    native,
    rest,
)
from tests.test_liuren_ordered_patterns import raw

ROOT = Path(__file__).resolve().parents[1]
REF = reference()
CLAUSES = REF["readings"]["selected_clauses"]
PAYLOADS = json.loads((ROOT / "tests/fixtures/ren_anchors_v1/faults.json").read_text())[
    "payloads"
]


@pytest.fixture(autouse=True)
def native_solar(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))


@pytest.mark.parametrize("clause", CLAUSES[:24], ids=lambda c: c["id"])
def test_each_literal_stage_and_god_pair(clause):
    stages = [c["required_stage"] for c in CLAUSES[:12]]
    ordered = "亥子丑寅卯辰巳午未申酉戌"
    branch = (
        ordered[stages.index(clause["required_stage"])]
        if "required_stage" in clause
        else "寅"
    )
    value = course_conditions(
        "甲子", transmissions([branch, "寅", "卯"], clause["required_god"], "子")
    )
    assert clause["id"] in value["matched_ids"]
    LiurenCourseConditions.model_validate(value)


def test_entire_frozen_condition_space_and_unresolved_names_are_preserved():
    result = audit()
    assert result["engineering_checks_passed"] and not result["failures"]
    assert result["mathematical_stage_god_contexts"] == 8640
    assert result["structural_contexts"] == 19008
    assert all(result["match_counts"][f"S{i:02}"] == 60 for i in range(1, 13))
    assert all(result["match_counts"][f"G{i:02}"] == 720 for i in range(1, 13))
    assert [result["match_counts"][f"B{i:02}"] for i in range(1, 4)] == [230, 1, 60]
    assert result["new_historical_events"] == result["new_empirical_events"] == 0
    assert result["goal_complete"] is result["full_classical_conformance"] is False
    notes = course_conditions("甲子", transmissions(["辰", "寅", "卯"], "天后", "子"))[
        "name_reading_notes"
    ]
    assert notes[0]["scan_reading"] == "退齡" and notes[0]["adjudication"] is None
    assert REF["readings"]["online_transcription_used_as_calculation_oracle"] is False


@pytest.mark.parametrize(
    "day,branches,god,seat,yes,no",
    [
        ("甲子", "辰寅卯", "天后", "子", ["S06", "G12", "B01"], ["S02"]),
        ("甲子", "子寅卯", "天后", "子", ["G12"], ["S06"]),
        ("戊子", "寅寅卯", "青龙", "子", ["S01"], []),
        ("戊子", "申寅卯", "青龙", "子", [], ["S01"]),
        ("己丑", "申寅卯", "玄武", "子", ["S02"], []),
        ("甲子", "辰寅卯", "贵人", "丑", ["G01"], ["B01"]),
        ("甲子", "酉酉酉", "贵人", "子", ["B02"], []),
        ("甲子", "寅寅寅", "贵人", "子", [], ["B02"]),
        ("甲子", "子寅酉", "贵人", "子", ["B03"], []),
        ("甲戌", "戌寅未", "贵人", "子", ["B03"], []),
        ("甲戌", "子寅酉", "贵人", "子", [], ["B03"]),
    ],
)
def test_distinguishes_nearby_but_different_rules(day, branches, god, seat, yes, no):
    value = course_conditions(day, transmissions(list(branches), god, seat))
    assert set(yes) <= set(value["matched_ids"])
    assert not set(no) & set(value["matched_ids"])


@pytest.mark.parametrize("fault", ["bytes", "manifest", "extra", "missing"])
def test_reference_cannot_be_pruned_or_relabelled(fault, tmp_path):
    dest = tmp_path / "reference"
    shutil.copytree(CORPUS, dest)
    if fault == "bytes":
        with (dest / "readings.json").open("ab") as handle:
            handle.write(b" ")
    elif fault == "manifest":
        (dest / "freeze.json").write_text("{}")
    elif fault == "extra":
        (dest / "extra").write_text("")
    else:
        (dest / "chapter-catalog.json").unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        reference(dest)


@pytest.mark.parametrize(
    "fault",
    [
        "source",
        "reorder",
        "prune",
        "match",
        "numeric_bool",
        "full_claim",
        "day",
        "stage",
        "verdict",
        "name",
    ],
)
def test_present_claims_are_checked(fault):
    value = course_conditions("甲子", transmissions(["辰", "寅", "卯"], "天后", "子"))
    if fault == "source":
        value["source_sha256"] = "fake"
    elif fault == "reorder":
        value["stage_god_patterns"].reverse()
    elif fault == "prune":
        value["god_patterns"].pop()
    elif fault == "match":
        value["stage_god_patterns"][5]["matched"] = False
    elif fault == "numeric_bool":
        value["god_patterns"][0]["matched"] = 0
    elif fault == "full_claim":
        value["complete_classical_conformance"] = 0
    elif fault == "day":
        value["day_ganzhi"] = "甲丑"
    elif fault == "stage":
        value["initial_stage"] = "沐浴"
    elif fault == "verdict":
        value["comprehensive_judgement"] = "guaranteed"
    else:
        value["stage_god_patterns"][0]["name"] = "遐龄"
    with pytest.raises(ValidationError):
        LiurenCourseConditions.model_validate(value)


def test_sparse_projection_preserves_unknowns():
    for value in (
        {"matched_ids": ["S06", "G12"]},
        {"comprehensive_judgement": None},
        {"stage_god_patterns": [{"name": c["name"]} for c in CLAUSES[:12]]},
    ):
        LiurenCourseConditions.model_validate(value)


@pytest.mark.parametrize(
    "fault", ["day", "day_type", "missing", "list", "branch", "god", "seat", "null"]
)
def test_invalid_inputs_are_not_filled(fault):
    day = "甲子"
    values = transmissions(["辰", "寅", "卯"], "天后", "子")
    if fault == "day":
        day = "甲丑"
    elif fault == "day_type":
        day = None
    elif fault == "missing":
        values.pop("final")
    elif fault == "list":
        values = list(values.values())
    elif fault == "null":
        values = None
    else:
        values["initial"][
            {"branch": "branch", "god": "god", "seat": "earth_branch"}[fault]
        ] = "unknown"
    with pytest.raises(ValueError):
        course_conditions(day, values)


@pytest.mark.parametrize(
    "key", ["liureng_gods", "liureng_runyear", "jinkou", "sanshiunited"]
)
@pytest.mark.parametrize("project", [False, True])
def test_same_new_facts_on_real_rest_mcp_cli(key, project, rest, tmp_path, capsys):
    spec = SPECS[key]
    path = "liureng.transmission_relations.course_conditions"
    params = [("as_of", AS_OF), ("response_char_limit", "0")]
    flags = ["--response-char-limit", "0"]
    options = {}
    if project:
        params += [
            ("fields", path),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ]
        flags += [
            "--fields",
            path,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ]
        options.update(fields=[path], strict_fields=True, include_snapshot_text=False)
    http = rest.post(spec.rest_path, json=PAYLOADS[key], params=params)
    protocol = asyncio.run(native(spec, PAYLOADS[key], **options))
    code, cli = call_cli(spec, PAYLOADS[key], tmp_path, capsys, flags=flags)
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert (
        business(http.json()) == business(protocol.structured_content) == business(cli)
    )
    for body in (http.json(), protocol.structured_content, cli):
        spec.output_model.model_validate(body)
        course = body["liureng"]["transmission_relations"]["course_conditions"]
        assert len(course["stage_god_patterns"]) == len(course["god_patterns"]) == 12
        assert len(course["structural_patterns"]) == 3
        assert (
            course["comprehensive_judgement"] is None
            and course["complete_classical_conformance"] is False
        )


@pytest.mark.parametrize(
    "key", ["liureng_gods", "liureng_runyear", "jinkou", "sanshiunited"]
)
@pytest.mark.parametrize(
    "fault", ["missing", "foreign", "trace", "duplicate", "old_version"]
)
def test_complete_gate_binds_same_board_even_if_foreign_proof_is_consistent(key, fault):
    value = raw(key)
    board = value["liureng"]
    if fault in ("missing", "old_version"):
        board["transmission_relations"].pop("course_conditions")
        if fault == "old_version":
            board["ruleset"]["version"] = "1.0.0"
    elif fault == "foreign":
        actual = board["transmission_relations"]["course_conditions"]
        god = "天后" if actual["initial_god"] != "天后" else "贵人"
        fake = course_conditions(
            actual["day_ganzhi"],
            transmissions(actual["branches"], god, actual["initial_earth_branch"]),
        )
        board["transmission_relations"]["course_conditions"] = fake
        board["rule_trace"] = [
            (
                course_conditions_trace(fake)
                if t["rule_id"] == "liuren.course_conditions"
                else t
            )
            for t in board["rule_trace"]
        ]
    else:
        trace = next(
            t for t in board["rule_trace"] if t["rule_id"] == "liuren.course_conditions"
        )
        if fault == "trace":
            board["rule_trace"].remove(trace)
        else:
            board["rule_trace"].append(copy.deepcopy(trace))
    with pytest.raises(ValueError):
        require_complete_ren_anchors(key, value)


@pytest.mark.parametrize("project", [False, True])
def test_false_course_fails_before_unrelated_projection(
    project, rest, monkeypatch, tmp_path, capsys
):
    spec = SPECS["liureng_gods"]
    value = raw(spec.key)
    value["liureng"]["transmission_relations"]["course_conditions"][
        "initial_stage"
    ] = "invented"
    fake = replace(spec, bind=lambda _: (lambda: copy.deepcopy(value), (), {}))
    original = execution.execute_spec
    monkeypatch.setattr(
        execution,
        "execute_spec",
        lambda actual, request: original(
            fake if actual.key == spec.key else actual, request
        ),
    )
    params = [("response_char_limit", "0")]
    flags = ["--response-char-limit", "0"]
    options = {}
    if project:
        params += [("fields", "four_pillars"), ("strict_fields", "true")]
        flags += ["--fields", "four_pillars", "--strict-fields", "true"]
        options.update(fields=["four_pillars"], strict_fields=True)
    http = rest.post(spec.rest_path, json=PAYLOADS[spec.key], params=params)
    protocol = asyncio.run(native(spec, PAYLOADS[spec.key], **options))
    code, _ = call_cli(spec, PAYLOADS[spec.key], tmp_path, capsys, flags=flags)
    assert http.status_code == 500 and protocol.is_error and code != 0

"""Printed pair anchors, same-board facts and the actual three transports."""

import asyncio
import copy
import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

import fatebridge.application.execution as execution
from fatebridge.core.metaphysics.liureng import build_liureng_board
from fatebridge.core.metaphysics.liureng_branch_relations import (
    branch_pair_facts,
    branch_relations,
)
from fatebridge.core.output_liuren_branches import LiurenBranchRelations, rebuild
from scripts.audit_liuren_branch_relations import CORPUS, FACTS, audit, reference
from scripts.audit_ren_classical import make_seed
from tests.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    native,
    rest,
)

ROOT = Path(__file__).resolve().parents[1]
REF = reference()
PAYLOADS = json.loads((ROOT / "tests/fixtures/ren_anchors_v1/faults.json").read_text())[
    "payloads"
]


@pytest.fixture(autouse=True)
def native_files(monkeypatch):
    from fatebridge.core.ephemeris_runtime import (
        configure_ephemeris_path,
        configured_ephemeris_path,
    )

    previous = configured_ephemeris_path()
    monkeypatch.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    try:
        yield
    finally:
        configure_ephemeris_path(previous)


def raw(key="liureng_gods", **extra):
    spec = SPECS[key]
    payload = {**PAYLOADS[key], **extra}
    fn, args, kw = spec.bind(spec.request_model.model_validate(payload))
    return fn(*args, **kw)


@pytest.mark.parametrize("case", REF["synthetic_cases"])
def test_handwritten_pairs_keep_all_simultaneous_relations(case):
    value = branch_pair_facts(case["left"], case["right"])
    assert all(value[k] is (k in case["positive"]) for k in FACTS)
    assert value["harmony_annotation"] == case["annotation"]


@pytest.mark.parametrize("bad", ["", "子丑", "北", None, 0])
def test_invalid_branch_pair_is_rejected(bad):
    with pytest.raises(ValueError):
        branch_pair_facts(bad, "子")


@pytest.mark.parametrize("kind", ["edit", "prune", "extra", "missing", "refreeze"])
def test_original_tables_cannot_be_edited_to_make_comparisons_pass(kind, tmp_path):
    target = tmp_path / "corpus"
    shutil.copytree(CORPUS, target)
    if kind in {"edit", "prune"}:
        p = target / "reference.json"
        value = json.loads(p.read_text())
        if kind == "edit":
            value["synthetic_cases"][0]["positive"].remove("liupo")
        else:
            value["tables"]["xing"].pop()
        p.write_text(json.dumps(value))
    elif kind == "extra":
        (target / "extra.json").write_text("{}")
    elif kind == "missing":
        (target / "source-pages.pdf").unlink()
    else:
        (target / "freeze.json").write_text("{}")
    with pytest.raises((ValueError, FileNotFoundError)):
        reference(target)


def test_complete_source_tables_and_symbolic_ledger_have_distinct_denominators(
    tmp_path, monkeypatch
):
    import scripts.audit_liuren_branch_relations as module

    alias = tmp_path / "source-alias"
    alias.symlink_to(ROOT, target_is_directory=True)
    monkeypatch.setattr(
        module, "__file__", str(alias / "scripts/audit_liuren_branch_relations.py")
    )
    result = audit()
    assert result["engineering_checks_passed"] and result["implementation_unchanged"]
    assert (
        result["literal_pair_anchors"] == 36
        and result["literal_harmony_annotations"] == 2
    )
    assert len(result["synthetic_cases"]) == 10
    assert len(result["ordered_pair_matrix"]) == 144
    assert result["symbolic_board_count"] == 720
    assert result["symbolic_pair_comparisons"] == 33840
    assert result["new_historical_events"] == result["new_empirical_events"] == 0
    assert result["full_classical_conformance"] is result["goal_complete"] is False


def test_first_lesson_earth_branch_never_replaces_day_stem_element():
    board = build_liureng_board(
        make_seed(dict(day="丙寅", hour="子")), month_general_override="卯"
    )
    first = board["four_lessons"][0]
    assert first["lower_branch"] == "巳" and first["upper_branch"] == "申"
    assert first["upper_lower_relation"] == "下贼上"
    assert "不据合独断成局" in first["style_basis"]
    row = next(r for r in board["branch_relations"]["rows"] if r["id"] == "lesson.1")
    assert row["facts"]["liuhe"] and row["facts"]["liupo"]
    assert row["facts"]["right_xing_left"] and not row["facts"]["left_xing_right"]
    assert row["facts"]["harmony_annotation"] == "刑合"
    assert board["three_transmissions"]["initial"]["branch"] == "申"
    other = build_liureng_board(
        make_seed(dict(day="乙丑", hour="子")), month_general_override="辰"
    )
    assert other["four_lessons"][0]["lower_branch"] == "辰"
    assert other["four_lessons"][0]["upper_branch"] == "申"
    assert other["four_lessons"][0]["upper_lower_relation"] == "上克下"


@pytest.mark.parametrize("kind", ["day", "shift", "lessons", "transmissions"])
def test_inconsistent_context_is_rejected(kind):
    board = build_liureng_board(
        make_seed(dict(day="甲子", hour="子")), month_general_override="子"
    )
    e = board["branch_relations"]
    kw = dict(
        day_ganzhi="甲子",
        year_branch="午",
        month_branch="寅",
        hour_branch="子",
        month_general_branch="子",
        sky_by_earth=e["sky_by_earth"],
        lessons=e["lesson_branches"],
        transmissions=list(e["transmission_branches"].values()),
    )
    if kind == "day":
        kw["day_ganzhi"] = "甲丑"
    elif kind == "shift":
        kw["hour_branch"] = "丑"
    elif kind == "lessons":
        kw["lessons"] = copy.deepcopy(kw["lessons"])
        kw["lessons"][0]["lower_branch"] = "子"
    else:
        kw["transmissions"] = ["子"]
    with pytest.raises(ValueError):
        branch_relations(**kw)


@pytest.mark.parametrize(
    "key", ["liureng_gods", "liureng_runyear", "jinkou", "sanshiunited"]
)
@pytest.mark.parametrize("mode", ["full", "ledger", "partial_context"])
def test_complete_and_projected_evidence_agrees_across_transports(
    key, mode, rest, tmp_path, capsys
):
    spec = SPECS[key]
    fields = ["four_pillars", "liureng.branch_relations", "liureng.ruleset"]
    if key == "sanshiunited":
        fields = [
            "liureng.branch_relations",
            "subresults.liureng_gods.liureng.branch_relations",
            "subresults.liureng_gods.four_pillars",
        ]
    if mode == "partial_context":
        fields = [
            "liureng.branch_relations.rows",
            "liureng.branch_relations.day_ganzhi",
            "liureng.branch_relations.calendar_branches",
            "liureng.branch_relations.sky_by_earth.子",
            "liureng.branch_relations.month_general_branch",
            "liureng.branch_relations.lesson_branches",
            "liureng.branch_relations.transmission_branches",
        ]
    params = [("as_of", AS_OF), ("response_char_limit", "0")]
    flags, options = ["--response-char-limit", "0"], {}
    if mode != "full":
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
    http = rest.post(spec.rest_path, json=PAYLOADS[key], params=params)
    mcp = asyncio.run(native(spec, PAYLOADS[key], **options))
    code, cli = call_cli(spec, PAYLOADS[key], tmp_path, capsys, flags=flags)
    assert http.status_code == 200 and code == 0 and not mcp.is_error
    values = [http.json(), cli, mcp.structured_content]
    assert business(values[0]) == business(values[1]) == business(values[2])
    for value in values:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(value)
        evidence = value["liureng"]["branch_relations"]
        assert len(evidence["rows"]) == 47
        if mode != "partial_context":
            assert evidence["complete_classical_conformance"] is False
            assert evidence["comprehensive_judgement"] is None
            if key == "sanshiunited":
                assert (
                    evidence
                    == value["subresults"]["liureng_gods"]["liureng"][
                        "branch_relations"
                    ]
                )


@pytest.mark.parametrize(
    "key", ["liureng_gods", "liureng_runyear", "jinkou", "sanshiunited"]
)
def test_array_item_projection_remains_an_explicit_protocol_error(
    key, rest, tmp_path, capsys
):
    # The shared projection contract permits object paths and whole arrays.
    # Preserve the initially attempted path as a negative request case.
    spec = SPECS[key]
    fields = ["liureng.branch_relations.rows.facts.liuhe"]
    http = rest.post(
        spec.rest_path,
        json=PAYLOADS[key],
        params={"fields": fields[0], "strict_fields": "true"},
    )
    mcp = asyncio.run(native(spec, PAYLOADS[key], fields=fields, strict_fields=True))
    code, cli = call_cli(
        spec,
        PAYLOADS[key],
        tmp_path,
        capsys,
        flags=["--fields", *fields, "--strict-fields", "true"],
    )
    assert http.status_code == 422 and mcp.is_error and code != 0
    assert "liureng" not in http.json() and "liureng" not in cli


def corrupt(kind):
    value = raw()
    board = value["liureng"]
    e = board["branch_relations"]
    if kind in FACTS:
        e["rows"][0]["facts"][kind] = not e["rows"][0]["facts"][kind]
    elif kind == "annotation":
        e["rows"][0]["facts"]["harmony_annotation"] = "刑合"
    elif kind == "delete":
        board.pop("branch_relations")
    elif kind == "prune":
        e["rows"].pop()
    elif kind == "duplicate":
        e["rows"][1] = copy.deepcopy(e["rows"][0])
    elif kind == "missing_fact":
        e["rows"][0]["facts"].pop("liupo")
    elif kind == "judgement":
        e["comprehensive_judgement"] = False
    elif kind == "trace":
        next(
            r for r in board["rule_trace"] if r["rule_id"] == "liuren.branch_relations"
        )["result"]["row_count"] = 46
    elif kind == "year":
        e["calendar_branches"]["year"] = (
            "子" if e["calendar_branches"]["year"] != "子" else "丑"
        )
        e = rebuild(e)
        board["branch_relations"] = e
        next(
            r for r in board["rule_trace"] if r["rule_id"] == "liuren.branch_relations"
        )["result"]["annotated_harmony_rows"] = [
            r["id"] for r in e["rows"] if r["facts"]["harmony_annotation"] is not None
        ]
    return value


@pytest.mark.parametrize(
    "kind",
    [
        *FACTS,
        "annotation",
        "delete",
        "prune",
        "duplicate",
        "missing_fact",
        "judgement",
        "trace",
        "year",
    ],
)
def test_false_or_missing_evidence_fails_full_output_before_any_projection(kind):
    with pytest.raises(execution.OutputContractError):
        execution.validate_output(SPECS["liureng_gods"], corrupt(kind))


@pytest.mark.parametrize("kind", ["liupo", "year", "delete", "trace"])
@pytest.mark.parametrize("project", [False, True])
def test_wrong_branch_facts_fail_in_actual_three_transports(
    kind, project, rest, monkeypatch, tmp_path, capsys
):
    key = "liureng_gods"
    bad = corrupt(kind)
    original = execution.execute_spec

    def broken(spec, request):
        if spec.key == key:
            spec = replace(spec, bind=lambda _: (lambda: copy.deepcopy(bad), (), {}))
        return original(spec, request)

    monkeypatch.setattr(execution, "execute_spec", broken)
    options, flags = {}, ["--response-char-limit", "0"]
    params = {"as_of": AS_OF, "response_char_limit": 0}
    if project:
        params.update(fields="analysis_type", strict_fields="true")
        flags += ["--fields", "analysis_type", "--strict-fields", "true"]
        options = dict(fields=["analysis_type"], strict_fields=True)
    spec = SPECS[key]
    http = rest.post(spec.rest_path, json=PAYLOADS[key], params=params)
    mcp = asyncio.run(native(spec, PAYLOADS[key], **options))
    code, cli = call_cli(spec, PAYLOADS[key], tmp_path, capsys, flags=flags)
    assert http.status_code == 500 and mcp.is_error and code != 0
    for value in [http.json(), cli, mcp.structured_content]:
        assert value["error_code"] == "internal_error" and "liureng" not in value


def test_partial_maps_and_partial_facts_do_not_invent_missing_context():
    value = raw()["liureng"]["branch_relations"]
    value["sky_by_earth"] = {"子": value["sky_by_earth"]["子"]}
    value["rows"] = [{"facts": {"liuhe": r["facts"]["liuhe"]}} for r in value["rows"]]
    LiurenBranchRelations.model_validate(value)
    with pytest.raises(ValidationError):
        LiurenBranchRelations.model_validate({"comprehensive_judgement": False})


def test_default_and_selected_snapshots_preserve_source_and_coexisting_relations():
    spec = SPECS["liureng_gods"]
    payload = dict(PAYLOADS["liureng_gods"])
    payload.pop("selected_sections", None)
    fn, args, kw = spec.bind(spec.request_model.model_validate(payload))
    full = fn(*args, **kw)
    assert "[支位合冲刑破害]" in full["snapshot_text"]
    assert full["snapshot_text"] == full["snapshot_export"]["export_text"]
    selected = raw(selected_sections=["支位合冲刑破害"])
    assert "[支位合冲刑破害]" in selected["snapshot_export"]["export_text"]
    assert "不据合独断成局" in selected["snapshot_text"]
    assert "[三传]" not in selected["snapshot_export"]["export_text"]


@pytest.mark.parametrize("key", ["liureng_gods", "jinkou"])
def test_current_automatic_de440_policy_delivers_the_same_source_facts(
    key, monkeypatch, rest, tmp_path, capsys
):
    from scripts.audit_liuren_branch_relations import expected

    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    spec = SPECS[key]
    fields = [
        "liureng.branch_relations",
        "liureng.calendar_policy.solar_term_dependencies",
    ]
    options = dict(fields=fields, strict_fields=True, include_snapshot_text=False)
    http = rest.post(
        spec.rest_path,
        json=PAYLOADS[key],
        params=[
            *[("fields", f) for f in fields],
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
        ],
    )
    mcp = asyncio.run(native(spec, PAYLOADS[key], **options))
    code, cli = call_cli(
        spec,
        PAYLOADS[key],
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
    assert http.status_code == 200 and code == 0 and not mcp.is_error
    values = [http.json(), cli, mcp.structured_content]
    assert business(values[0]) == business(values[1]) == business(values[2])
    for value in values:
        board = value["liureng"]
        for row in board["branch_relations"]["rows"]:
            assert row["facts"] == expected(
                REF, row["left_branch"], row["right_branch"]
            )
        for term in board["calendar_policy"]["solar_term_dependencies"]:
            assert term["provider"] == "jpl_de440"
            assert term["ephemeris_model"] == "fatebridge_de440_solar_v1"
            assert term["ephemeris_retflags"] == []
            details = term["solar_model_details"]
            assert details["source_kernel_sha256"] != details["coefficient_sha256"]
            assert details["accuracy_certified"] is False

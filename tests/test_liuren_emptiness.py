"""Original empty-place distinction and same-run port evidence."""

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
from fatebridge.core.metaphysics.liureng_emptiness import emptiness_evidence
from fatebridge.core.output_liuren_emptiness import LiurenEmptinessEvidence
from tests.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    native,
    rest,
)

ROOT = Path(__file__).resolve().parents[1]
MOD = importlib.util.spec_from_file_location(
    "emptiness_audit", ROOT / "scripts/audit_liuren_emptiness.py"
)
assert MOD and MOD.loader
AUDIT = importlib.util.module_from_spec(MOD)
MOD.loader.exec_module(AUDIT)
REFERENCE = AUDIT.reference()
PAYLOADS = json.loads((ROOT / "tests/fixtures/ren_anchors_v1/faults.json").read_text())[
    "payloads"
]


def raw(key="liureng_gods"):
    spec = SPECS[key]
    fn, args, kw = spec.bind(spec.request_model.model_validate(PAYLOADS[key]))
    return fn(*args, **kw)


def test_partial_example_and_generated_contexts_have_distinct_denominators():
    r = AUDIT.audit()
    assert r["engineering_checks_passed"] and r["implementation_unchanged"]
    assert len(r["literal_xun_anchors"]) == 6
    assert r["literal_partial_example"]["matched"]
    assert len(r["synthetic_cases"]) == 6
    assert r["synthetic_context_count"] == 8640
    assert r["synthetic_row_comparisons"] == 103680
    assert r["synthetic_role_comparisons"] == 25920
    assert r["synthetic_matrix_failures"] == []
    assert r["new_historical_events"] == r["new_empirical_events"] == 0
    assert r["goal_complete"] is r["full_classical_conformance"] is False


@pytest.mark.parametrize("kind", ["edit", "prune", "missing", "extra", "refreeze"])
def test_frozen_source_readings_cannot_be_retuned(tmp_path, kind):
    p = tmp_path / "corpus"
    shutil.copytree(AUDIT.CORPUS, p)
    if kind in ("edit", "prune"):
        q = p / "reference.json"
        v = json.loads(q.read_text())
        if kind == "edit":
            v["synthetic_cases"][0]["selected_rows"][0]["seat_exception"] = False
        else:
            v["synthetic_cases"].pop()
        q.write_text(json.dumps(v))
    elif kind == "missing":
        (p / "source-pages.pdf").unlink()
    elif kind == "extra":
        (p / "new.json").write_text("{}")
    else:
        (p / "freeze.json").write_text("{}")
    with pytest.raises((ValueError, FileNotFoundError), match="Frozen|source-pages"):
        AUDIT.reference(p)


@pytest.mark.parametrize("case", REFERENCE["synthetic_cases"], ids=lambda c: c["id"])
def test_handwritten_contexts_keep_sky_empty_when_earth_is_exempt(case):
    e = emptiness_evidence(**AUDIT.context(case))
    LiurenEmptinessEvidence.model_validate(e)
    by_sky = {r["sky_branch"]: r for r in e["rows"]}
    for expected in case["selected_rows"]:
        actual = by_sky[expected["sky"]]
        assert actual["earth_branch"] == expected["earth"]
        assert actual["sky_xun_kong"] is expected["sky_empty"]
        assert actual["earth_xun_kong"] is expected["earth_empty"]
        assert actual["earth_stem_house_exception"] is expected["seat_exception"]
        assert actual["sky_authority_roles"] == expected["roles"]
    assert all(r["effective_empty"] is None for r in e["rows"])
    assert e["comprehensive_judgement"] is None


@pytest.mark.parametrize(
    "kind", ["day", "branch", "missing", "nonrotation", "wrong_shift"]
)
def test_invalid_calculation_context_is_rejected(kind):
    c = AUDIT.context(REFERENCE["synthetic_cases"][0])
    if kind == "day":
        c["day_ganzhi"] = "甲丑"
    elif kind == "branch":
        c["hour_branch"] = "子丑"
    elif kind == "missing":
        c["sky_by_earth"].pop("子")
    elif kind == "nonrotation":
        m = c["sky_by_earth"]
        m["子"], m["丑"] = m["丑"], m["子"]
    else:
        c["month_general_branch"] = "子"
    with pytest.raises(ValueError):
        emptiness_evidence(**c)


@pytest.mark.parametrize(
    "key", ["liureng_gods", "liureng_runyear", "jinkou", "sanshiunited"]
)
@pytest.mark.parametrize("project", [False, True])
def test_empty_scope_is_same_on_rest_mcp_cli(key, project, rest, tmp_path, capsys):
    spec = SPECS[key]
    fields = [
        (
            "subresults.liureng_gods.four_pillars"
            if key == "sanshiunited"
            else "four_pillars"
        ),
        "liureng.emptiness_evidence",
        "liureng.month_general",
        "liureng.three_transmissions",
        "liureng.twelve_board",
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
        evidence = board["emptiness_evidence"]
        assert len(evidence["rows"]) == 12 and len(evidence["role_conditions"]) == 3
        assert board["ruleset"]["version"] == "1.16.0"
        by_sky = {r["sky_branch"]: r for r in evidence["rows"]}
        for p in ("initial", "middle", "final"):
            transmission = board["three_transmissions"][p]
            row = by_sky[transmission["branch"]]
            assert row["sky_xun_kong"] is transmission["xun_kong"]
            assert row["earth_xun_kong"] is transmission["seated_kong"]
            assert row["earth_branch"] == transmission["earth_branch"]


@pytest.mark.parametrize(
    "kind", ["base_empty", "seat", "role", "same_day", "effective", "delete"]
)
@pytest.mark.parametrize("project", [False, True])
def test_bad_empty_explanation_facts_fail_before_projection(
    kind, project, rest, monkeypatch, tmp_path, capsys
):
    key = "liureng_gods"
    spec = SPECS[key]
    bad = raw()
    e = bad["liureng"]["emptiness_evidence"]
    if kind == "base_empty":
        e["rows"][0]["sky_xun_kong"] = not e["rows"][0]["sky_xun_kong"]
    elif kind == "seat":
        row = next(r for r in e["rows"] if r["earth_is_day_stem_house"])
        row["earth_xun_kong"] = True
        row["earth_stem_house_exception"] = False
    elif kind == "role":
        e["role_conditions"][0]["branch"] = next(
            b for b in AUDIT.BRANCHES if b != e["year_branch"]
        )
    elif kind == "same_day":
        c = AUDIT.context(REFERENCE["synthetic_cases"][1])
        e.update(emptiness_evidence(**c))
    elif kind == "effective":
        e["rows"][0]["effective_empty"] = False
    else:
        e.pop("rows")
    if kind != "delete":
        with pytest.raises(ValidationError):
            spec.output_model.model_validate(bad)
    with pytest.raises(execution.OutputContractError):
        execution.validate_output(spec, bad)
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
    assert http.status_code == 500 and protocol.is_error and code != 0
    for body in (http.json(), protocol.structured_content, cli):
        assert body["error_code"] == "internal_error"
        assert "liureng" not in body


@pytest.mark.parametrize(
    "field", ["day_ganzhi", "role_conditions", "nianming_status", "rows"]
)
def test_partial_projection_remains_partial_but_full_output_requires_evidence(field):
    bad = raw()
    bad["liureng"]["emptiness_evidence"].pop(field)
    SPECS["liureng_gods"].output_model.model_validate(bad)
    with pytest.raises(execution.OutputContractError):
        execution.validate_output(SPECS["liureng_gods"], bad)


def test_projected_unknown_verdict_cannot_become_false():
    v = {
        "comprehensive_judgement": None,
        "nianming_status": "not_adjudicated_in_this_excerpt",
    }
    assert LiurenEmptinessEvidence.model_validate(v).model_dump(exclude_unset=True) == v
    with pytest.raises(ValidationError):
        LiurenEmptinessEvidence.model_validate({"comprehensive_judgement": False})


def test_new_empty_scope_has_default_and_selected_snapshot_export():
    spec = SPECS["liureng_gods"]
    payload = dict(PAYLOADS["liureng_gods"])
    payload.pop("selected_sections", None)
    fn, args, kw = spec.bind(spec.request_model.model_validate(payload))
    full = fn(*args, **kw)
    assert full["snapshot_text"] == full["snapshot_export"]["export_text"]
    assert "[空亡分层条件]" in full["snapshot_text"]
    payload = {**PAYLOADS["liureng_gods"], "selected_sections": ["空亡分层条件"]}
    fn, args, kw = spec.bind(spec.request_model.model_validate(payload))
    selected = fn(*args, **kw)
    export = selected["snapshot_export"]["export_text"]
    assert "[空亡分层条件]" in export and "综合有效空亡未裁定" in export
    assert "[三传]" not in export


@pytest.mark.parametrize("anchor", ["board", "transmissions"])
def test_present_board_anchors_work_without_projected_four_pillars(anchor):
    from fatebridge.core.output_chinese import Liuren

    full = raw()["liureng"]
    evidence = copy.deepcopy(full["emptiness_evidence"])
    c = {
        "day_ganzhi": evidence["day_ganzhi"],
        "year_branch": evidence["year_branch"],
        "month_branch": evidence["month_building_branch"],
        "month_general_branch": evidence["month_general_branch"],
        "hour_branch": "丑" if evidence["hour_branch"] == "子" else "子",
    }
    shifted = (
        AUDIT.BRANCHES.index(c["month_general_branch"])
        - AUDIT.BRANCHES.index(c["hour_branch"])
    ) % 12
    c["sky_by_earth"] = {
        b: AUDIT.BRANCHES[(i + shifted) % 12] for i, b in enumerate(AUDIT.BRANCHES)
    }
    evidence = emptiness_evidence(**c)
    key = "twelve_board" if anchor == "board" else "three_transmissions"
    with pytest.raises(ValidationError):
        Liuren.model_validate({"emptiness_evidence": evidence, key: full[key]})

"""The missing 将命 input is explicit, nullable and faithful on every port."""

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
from fatebridge.core.metaphysics.jinkou_relations import natal_absolute
from fatebridge.core.output_chinese import JinkouJue
from fatebridge.core.output_jinkou_natal import JinkouNatalAbsolute
from fatebridge.core.requests.metaphysics import JinkouAnalysisRequest
from tests.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    native,
    rest,
)
from tests.test_ren_transports import PAYLOAD

ROOT = Path(__file__).resolve().parents[1]
MOD = importlib.util.spec_from_file_location(
    "audit_natal", ROOT / "scripts/audit_jinkou_natal.py"
)
assert MOD and MOD.loader
AUDIT = importlib.util.module_from_spec(MOD)
MOD.loader.exec_module(AUDIT)
REFERENCE = AUDIT.reference()
SPEC = SPECS["jinkou"]


def raw(natal="酉"):
    request = SPEC.request_model.model_validate(
        dict(PAYLOAD, di_fen="酉", natal_branch=natal)
    )
    fn, args, kw = SPEC.bind(request)
    return fn(*args, **kw)


def test_complete_named_pair_matrix_and_missing_input_do_not_become_events():
    r = AUDIT.audit()
    assert r["selected_rule_checks_passed"]
    assert r["synthetic_matrix_count"] == 144 and r["synthetic_positive_count"] == 8
    assert r["missing_natal_contexts"] == 12 and r["missing_natal_preserved_unknown"]
    assert r["new_historical_events"] == r["new_empirical_outcomes"] == 0
    assert r["full_classical_conformance"] is r["goal_complete"] is False


@pytest.mark.parametrize("c", REFERENCE["cases"])
def test_predeclared_pair_directions_and_unknowns(c):
    value = natal_absolute(c["general"], c["natal"])
    assert value["matched"] is c["matched"] and value["element"] == c["element"]
    JinkouNatalAbsolute.model_validate(value)


@pytest.mark.parametrize("change", ["edit", "missing", "extra", "prune"])
def test_predeclared_source_cannot_be_changed_or_pruned(tmp_path, change):
    dest = tmp_path / "source"
    shutil.copytree(AUDIT.CORPUS, dest)
    if change in {"edit", "prune"}:
        p = dest / "reference.json"
        value = json.loads(p.read_text())
        if change == "edit":
            value["pairs"][0]["element"] = "木"
        else:
            value["cases"].pop()
        p.write_text(json.dumps(value))
    elif change == "missing":
        (dest / "source-page.pdf").unlink()
    else:
        (dest / "new.json").write_text("{}")
    with pytest.raises(ValueError, match="Frozen natal"):
        AUDIT.reference(dest)


@pytest.mark.parametrize("value", ["甲子", "1990", "", " 子 ", "未知", 0])
def test_unknown_or_year_labels_are_not_treated_as_confirmed_birth_branches(value):
    with pytest.raises(ValidationError):
        JinkouAnalysisRequest.model_validate(dict(PAYLOAD, natal_branch=value))


def test_omission_and_null_keep_unknown_while_all_twelve_explicit_branches_are_valid():
    for branch in "子丑寅卯辰巳午未申酉戌亥":
        assert (
            JinkouAnalysisRequest.model_validate(
                dict(PAYLOAD, natal_branch=branch)
            ).natal_branch
            == branch
        )
    assert JinkouAnalysisRequest.model_validate(PAYLOAD).natal_branch is None
    assert raw(None)["jinkou"]["relations"]["si_jue"]["natal"]["matched"] is None


@pytest.mark.parametrize("natal", [None, "卯", "申"])
@pytest.mark.parametrize("project", [False, True])
def test_explicit_and_missing_natal_are_delivered_on_three_ports(
    natal, project, rest, tmp_path, capsys
):
    payload = dict(PAYLOAD, di_fen="酉", natal_branch=natal)
    params = [("as_of", AS_OF), ("response_char_limit", "0")]
    options = {}
    flags = ["--response-char-limit", "0"]
    if project:
        fields = [
            "four_pillars",
            "jinkou.rows",
            "jinkou.relations.si_jue",
            "jinkou.ruleset",
        ]
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
    http = rest.post(SPEC.rest_path, json=payload, params=params)
    protocol = asyncio.run(native(SPEC, payload, **options))
    code, cli = call_cli(SPEC, payload, tmp_path, capsys, flags=flags)
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert (
        business(http.json()) == business(protocol.structured_content) == business(cli)
    )
    for body in (http.json(), protocol.structured_content, cli):
        SPEC.output_model.model_validate(body)
        Draft202012Validator(SPEC.output_model.model_json_schema()).validate(body)
        j = body["jinkou"]
        value = j["relations"]["si_jue"]["natal"]
        assert (
            value["right_branch"] == natal
            and value["left_branch"] == j["rows"][2]["content"]
        )
        assert len(j["relations"]["si_jue"]["checks"]) == 5
        assert bool(j["relations"]["si_jue"]["unavailable"]) is (natal is None)
        assert (value["matched"] is None) is (natal is None)
        # This civil input's unchanged general is 申: 卯 is a named 木绝 pair,
        # while 申 itself is a negative case. These labels are in the frozen table.
        assert value["matched"] is {None: None, "卯": True, "申": False}[natal]
        if not project:
            assert value["basis"] in body["snapshot_text"]
        assert j["ruleset"]["version"] == "1.16.0"


def test_explicit_natal_never_changes_the_four_positions_calendar_or_use():
    old = raw(None)
    for natal in ("子", "卯", "申"):
        new = raw(natal)
        for key in ("four_pillars", "analysis_context", "calendar_context", "liureng"):
            assert new[key] == old[key]
        for key in (
            "rows",
            "overview",
            "motions",
            "internal_strength",
            "qi_evidence",
            "patterns",
            "use_evidence",
            "combinations",
        ):
            assert new["jinkou"][key] == old["jinkou"][key]


@pytest.mark.parametrize(
    "fault",
    REFERENCE["faults"]
    + ["trace_match", "trace_general", "trace_natal", "delete_trace"],
)
@pytest.mark.parametrize("project", [False, True])
def test_corrupt_natal_evidence_fails_before_unrelated_projection(
    fault, project, rest, monkeypatch, tmp_path, capsys
):
    bad = raw(None if fault == "invent_missing_match" else "酉")
    jue = bad["jinkou"]["relations"]["si_jue"]
    node = jue["natal"]
    if fault == "flip_match":
        node["matched"] = not node["matched"]
    elif fault == "wrong_phase":
        node["element"] = "木" if node["element"] != "木" else "金"
    elif fault == "wrong_general":
        wrong = "子" if node["left_branch"] != "子" else "丑"
        # A self-consistent replacement must still be rejected against this board.
        jue["natal"] = natal_absolute(wrong, node["right_branch"])
    elif fault == "invent_missing_match":
        node["matched"] = False
    elif fault == "retain_unavailable_after_known":
        jue["unavailable"] = raw(None)["jinkou"]["relations"]["si_jue"]["unavailable"]
    elif fault == "delete_natal_dependency":
        del jue["natal"]
    else:
        trace = next(
            t
            for t in bad["jinkou"]["rule_trace"]
            if t["rule_id"] == "jinkou.jingben_relations"
        )
        # Split domain aliases to change only the serialized trace copy.
        trace["result"] = copy.deepcopy(trace["result"])
        target = trace["result"]["si_jue"]
        if fault == "trace_match":
            target["natal"]["matched"] = not target["natal"]["matched"]
        elif fault == "trace_general":
            target["natal"] = natal_absolute("子", "酉")
        elif fault == "trace_natal":
            target["natal"] = natal_absolute(node["left_branch"], "卯")
        else:
            del target["natal"]
    if fault in {"delete_natal_dependency", "delete_trace"}:
        SPEC.output_model.model_validate(
            bad
        )  # Sparse public projections allow omission.
    else:
        with pytest.raises(ValidationError):
            SPEC.output_model.model_validate(bad)
    original = execution.execute_spec

    def broken(actual, request):
        if actual.key == "jinkou":
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
    http = rest.post(SPEC.rest_path, json=PAYLOAD, params=params)
    protocol = asyncio.run(native(SPEC, PAYLOAD, **options))
    code, cli = call_cli(SPEC, PAYLOAD, tmp_path, capsys, flags=flags)
    assert http.status_code == 500 and protocol.is_error and code == 1
    assert cli["error_code"] == "internal_error"


def test_sparse_knownness_projections_check_only_present_anchors():
    assert JinkouNatalAbsolute.model_validate({"matched": None}).matched is None
    assert (
        JinkouJue.model_validate({"natal": {"right_branch": "酉"}}).natal.right_branch
        == "酉"
    )
    with pytest.raises(ValidationError):
        JinkouNatalAbsolute.model_validate({"right_branch": None, "matched": False})
    with pytest.raises(ValidationError):
        JinkouNatalAbsolute.model_validate(
            {"right_branch": "酉", "status": "missing_birth_branch"}
        )


def test_cli_explicit_flag_overrides_an_unspecified_natal_branch(tmp_path, capsys):
    code, value = call_cli(
        SPEC,
        dict(PAYLOAD, di_fen="酉"),
        tmp_path,
        capsys,
        flags=["--natal-branch", "卯", "--response-char-limit", "0"],
    )
    assert code == 0
    node = value["jinkou"]["relations"]["si_jue"]["natal"]
    assert node["right_branch"] == "卯" and node["matched"] is True


def test_invalid_natal_input_is_an_input_error_on_every_port(rest, tmp_path, capsys):
    payload = dict(PAYLOAD, natal_branch="甲子")
    http = rest.post(SPEC.rest_path, json=payload)
    protocol = asyncio.run(native(SPEC, payload))
    code, cli = call_cli(SPEC, payload, tmp_path, capsys)
    assert http.status_code == 422 and protocol.is_error and code == 1
    assert cli["error_code"] == "validation_error"


def test_trace_alone_is_a_legal_projection_with_its_own_pair_anchors():
    body = raw("卯")
    SPEC.output_model.model_validate(
        {"jinkou": {"rule_trace": body["jinkou"]["rule_trace"]}}
    )

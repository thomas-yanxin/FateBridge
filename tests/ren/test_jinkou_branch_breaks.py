"""Printed pair membership, same-course binding, and actual public transports."""

import copy
import json
import shutil
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import pytest
from pydantic import ValidationError

import fatebridge.application.execution as execution
from fatebridge.core.metaphysics.jinkou_branch_breaks import branch_breaks, pair_facts
from fatebridge.core.output_chinese import JinkouCourse
from fatebridge.core.output_jinkou_breaks import JinkouBranchBreaks
from scripts.ren.audit_jinkou_branch_breaks import CORPUS, reference
from tests.support.transports import (
    AS_OF,
    REST_POST_CASES,
    SPECS,
    business,
    native,
    rest,
    surface_calls,
)

ROOT = Path(__file__).resolve().parents[2]
SPEC = SPECS["jinkou"]
PAYLOAD = {
    **REST_POST_CASES[SPEC.rest_path](),
    "birth_year_ganzhi": "甲子",
    "year_fate_age": 43,
    "gender": "男",
}


@pytest.fixture(autouse=True)
def native_solar(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))


@lru_cache(maxsize=1)
def raw():
    fn, args, kw = SPEC.bind(SPEC.request_model.model_validate(PAYLOAD))
    return fn(*args, **kw)


def course(body, role):
    board = body["jinkou"]
    return board if role == "primary" else board[role]["course"]


def test_entire_independent_matrix_and_all_internal_branch_triples():
    data = reference()
    for expected in data["reference"]["pair_matrix"]:
        assert pair_facts(expected["left_branch"], expected["right_branch"]) == expected
    for case in data["reference"]["contexts"]:
        result = branch_breaks(*case["branches"])
        assert result["rows"] == case["rows"]
        JinkouBranchBreaks.model_validate(result)
    assert data["reference"]["counts"] == dict(
        matrix=144,
        printed_pairs=7,
        pair_present_in_matrix=14,
        triples=1728,
        position_comparisons=5184,
        pair_present_in_comparisons=504,
    )
    assert data["readings"]["reader_count"] == 1
    assert data["readings"]["blinded"] is False


@pytest.mark.parametrize("change", ["reference", "source", "joint"])
def test_reference_or_joint_manifest_rewrite_cannot_relabel_the_pairs(tmp_path, change):
    import hashlib

    target = tmp_path / "corpus"
    shutil.copytree(CORPUS, target)
    name = "page-113.jpg" if change == "source" else "reference.json"
    path = target / name
    path.write_bytes(path.read_bytes() + b" ")
    if change == "joint":
        manifest = json.loads((target / "freeze.json").read_text())
        manifest["files"][name] = hashlib.sha256(path.read_bytes()).hexdigest()
        (target / "freeze.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Frozen printed-break"):
        reference(target)


def test_reversed_position_order_preserves_printed_order_and_unknown_effects():
    a, b = pair_facts("申", "巳"), pair_facts("巳", "申")
    assert a["source_pair_present"] is b["source_pair_present"] is True
    assert a["source_order"] == "left_then_right"
    assert b["source_order"] == "right_then_left"
    assert a["source_written_pair"] == b["source_written_pair"] == ["申", "巳"]
    assert a["effective_break"] is b["effect_direction"] is None
    assert pair_facts("申", "寅")["source_pair_present"] is False  # 对冲不替代破支表。
    for board in [course(raw(), r) for r in ("primary", "natal_course", "year_fate")]:
        assert board["use_evidence"]["comprehensive_position"] is None
        assert board["ruleset"]["version"] == "1.16.0"
        selected = [
            t
            for t in board["rule_trace"]
            if t["rule_id"] == "jinkou.printed_break_pairs"
        ]
        assert len(selected) == 1
        assert selected[0]["result"] == board["branch_breaks"]


@pytest.mark.parametrize(
    "a,b", [("甲", "子"), ("申巳", "子"), (None, "子"), ("", "子")]
)
def test_invalid_symbols_are_not_interpreted_as_unmatched(a, b):
    with pytest.raises(ValueError):
        pair_facts(a, b)


@pytest.mark.parametrize("project", [False, True])
def test_valid_same_course_facts_survive_actual_rest_mcp_cli(project, surface_calls):
    params = [("as_of", AS_OF), ("response_char_limit", "0")]
    flags, options = ["--response-char-limit", "0"], {}
    if project:
        fields = [
            "jinkou.branch_breaks",
            "jinkou.natal_course.course.branch_breaks",
            "jinkou.year_fate.course.branch_breaks",
        ]
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
    http, protocol, code, cli = surface_calls(
        SPEC, PAYLOAD, params=params, options=options, flags=flags, cli_first=False
    )
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    assert (
        business(http.json()) == business(cli) == business(protocol.structured_content)
    )
    for body in (http.json(), cli, protocol.structured_content):
        for role in ("primary", "natal_course", "year_fate"):
            block = course(body, role)["branch_breaks"]
            assert len(block["rows"]) == 3
            assert block["effective_break"] is block["effect_direction"] is None


@pytest.mark.parametrize("role", ["primary", "natal_course", "year_fate"])
@pytest.mark.parametrize("project", [False, True])
@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "wrong_branch",
        "wrong_pair",
        "false_effect",
        "false_source",
        "integer_bool",
    ],
)
def test_faults_in_each_course_are_rejected_before_projection_on_all_ports(
    role, project, fault, monkeypatch, surface_calls
):
    bad = copy.deepcopy(raw())
    board = course(bad, role)
    block = board["branch_breaks"]
    if fault == "missing":
        del board["branch_breaks"]
    elif fault == "wrong_branch":
        row = block["rows"][0]
        row["left_branch"] = "子" if row["left_branch"] != "子" else "丑"
    elif fault == "wrong_pair":
        block["rows"][0]["source_pair_present"] = not block["rows"][0][
            "source_pair_present"
        ]
    elif fault == "false_effect":
        block["effective_break"] = True
    elif fault == "false_source":
        block["source_sha256"] = "invented"
    else:
        block["rows"][0]["source_pair_present"] = int(
            block["rows"][0]["source_pair_present"]
        )
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
    http, protocol, code, cli = surface_calls(
        SPEC, PAYLOAD, params=params, options=options, flags=flags, cli_first=False
    )
    assert http.status_code == 500 and protocol.is_error and code == 1
    assert cli["error_code"] == "internal_error"


def test_sparse_views_keep_missing_anchors_missing_and_trace_facts_are_checked():
    block = raw()["jinkou"]["branch_breaks"]
    sparse = dict(branch_breaks=block)
    assert JinkouCourse.model_validate(sparse).model_dump(exclude_unset=True) == sparse
    trace = copy.deepcopy(
        next(
            t
            for t in raw()["jinkou"]["rule_trace"]
            if t["rule_id"] == "jinkou.printed_break_pairs"
        )
    )
    trace["result"]["source_sha256"] = "invented"
    with pytest.raises(ValidationError):
        JinkouCourse.model_validate(dict(rule_trace=[trace]))


def test_shared_producer_validator_metadata_cannot_be_its_own_source_oracle(
    monkeypatch,
):
    import fatebridge.core.metaphysics.jinkou_branch_breaks as production
    from scripts.ren.audit_jinkou_branch_breaks import audit

    monkeypatch.setattr(production, "SCAN_SHA256", "fabricated_source")
    result = audit()
    assert result["finite_pair_facts_passed"] is False
    assert len(result["failures"]) == 1728
    assert (
        result["independent_source_metadata"]["source_sha256"]
        == reference()["readings"]["source_sha256"]
    )


def test_scan_extra_pair_is_not_deleted_to_match_the_web_transcription():
    from scripts.ren.audit_jinkou_branch_breaks import INITIAL_CORPUS, INITIAL_PIN, sha

    value = branch_breaks("寅", "巳", "申")
    assert value["written_pairs"] == [
        list(p) for p in ("申巳", "戌未", "亥寅", "寅巳", "丑辰", "午卯", "酉子")
    ]
    assert len(value["transcription_written_pairs"]) == 6
    assert value["scan_extra_pairs"] == [["寅", "巳"]]
    assert value["extra_pair_author_intent"] is None
    assert pair_facts("寅", "巳")["source_pair_present"] is True
    assert sha(INITIAL_CORPUS / "freeze.json") == INITIAL_PIN
    original = json.loads((INITIAL_CORPUS / "reference.json").read_text())
    assert original["counts"]["printed_pairs"] == 6
    assert original["counts"]["pair_present_in_matrix"] == 12


def test_reverting_to_six_pairs_fails_the_fixed_scan_reference(monkeypatch):
    import fatebridge.core.metaphysics.jinkou_branch_breaks as production
    from scripts.ren.audit_jinkou_branch_breaks import audit

    monkeypatch.setattr(
        production,
        "WRITTEN_PAIRS",
        tuple(p for p in production.WRITTEN_PAIRS if p != "寅巳"),
    )
    result = audit()
    assert result["matrix_match_count"] == 142
    assert result["row_mismatch_count"] == 66
    assert result["finite_pair_facts_passed"] is False
    assert result["initial_incomplete_reading"]["coverage_claim_invalidated"] is True

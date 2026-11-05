"""Original ordered clauses, same-board binding and real local transports."""

import asyncio
import copy
import itertools
import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

import fatebridge.application.execution as execution
from fatebridge.core.metaphysics.liureng_ordered_patterns import (
    ordered_transmission_patterns,
)
from fatebridge.core.output_liuren_ordered_patterns import LiurenOrderedPatterns
from fatebridge.core.output_ren_anchors import require_complete_ren_anchors
from scripts.ren.audit_liuren_ordered_patterns import CORPUS, audit, reference
from tests.evaluation.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    native,
    rest,
)

ROOT = Path(__file__).resolve().parents[2]
REF = reference()
PAYLOADS = json.loads((ROOT / "tests/fixtures/ren_anchors_v1/faults.json").read_text())[
    "payloads"
]


@pytest.fixture(autouse=True)
def native_solar(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))


@pytest.mark.parametrize("clause", REF["clauses"], ids=lambda c: c["id"])
def test_all_permutations_distinguish_the_literal_order(clause):
    for triple in itertools.permutations(clause["branches"]):
        value = ordered_transmission_patterns(list(triple))
        expected = [c["id"] for c in REF["clauses"] if list(triple) == c["branches"]]
        assert value["matched_ids"] == expected
        LiurenOrderedPatterns.model_validate(value)


def test_frozen_anchors_and_entire_symbolic_space():
    result = audit()
    assert result["engineering_checks_passed"] and result["implementation_unchanged"]
    assert (
        result["mathematical_cases"] == 1728 and result["symbolic_board_count"] == 720
    )
    assert result["mathematical_counts"] == dict(
        zhuolun=1, zhuyin=1, xuangai=1, none=1725
    )
    assert result["new_historical_events"] == result["new_empirical_events"] == 0
    assert result["goal_complete"] is result["full_classical_conformance"] is False


@pytest.mark.parametrize("fault", ["bytes", "manifest", "extra", "missing"])
def test_reference_is_pinned_without_pruning(fault, tmp_path):
    path = tmp_path / "reference"
    shutil.copytree(CORPUS, path)
    if fault == "bytes":
        with (path / "readings.json").open("ab") as f:
            f.write(b" ")
    elif fault == "manifest":
        (path / "freeze.json").write_text("{}")
    elif fault == "extra":
        (path / "extra.json").write_text("{}")
    else:
        (path / "source-pages.pdf").unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        reference(path)


@pytest.mark.parametrize(
    "branches",
    [
        ["卯", "戌"],
        ["卯", "戌", "巳", "午"],
        ["卯", "戌", None],
        ["卯", "戌", "北"],
        "卯戌巳",
        None,
    ],
)
def test_invalid_order_is_not_guessed(branches):
    with pytest.raises(ValueError):
        ordered_transmission_patterns(branches)


@pytest.mark.parametrize(
    "fault", ["source", "reverse", "prune", "matched", "numeric_bool", "conformance"]
)
def test_present_facts_cannot_be_rewritten(fault):
    value = ordered_transmission_patterns(["卯", "戌", "巳"])
    if fault == "source":
        value["source_sha256"] = "invented"
    elif fault == "reverse":
        value["evaluations"].reverse()
    elif fault == "prune":
        value["evaluations"].pop()
    elif fault == "matched":
        value["evaluations"][0]["matched"] = False
    elif fault == "numeric_bool":
        value["evaluations"][0]["matched"] = 1
    else:
        value["complete_classical_conformance"] = 0
    with pytest.raises(ValidationError):
        LiurenOrderedPatterns.model_validate(value)


def test_sparse_projection_keeps_only_returned_facts():
    LiurenOrderedPatterns.model_validate({"matched_ids": ["zhuolun"]})
    LiurenOrderedPatterns.model_validate(
        {"evaluations": [{"name": c["name"]} for c in REF["clauses"]]}
    )


def raw(key):
    spec = SPECS[key]
    fn, args, kwargs = spec.bind(spec.request_model.model_validate(PAYLOADS[key]))
    return fn(*args, **kwargs)


@pytest.mark.parametrize(
    "key", ["liureng_gods", "liureng_runyear", "jinkou", "sanshiunited"]
)
@pytest.mark.parametrize("project", [False, True])
def test_actual_three_ports_deliver_the_same_new_facts(
    key, project, rest, tmp_path, capsys
):
    spec = SPECS[key]
    fields = ["liureng.transmission_relations.named_structures"]
    params = [("as_of", AS_OF), ("response_char_limit", "0")]
    flags = ["--response-char-limit", "0"]
    options = {}
    if project:
        params += [
            ("fields", fields[0]),
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
        value = body["liureng"]["transmission_relations"]["named_structures"]
        assert (
            len(value["evaluations"]) == 3
            and value["complete_classical_conformance"] is False
        )


@pytest.mark.parametrize(
    "key", ["liureng_gods", "liureng_runyear", "jinkou", "sanshiunited"]
)
@pytest.mark.parametrize(
    "fault", ["missing", "other_order", "trace", "trace_duplicate"]
)
def test_full_result_requires_same_board_order_and_one_trace(key, fault):
    value = raw(key)
    board = value["liureng"]
    if fault == "missing":
        board["transmission_relations"].pop("named_structures")
    elif fault == "other_order":
        board["transmission_relations"]["named_structures"] = (
            ordered_transmission_patterns(["卯", "戌", "巳"])
        )
    else:
        trace = next(
            t
            for t in board["rule_trace"]
            if t["rule_id"] == "liuren.ordered_transmission_patterns"
        )
        if fault == "trace":
            board["rule_trace"].remove(trace)
        else:
            board["rule_trace"].append(copy.deepcopy(trace))
    with pytest.raises(ValueError):
        require_complete_ren_anchors(key, value)


@pytest.mark.parametrize("project", [False, True])
def test_false_order_fails_before_projection_on_three_ports(
    project, rest, monkeypatch, tmp_path, capsys
):
    key = "liureng_gods"
    spec = SPECS[key]
    value = raw(key)
    row = value["liureng"]["transmission_relations"]["named_structures"]["evaluations"][
        0
    ]
    row["matched"] = not row["matched"]
    fake = replace(spec, bind=lambda _: (lambda: copy.deepcopy(value), (), {}))
    original = execution.execute_spec

    def broken(actual, request):
        return original(fake if actual.key == key else actual, request)

    monkeypatch.setattr(execution, "execute_spec", broken)
    params = [("response_char_limit", "0")]
    flags = ["--response-char-limit", "0"]
    options = {}
    if project:
        params += [("fields", "four_pillars"), ("strict_fields", "true")]
        flags += ["--fields", "four_pillars", "--strict-fields", "true"]
        options.update(fields=["four_pillars"], strict_fields=True)
    http = rest.post(spec.rest_path, json=PAYLOADS[key], params=params)
    protocol = asyncio.run(native(spec, PAYLOADS[key], **options))
    code, cli = call_cli(spec, PAYLOADS[key], tmp_path, capsys, flags=flags)
    assert http.status_code == 500 and protocol.is_error and code != 0

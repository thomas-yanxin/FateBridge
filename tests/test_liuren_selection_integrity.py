"""Nine-method evidence cannot contradict the returned day and sky board."""

import asyncio
import copy
import importlib.util
import json
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import pytest
from pydantic import ValidationError

import fatebridge.application.execution as execution
from fatebridge.core.output_chinese import Liuren
from tests.test_agentic_nested_outputs import (
    AS_OF,
    REST_POST_CASES,
    SPECS,
    call_cli,
    native,
    rest,
)

ROOT = Path(__file__).resolve().parents[1]
MODULE = importlib.util.spec_from_file_location(
    "selection_integrity", ROOT / "scripts/audit_liuren_selection_integrity.py"
)
assert MODULE and MODULE.loader
AUDIT = importlib.util.module_from_spec(MODULE)
MODULE.loader.exec_module(AUDIT)
REF = AUDIT.resolved_reference()
PROTOCOL = json.loads((AUDIT.CORPUS / "protocol.json").read_text())


def payload(key):
    spec = SPECS[key]
    values = REST_POST_CASES[spec.rest_path]()
    values.update(
        {
            k: v
            for k, v in PROTOCOL["public_payload"].items()
            if k in spec.request_model.model_fields
        }
    )
    if key == "sanshiunited":
        values.update(
            date="2000-01-27",
            time="08:00:00",
            zone="+08:00",
            liureng_yue=None,
            liureng_is_diurnal=None,
        )
    return values


@lru_cache(maxsize=4)
def output(key="liureng_gods"):
    spec = SPECS[key]
    fn, args, kw = spec.bind(spec.request_model.model_validate(payload(key)))
    return fn(*args, **kw)


@pytest.mark.parametrize("fault", ["harm_depth", "named_label", "selected_lesson"])
def test_preexisting_complete_output_cannot_accept_wrong_selection_facts(fault):
    with pytest.raises(execution.OutputContractError):
        execution.validate_output(
            SPECS["liureng_gods"], AUDIT.corrupt(output(), "liureng_gods", fault)
        )


@pytest.mark.parametrize("case", REF["cases"], ids=lambda c: c["id"])
def test_primary_printed_harm_counts_and_transmissions(case):
    board = AUDIT.observe(case["day"], case["gan_upper"])
    traces = board["rule_trace"]
    assert (
        next(t["result"] for t in traces if t["rule_id"] == "liuren.harm_depth")
        == case["depths"]
    )
    assert [
        board["three_transmissions"][p]["branch"]
        for p in ("initial", "middle", "final")
    ] == case["transmissions"]
    paths = next(t["result"] for t in traces if t["rule_id"] == "liuren.harm_paths")
    assert {
        str(item["lesson_index"]): item["harm_count"] for item in paths["candidates"]
    } == case["depths"]
    assert all(not item["terminal_home_counted"] for item in paths["candidates"])


@pytest.mark.parametrize("key", PROTOCOL["tools"])
@pytest.mark.parametrize(
    "fault",
    PROTOCOL["faults"]
    + [
        "harm_path_count",
        "harm_path_station",
        "harm_path_element",
        "harm_path_token",
        "harm_path_flag",
        "harm_path_extra",
    ],
)
@pytest.mark.parametrize("project", [False, True])
def test_full_nine_method_facts_reject_faults_before_projection_on_three_ports(
    key, fault, project, rest, monkeypatch, tmp_path, capsys
):
    spec = SPECS[key]
    bad = AUDIT.corrupt(output(key), key, fault)
    with pytest.raises(execution.OutputContractError):
        execution.validate_output(spec, bad)
    original = execution.execute_spec

    def broken(selected, request):
        if selected.key == key:
            selected = replace(
                selected, bind=lambda _: (lambda: copy.deepcopy(bad), (), {})
            )
        return original(selected, request)

    monkeypatch.setattr(execution, "execute_spec", broken)
    params = {"as_of": AS_OF, "response_char_limit": 0}
    opts = {}
    flags = ["--response-char-limit", "0"]
    if project:
        params.update(fields="analysis_type", strict_fields="true")
        opts.update(fields=["analysis_type"], strict_fields=True)
        flags += ["--fields", "analysis_type", "--strict-fields", "true"]
    http = rest.post(spec.rest_path, json=payload(key), params=params)
    protocol = asyncio.run(native(spec, payload(key), **opts))
    code, cli = call_cli(spec, payload(key), tmp_path, capsys, flags=flags)
    assert http.status_code == 500 and protocol.is_error and code == 1
    assert cli["error_code"] == "internal_error"


@pytest.mark.parametrize("key", PROTOCOL["tools"])
@pytest.mark.parametrize("project", [False, True])
def test_valid_four_entry_points_preserve_all_nine_method_evidence(
    key, project, rest, tmp_path, capsys
):
    spec = SPECS[key]
    fields = [
        "liureng.four_lessons",
        "liureng.three_transmissions",
        "liureng.classification",
        "liureng.rule_trace",
        "liureng.meta",
    ]
    params = [("as_of", AS_OF), ("response_char_limit", "0")]
    opts = {}
    flags = ["--response-char-limit", "0"]
    if project:
        params += [("fields", p) for p in fields] + [("strict_fields", "true")]
        opts.update(fields=fields, strict_fields=True)
        flags += ["--fields", *fields, "--strict-fields", "true"]
    http = rest.post(spec.rest_path, json=payload(key), params=params)
    protocol = asyncio.run(native(spec, payload(key), **opts))
    code, cli = call_cli(spec, payload(key), tmp_path, capsys, flags=flags)
    assert http.status_code == 200 and not protocol.is_error and code == 0
    for body in [http.json(), protocol.structured_content, cli]:
        for name in [
            "four_lessons",
            "three_transmissions",
            "classification",
            "rule_trace",
            "meta",
        ]:
            assert body["liureng"][name] == output(key)["liureng"][name]


def test_partial_facts_keep_absent_context_absent_but_bind_available_context():
    for value in [
        {},
        {"classification": {"labels": ["元首"]}},
        {"meta": {"selected_lesson_index": None}},
    ]:
        assert Liuren.model_validate(value).model_dump(exclude_unset=True) == value
    body = copy.deepcopy(output()["liureng"])
    body["classification"]["labels"] = ["元首"]
    with pytest.raises(ValidationError):
        Liuren.model_validate(body)


def test_unresolved_terminal_variants_cannot_be_relabelled_as_classical_success():
    report = AUDIT.audit()
    assert report["printed_count"] == report["printed_matched_count"] == 6
    assert report["raw_frozen_matched_count"] == 5
    assert report["post_observation_erratum"]["observed_after_red_run"]
    assert report["aggregate_source_counts"] == {
        "涉害": 63,
        "见机": 9,
        "察微": 2,
        "缀瑕": 1,
    }
    assert (
        not report["terminal_inclusion_adjudicated"]
        and not report["whole_book_conformance"]
        and not report["goal_complete"]
    )

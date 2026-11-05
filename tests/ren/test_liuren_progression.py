"""Original progression evidence, strict same-board anchors and actual transports."""

import asyncio
import copy
import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

import fatebridge.application.execution as execution
from fatebridge.application.examples import evidence_views
from fatebridge.core.metaphysics.liureng import build_liureng_board
from fatebridge.core.metaphysics.liureng_progression import transmission_progression
from fatebridge.core.output_chinese import Liuren
from fatebridge.core.output_liuren_progression import (
    LiurenProgression,
    require_complete_progression,
)
from scripts.ren.audit_liuren_progression import CORPUS, audit, reference
from scripts.ren.audit_ren_classical import make_seed
from tests.evaluation.test_agentic_nested_outputs import (
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


@pytest.mark.parametrize("case", REF["synthetic_cases"])
def test_frozen_synthetic_condition_keeps_effective_judgement_unknown(case):
    got = transmission_progression(case["day"], case["branches"])
    assert (
        got["kind"],
        got["sequence_direction"],
        got["raw_branch_empty_conditional_reading"],
    ) == (case["kind"], case["direction"], case["reading"])
    assert got["effective_direction"] is got["comprehensive_judgement"] is None
    assert got["complete_classical_conformance"] is False
    LiurenProgression.model_validate(got)


@pytest.mark.parametrize("fault", ["bytes", "manifest", "extra", "missing"])
def test_frozen_reference_cannot_be_pruned_or_refrozen(fault, tmp_path):
    folder = tmp_path / "corpus"
    shutil.copytree(CORPUS, folder)
    if fault == "bytes":
        with (folder / "reference.json").open("ab") as f:
            f.write(b" ")
    elif fault == "manifest":
        (folder / "freeze.json").write_text("{}")
    elif fault == "extra":
        (folder / "extra").write_text("")
    else:
        (folder / "source-pages.pdf").unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        reference(folder)


@pytest.mark.parametrize(
    "day,branches",
    [
        ("甲丑", ["子", "丑", "寅"]),
        ("甲子", ["子", "丑"]),
        ("甲子", ["子", "丑", "北"]),
        ("甲子", ["子", "丑", None]),
        ("甲子", None),
    ],
)
def test_invalid_symbolic_inputs_rejected(day, branches):
    with pytest.raises(ValueError):
        transmission_progression(day, branches)


def test_all_mathematical_combinations_and_symbolic_boards_with_canonical_paths(
    tmp_path, monkeypatch
):
    import scripts.ren.audit_liuren_progression as mod

    alias = tmp_path / "source"
    alias.symlink_to(ROOT, target_is_directory=True)
    monkeypatch.setattr(
        mod, "__file__", str(alias / "scripts/ren/audit_liuren_progression.py")
    )
    result = audit()
    assert result["engineering_checks_passed"] and result["implementation_unchanged"]
    assert result["literal_examples"] == 8 and result["rotational_expansions"] == 48
    assert (
        result["mathematical_cases"] == 103680
        and sum(result["mathematical_counts"].values()) == 103680
    )
    assert result["symbolic_board_count"] == 720 and not result["failures"]
    assert result["new_historical_events"] == result["new_empirical_events"] == 0
    assert result["full_classical_conformance"] is result["goal_complete"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("kind", "间断"),
        ("sequence_direction", "退"),
        ("steps", [2, 2]),
        ("branches", ["子", "丑"]),
        ("branch_xun_kong", [False, False, False]),
        ("raw_branch_empty_conditional_reading", "按支序进读"),
        ("raw_branch_empty_conditional_direction", "进"),
        ("effective_direction", "进"),
        ("comprehensive_judgement", "吉"),
        ("source_sha256", "fake"),
        ("original_pdf_pages", [111, 112]),
        ("scope", "已经全书通过"),
        ("structure_matched", 1),
        ("branch_xun_kong", [0, False, False]),
    ],
)
def test_same_context_tampering_rejected(field, value):
    evidence = transmission_progression("甲子", ["亥", "子", "丑"])
    evidence[field] = value
    with pytest.raises(ValidationError):
        LiurenProgression.model_validate(evidence)


def board():
    return build_liureng_board(
        make_seed(dict(day="甲子", hour="子")), month_general_override="丑"
    )


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "trace_missing",
        "trace_duplicate",
        "trace_forged",
        "effective",
        "branch",
        "day",
        "empty",
    ],
)
def test_full_before_projection_guard_rejects_corruption(fault):
    b = board()
    if fault == "missing":
        b.pop("transmission_progression")
    elif fault.startswith("trace_"):
        trace = next(
            r
            for r in b["rule_trace"]
            if r["rule_id"] == "liuren.transmission_progression"
        )
        if fault == "trace_missing":
            b["rule_trace"].remove(trace)
        elif fault == "trace_duplicate":
            b["rule_trace"].append(copy.deepcopy(trace))
        else:
            trace["result"]["kind"] = "间断"
    elif fault == "effective":
        b["transmission_progression"]["effective_direction"] = "进"
    elif fault == "branch":
        b["three_transmissions"]["initial"]["branch"] = "亥"
    elif fault == "day":
        b["transmission_progression"]["day_ganzhi"] = "甲戌"
    else:
        b["three_transmissions"]["initial"]["xun_kong"] = True
    with pytest.raises(ValueError):
        require_complete_progression(b)


def test_sparse_projection_can_omit_context_but_copresent_facts_must_agree():
    Liuren.model_validate(dict(transmission_progression=dict(kind="连茹")))
    b = board()
    ev = b["transmission_progression"]
    Liuren.model_validate(
        dict(transmission_progression=ev, three_transmissions=b["three_transmissions"])
    )
    b["three_transmissions"]["initial"]["branch"] = "亥"
    with pytest.raises(ValidationError):
        Liuren.model_validate(b)


@pytest.mark.parametrize("value", [True, 0, 1])
def test_partial_conformance_flag_requires_boolean_false(value):
    with pytest.raises(ValidationError):
        LiurenProgression.model_validate(dict(complete_classical_conformance=value))


def test_seated_empty_and_god_sky_never_replace_raw_branch_empty():
    found = False
    for g in "子丑寅卯辰巳午未申酉戌亥":
        b = build_liureng_board(
            make_seed(dict(day="甲子", hour="子")), month_general_override=g
        )
        ev = b["transmission_progression"]
        before = copy.deepcopy(ev)
        for n in ["initial", "middle", "final"]:
            b["three_transmissions"][n]["seated_kong"] = True
            b["three_transmissions"][n]["god"] = "天空"
        require_complete_progression(b)
        assert ev == before
        found |= ev["kind"] is not None
    assert found


@pytest.mark.parametrize("key", ["liureng_gods", "liureng_runyear", "jinkou"])
def test_actual_rest_native_mcp_cli_share_published_evidence_view(
    key, rest, tmp_path, capsys
):
    spec = SPECS[key]
    payload = copy.deepcopy(PAYLOADS[key])
    payload["selected_sections"] = ["起盘信息"]
    name = (
        "liuren_transmission_progression"
        if key == "jinkou"
        else "transmission_progression"
    )
    fields = evidence_views(spec)[name]["fields"]
    options = dict(fields=fields, strict_fields=True, include_snapshot_text=False)
    http = rest.post(
        spec.rest_path,
        json=payload,
        params=[
            *[("fields", f) for f in fields],
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
        ],
    )
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--response-char-limit",
            "0",
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ],
    )
    mcp = asyncio.run(native(spec, payload, **options))
    assert http.status_code == 200 and code == 0 and not mcp.is_error
    assert business(http.json()) == business(cli) == business(mcp.structured_content)
    ev = http.json()["liureng"]["transmission_progression"]
    assert ev["effective_direction"] is None and ev["comprehensive_judgement"] is None
    assert ev["branches"] == [
        http.json()["liureng"]["three_transmissions"][n]["branch"]
        for n in ["initial", "middle", "final"]
    ]


def test_snapshot_section_is_derived_from_same_conditional_evidence():
    spec = SPECS["liureng_gods"]
    payload = {**PAYLOADS["liureng_gods"], "selected_sections": ["三传连茹与间断"]}
    fn, args, kw = spec.bind(spec.request_model.model_validate(payload))
    result = fn(*args, **kw)
    ev = result["liureng"]["transmission_progression"]
    text = result["snapshot_text"]
    assert "、".join(ev["branches"]) in text and str(ev["steps"]) in text
    assert ev["empty_assumption"] in text and "综合有效进退：未裁定" in text
    assert (ev["raw_branch_empty_conditional_reading"] or "无所列释读") in text


def test_shared_execution_rejects_deleted_layer_before_requested_sparse_fields():
    spec = SPECS["liureng_gods"]
    fn, args, kw = spec.bind(
        spec.request_model.model_validate(PAYLOADS["liureng_gods"])
    )
    result = fn(*args, **kw)
    result["liureng"].pop("transmission_progression")
    bad = replace(spec, bind=lambda _: (lambda: copy.deepcopy(result), (), {}))
    with pytest.raises(execution.OutputContractError):
        execution.execute_spec(
            bad, spec.request_model.model_validate(PAYLOADS["liureng_gods"])
        )


@pytest.mark.parametrize("project", [False, True])
def test_deleted_progression_fails_actual_transports_before_projection(
    project, rest, monkeypatch, tmp_path, capsys
):
    spec = SPECS["liureng_gods"]
    payload = PAYLOADS["liureng_gods"]
    fn, args, kw = spec.bind(spec.request_model.model_validate(payload))
    bad = fn(*args, **kw)
    bad["liureng"].pop("transmission_progression")
    original = execution.execute_spec

    def broken(current, request):
        if current.key == "liureng_gods":
            current = replace(
                current, bind=lambda _: (lambda: copy.deepcopy(bad), (), {})
            )
        return original(current, request)

    monkeypatch.setattr(execution, "execute_spec", broken)
    params = [("response_char_limit", "0")]
    flags = ["--response-char-limit", "0"]
    options = {}
    if project:
        params += [("fields", "four_pillars"), ("strict_fields", "true")]
        flags += ["--fields", "four_pillars", "--strict-fields", "true"]
        options = dict(fields=["four_pillars"], strict_fields=True)
    http = rest.post(spec.rest_path, json=payload, params=params)
    protocol = asyncio.run(native(spec, payload, **options))
    code, cli = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    assert http.status_code == 500 and protocol.is_error and code != 0
    assert all(
        v["error_code"] == "internal_error" and "liureng" not in v
        for v in [http.json(), protocol.structured_content, cli]
    )

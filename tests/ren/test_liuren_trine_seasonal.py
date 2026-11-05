"""Nominal completed trines acquire seasonal facts without changing their parts."""

import asyncio
import copy
import hashlib
import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

import fatebridge.application.execution as execution
from fatebridge.core.metaphysics.liureng import build_liureng_board
from fatebridge.core.metaphysics.liureng_trine_seasonal import nominal_seasonal_evidence
from fatebridge.core.output_chinese import Liuren
from fatebridge.core.output_liuren_trine_seasonal import LiurenNominalTrineSeasonal
from scripts.ren.audit_liuren_seasonal import seed_for
from scripts.ren.audit_liuren_trine_seasonal import CORPUS, FIELD, audit, reference
from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
    rest,
)

ROOT = Path(__file__).resolve().parents[2]
PAYLOADS = json.loads((ROOT / "tests/fixtures/ren_anchors_v1/faults.json").read_text())[
    "payloads"
]


def source_board():
    return build_liureng_board(
        seed_for("辛未", "午"),
        month_general_override="辰",
        guiren_profile="tanyuan_xieji_v1",
        is_diurnal_override=True,
    )


@pytest.mark.parametrize(
    "fault", ["data", "manifest", "missing", "extra", "joint_rewrite"]
)
def test_literal_reference_and_full_triple_inventory_cannot_be_rewritten(
    fault, tmp_path
):
    target = tmp_path / "ref"
    shutil.copytree(CORPUS, target)
    p = target / "reference.json"
    if fault in {"data", "joint_rewrite"}:
        v = json.loads(p.read_text())
        v["trines"].pop()
        p.write_text(json.dumps(v))
        if fault == "joint_rewrite":
            m = json.loads((target / "freeze.json").read_text())
            m[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
            (target / "freeze.json").write_text(json.dumps(m))
    elif fault == "manifest":
        (target / "freeze.json").write_text("{}")
    elif fault == "missing":
        p.unlink()
    else:
        (target / "extra").write_text("")
    with pytest.raises((ValueError, FileNotFoundError)):
        reference(target)


def test_all_ordered_triples_and_months_match_literal_nominal_powers():
    r = audit()
    assert r["selected_component_checks_passed"] and not r["failures"]
    assert r["counts"] == dict(
        ordered_triples_per_month=20736,
        trine_slots=82944,
        complete_nominal_evidence=288,
        source_example_components=1,
    )
    assert (
        not r["full_named_course_adjudicated"]
        and not r["full_classical_conformance"]
        and not r["goal_complete"]
    )


def test_summer_wood_example_keeps_water_wood_and_earth_as_separate_raw_phases():
    b = source_board()
    Liuren.model_validate(b)
    assert [
        b["three_transmissions"][p]["branch"] for p in ["initial", "middle", "final"]
    ] == ["亥", "卯", "未"]
    e = next(
        t[FIELD]
        for t in b["transmission_relations"]["trines"]
        if t["branches_complete"]
    )
    assert (e["nominal_element"], e["nominal_power"], e["course_component"]) == (
        "木",
        "休",
        "既往",
    )
    assert (
        e["full_named_course_adjudicated"] is False
        and e["transformation_confirmed"] is None
    )
    assert [r["element"] for r in b["transmission_relations"]["rows"]] == [
        "水",
        "木",
        "土",
    ]


@pytest.mark.parametrize(
    "value",
    [
        {"nominal_power": "休"},
        {"month_branch": "午", "nominal_power": "休"},
        {"nominal_element": "木", "nominal_power": "休"},
    ],
)
def test_missing_month_or_nominal_phase_stays_unknown_without_inventing_data(value):
    assert (
        LiurenNominalTrineSeasonal.model_validate(value).model_dump(exclude_unset=True)
        == value
    )


@pytest.mark.parametrize("value", [True, 0, 1, None])
def test_component_does_not_gain_a_full_named_course_certificate(value):
    with pytest.raises(ValidationError):
        LiurenNominalTrineSeasonal.model_validate(
            {"full_named_course_adjudicated": value}
        )


def test_no_nominal_earth_trine_is_invented():
    with pytest.raises(ValueError):
        nominal_seasonal_evidence("午", "土")
    with pytest.raises(ValidationError):
        LiurenNominalTrineSeasonal.model_validate({"nominal_element": "土"})


@pytest.mark.parametrize(
    "field,value",
    [
        ("nominal_power", "旺"),
        ("course_component", "得势"),
        ("source_url", "https://example.invalid/forged"),
        ("month_branch", "子"),
    ],
)
def test_own_board_month_phase_and_source_bind_every_present_context(field, value):
    b = source_board()
    bad = copy.deepcopy(b)
    e = next(
        t[FIELD]
        for t in bad["transmission_relations"]["trines"]
        if t["branches_complete"]
    )
    e[field] = value
    with pytest.raises(ValidationError):
        Liuren.model_validate(bad)


def test_root_month_anchor_rejects_coherent_foreign_month_even_without_other_raw_anchors():
    b = source_board()
    trines = copy.deepcopy(b["transmission_relations"]["trines"])
    e = next(t for t in trines if t["branches_complete"])
    e[FIELD] = nominal_seasonal_evidence("子", "木")
    with pytest.raises(ValidationError):
        SPECS["liureng_gods"].output_model.model_validate(
            {
                "four_pillars": {"month": {"branch": "午"}},
                "liureng": {"transmission_relations": {"trines": trines}},
            }
        )


def test_coarse_same_group_cannot_mask_a_wrong_literal_power(monkeypatch):
    from fatebridge.core.metaphysics.liureng_seasonal import POWERS

    monkeypatch.setitem(POWERS["春"], "金", "死")
    result = audit()
    assert not result["selected_component_checks_passed"]
    assert any(f["kind"] == "nominal_power" for f in result["failures"])


@pytest.mark.parametrize(
    "key", ["liureng_gods", "liureng_runyear", "jinkou", "sanshiunited"]
)
def test_all_four_entrypoints_deliver_new_context_identically_on_three_ports(
    key, rest, tmp_path, capsys
):
    spec = SPECS[key]
    fields = [
        "liureng.transmission_relations.trines",
        "liureng.seasonal_evidence.month_branch",
    ]
    params = [("fields", f) for f in fields] + [
        ("strict_fields", "true"),
        ("include_snapshot_text", "false"),
        ("response_char_limit", "0"),
    ]
    http = rest.post(spec.rest_path, json=PAYLOADS[key], params=params)
    mcp = asyncio.run(
        native(
            spec,
            PAYLOADS[key],
            fields=fields,
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
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
    assert http.status_code == 200 and not mcp.is_error and code == 0
    assert business(http.json()) == business(mcp.structured_content) == business(cli)
    assert all(FIELD in t for t in cli["liureng"]["transmission_relations"]["trines"])


@pytest.mark.parametrize("fault", ["delete", "forge"])
@pytest.mark.parametrize("project", [False, True])
def test_full_result_cannot_hide_missing_or_forged_new_evidence_before_projection(
    fault, project, rest, monkeypatch, tmp_path, capsys
):
    spec = SPECS["liureng_gods"]
    fn, args, kwargs = spec.bind(
        spec.request_model.model_validate(PAYLOADS["liureng_gods"])
    )
    valid = fn(*args, **kwargs)
    execution.validate_output(spec, valid)
    bad = copy.deepcopy(valid)
    trines = bad["liureng"]["transmission_relations"]["trines"]
    if fault == "delete":
        for t in trines:
            t.pop(FIELD)
    else:
        t = trines[0]
        t[FIELD] = nominal_seasonal_evidence(
            bad["liureng"]["seasonal_evidence"]["month_branch"], t["nominal_element"]
        )
        t["branches_complete"] = False
    with pytest.raises(execution.OutputContractError):
        execution.validate_output(spec, bad)
    original = execution.execute_spec

    def broken(actual, request):
        if actual.key == spec.key:
            actual = replace(
                actual, bind=lambda _: (lambda: copy.deepcopy(bad), (), {})
            )
        return original(actual, request)

    monkeypatch.setattr(execution, "execute_spec", broken)
    fields = ["analysis_type"] if project else None
    params = {"response_char_limit": 0}
    flags = ["--response-char-limit", "0"]
    options = {}
    if fields:
        params.update(fields="analysis_type", strict_fields="true")
        flags += ["--fields", "analysis_type", "--strict-fields", "true"]
        options.update(fields=fields, strict_fields=True)
    http = rest.post(spec.rest_path, json=PAYLOADS["liureng_gods"], params=params)
    mcp = asyncio.run(native(spec, PAYLOADS["liureng_gods"], **options))
    code, cli = call_cli(spec, PAYLOADS["liureng_gods"], tmp_path, capsys, flags=flags)
    assert (
        http.status_code == 500
        and mcp.is_error
        and code == 1
        and cli["error_code"] == "internal_error"
    )

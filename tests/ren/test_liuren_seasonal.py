"""Literal seasonal states, conditional emptiness and same-board protocols."""

import asyncio
import copy
import json
import shutil
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

import fatebridge.application.execution as execution
from fatebridge.application.examples import evidence_views
from fatebridge.core.metaphysics.liureng import build_liureng_board
from fatebridge.core.metaphysics.liureng_seasonal import seasonal_evidence
from fatebridge.core.output_chinese import Liuren
from fatebridge.core.output_liuren_seasonal import (
    LiurenSeasonalEvidence,
    LiurenSeasonalRow,
    require_complete_seasonal,
)
from scripts.ren.audit_liuren_seasonal import BRANCHES, CORPUS, reference, seed_for
from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
    rest,
)

ROOT = Path(__file__).resolve().parents[2]
REF = reference()
GODS = list(REF["literal_god_elements"])
PAYLOADS = json.loads((ROOT / "tests/fixtures/ren_anchors_v1/faults.json").read_text())[
    "payloads"
]


@pytest.fixture(autouse=True)
def native_solar(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)


def sample(day="甲子", month="午", sky="戌", god="白虎"):
    rotation = (GODS.index(god) - BRANCHES.index(sky)) % 12
    return seasonal_evidence(
        day_ganzhi=day,
        month_branch=month,
        sky_by_earth=dict(zip(BRANCHES, BRANCHES)),
        god_by_sky={b: GODS[(i + rotation) % 12] for i, b in enumerate(BRANCHES)},
    )


def board(month="午", **kwargs):
    return build_liureng_board(
        seed_for("甲子", month), month_general_override="丑", **kwargs
    )


@pytest.mark.parametrize("case", REF["synthetic_cases"])
def test_predeclared_synthetic_conditions_keep_branch_and_god_separate(case):
    r = sample(case["day"], case["month"], case["sky"], case["god"])
    LiurenSeasonalEvidence.model_validate(r)
    row = next(v for v in r["rows"] if v["sky_branch"] == case["sky"])
    assert (row["sky_seasonal_power"], row["sky_empty_seasonal_condition"]) == (
        case["expected_sky_power"],
        case["expected_raw_condition"],
    )
    assert row["effective_empty_class"] is r["effective_empty_classification"] is None
    assert (
        r["effective_true_half_adjudicated"]
        is r["complete_classical_conformance"]
        is False
    )


def test_all25_literal_phase_cells_and12_god_phases_are_frozen_separately_from_month_profile():
    assert REF["literal_phase_cells"] == 25 and len(REF["literal_god_elements"]) == 12
    for month in ["寅", "巳", "申", "亥", "辰"]:
        got = sample(month=month)
        assert (
            got["phase_powers"]
            == REF["literal_phase_table"][REF["declared_month_partition"][month]]
        )
        for row in got["rows"]:
            assert row["god_element"] == REF["literal_god_elements"][row["god"]]
    assert "整月" in got["month_partition_basis"] and "十八" in got["scope"]
    assert "壬申例未载月令" in got["scope"]


@pytest.mark.parametrize("fault", ["data", "manifest", "extra", "missing"])
def test_frozen_source_inventory_cannot_be_refrozen_or_pruned(fault, tmp_path):
    p = tmp_path / "corpus"
    shutil.copytree(CORPUS, p)
    if fault == "data":
        with (p / "reference.json").open("ab") as f:
            f.write(b" ")
    elif fault == "manifest":
        (p / "freeze.json").write_text("{}")
    elif fault == "extra":
        (p / "extra").write_text("")
    else:
        (p / "source-pages.pdf").unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        reference(p)


def test_day_stem_soil_does_not_borrow_its_fire_twelve_life_stage_element():
    b = build_liureng_board(seed_for("戊辰", "寅"), month_general_override="丑")
    e = b["seasonal_evidence"]
    assert e["day_stem_element"] == "土" and e["day_stem_seasonal_power"] == "死"
    assert e["phase_powers"]["火"] == "相"


def test_month_general_and_guiren_choices_do_not_replace_month_building_or_branch_phase():
    a = board("卯", guiren_profile="liuren_common_v1", is_diurnal_override=True)
    b = board("卯", guiren_profile="tanyuan_xieji_v1", is_diurnal_override=True)
    assert (
        a["seasonal_evidence"]["month_branch"] == "卯"
        and a["month_general"]["branch"] == "丑"
    )
    arows = {r["sky_branch"]: r for r in a["seasonal_evidence"]["rows"]}
    brows = {r["sky_branch"]: r for r in b["seasonal_evidence"]["rows"]}
    assert all(
        arows[k]["sky_seasonal_power"] == brows[k]["sky_seasonal_power"]
        for k in BRANCHES
    )
    assert any(
        arows[k]["god_seasonal_power"] != brows[k]["god_seasonal_power"]
        for k in BRANCHES
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("sky_element", "木"),
        ("god_element", "水"),
        ("earth_element", "火"),
        ("sky_empty_seasonal_condition", "真空条件"),
        ("effective_empty_class", "半空"),
        ("sky_xun_kong", 1),
    ],
)
def test_row_own_facts_and_unknown_effective_class_cannot_be_forged(field, value):
    r = next(r for r in sample()["rows"] if r["sky_branch"] == "戌")
    r[field] = value
    with pytest.raises(ValidationError):
        LiurenSeasonalRow.model_validate(r)


@pytest.mark.parametrize(
    "fault",
    [
        "day",
        "month",
        "partition",
        "table",
        "day_power",
        "row_power",
        "true_list",
        "half_list",
        "duplicate",
        "reverse",
        "true",
        "zero",
        "full",
        "scope",
    ],
)
def test_full_same_context_evidence_rejects_internal_contradictions(fault):
    e = sample()
    if fault == "day":
        e["day_ganzhi"] = "甲丑"
    elif fault == "month":
        e["month_branch"] = "卯"
    elif fault == "partition":
        e["season_partition"] = "冬"
    elif fault == "table":
        e["phase_powers"]["土"] = "死"
    elif fault == "day_power":
        e["day_stem_seasonal_power"] = "旺"
    elif fault == "row_power":
        e["rows"][0]["god_seasonal_power"] = "死"
    elif fault == "true_list":
        e["raw_true_condition_branches"] = []
    elif fault == "half_list":
        e["raw_half_condition_branches"] = []
    elif fault == "duplicate":
        e["rows"].append(copy.deepcopy(e["rows"][0]))
    elif fault == "reverse":
        e["rows"].reverse()
    elif fault == "true":
        e["effective_true_half_adjudicated"] = True
    elif fault == "zero":
        e["complete_classical_conformance"] = 0
    elif fault == "full":
        e["complete_classical_conformance"] = True
    else:
        e["scope"] = "已认证全书"
    with pytest.raises(ValidationError):
        LiurenSeasonalEvidence.model_validate(e)


def test_sparse_context_validates_copresent_table_without_inventing_missing_inputs():
    LiurenSeasonalEvidence.model_validate(dict(phase_powers={"土": "相"}))
    with pytest.raises(ValidationError):
        LiurenSeasonalEvidence.model_validate(
            dict(month_branch="午", phase_powers={"土": "死"})
        )
    e = sample()
    partial = dict(phase_powers=e["phase_powers"], rows=e["rows"])
    LiurenSeasonalEvidence.model_validate(partial)
    partial["phase_powers"] = {"土": "死"}
    with pytest.raises(ValidationError):
        LiurenSeasonalEvidence.model_validate(partial)


@pytest.mark.parametrize(
    "fault",
    ["missing", "trace", "duplicate_trace", "forged_trace", "other_month", "effective"],
)
def test_full_guard_rejects_missing_trace_and_valid_other_month_before_projection(
    fault,
):
    b = board()
    trace = next(
        t for t in b["rule_trace"] if t["rule_id"] == "liuren.seasonal_conditions"
    )
    if fault == "missing":
        b.pop("seasonal_evidence")
    elif fault == "trace":
        b["rule_trace"].remove(trace)
    elif fault == "duplicate_trace":
        b["rule_trace"].append(copy.deepcopy(trace))
    elif fault == "forged_trace":
        trace["result"]["month_branch"] = "卯"
    elif fault == "other_month":
        b["seasonal_evidence"] = board("卯")["seasonal_evidence"]
    else:
        b["seasonal_evidence"]["effective_empty_classification"] = "真空"
    with pytest.raises(ValueError):
        require_complete_seasonal(b)


@pytest.mark.parametrize("key", ["liureng_gods", "liureng_runyear", "jinkou"])
def test_published_actual_evidence_view_agrees_in_rest_native_mcp_and_cli(
    key, rest, tmp_path, capsys
):
    s = SPECS[key]
    p = copy.deepcopy(PAYLOADS[key])
    name = "liuren_seasonal_evidence" if key == "jinkou" else "seasonal_evidence"
    fields = evidence_views(s)[name]["fields"]
    opts = dict(fields=fields, strict_fields=True, include_snapshot_text=False)
    h = rest.post(
        s.rest_path,
        json=p,
        params=[
            *[("fields", f) for f in fields],
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
        ],
    )
    code, c = call_cli(
        s,
        p,
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
    m = asyncio.run(native(s, p, **opts))
    assert h.status_code == 200 and code == 0 and not m.is_error
    assert business(h.json()) == business(c) == business(m.structured_content)
    e = h.json()["liureng"]["seasonal_evidence"]
    assert e["month_branch"] == h.json()["four_pillars"]["month"]["branch"]
    assert (
        e["effective_empty_classification"] is None
        and not e["effective_true_half_adjudicated"]
    )


def test_snapshot_lines_keep_branch_god_earth_and_effective_scope_separate():
    s = SPECS["liureng_gods"]
    p = {**PAYLOADS["liureng_gods"], "selected_sections": ["季节五态与支神本空条件"]}
    fn, args, kw = s.bind(s.request_model.model_validate(p))
    r = fn(*args, **kw)
    text = r["snapshot_text"]
    e = r["liureng"]["seasonal_evidence"]
    assert e["month_partition_basis"] in text and e["scope"] in text
    for row in e["rows"]:
        line = next(
            v for v in text.splitlines() if v.startswith("地盘" + row["earth_branch"])
        )
        assert (
            f"天盘支神{row['sky_branch']}{row['sky_element']}{row['sky_seasonal_power']}"
            in line
        )
        assert (
            f"天将{row['god']}{row['god_element']}{row['god_seasonal_power']}" in line
        )
        assert (
            row["sky_empty_seasonal_condition"] or "未入本空，不套真半"
        ) in line and "未裁定" in line


@pytest.mark.parametrize("project", [False, True])
def test_actual_three_protocols_reject_deleted_evidence_even_when_fields_hide_it(
    project, rest, monkeypatch, tmp_path, capsys
):
    s = SPECS["liureng_gods"]
    p = PAYLOADS["liureng_gods"]
    fn, args, kw = s.bind(s.request_model.model_validate(p))
    bad = fn(*args, **kw)
    bad["liureng"].pop("seasonal_evidence")
    original = execution.execute_spec

    def broken(spec, request):
        if spec.key == s.key:
            spec = replace(spec, bind=lambda _: (lambda: copy.deepcopy(bad), (), {}))
        return original(spec, request)

    monkeypatch.setattr(execution, "execute_spec", broken)
    params = [("response_char_limit", "0")]
    flags = ["--response-char-limit", "0"]
    opts = {}
    if project:
        params += [("fields", "four_pillars"), ("strict_fields", "true")]
        flags += ["--fields", "four_pillars", "--strict-fields", "true"]
        opts = dict(fields=["four_pillars"], strict_fields=True)
    h = rest.post(s.rest_path, json=p, params=params)
    m = asyncio.run(native(s, p, **opts))
    code, c = call_cli(s, p, tmp_path, capsys, flags=flags)
    assert h.status_code == 500 and m.is_error and code != 0
    assert all(
        v["error_code"] == "internal_error" for v in [h.json(), m.structured_content, c]
    )


@pytest.mark.parametrize("key", ["liureng_gods", "jinkou"])
@pytest.mark.parametrize("side", ["floor", "next_second"])
def test_frozen_qingming_second_boundary_reaches_seasonal_table_across_protocols(
    key, side, monkeypatch, rest, tmp_path, capsys
):
    from scripts.ren.audit_ren_seconds import reference as seconds_reference

    r = next(
        r for r in seconds_reference()["data"]["rows"] if r["id"] == f"2026-清明-{side}"
    )
    instant = datetime.fromisoformat(r["civil_utc"])
    ephe = tmp_path / "empty"
    ephe.mkdir()
    monkeypatch.setenv("SE_EPHE_PATH", str(ephe))
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    p = dict(
        analysis_year=instant.year,
        analysis_month=instant.month,
        analysis_day=instant.day,
        analysis_hour=instant.hour,
        analysis_minute=instant.minute,
        analysis_second=instant.second,
        analysis_timezone="UTC",
        use_true_solar_time=False,
        is_diurnal=True,
    )
    if key == "jinkou":
        p["di_fen"] = "酉"
    s = SPECS[key]
    view = "liuren_seasonal_evidence" if key == "jinkou" else "seasonal_evidence"
    fields = evidence_views(s)[view]["fields"]
    opts = dict(fields=fields, strict_fields=True, include_snapshot_text=False)
    h = rest.post(
        s.rest_path,
        json=p,
        params=[
            *[("fields", f) for f in fields],
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
        ],
    )
    code, c = call_cli(
        s,
        p,
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
    m = asyncio.run(native(s, p, **opts))
    assert h.status_code == 200 and code == 0 and not m.is_error
    assert business(h.json()) == business(c) == business(m.structured_content)
    e = h.json()["liureng"]["seasonal_evidence"]
    month = r["expected"]["month"][1]
    assert (
        e["month_branch"] == month
        and h.json()["four_pillars"]["month"]["branch"] == month
    )
    assert (
        e["phase_powers"]
        == REF["literal_phase_table"][REF["declared_month_partition"][month]]
    )
    assert (e["season_partition"], e["phase_powers"]["木"]) == (
        ("春", "旺") if side == "floor" else ("季月", "囚")
    )

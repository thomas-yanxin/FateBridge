"""Conditional temporal splits retain unresolved calendar and encounter semantics."""

import asyncio
import hashlib
import json
import shutil
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from pydantic import ValidationError

import fatebridge.api as api
import scripts.ziwei.audit_ziwei_subperiods as audit
from fatebridge.application.examples import evidence_views
from fatebridge.application.execution import execute_tool
from fatebridge.cli import run
from fatebridge.core.metaphysics.ziwei import build_ziwei_chart, build_ziwei_horoscope
from fatebridge.core.output_chinese import (
    ZiweiDecadeHalf,
    ZiweiLimitStarGroup,
    ZiweiLimitSubperiods,
    ZiweiSmallLimitHalf,
)
from fatebridge.core.ziwei_subperiods import decade_half, limit_subperiod_evidence
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from scripts.ziwei.audit_ziwei_limits import _seed
from scripts.ziwei.ziwei_conditional_inputs import synthetic_birth_clock
from tests.fixtures.mcp_receipt import assert_same_run_receipt, verified_inline_business


def test_original_text_and_conditional_coverage_are_separate():
    r = audit.audit_subperiods()
    assert not r["differences"]
    assert (r["textual_group_definitions"], r["textual_star_entities"]) == (22, 23)
    assert r["dual_group_star_entities"] == 6
    assert r["frozen_conditional_boundary_vectors"] == 30
    assert r["original_preimplementation_policy_chart_cases"] == 1000
    assert r["postimplementation_coverage_chart_cases"] == 1960
    assert r["whole_chart_conditional_age_cases"] == 2960
    assert r["actual_star_joins_checked"] == 68080
    assert r["observed_bureau_numbers"] == [2, 3, 4, 5, 6]
    assert r["source_transcription_method"] == "single_assistant_visual_reading"
    assert r["independent_human_reviewers"] == r["independent_model_reviewers"] == 0
    assert not r["independent_calendar_or_placement_oracle"]
    assert r["xiaoxian_calendar_half_years_selected"] == 0
    assert r["full_traditional_judgments_evaluated"] == 0
    assert r["live_model_blind_evaluation"] == "not_run"


def test_wrong_phase_in_real_result_is_detected(monkeypatch):
    original = audit.build_ziwei_horoscope

    def wrong(*a, **kw):
        h = original(*a, **kw)
        r = h["ming_limit_subperiods"]["daxian"]
        if r["half"] == "upper_five_years":
            r["half"] = "lower_five_years"
        return h

    monkeypatch.setattr(audit, "build_ziwei_horoscope", wrong)
    result = audit.audit_subperiods()
    assert len(result["differences"]) == 1440


def test_original_image_and_definition_sources_are_required(tmp_path):
    for name in ["naj_ming_subperiods_v1", "naj_ming_symbolism_v1"]:
        shutil.copytree(audit.FIXTURES / name, tmp_path / name)
    target = tmp_path / "naj_ming_subperiods_v1/frame_0035.jpg"
    original = target.read_bytes()
    target.write_bytes(b"changed")
    with pytest.raises(ValueError, match="subperiod source checksum"):
        audit.audit_subperiods(tmp_path)
    target.write_bytes(original)
    (tmp_path / "naj_ming_symbolism_v1/frame_0083.jpg").write_bytes(b"changed")
    with pytest.raises(ValueError, match="group definition source checksum"):
        audit.audit_subperiods(tmp_path)


@pytest.mark.parametrize("first", [2, 3, 4, 5, 6])
def test_split_uses_selected_start_not_age_last_digit(first):
    for period in range(12):
        lo = first + 10 * period
        palace = dict(ganzhi="甲子", daxian=f"{lo}~{lo + 9}")
        for offset in range(10):
            r = decade_half([palace], dict(status="computed", branch="子"), lo + offset)
            assert r["year_ordinal_in_decade"] == offset + 1
            assert r["half"] == (
                "upper_five_years" if offset < 5 else "lower_five_years"
            )
            assert not r["calendar_boundaries_classically_verified"]


@pytest.mark.parametrize(
    "text,age", [(None, 7), ("2~12", 7), ("2~11", 12), ("bad", 7), ("0~9", 7)]
)
def test_inconsistent_range_stays_unknown(text, age):
    r = decade_half(
        [dict(ganzhi="甲子", daxian=text)], dict(status="computed", branch="子"), age
    )
    assert r["status"] == "unresolved" and r["half"] is None


def test_missing_or_duplicate_branch_cannot_select_half():
    palace = dict(ganzhi="甲子", daxian="2~11")
    for palaces in [[], [palace, palace]]:
        assert (
            decade_half(palaces, dict(status="computed", branch="子"), 7)["half"]
            is None
        )
    r = decade_half([palace], dict(status="not_started", branch=None), 1)
    assert r["status"] == "not_started" and r["year_ordinal_in_decade"] is None


def _chart_and_horoscope():
    c = build_ziwei_chart(_seed(1984, 11), "男")
    h = build_ziwei_horoscope(
        birth_seed=synthetic_birth_clock(int((c)["lunar_date"]["year"])),
        chart=c,
        gender="男",
        target_seed=_seed(1990),
    )
    return c, h


def test_dual_labels_unclassified_stars_and_malefics_are_not_filtered():
    _, h = _chart_and_horoscope()
    e = h["ming_limit_subperiods"]
    rows = {r["star"]: r for r in e["natal_star_groups"]}
    assert {n for n, r in rows.items() if r["textual_group"] == "both"} == {
        "紫微",
        "太阳",
        "太阴",
        "文昌",
        "左辅",
        "右弼",
    }
    assert all(
        rows[n]["textual_daxian_half"] is None
        for n in ["紫微", "太阳", "太阴", "文昌", "左辅", "右弼"]
    )
    assert all(rows[n]["textual_group"] == "north" for n in ["擎羊", "陀罗"])
    assert all(rows[n]["textual_group"] == "south" for n in ["火星", "铃星"])
    assert {"天魁", "天钺", "天马", "地空", "地劫"} <= set(
        e["unclassified_natal_stars"]
    )
    assert all(r["selected_as_relevant_star"] is None for r in rows.values())
    assert e["xiaoxian"]["half"] is None and e["full_traditional_judgment"] is None


def test_missing_duplicate_occurrences_and_mutation_are_retained():
    c, h = _chart_and_horoscope()
    before = deepcopy((c, h))
    e = limit_subperiod_evidence(
        c["palaces"], h["scopes"], nominal_age=h["nominal_age"]
    )
    e["natal_star_groups"][0]["actual_occurrences"][0]["natal_branch"] = "假"
    e["limitations"].clear()
    assert (c, h) == before
    p = h["scopes"][1]["palace_map"]
    for palace in p:
        palace["natal_stars_detail"] = [
            s for s in palace["natal_stars_detail"] if s["name"] != "紫微"
        ]
    p[0]["natal_stars_detail"] += [dict(name="太阳", mutagen=None)]
    e = limit_subperiod_evidence(
        c["palaces"], h["scopes"], nominal_age=h["nominal_age"]
    )
    rows = {r["star"]: r for r in e["natal_star_groups"]}
    assert len(rows["紫微"]["actual_occurrences"]) == 0
    assert len(rows["太阳"]["actual_occurrences"]) == 2
    assert rows["太阳"]["selected_as_relevant_star"] is None


@pytest.mark.parametrize(
    "model,payload",
    [
        (ZiweiDecadeHalf, dict(calendar_boundaries_classically_verified=True)),
        (ZiweiSmallLimitHalf, dict(half="upper_half_year")),
        (ZiweiSmallLimitHalf, dict(half_start="2026-07-01")),
        (ZiweiLimitStarGroup, dict(selected_as_relevant_star=True)),
        (ZiweiLimitSubperiods, dict(full_traditional_judgment=True)),
        (ZiweiLimitSubperiods, dict(source_outcome_claim_adopted=True)),
    ],
)
def test_public_models_reject_uncomputed_claims(model, payload):
    with pytest.raises(ValidationError):
        model.model_validate(payload)


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
@pytest.mark.parametrize("detail", [False, True])
def test_limit_views_match_rest_native_mcp_cli_and_same_run_pages(
    profile, detail, monkeypatch, capsys
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    spec = next(s for s in CATALOG if s.key == "ziwei_horoscope")
    inputs = dict(
        birth_year=1984,
        birth_month=2,
        birth_day=2,
        birth_hour=2,
        gender="男",
        birth_timezone="Asia/Shanghai",
        use_true_solar_time=False,
        rule_profile=profile,
        sihua_source="naj_ming_v1",
        target_year=1990,
        target_month=10,
        target_day=22,
        target_hour=12,
    )
    fields = evidence_views(spec)[
        "limit_subperiod_details" if detail else "limit_subperiods"
    ]["fields"]
    opts = dict(
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        as_of="2026-10-22T12:00:00+08:00",
    )
    rest = TestClient(api.app).post(
        spec.rest_path,
        json=inputs,
        params=[
            ("as_of", opts["as_of"]),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            *[("fields", f) for f in fields],
        ],
    )
    assert rest.status_code == 200, rest.text

    async def call():
        async with Client(create_mcp_app(families="metaphysics")) as client:
            r = await client.call_tool("ziwei_horoscope", {**inputs, **opts})
            assert not r.is_error
            p = r.structured_content
            assert len(json.dumps(p, ensure_ascii=False, separators=(",", ":"))) <= 8192
            if not detail:
                return await verified_inline_business(client, p)
            if "result_delivery" not in p:
                return p
            ref = p["result_delivery"]
            uri, raw = ref["first_page_uri"], ""
            while uri:
                page = json.loads((await client.read_resource(uri))[0].text)
                raw += page["text"]
                uri = page["next_uri"]
            assert hashlib.sha256(raw.encode()).hexdigest() == ref["sha256"]
            full = json.loads(raw)
            assert_same_run_receipt(
                p["run_metadata"],
                full["run_metadata"],
                deferred_fields=ref["deferred_fields"],
            )
            return full

    native = asyncio.run(call())
    args = ["ziwei_horoscope"]
    for k, v in inputs.items():
        args += ["--" + k.replace("_", "-"), str(v)]
    args += [
        "--as-of",
        opts["as_of"],
        "--strict-fields",
        "--no-include-snapshot-text",
        "--fields",
        *fields,
    ]
    capsys.readouterr()
    assert run(args) == 0
    cli = json.loads(capsys.readouterr().out)
    bodies = [
        {k: v for k, v in p.items() if k not in ("run_metadata", "result_delivery")}
        for p in [rest.json(), native, cli]
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    e = bodies[0]["ziwei_horoscope"]["ming_limit_subperiods"]
    assert e["daxian"]["half"] == "lower_five_years"
    assert e["xiaoxian"]["half"] is None and e["full_traditional_judgment"] is None
    assert ("natal_star_groups" in e) is detail
    if detail:
        assert len(e["natal_star_groups"]) == 23


def test_same_run_claim_verifier_preserves_unresolved_half_year():
    spec = next(s for s in CATALOG if s.key == "ziwei_horoscope")
    request = spec.request_model.model_validate(
        dict(
            birth_year=1984,
            birth_month=2,
            birth_day=2,
            birth_hour=2,
            gender="男",
            birth_timezone="Asia/Shanghai",
            use_true_solar_time=False,
            target_year=1990,
            target_month=10,
            target_day=22,
            target_hour=12,
        )
    )
    p = execute_tool(spec, request)
    m = p["run_metadata"]

    def claim(value):
        return CalculationClaim(
            path="ziwei_horoscope.ming_limit_subperiods.xiaoxian.half",
            value=value,
            run_id=m["run_id"],
            business_output_sha256=m["business_output_sha256"],
        )

    assert (
        verify_calculation_claims(p, [claim(None)])["status"]
        == "verified_structured_facts"
    )
    assert (
        verify_calculation_claims(p, [claim("lower_half_year")])["status"] == "rejected"
    )

"""A not-yet-started decade cannot acquire a childhood palace or transformations."""

import asyncio
import hashlib
import json
import shutil
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
import scripts.ziwei.audit_ziwei_activation as audit
from fatebridge.application.examples import evidence_views
from fatebridge.application.execution import execute_tool
from fatebridge.cli import run
from fatebridge.core.metaphysics.ziwei import _palace_for_nominal_age, build_ziwei_chart
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.metaphysics import calculate_ziwei_horoscope
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.birth_input import create_person_info
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from scripts.ziwei.audit_ziwei_limits import _seed
from tests.fixtures.mcp_receipt import assert_same_run_receipt, verified_inline_business

BIRTH = dict(
    birth_year=1984,
    birth_month=2,
    birth_day=2,
    birth_hour=2,
    gender="男",
    birth_timezone="Asia/Shanghai",
    use_true_solar_time=False,
)


def test_conditional_activation_audit_preserves_denominators_and_uncertainties():
    r = audit.audit_activation()
    assert not r["mismatches"]
    assert r["conditional_chart_inputs"] == 20
    assert r["conditional_age_cases_checked"] == 100
    assert (r["pre_decade_cases"], r["started_decade_cases"]) == (60, 40)
    assert r["given_bureaus"] == [2, 3, 4, 5, 6]
    assert r["new_independent_sources"] == 0
    assert not r["independent_calendar_or_placement_oracle"]
    assert not r["historical_age_boundary_certified"]
    assert not r["historical_unique_policy_certified"]
    assert not r["whole_book_acceptance_passed"]


def test_reintroduced_four_transformations_fail_all_pre_decade_cases(monkeypatch):
    original = audit.build_ziwei_horoscope

    def broken(**kw):
        h = original(**kw)
        if h["scopes"][0]["status"] == "not_started":
            h["scopes"][0]["mutagen"] = {"化禄": "太阴"}
            h["scopes"][0]["palace_map"] = [{"branch": "丑"}]
        return h

    monkeypatch.setattr(audit, "build_ziwei_horoscope", broken)
    r = audit.audit_activation()
    assert len(r["mismatches"]) == 60
    assert all("null_mutagen" in row["failed"] for row in r["mismatches"])


def _copy_policy_sources(tmp_path):
    fixtures = tmp_path / "ziwei_independent"
    fixtures.mkdir()
    for name in ("naj_ming_limits_v1", "naj_ming_childhood_v1"):
        shutil.copytree(audit.FIXTURES / name, fixtures / name)
    shutil.copy(audit.FIXTURES / "pre_decade_policy_manifest.json", fixtures)
    shutil.copy(audit.FIXTURES.parent / "ziwei_horoscope_reference.json", tmp_path)
    return fixtures


def test_activation_audit_requires_previously_frozen_source_page(tmp_path):
    fixtures = _copy_policy_sources(tmp_path)
    (fixtures / "naj_ming_childhood_v1/frame_0080.jpg").write_bytes(b"changed")
    with pytest.raises(ValueError, match="activation source checksum mismatch"):
        audit.audit_activation(fixtures)


def test_software_reference_cannot_be_rewritten_to_hide_declared_differences(tmp_path):
    fixtures = _copy_policy_sources(tmp_path)
    p = tmp_path / "ziwei_horoscope_reference.json"
    r = json.loads(p.read_text())
    r["childhood_one"]["scopes"]["大限"] = {"branch": None, "mutagen": None}
    p.write_text(json.dumps(r))
    with pytest.raises(ValueError, match="software reference checksum mismatch"):
        audit.audit_activation(fixtures)


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
def test_formal_lookup_rejects_both_pre_start_and_out_of_range_ages(profile):
    chart = build_ziwei_chart(_seed(1984, 1), "男", rule_profile=profile)
    assert chart["wuxing_ju"]["number"] == 6
    before = deepcopy(chart)
    with pytest.raises(ValueError, match="尚未起正式大限"):
        _palace_for_nominal_age(chart["palaces"], 5)
    with pytest.raises(ValueError, match="支持范围"):
        _palace_for_nominal_age(chart["palaces"], 126)
    assert _palace_for_nominal_age(chart["palaces"], 6)["daxian"] == "6~15"
    assert _palace_for_nominal_age(chart["palaces"], 125)["daxian"] == "116~125"
    assert chart == before


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
def test_actual_cny_crossing_does_not_generate_a_pre_start_decade(profile):
    results = [
        calculate_ziwei_horoscope(
            create_person_info(**BIRTH),
            rule_profile=profile,
            target_year=1985,
            target_month=2,
            target_day=day,
            target_hour=12,
        )
        for day in (19, 20)
    ]
    before, started = (r["ziwei_horoscope"] for r in results)
    d = before["scopes"][0]
    assert before["nominal_age"] == 1 and d["first_age"] == 2
    assert d["status"] == "not_started" and d["mutagen"] is None
    assert d["natal_palace_name"] is None and not d["palace_map"]
    assert before["childhood_limit"]["natal_palace_name"] == "命宫"
    assert before["source_comparison"]["daxian"]["actual_branch"] is None
    assert (
        before["source_comparison"]["daxian"][
            "matches_literal_reading_given_bureau_age"
        ]
        is None
    )
    assert (
        "尚未起正式大限（2岁起）；本层宫位、宫干和四化未生成"
        in results[0]["snapshot_text"]
    )
    text = results[0]["snapshot_text"]
    assert "当前为童限取宫" not in text and "None" not in text
    assert started["nominal_age"] == 2
    active = started["scopes"][0]
    assert active["status"] == "computed"
    assert active["natal_palace_name"] == (
        "命宫" if profile == "iztro_2_5_8" else "父母宫"
    )
    assert len(active["mutagen"]) == 4
    assert len(active["mutagen_natal_links"]) == 4
    assert len(active["palace_map"]) == 12
    assert len(before["scopes"]) == len(started["scopes"]) == 6


def test_same_run_null_facts_reject_invented_decade_palace_and_transformations():
    spec = next(s for s in CATALOG if s.key == "ziwei_horoscope")
    request = spec.request_model.model_validate(
        {
            **BIRTH,
            "target_year": 1985,
            "target_month": 2,
            "target_day": 19,
            "target_hour": 12,
        }
    )
    payload = execute_tool(spec, request)
    receipt = payload["run_metadata"]

    def claim(path, value):
        return CalculationClaim(
            path="ziwei_horoscope.scopes.0." + path,
            value=value,
            run_id=receipt["run_id"],
            business_output_sha256=receipt["business_output_sha256"],
        )

    valid = [
        claim("status", "not_started"),
        claim("branch", None),
        claim("mutagen", None),
    ]
    assert (
        verify_calculation_claims(payload, valid)["status"]
        == "verified_structured_facts"
    )
    for c in [
        claim("branch", "丑"),
        claim("mutagen", {}),
        claim("status", "computed"),
        claim("natal_palace_name", "命宫"),
    ]:
        assert verify_calculation_claims(payload, [c])["status"] == "rejected"


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
@pytest.mark.parametrize("day", [19, 20])
@pytest.mark.parametrize("view", ["decade_activation", "complete_scope_records"])
def test_availability_and_nulls_survive_three_surfaces_and_same_run_pages(
    profile, day, view, monkeypatch, capsys
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    spec = next(s for s in CATALOG if s.key == "ziwei_horoscope")
    fields = (
        evidence_views(spec)[view]["fields"]
        if view == "decade_activation"
        else ["ziwei_horoscope.scopes", "ziwei_horoscope.childhood_limit"]
    )
    inputs = {
        **BIRTH,
        "rule_profile": profile,
        "target_year": 1985,
        "target_month": 2,
        "target_day": day,
        "target_hour": 12,
    }
    opts = dict(
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        as_of="2026-10-22T12:00:00+08:00",
    )
    rest = TestClient(api.app).post(
        "/api/cn/ziwei/horoscope",
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
            r = await client.call_tool(
                "ziwei_horoscope", {**inputs, **opts}, raise_on_error=False
            )
            assert not r.is_error, r.content
            p = r.structured_content
            if view == "decade_activation":
                return await verified_inline_business(client, p)
            assert len(json.dumps(p, ensure_ascii=False, separators=(",", ":"))) <= 8192
            if "result_delivery" not in p:
                return p
            ref = p["result_delivery"]
            text, uri = "", ref["first_page_uri"]
            while uri:
                page = json.loads((await client.read_resource(uri))[0].text)
                text += page["text"]
                uri = page["next_uri"]
            assert hashlib.sha256(text.encode()).hexdigest() == ref["sha256"]
            full = json.loads(text)
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
    h = bodies[0]["ziwei_horoscope"]
    if view == "decade_activation":
        d = h["source_comparison"]["daxian"]
        assert d["formal_scope_status"] == ("not_started" if day == 19 else "computed")
        assert d["before_formal_decade_start"] is (day == 19)
        assert d["actual_branch"] == (
            None if day == 19 else "丑" if profile == "iztro_2_5_8" else "寅"
        )
    else:
        d = h["scopes"][0]
        assert d["status"] == ("not_started" if day == 19 else "computed")
        if day == 19:
            assert d["mutagen"] is None and d["natal_palace_name"] is None
            assert d["palace_map"] == d["mutagen_natal_links"] == []
        assert len(h["scopes"]) == 6
        assert all(len(s["mutagen_natal_links"]) == 4 for s in h["scopes"][1:])

"""An incomplete classical clause cannot certify a software convention."""

import asyncio
import json
import shutil

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
import scripts.audit_ziwei_auxiliaries as audit
from fatebridge.application.examples import evidence_views
from fatebridge.cli import run
from fatebridge.core.metaphysics.ziwei import build_ziwei_chart
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from tests.fixtures.mcp_receipt import verified_inline_business


def test_auxiliary_corpus_keeps_unknowns_and_source_denominators_separate():
    result = audit.audit_auxiliaries()
    assert result["source_complete_directional_rule_groups"] == 8
    assert result["source_stars_with_complete_normal_month_rules"] == 16
    assert result["source_incomplete_fire_bell_pairs"] == 4
    assert result["normal_factor_domain_inputs"] == 382
    assert result["leap_boundary_inputs"] == 32
    assert result["derived_charts_checked_across_two_profiles"] == 828
    assert result["derived_comparable_placement_rows"] == 12864
    assert result["derived_unresolved_rows"] == 2040
    assert not result["mismatches"]
    for key in [
        "fire_bell_hour_expectations_verified",
        "monthly_leap_policy_verified",
        "all_auxiliary_stars_verified",
        "whole_book_acceptance_passed",
    ]:
        assert not result[key]


@pytest.mark.parametrize("hour", ["子", "丑", "午", "亥"])
def test_fire_bell_hour_matching_zero_offset_never_resolves_missing_instruction(hour):
    chart = build_ziwei_chart(audit._seed(1984, 1, 1, hour, False), "男")
    evidence = chart["auxiliary_placement_sources"]
    rows = {r["star"]: r for r in evidence["placements"]}
    for star in ["火星", "铃星"]:
        assert rows[star]["expected_branch"] is None
        assert rows[star]["matches_source_rule"] is None
        assert "even_for_zi_hour" in rows[star]["unresolved_reason"]
    assert evidence["methods"]["fire_bell"]["pair_as_written"] == "寅戌"
    assert (
        evidence["methods"]["fire_bell"]["hour_instruction_status"]
        == "not_stated_in_this_passage"
    )
    assert not evidence["compared_rules_applied"]


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
def test_ming_shen_leap_clause_cannot_certify_monthly_auxiliaries(profile):
    chart = build_ziwei_chart(
        audit._seed(1984, 4, 16, "亥", True), "女", rule_profile=profile
    )
    evidence = chart["auxiliary_placement_sources"]
    rows = {r["star"]: r for r in evidence["placements"]}
    for star in ["左辅", "右弼", "天刑", "天姚", "三台", "八座"]:
        assert rows[star]["expected_branch"] is None
        assert rows[star]["matches_source_rule"] is None
        assert (
            rows[star]["unresolved_reason"]
            == "leap_month_policy_not_stated_for_this_rule"
        )
    for star in [
        "文昌",
        "文曲",
        "地劫",
        "地空",
        "台辅",
        "封诰",
        "天哭",
        "天虚",
        "龙池",
        "凤阁",
    ]:
        assert rows[star]["matches_source_rule"]
    assert "天空" in evidence["unchecked_star_names"]
    assert "地空" not in evidence["unchecked_star_names"]
    assert len(evidence["unchecked_star_names"]) == 48


def test_source_mapping_results_cannot_mutate_the_cached_source():
    first = build_ziwei_chart(audit._seed(1984, 1, 1, "子", False), "男")
    first["auxiliary_placement_sources"]["source_name_mapping"][
        "source_天空"
    ] = "runtime_天空"
    second = build_ziwei_chart(audit._seed(1984, 1, 1, "子", False), "男")
    assert (
        second["auxiliary_placement_sources"]["source_name_mapping"]["source_天空"]
        == "runtime_地空"
    )


def test_wrong_tai_position_is_detected_without_redefining_source(monkeypatch):
    original = audit.build_ziwei_chart

    def corrupt(*args, **kwargs):
        chart = original(*args, **kwargs)
        for i, p in enumerate(chart["palaces"]):
            star = next((s for s in p["stars_detail"] if s["name"] == "三台"), None)
            if star:
                p["stars_detail"].remove(star)
                chart["palaces"][(i + 1) % 12]["stars_detail"].append(star)
                break
        return chart

    monkeypatch.setattr(audit, "build_ziwei_chart", corrupt)
    result = audit.audit_auxiliaries()
    assert result["status"] == "failed"
    assert any(r["case"].startswith("placement/") for r in result["mismatches"])
    assert any(r["case"].startswith("source_join/") for r in result["mismatches"])


def test_rewriting_runtime_auxiliary_table_does_not_rewrite_frozen_rules(
    tmp_path, monkeypatch
):
    name = "src/fatebridge/data/classical/ziwei-naj-ming-auxiliaries.json"
    data = json.loads((audit.ROOT / name).read_text())
    data["methods"][0]["rows"][0]["direction"] = "forward"
    target = tmp_path / name
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(data, ensure_ascii=False))
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    result = audit.audit_auxiliaries()
    assert any(
        r["case"] == "production_source_data/methods" for r in result["mismatches"]
    )


def test_source_audit_requires_actual_frozen_image_bytes(tmp_path):
    d = "naj_ming_auxiliaries_v1"
    shutil.copytree(audit.FIXTURES / d, tmp_path / d)
    p = tmp_path / d / "frame_0076.jpg"
    p.write_bytes(p.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="Ming auxiliary source checksum mismatch"):
        audit.audit_auxiliaries(tmp_path)


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
def test_auxiliary_source_view_matches_real_rest_mcp_cli_and_default_budget(
    monkeypatch, capsys, profile
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    spec = next(s for s in CATALOG if s.key == "ziwei_birth")
    fields = evidence_views(spec)["auxiliary_sources"]["fields"]
    inputs = dict(
        birth_year=2020,
        birth_month=5,
        birth_day=23,
        birth_hour=0,
        birth_minute=0,
        birth_timezone="Asia/Shanghai",
        gender="女",
        use_true_solar_time=False,
        rule_profile=profile,
    )
    options = dict(
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        as_of="2026-10-22T12:00:00+08:00",
    )
    rest = TestClient(api.app).post(
        "/api/cn/ziwei/birth",
        json=inputs,
        params=[
            *[("fields", f) for f in fields],
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("as_of", options["as_of"]),
        ],
    )
    assert rest.status_code == 200, rest.text

    async def call():
        async with Client(create_mcp_app(families="metaphysics")) as client:
            result = await client.call_tool("ziwei_birth", {**inputs, **options})
            await verified_inline_business(client, result.structured_content)
            return result

    native = asyncio.run(call())
    assert not native.is_error
    args = ["ziwei_birth"]
    for k, v in inputs.items():
        args.extend(["--" + k.replace("_", "-"), str(v)])
    args.extend(
        [
            "--fields",
            *fields,
            "--strict-fields",
            "--no-include-snapshot-text",
            "--as-of",
            options["as_of"],
        ]
    )
    capsys.readouterr()
    assert run(args) == 0
    cli = json.loads(capsys.readouterr().out)
    bodies = [
        {k: v for k, v in p.items() if k not in ("run_metadata", "result_delivery")}
        for p in (rest.json(), native.structured_content, cli)
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    e = bodies[0]["ziwei_birth"]["auxiliary_placement_sources"]
    assert len(e["placements"]) == 18
    assert sum(r["matches_source_rule"] is None for r in e["placements"]) == 8
    assert not e["whole_book_conformance_claimed"]

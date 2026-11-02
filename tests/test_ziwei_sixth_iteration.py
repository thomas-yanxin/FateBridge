"""Source-conditioned prerequisites stay separate from selected chart rules."""

import asyncio
import copy
import json
import shutil

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
import scripts.audit_ziwei_prerequisites as audit
from fatebridge.cli import run
from fatebridge.core.metaphysics.ziwei import build_ziwei_chart
from fatebridge.core.ziwei_sources import ziwei_prerequisite_source_evidence
from fatebridge.mcp_server import create_mcp_app


def evidence(chart):
    return chart["rule_trace"][2]["outputs"]["source_comparison"]


def test_ming_prerequisites_exhaust_small_normal_input_domain_without_inflating_sources():
    result = audit.audit_prerequisites()
    assert result["source_wuhu_anchor_rows"] == 5
    assert result["source_nayin_pair_rows"] == 30
    assert result["source_palace_names"] == 12
    assert result["derived_first_month_hour_pairs"] == 12
    assert result["normal_lunar_input_combinations"] == 1440
    assert result["leap_boundary_input_combinations"] == 16
    assert result["derived_charts_checked_across_two_profiles"] == 2912
    assert result["distinct_nayin_ganzhi_reached"] == 60
    assert not result["mismatches"]
    assert len(result["known_profile_differences"]) == 8
    assert not result["current_profiles_conform_to_this_prerequisite_subset"]
    assert not result["nayin_name_equality_tested"]
    assert result["unresolved_internal_nayin_name_glyphs"] == 1
    assert result["manual_reader_count"] == 1
    assert not result["whole_book_acceptance_passed"]


def test_printed_worked_example_and_absolute_yin_stem_wrap():
    chart = build_ziwei_chart(audit._seed(1984, 1, 1, "子", False), "男")
    result = evidence(chart)
    assert result["expected"] == {
        "effective_month": 1,
        "ming_branch": "寅",
        "shen_branch": "寅",
        "ming_ganzhi": "丙寅",
        "nayin_element": "火",
        "ju_number": 6,
    }
    assert result["matches_source_chain"]
    # After 亥 the stem continues through 丙子丁丑; it must not reset to
    # 甲子乙丑 simply because the ordinary earthly-branch array begins at 子.
    wrapped = build_ziwei_chart(audit._seed(1984, 1, 1, "寅", False), "女")
    assert wrapped["palaces"][0]["ganzhi"] == "丙子"
    assert evidence(wrapped)["matches_source_chain"]


def test_uncertain_internal_name_glyph_does_not_certify_literal_nayin_names():
    chart = build_ziwei_chart(audit._seed(1985, 3, 1, "子", False), "男")
    result = evidence(chart)
    assert result["expected"]["ming_ganzhi"] == "庚辰"
    assert result["expected"]["nayin_element"] == "金"
    assert result["expected"]["ju_number"] == 4
    assert result["matches_source_chain"]  # Scoped numerical check only.
    assert not result["source_nayin_name_reading_complete"]
    assert "字形待定" in result["source_nayin_name_reading"]
    assert result["nayin_name_comparison"] == "not_performed_element_and_bureau_only"
    assert not result["whole_book_conformance_claimed"]


def test_a_wrong_bureau_or_non_ming_palace_stem_cannot_inherit_a_matching_anchor():
    chart = build_ziwei_chart(audit._seed(1984, 1, 1, "子", False), "男")
    palaces = copy.deepcopy(chart["palaces"])
    palaces[1]["ganzhi"] = "己卯"  # Ming unchanged; another stem corrupted.
    result = ziwei_prerequisite_source_evidence(
        lunar_month=1,
        is_leap=False,
        effective_month=1,
        hour_branch="子",
        year_stem="甲",
        shen_branch="寅",
        palaces=palaces,
        nayin="爐中火",
        bureau=2,
    )
    assert result["checks"]["ming_ganzhi"]
    assert not result["checks"]["ju_number"]
    assert not result["checks"]["palace_stems_by_absolute_branch"]
    assert not result["matches_source_chain"]


def test_runtime_resource_edits_cannot_rewrite_frozen_nayin_readings(
    tmp_path, monkeypatch
):
    name = "src/fatebridge/data/classical/ziwei-naj-ming-prerequisites.json"
    data = json.loads((audit.ROOT / name).read_text())
    data["nayin"]["rows"][0]["element"] = "火"
    target = tmp_path / name
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(data, ensure_ascii=False))
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    result = audit.audit_prerequisites()
    assert any(
        d["case"] == "production_source_data/nayin" for d in result["mismatches"]
    )


def test_source_audit_needs_the_frozen_image_bytes(tmp_path):
    directory = "naj_ming_prerequisites_v1"
    source = audit.FIXTURES / directory
    destination = tmp_path / directory
    shutil.copytree(source, destination)
    path = destination / "nayin-bottom.jpg"
    path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="Ming prerequisite source checksum mismatch"):
        audit.audit_prerequisites(tmp_path)


@pytest.mark.parametrize(
    "profile,matches,branch",
    [
        ("iztro_2_5_8", False, "巳"),
        ("quanshu_v2_excerpt", True, "午"),
    ],
)
def test_leap_source_chain_and_active_chart_remain_distinct_on_rest_mcp_cli(
    monkeypatch,
    capsys,
    profile,
    matches,
    branch,
):
    # HKO 2020-05-23 = leap fourth month day 1. The source comparison concerns
    # the two explicit month policies after that independently checked input.
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
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
        fields=["ziwei_birth.rule_trace"],
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
        as_of="2026-10-22T12:00:00+08:00",
    )
    rest = TestClient(api.app).post(
        "/api/cn/ziwei/birth",
        json=inputs,
        params=[
            ("fields", "ziwei_birth.rule_trace"),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
            ("as_of", options["as_of"]),
        ],
    )
    assert rest.status_code == 200, rest.text

    async def call():
        async with Client(create_mcp_app(families="metaphysics")) as client:
            return await client.call_tool("ziwei_birth", {**inputs, **options})

    native = asyncio.run(call())
    assert not native.is_error
    args = ["ziwei_birth"]
    for key, value in inputs.items():
        args.extend(["--" + key.replace("_", "-"), str(value)])
    args.extend(
        [
            "--fields",
            "ziwei_birth.rule_trace",
            "--strict-fields",
            "--no-include-snapshot-text",
            "--response-char-limit",
            "0",
            "--as-of",
            options["as_of"],
        ]
    )
    capsys.readouterr()
    assert run(args) == 0
    cli = json.loads(capsys.readouterr().out)
    bodies = [
        {k: v for k, v in p.items() if k != "run_metadata"}
        for p in (rest.json(), native.structured_content, cli)
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    trace = bodies[0]["ziwei_birth"]["rule_trace"]
    result = trace[2]["outputs"]["source_comparison"]
    assert result["expected"]["effective_month"] == 5
    assert result["expected"]["ming_branch"] == "午"
    assert result["actual"]["ming_branch"] == branch
    assert result["matches_source_chain"] is matches
    assert not result["compared_rules_applied"]
    assert trace[3]["inputs"]["ju_number"] == result["actual"]["ju_number"]

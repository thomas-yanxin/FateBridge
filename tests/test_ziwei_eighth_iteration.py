"""Selected literal rules must change calculations, not just claim compliance."""

import asyncio
import json
import shutil

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
import scripts.audit_ziwei_limits as audit
from fatebridge.application.examples import evidence_views
from fatebridge.cli import run
from fatebridge.core.metaphysics.ziwei import build_ziwei_chart, build_ziwei_horoscope
from fatebridge.core.ziwei_rulesets import ziwei_ruleset_metadata
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from scripts.ziwei_conditional_inputs import synthetic_birth_clock
from tests.fixtures.mcp_receipt import verified_inline_business


def test_selected_limit_readings_have_independent_expected_sequences():
    r = audit.audit_limits()
    assert not r["mismatches"]
    assert r["daxian_assignments_checked"] == 5760
    assert r["daxian_boundary_horoscopes_checked"] == 1920
    assert r["bureau_coverage"] == [2, 3, 4, 5, 6]
    assert r["xiaoxian_age_ordinal_cases"] == 576
    assert r["ordinary_birth_month_doujun_cases"] == 3456
    assert r["fire_bell_selected_method_cases"] == 288
    assert r["daxian_literal_first_palace_comparison"] == {
        "iztro_2_5_8": {"matches": 0, "differences": 240},
        "quanshu_v2_excerpt": {"matches": 240, "differences": 0},
    }
    assert r["fire_bell_year_only_reading_comparison"] == {
        "iztro_2_5_8": {"matches": 12, "differences": 132},
        "quanshu_v2_excerpt": {"matches": 144, "differences": 0},
    }
    assert not r["unique_historical_fire_hour_interpretation_verified"]
    assert not r["age_calendar_convention_verified"]
    assert not r["whole_book_acceptance_passed"]


@pytest.mark.parametrize(
    "year,gender,first",
    [
        (1984, "男", "父母宫"),
        (1984, "女", "兄弟宫"),
        (1985, "男", "兄弟宫"),
        (1985, "女", "父母宫"),
    ],
)
def test_excerpt_first_decade_is_literal_neighbor_and_ming_remains_natal(
    year, gender, first
):
    chart = build_ziwei_chart(
        audit._seed(year), gender, rule_profile="quanshu_v2_excerpt"
    )
    assert chart["ruleset"]["version"] == "1.3.2"
    p = next(p for p in chart["palaces"] if p["daxian_period"] == 1)
    assert p["name"] == first
    assert chart["rule_trace"][-1]["outputs"]["initial_palace_name"] == first
    assert p["daxian"].startswith(str(chart["wuxing_ju"]["number"]) + "~")
    assert (
        next(p for p in chart["palaces"] if p["name"] == "命宫")["daxian_period"] == 12
    )
    assert (
        chart["ming_gong"]["branch"]
        == next(p for p in chart["palaces"] if p["name"] == "命宫")["ganzhi"][1]
    )
    assert sorted(p["daxian_period"] for p in chart["palaces"]) == list(range(1, 13))


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
def test_fire_year_only_reading_is_distinct_from_both_forward_hour_walks(profile):
    positions = []
    for hour in ["子", "丑", "午", "亥"]:
        chart = build_ziwei_chart(
            audit._seed(1984, hour=hour), "男", rule_profile=profile
        )
        stars = {
            s["name"]: p["ganzhi"][1]
            for p in chart["palaces"]
            for s in p["stars_detail"]
        }
        positions.append((stars["火星"], stars["铃星"]))
        # The older bare-verse comparison stays unresolved. A selected reading
        # does not retrospectively manufacture a missing hour instruction.
        rows = {
            r["star"]: r for r in chart["auxiliary_placement_sources"]["placements"]
        }
        assert rows["火星"]["expected_branch"] is None
        assert rows["铃星"]["matches_source_rule"] is None
    assert positions == (
        [("寅", "戌")] * 4
        if profile == "quanshu_v2_excerpt"
        else [("寅", "戌"), ("卯", "亥"), ("申", "辰"), ("丑", "酉")]
    )


def test_leap_doujun_and_childhood_substitution_remain_unverified():
    c = build_ziwei_chart(
        audit._seed(1984, 4, 16, leap=True), "女", rule_profile="quanshu_v2_excerpt"
    )
    h = build_ziwei_horoscope(
        birth_seed=synthetic_birth_clock(int((c)["lunar_date"]["year"])),
        chart=c,
        gender="女",
        target_seed=audit._seed(1984),
    )
    e = h["source_comparison"]
    assert e["doujun"]["expected_branch"] is None
    assert e["doujun"]["matches_source_rule"] is None
    assert not e["doujun"]["downstream_month_day_hour_rules_verified"]
    assert not e["fire_bell"]["unique_ming_hour_interpretation_certified"]
    assert not e["whole_book_conformance_claimed"]
    assert h["nominal_age"] == 1
    assert not e["daxian"]["active_scope_is_childhood_substitute"]
    assert e["daxian"]["formal_scope_status"] == "not_started"
    assert e["daxian"]["matches_literal_reading_given_bureau_age"] is None


def test_relabeling_old_software_positions_as_new_excerpt_cannot_pass_audit(
    monkeypatch,
):
    original = audit.build_ziwei_chart

    def relabel(*args, **kwargs):
        requested = kwargs.get("rule_profile")
        if requested == "quanshu_v2_excerpt":
            kwargs["rule_profile"] = "iztro_2_5_8"
        c = original(*args, **kwargs)
        if requested == "quanshu_v2_excerpt":
            c["ruleset"] = ziwei_ruleset_metadata(requested)
        return c

    monkeypatch.setattr(audit, "build_ziwei_chart", relabel)
    r = audit.audit_limits()
    assert r["status"] == "failed"
    assert any(d["case"].startswith("daxian_assignment/") for d in r["mismatches"])
    assert any(d["case"].startswith("fire_bell/") for d in r["mismatches"])


def test_rewriting_runtime_limit_table_cannot_redefine_frozen_source(
    tmp_path, monkeypatch
):
    name = "src/fatebridge/data/classical/ziwei-naj-ming-limits.json"
    data = json.loads((audit.ROOT / name).read_text())
    data["daxian"]["initial_palace_by_direction"]["forward"] = "命宫"
    p = tmp_path / name
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(data, ensure_ascii=False))
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    r = audit.audit_limits()
    assert any(d["case"] == "production_source_data" for d in r["mismatches"])


def test_frozen_limit_audit_requires_the_actual_source_images(tmp_path):
    name = "naj_ming_limits_v1"
    shutil.copytree(audit.FIXTURES / name, tmp_path / name)
    p = tmp_path / name / "frame_0080.jpg"
    p.write_bytes(p.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="Ming limit source checksum mismatch"):
        audit.audit_limits(tmp_path)


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
@pytest.mark.parametrize("target_day,age", [(19, 1), (20, 2)])
def test_cny_limit_boundary_and_actual_profile_reading_match_rest_mcp_cli(
    monkeypatch, capsys, profile, target_day, age
):
    # HKO 1984-02-02 and 1985-02-20 are the two respective first lunar days.
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    spec = next(s for s in CATALOG if s.key == "ziwei_horoscope")
    fields = evidence_views(spec)["source_rules"]["fields"]
    inputs = dict(
        birth_year=1984,
        birth_month=2,
        birth_day=2,
        birth_hour=2,
        birth_minute=0,
        birth_timezone="Asia/Shanghai",
        gender="男",
        use_true_solar_time=False,
        target_year=1985,
        target_month=2,
        target_day=target_day,
        target_hour=12,
        target_timezone="Asia/Shanghai",
        rule_profile=profile,
    )
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
            *[("fields", f) for f in fields],
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("as_of", opts["as_of"]),
        ],
    )
    assert rest.status_code == 200, rest.text

    async def call():
        async with Client(create_mcp_app(families="metaphysics")) as c:
            result = await c.call_tool("ziwei_horoscope", {**inputs, **opts})
            await verified_inline_business(c, result.structured_content)
            return result

    native = asyncio.run(call())
    assert not native.is_error
    args = ["ziwei_horoscope"]
    for k, v in inputs.items():
        args.extend(["--" + k.replace("_", "-"), str(v)])
    args.extend(
        [
            "--fields",
            *fields,
            "--strict-fields",
            "--no-include-snapshot-text",
            "--as-of",
            opts["as_of"],
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
    h = bodies[0]["ziwei_horoscope"]
    e = h["source_comparison"]
    selected = profile == "quanshu_v2_excerpt"
    assert h["nominal_age"] == age
    assert h["ruleset"]["version"] == ("1.3.2" if selected else "1.1.2")
    assert e["daxian"]["actual_initial_palace"] == ("父母宫" if selected else "命宫")
    assert e["daxian"]["matches_literal_initial_palace"] is selected
    assert e["daxian"]["actual_branch"] == (
        None if age == 1 else "寅" if selected else "丑"
    )
    assert e["daxian"]["active_scope_is_childhood_substitute"] is False
    assert e["daxian"]["before_formal_decade_start"] is (age == 1)
    assert e["fire_bell"]["actual_positions"] == (
        {"火星": "寅", "铃星": "戌"} if selected else {"火星": "卯", "铃星": "亥"}
    )
    assert e["doujun"]["matches_source_rule"]
    assert e["xiaoxian"]["matches_source_given_age"]

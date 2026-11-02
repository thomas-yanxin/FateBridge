"""Complete historical date cohort, annual-boundary and real-transport checks."""

import asyncio
import hashlib
import json
import shutil
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application.examples import suggested_fields
from fatebridge.application.projection import project_fields
from fatebridge.cli import run
from fatebridge.core.metaphysics.taiyi import build_taiyi_board
from fatebridge.core.metaphysics.taiyi_year_calendar import (
    DEFAULT_YEAR_PROFILE,
    HISTORICAL_YEAR_PROFILE,
    historical_year_context,
)
from fatebridge.core.output_chinese import Taiyi
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.metaphysics import calculate_taiyi_analysis
from fatebridge.services.tool_catalog import CATALOG
from scripts.audit_taiyi_year_calendar import CORPUS, audit, julian_jdn, public_case
from tests.test_taiyi_enclosures import resolve
from tests.test_taiyi_periods import seed_at
from tests.test_taiyi_transports import _same_run_payload


def test_complete_printed_cohort_and_classical_example_have_separate_denominators():
    r = audit()
    assert r["required_month_start_anchors"] == r["matching_month_start_anchors"] == 63
    assert r["complete_month_intervals"] == 62
    assert r["daily_reconstruction_checks"] == 1831 and not r["daily_disagreements"]
    assert r["leap_months"] == [[382, 9], [385, 5]]
    assert r["cohort_calendar_reconstruction_passed"] is True
    c = r["actual_public_annual_replay"]
    assert c["matching_numeric_observations"] == 11
    assert c["source_ju_matches"] is c["enclosure_targets_match"] is True
    assert c["enclosure_subjects"] == ["始击", "客大将"]
    assert c["enclosure_profile"] == "jinjing_vol3_principal_enclosure_v1"
    assert len(c["additional_pair_enclosures"]) == 4
    assert not c["additional_pairs_included_in_original_source_denominator"]
    assert r["full_ancient_calendar_reconstructed"] is False
    assert r["classic_year_boundary_adjudicated"] is False
    assert r["whole_goal_complete"] is False


@pytest.mark.parametrize(
    "d,y",
    [
        ("0381-02-11", 381),
        ("0382-02-01", 382),
        ("0383-02-20", 383),
        ("0384-02-09", 384),
        ("0385-01-28", 385),
    ],
)
def test_each_historical_year_boundary_on_real_public_chain(d, y):
    start = date.fromisoformat(d)
    r = public_case(start.year, start.month, start.day)
    b = r["taiyi"]
    assert b["calendar_rules"]["year"] == y
    h = b["calendar_rules"]["historical_calendar"]
    assert (h["month"], h["day"], h["is_leap_month"]) == (1, 1, False)
    previous = start - timedelta(days=1)
    before = public_case(previous.year, previous.month, previous.day)
    if y == 381:
        assert "仅覆盖" in before["error"] and "taiyi" not in before
    else:
        assert before["taiyi"]["calendar_rules"]["year"] == y - 1
        assert (
            b["core_board"]["accumulation"]
            - before["taiyi"]["core_board"]["accumulation"]
            == 1
        )
    assert "完整古历" in h["scope"]


@pytest.mark.parametrize("d,m", [("0382-10-25", 9), ("0385-06-25", 5)])
def test_original_bold_repeated_month_is_leap_not_a_renumbered_month(d, m):
    start = date.fromisoformat(d)
    a = historical_year_context(start)
    b = historical_year_context(start - timedelta(days=1))
    assert (a["month"], a["day"], a["is_leap_month"]) == (m, 1, True)
    assert b["month"] == m and b["is_leap_month"] is False
    assert a["year"] == b["year"]


def test_same_julian_label_mistaken_as_gregorian_changes_the_annual_ju():
    good = public_case(385, 1, 28)["taiyi"]
    wrong = public_case(385, 1, 27)["taiyi"]
    assert (
        good["calendar_rules"]["historical_calendar"]["source_year_start_julian"]
        == "0385-01-27"
    )
    assert (good["core_board"]["kook_number"], wrong["core_board"]["kook_number"]) == (
        70,
        69,
    )
    assert good["calendar_rules"]["year_ganzhi"] == "乙酉"
    assert good["calendar_rules"]["input_calendar"] == "proleptic_gregorian"


def test_historical_year_is_not_replaced_by_solar_pillar_year_or_corrected_day():
    r = calculate_taiyi_analysis(
        analysis_year=385,
        analysis_month=1,
        analysis_day=28,
        analysis_hour=0,
        analysis_minute=1,
        analysis_timezone="+08:00",
        analysis_longitude=0,
        use_true_solar_time=True,
        year_profile=HISTORICAL_YEAR_PROFILE,
    )
    b = r["taiyi"]
    assert b["calendar_rules"]["year_ganzhi"] == "乙酉"
    assert b["calendar_rules"]["historical_calendar"]["civil_date"] == "0385-01-28"
    assert b["calendar_rules"]["solar_correction_affects_year"] is False
    assert "太乙专用" in r["snapshot_text"]
    assert r["calendar_context"]["lunar_calendar"] is None


def test_original_annual_default_and_explicit_default_are_unchanged():
    a = calculate_taiyi_analysis(
        analysis_year=2026,
        analysis_month=4,
        analysis_day=4,
        analysis_hour=12,
        analysis_timezone="+08:00",
    )
    b = calculate_taiyi_analysis(
        analysis_year=2026,
        analysis_month=4,
        analysis_day=4,
        analysis_hour=12,
        analysis_timezone="+08:00",
        year_profile=DEFAULT_YEAR_PROFILE,
    )
    assert a == b
    assert "historical_calendar" not in a["taiyi"]["calendar_rules"]
    old = calculate_taiyi_analysis(
        analysis_year=385,
        analysis_month=7,
        analysis_day=1,
        analysis_hour=12,
        analysis_timezone="+08:00",
    )
    assert "taiyi" not in old and "error" in old


@pytest.mark.parametrize("d", ["0381-02-10", "0386-02-16", "1561-10-20", "2026-04-04"])
def test_historical_profile_never_extrapolates_or_falls_back(d):
    day = date.fromisoformat(d)
    with pytest.raises(ValueError, match="仅覆盖"):
        historical_year_context(day)
    r = public_case(day.year, day.month, day.day)
    assert "taiyi" not in r and "仅覆盖" in r["error"]


@pytest.mark.parametrize("profile", [True, False, 12, {}, [], "unknown"])
def test_invalid_profile_fails_as_domain_validation(profile):
    from datetime import datetime

    with pytest.raises(ValueError, match="year_profile"):
        build_taiyi_board(
            seed_at(datetime(2026, 4, 4, 12)), "未知", year_profile=profile
        )


def test_each_historical_fact_is_projection_safe_and_typed():
    b = public_case()["taiyi"]
    for key in b["calendar_rules"]["historical_calendar"]:
        field = "taiyi.calendar_rules.historical_calendar." + key
        Taiyi.model_validate(
            project_fields({"taiyi": b}, [field], strict_fields=True)["taiyi"]
        )
    assert "本年月首原儒略历" in public_case()["snapshot_text"]


@pytest.mark.parametrize("attempt", ["drop_month", "drop_raw_counter", "change_image"])
def test_entire_cohort_and_original_scans_cannot_be_reduced(tmp_path, attempt):
    c = tmp_path / "v12"
    shutil.copytree(CORPUS, c)
    manifest_path = c / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for row in manifest["prior_source_references"] + [manifest["source_reference"]]:
        row["file"] = str((CORPUS / row["file"]).resolve())
    if attempt == "change_image":
        (c / "sino-western-pdf101.jpg").write_bytes(b"changed")
        manifest_path.write_text(json.dumps(manifest))
        with pytest.raises(ValueError, match="指纹"):
            audit(c)
        return
    p = c / "month-starts.json"
    data = json.loads(p.read_text())
    if attempt == "drop_month":
        data["months"].pop(22)
    else:
        del data["months"][22]["printed_cycle_counter"]
    p.write_text(json.dumps(data))
    for row in manifest["source_files"]:
        if row["file"] == p.name:
            row["sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="完整五年.*63"):
        audit(c)


def payload(key, day="0385-07-01", mode="year"):
    if key == "taiyi":
        d = date.fromisoformat(day)
        return {
            "analysis_year": d.year,
            "analysis_month": d.month,
            "analysis_day": d.day,
            "analysis_hour": 12,
            "analysis_timezone": "+08:00",
            "use_true_solar_time": False,
            "calculation_mode": mode,
            "year_profile": HISTORICAL_YEAR_PROFILE,
        }
    return {
        "date": day,
        "time": "12:00:00",
        "zone": "+08:00",
        "use_true_solar_time": False,
        "taiyi_options": {
            "calculation_mode": mode,
            "year_profile": HISTORICAL_YEAR_PROFILE,
        },
    }


@pytest.mark.parametrize("key", ["taiyi", "sanshiunited"])
@pytest.mark.parametrize(
    "day,expected_year", [("0385-01-27", 384), ("0385-01-28", 385)]
)
def test_historical_year_source_facts_match_real_rest_mcp_cli(
    monkeypatch, capsys, key, day, expected_year
):
    p = payload(key, day)
    fields = ["taiyi.calendar_rules", "taiyi.core_board", "snapshot_text"]
    if key == "sanshiunited":
        fields += ["synthesis.limitations"]
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    route = "/api/cn/taiyi" if key == "taiyi" else "/api/divination/sanshiunited"
    rest = TestClient(api.app).post(
        route,
        json=p,
        params=[
            ("strict_fields", "true"),
            ("response_char_limit", "0"),
            *[("fields", x) for x in fields],
        ],
    )
    assert rest.status_code == 200, rest.text

    async def invoke():
        async with Client(create_mcp_app()) as client:
            r = await client.call_tool(
                key,
                {
                    **p,
                    "fields": fields,
                    "strict_fields": True,
                    "response_char_limit": 0,
                },
            )
            assert not r.is_error
            return r.structured_content

    mcp = asyncio.run(invoke())
    args = [key]
    for k, v in p.items():
        args += [
            "--" + k.replace("_", "-"),
            json.dumps(v) if isinstance(v, dict) else str(v),
        ]
    args += ["--strict-fields", "--response-char-limit", "0", "--fields", *fields]
    capsys.readouterr()
    assert run(args) == 0
    cli = json.loads(capsys.readouterr().out)
    for field in fields:
        assert resolve(rest.json(), field) == resolve(mcp, field) == resolve(cli, field)
    assert mcp["taiyi"]["calendar_rules"]["year"] == expected_year
    if key == "sanshiunited":
        assert "未认证三式共同古历" in mcp["synthesis"]["limitations"][0]


@pytest.mark.parametrize("key", ["taiyi", "sanshiunited"])
@pytest.mark.parametrize("mode", ["month", "day", "hour"])
def test_year_profile_wrong_mode_is_rejected_on_actual_transports(
    monkeypatch, capsys, key, mode
):
    p = payload(key, mode=mode)
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    route = "/api/cn/taiyi" if key == "taiyi" else "/api/divination/sanshiunited"
    r = TestClient(api.app).post(route, json=p)
    assert r.status_code == 400

    async def invoke():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(key, p, raise_on_error=False)

    assert asyncio.run(invoke()).is_error
    args = [key]
    for k, v in p.items():
        args += [
            "--" + k.replace("_", "-"),
            json.dumps(v) if isinstance(v, dict) else str(v),
        ]
    capsys.readouterr()
    assert run(args) != 0


@pytest.mark.parametrize("key", ["taiyi", "sanshiunited"])
@pytest.mark.parametrize("day", ["0385-01-27", "0385-01-28"])
def test_published_historical_year_first_view_keeps_source_and_limitations_inline(
    key, day
):
    spec = next(s for s in CATALOG if s.key == key)
    fields = suggested_fields(spec, view="historical_year_calendar")

    async def invoke():
        async with Client(create_mcp_app()) as client:
            r = await client.call_tool(
                key,
                {
                    **payload(key, day),
                    "fields": fields,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            )
            return await _same_run_payload(client, r)

    r = asyncio.run(invoke())
    b = r["taiyi"]
    assert (
        b["calendar_rules"]["historical_calendar"]["calendar_title"]
        == "两千年中西历对照表"
    )
    assert b["ruleset"]["classical_acceptance_passed"] is False
    Taiyi.model_validate(b)

"""JPL solar time is external evidence; minute endpoints are explicit hypotheses."""

import asyncio
import hashlib
import json
import shutil
from copy import deepcopy
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
import scripts.ziwei.audit_ziwei_solar_clock as audit
from fatebridge.application.examples import evidence_views
from fatebridge.cli import run
from fatebridge.core.ziwei_time_input import birth_clock_receipt
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.metaphysics import calculate_ziwei_birth
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.birth_input import create_person_info
from fatebridge.utils.solar_time import normalize_birth_time
from scripts.ziwei.audit_ziwei import FIXTURES, hko_rows
from tests.fixtures.mcp_receipt import verified_inline_business

BIRTH = dict(
    birth_year=2024,
    birth_month=12,
    birth_day=6,
    birth_hour=0,
    birth_minute=51,
    birth_timezone="UTC",
    birth_longitude=0,
    use_true_solar_time=True,
    gender="男",
)


def test_all_external_solar_clocks_join_hko_dates_and_real_placements():
    r = audit.audit_solar_clock(hko_rows, FIXTURES)
    assert r["independent_jpl_points"] == 449
    assert r["observer_sites"] == 7 and r["chart_checks"] == 898
    assert r["tolerance_seconds"] == 5
    assert not r["differences"]
    assert r["max_absolute_error_seconds"] <= 5
    assert r["unresolved_discrete_boundary_points"] == [
        dict(
            site="zero",
            instant="2024-12-06T00:51:00+00:00",
            distance_seconds=pytest.approx(1.40515),
        )
    ]
    assert not r["historical_timezone_certified"]
    assert not r["original_astrological_clock_policy_certified"]
    assert not r["full_calendar_acceptance_passed"]


def test_source_keeps_every_declared_instant_and_independent_solar_hour_angle():
    p, rows = audit.load_reference()
    assert len(rows) == p["expected_source_points"] == 449
    assert len({(r["site"]["id"], r["instant"]) for r in rows}) == 449
    assert {r["instant"].hour for r in rows} == set(range(24))
    assert {r["site"]["timezone"] for r in rows} >= {
        "Australia/Lord_Howe",
        "Pacific/Apia",
        "Asia/Kathmandu",
    }
    assert all(
        abs((r["apparent_hours"] - r["hour_angle"] - 12 + 12) % 24 - 12) < 1e-8
        for r in rows
    )


def test_corrupted_original_reply_is_rejected(tmp_path):
    shutil.copytree(audit.DIRECTORY, tmp_path / "data")
    (tmp_path / "data/zero-00.json").write_text("changed")
    with pytest.raises(ValueError, match="reply checksum mismatch"):
        audit.load_reference(tmp_path / "data")


@pytest.mark.parametrize("kind", ["site", "point", "duplicate", "solar_hour"])
def test_rehashed_wrong_metadata_or_tables_are_not_valid_sources(tmp_path, kind):
    directory = tmp_path / "data"
    shutil.copytree(audit.DIRECTORY, directory)
    m = json.loads((directory / "manifest.json").read_text())
    r = m["replies"][0]
    if kind == "site":
        r["request_parameters"]["SITE_COORD"] = "'1,0,0'"
    elif kind == "point":
        r["instants"] = r["instants"][:-1]
    elif kind == "duplicate":
        m["replies"].append(deepcopy(r))
    else:
        p = directory / r["path"]
        response = json.loads(p.read_text())
        response["result"] = response["result"].replace(
            "23.9385622219", "22.9385622219"
        )
        p.write_text(json.dumps(response))
        r["sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
    raw = json.dumps(m)
    (directory / "manifest.json").write_text(raw)
    (directory / "manifest.sha256").write_text(hashlib.sha256(raw.encode()).hexdigest())
    with pytest.raises(ValueError):
        audit.load_reference(directory)


def test_wrong_actual_hour_does_not_change_external_expectation(monkeypatch):
    original = audit.calculate_ziwei_birth

    def wrong(person, **kw):
        r = original(person, **kw)
        if (
            person.birth_timezone == "UTC"
            and person.birth_year == 1990
            and person.birth_hour == 0
        ):
            r["ziwei_birth"]["hour_branch"] = "wrong"
        return r

    monkeypatch.setattr(audit, "calculate_ziwei_birth", wrong)
    r = audit.audit_solar_clock(hko_rows, FIXTURES)
    assert len(r["differences"]) == 2
    assert all(x["checks"]["actual_hour"] is False for x in r["differences"])


def test_seconds_endpoint_does_not_replace_base_birth_facts_or_chart():
    r = calculate_ziwei_birth(create_person_info(**BIRTH))
    c = r["ziwei_birth"]
    s = c["calendar_basis"]["time_input"]["minute_sensitivity"]
    assert c["hour_branch"] == s["endpoint_hour_branches"][0] == "子"
    assert s["endpoint_hour_branches"] == ["子", "丑"]
    assert s["base_second"] == 0 and not s["birth_seconds_supplied"]
    assert s["crosses_hour_branch"] and not s["crosses_placement_date"]
    assert not s["endpoints_are_alternative_birth_facts"]
    assert not s["observed_birth_precision_certified"]
    assert r["analysis_context"]["time_input_minute_sensitive"]
    assert "未替换出生资料或命盘" in r["snapshot_text"]
    start, end = map(datetime.fromisoformat, s["endpoint_placement_datetimes"])
    # The EOT is evaluated again at the later physical instant.
    assert abs((end - start).total_seconds() - 59.999999) > 0.001


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
def test_given_minute_can_cross_lunar_new_year_without_changing_hour_branch(profile):
    r = calculate_ziwei_birth(
        create_person_info(
            **{
                **BIRTH,
                "birth_year": 1984,
                "birth_month": 2,
                "birth_day": 1,
                "birth_hour": 22,
                "birth_minute": 13,
                "birth_timezone": "Asia/Shanghai",
                "birth_longitude": 150,
            }
        ),
        rule_profile=profile,
    )
    c = r["ziwei_birth"]
    s = c["calendar_basis"]["time_input"]["minute_sensitivity"]
    assert s["crosses_placement_date"] and not s["crosses_hour_branch"]
    assert s["endpoint_hour_branches"] == ["子", "子"]
    assert s["endpoint_placement_datetimes"][0].startswith("1984-02-01")
    assert s["endpoint_placement_datetimes"][1].startswith("1984-02-02")
    assert c["lunar_date"] == dict(year=1983, month=12, day=30, is_leap_month=False)
    assert r["analysis_context"]["time_input_minute_sensitive"]


def test_sensitivity_does_not_apply_a_solar_model_when_solar_time_was_not_applied(
    monkeypatch,
):
    import fatebridge.core.ziwei_time_input as module

    p = create_person_info(**{**BIRTH, "use_true_solar_time": False})
    n = normalize_birth_time(p)

    def forbidden(*a, **kw):
        raise AssertionError("solar computation not selected")

    monkeypatch.setattr(module, "calculate_solar_time_adjustment", forbidden)
    r = birth_clock_receipt(p, n)
    s = r["minute_sensitivity"]
    assert not s["crosses_hour_branch"] and not s["crosses_placement_date"]
    assert s["endpoint_hour_branches"] == ["子", "子"]
    start, end = map(datetime.fromisoformat, s["endpoint_placement_datetimes"])
    assert end - start == timedelta(seconds=59.999999)


@pytest.mark.parametrize("tool", ["ziwei_birth", "ziwei_horoscope"])
def test_minute_diagnostics_have_three_surface_parity_and_fit_default_budget(
    tool, monkeypatch, capsys
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    spec = next(s for s in CATALOG if s.key == tool)
    fields = evidence_views(spec)["time_input"]["fields"]
    inputs = {**BIRTH}
    if tool == "ziwei_horoscope":
        inputs.update(target_year=2026, target_month=10, target_day=22, target_hour=12)
    opts = dict(
        as_of="2026-10-22T12:00:00+08:00",
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
    )
    rest = TestClient(api.app).post(
        "/api/cn/ziwei/" + ("birth" if tool == "ziwei_birth" else "horoscope"),
        json=inputs,
        params=[
            ("as_of", opts["as_of"]),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            *[("fields", x) for x in fields],
        ],
    )

    async def call():
        async with Client(create_mcp_app(families="metaphysics")) as client:
            r = await client.call_tool(tool, {**inputs, **opts}, raise_on_error=False)
            assert not r.is_error, r.content
            return await verified_inline_business(client, r.structured_content)

    native = asyncio.run(call())
    args = [tool]
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
    code = run(args)
    cli = json.loads(capsys.readouterr().out)
    assert code == 0, cli
    assert rest.status_code == 200, rest.text
    bodies = [
        {k: v for k, v in r.items() if k not in ("run_metadata", "result_delivery")}
        for r in (rest.json(), native, cli)
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    b = bodies[0][tool]["calendar_basis"]
    s = (b if tool == "ziwei_birth" else b["birth"])["time_input"]["minute_sensitivity"]
    assert s["endpoint_hour_branches"] == ["子", "丑"] and s["crosses_hour_branch"]

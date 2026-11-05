"""Post-implementation boundary regressions; not a blind classical oracle."""

import asyncio
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from pydantic import ValidationError

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.core.metaphysics.ziwei import build_ziwei_chart, build_ziwei_horoscope
from fatebridge.core.output_chinese import ZiweiNominalAgeCalendar
from fatebridge.core.ziwei_age import age_source_scope
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.metaphysics import (
    _build_analysis_seed,
    _build_person_seed,
    calculate_ziwei_birth,
    calculate_ziwei_horoscope,
)
from fatebridge.utils.birth_input import create_person_info
from fatebridge.utils.timezones import parse_timezone_name
from scripts.audit_ziwei_age import audit_age_calendar

FIXTURES = Path(__file__).parent / "data/ziwei_independent"
CASES = json.loads((FIXTURES / "clock_manifest.json").read_text())["cases"]
EAST = next(c["input"] for c in CASES if c["id"] == "cny_east_forward")
WEST = next(c["input"] for c in CASES if c["id"] == "cny_west_backward")
PROFILES = ["iztro_2_5_8", "quanshu_v2_excerpt"]


def target_at(iso, zone="Asia/Shanghai"):
    d = datetime.fromisoformat(iso).astimezone(parse_timezone_name(zone))
    return dict(
        target_year=d.year,
        target_month=d.month,
        target_day=d.day,
        target_hour=d.hour,
        target_minute=d.minute,
        target_timezone=zone,
    )


def result(birth=EAST, iso="1984-02-01T23:59:00+08:00", **kwargs):
    return calculate_ziwei_horoscope(
        create_person_info(**birth), **target_at(iso), **kwargs
    )


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("sihua", ["rule_profile", "naj_ming_v1"])
def test_old_failure_is_repaired_by_two_clock_endpoints_not_clamping(profile, sihua):
    before = result(rule_profile=profile, sihua_source=sihua)["ziwei_horoscope"]
    after = result(
        iso="1984-02-02T00:00:00+08:00", rule_profile=profile, sihua_source=sihua
    )["ziwei_horoscope"]
    assert before["nominal_age"] == 1 and after["nominal_age"] == 2
    for h, years in [(before, (1983, 1983)), (after, (1983, 1984))]:
        a = h["nominal_age_calendar"]
        assert (a["birth_lunar_year"], a["target_lunar_year"]) == years
        assert a["birth_placement_lunar_year"] == 1984
        assert a["physical_order_checked"]
        assert not a["age_boundary_classically_verified"]
        assert h["childhood_limit"]["given_age_ordinal"] == h["nominal_age"]
    assert before["scopes"][0]["status"] == "not_started"
    assert after["scopes"][0]["status"] == "computed"
    assert before["scopes"][1]["branch"] != after["scopes"][1]["branch"]


@pytest.mark.parametrize("profile", PROFILES)
def test_westward_solar_label_does_not_add_a_civil_year(profile):
    r = result(WEST, "1984-02-02T00:09:00+08:00", rule_profile=profile)
    h = r["ziwei_horoscope"]
    assert h["nominal_age"] == 1
    a = h["nominal_age_calendar"]
    assert a["birth_placement_lunar_year"] == 1983
    assert a["birth_lunar_year"] == a["target_lunar_year"] == 1984
    natal = calculate_ziwei_birth(create_person_info(**WEST), rule_profile=profile)[
        "ziwei_birth"
    ]
    assert natal["lunar_date"]["year"] == 1983
    assert h["scopes"][2]["stem"] == "甲"


@pytest.mark.parametrize(
    "iso,age", [("1984-02-01T23:59:00+08:00", 1), ("1984-02-02T00:00:00+08:00", 2)]
)
@pytest.mark.parametrize("zone", ["UTC", "America/New_York", "+14:00", "-12:00"])
def test_same_target_instant_does_not_change_age_when_display_zone_changes(
    iso, age, zone
):
    r = calculate_ziwei_horoscope(create_person_info(**EAST), **target_at(iso, zone))
    h = r["ziwei_horoscope"]
    assert h["nominal_age"] == age
    assert h["nominal_age_calendar"]["timezone"] == "Asia/Shanghai"
    expected = result(iso=iso)["ziwei_horoscope"]
    # Age-dependent scopes, childhood and half-decade joins must be identical;
    # target-clock flowing scopes may legitimately have different date labels.
    assert h["scopes"][:2] == expected["scopes"][:2]
    assert h["childhood_limit"] == expected["childhood_limit"]
    assert h["ming_limit_subperiods"] == expected["ming_limit_subperiods"]


@pytest.mark.parametrize("basis", ["birth_civil_timezone"])
def test_physical_prebirth_guard_is_not_bypassed_by_age_choice(basis):
    r = result(iso="1984-02-01T23:54:00+08:00", nominal_age_basis=basis)
    assert "目标时刻早于出生时刻" in r["error"]
    assert r["retryable"] is False


def test_exact_birth_instant_is_age_one_and_requires_no_default_time_guess():
    r = result(iso="1984-02-01T23:55:00+08:00")
    assert r["ziwei_horoscope"]["nominal_age"] == 1
    bad = result(nominal_age_basis="unknown")
    assert "未知紫微岁序口径" in bad["error"]


def test_core_does_not_silently_infer_age_from_a_synthetic_placement_year():
    birth = _build_person_seed(create_person_info(**EAST))
    chart = build_ziwei_chart(birth, "男")
    target = _build_analysis_seed(
        analysis_year=1984,
        analysis_month=2,
        analysis_day=1,
        analysis_hour=23,
        analysis_minute=59,
    )
    with pytest.raises(ValueError, match="需要实际出生时钟"):
        build_ziwei_horoscope(chart=chart, gender="男", target_seed=target)
    h = build_ziwei_horoscope(
        chart=chart, gender="男", birth_seed=birth, target_seed=target
    )
    assert h["nominal_age"] == 1


def test_age_receipt_cannot_claim_classical_verification():
    a = deepcopy(result()["ziwei_horoscope"]["nominal_age_calendar"])
    ZiweiNominalAgeCalendar.model_validate(a)
    a["age_boundary_classically_verified"] = True
    with pytest.raises(ValidationError):
        ZiweiNominalAgeCalendar.model_validate(a)


def test_mutating_one_source_receipt_does_not_change_the_next_run():
    first = result()["ziwei_horoscope"]["nominal_age_calendar"]
    first["boundary_source_evidence"]["citations"][0]["quote"] = "changed"
    later = result()["ziwei_horoscope"]["nominal_age_calendar"]
    assert later["boundary_source_evidence"]["citations"][0]["quote"] != "changed"


def test_independent_reading_corrects_quote_without_rewriting_failed_v1():
    old = json.loads((FIXTURES / "age_calendar_scope_v1/collation.json").read_text())
    new = age_source_scope()
    assert "本生時宮安斗君" in old["citations"][2]["quote"]
    assert "本生時安斗君" in new["citations"][2]["quote"]
    assert new["version"] == "1.0.1" and new["independent_reviewers"] == 1
    assert (
        new["correction_history"][0]["incorrect_quote"] == old["citations"][2]["quote"]
    )
    assert not new["age_boundary_classically_verified"]


def test_modified_v2_source_cannot_pass_its_frozen_checksum(tmp_path):
    folder = tmp_path / "age_calendar_scope_v2"
    folder.mkdir()
    (folder / "manifest.json").write_bytes(
        (FIXTURES / "age_calendar_scope_v2/manifest.json").read_bytes()
    )
    (folder / "collation.json").write_text("changed")
    with pytest.raises(ValueError, match="Age source scope checksum mismatch"):
        audit_age_calendar(lambda *_: [], tmp_path)


def test_repeated_birth_clock_uses_physical_order_for_both_age_methods():
    birth = create_person_info(
        birth_year=1991,
        birth_month=9,
        birth_day=15,
        birth_hour=1,
        birth_minute=40,
        birth_timezone="Asia/Shanghai",
        gender="男",
        use_true_solar_time=False,
    )
    target = dict(
        target_year=1991, target_month=9, target_day=15, target_hour=1, target_minute=20
    )
    for basis in ("birth_civil_timezone",):
        r = calculate_ziwei_horoscope(
            birth,
            **target,
            birth_utc_offset="+09:00",
            target_utc_offset="+08:00",
            nominal_age_basis=basis,
        )
        a = r["ziwei_horoscope"]["nominal_age_calendar"]
        assert a["nominal_age"] == 1
        assert a["birth_instant_utc"] == "1991-09-14T16:40:00+00:00"
        assert a["target_instant_utc"] == "1991-09-14T17:20:00+00:00"
        earlier = calculate_ziwei_horoscope(
            birth,
            **target,
            birth_utc_offset="+08:00",
            target_utc_offset="+09:00",
            nominal_age_basis=basis,
        )
        assert "目标时刻早于出生时刻" in earlier["error"]


@pytest.mark.parametrize("basis,age", [("birth_civil_timezone", 2)])
def test_age_basis_is_equal_in_real_rest_native_mcp_cli(
    basis, age, monkeypatch, capsys
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    inputs = {
        **EAST,
        **target_at("1984-02-02T00:00:00+08:00"),
        "nominal_age_basis": basis,
    }
    fields = ["ziwei_horoscope.nominal_age", "ziwei_horoscope.nominal_age_calendar"]
    options = dict(
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
    )
    rest = TestClient(api.app).post(
        "/api/cn/ziwei/horoscope",
        json=inputs,
        params=[
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
            *[("fields", f) for f in fields],
        ],
    )

    async def call():
        async with Client(create_mcp_app(families="metaphysics")) as client:
            return await client.call_tool(
                "ziwei_horoscope", {**inputs, **options}, raise_on_error=False
            )

    native = asyncio.run(call())
    args = ["ziwei_horoscope"]
    for key, value in inputs.items():
        args += ["--" + key.replace("_", "-"), str(value)]
    args += [
        "--strict-fields",
        "--no-include-snapshot-text",
        "--response-char-limit",
        "0",
        "--fields",
        *fields,
    ]
    capsys.readouterr()
    code = run(args)
    cli = json.loads(capsys.readouterr().out)
    assert rest.status_code == 200, rest.text
    assert not native.is_error, native.content
    assert code == 0, cli
    outputs = [rest.json(), native.structured_content, cli]
    facts = [o["ziwei_horoscope"] for o in outputs]
    assert facts[0] == facts[1] == facts[2]
    assert facts[0]["nominal_age"] == age
    a = facts[0]["nominal_age_calendar"]
    assert a["basis"] == "birth_civil_timezone"
    assert a["physical_order_checked"] is True

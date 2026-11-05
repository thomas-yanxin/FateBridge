"""Explicit offsets select physical instants without guessing ambiguous births."""

import asyncio
import json
import shutil
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application.examples import evidence_views, suggested_fields
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.metaphysics import (
    calculate_ziwei_birth,
    calculate_ziwei_horoscope,
)
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.birth_input import create_person_info
from fatebridge.utils.solar_time import normalize_birth_time
from scripts.ziwei.audit_ziwei_civil_fold import FIXTURES, audit_civil_fold
from tests.fixtures.mcp_receipt import verified_inline_business

BIRTH = dict(
    birth_year=1991,
    birth_month=9,
    birth_day=15,
    birth_hour=1,
    birth_minute=30,
    birth_timezone="Asia/Shanghai",
    birth_longitude=120,
    gender="男",
    use_true_solar_time=True,
)
TARGET = dict(
    target_year=1991, target_month=9, target_day=15, target_hour=1, target_minute=30
)


def test_frozen_rule_audit_keeps_independent_denominators_and_known_gaps():
    r = audit_civil_fold()
    assert not r["differences"]
    assert r["independent_rule_conditioned_instants"] == 2
    assert r["birth_receipts_checked"] == 16 and r["chronology_cases_checked"] == 8
    assert r["source_rule_records"] == 3 and r["manual_readers"] == 1
    assert (
        r["independent_lunar_date_vectors_added"]
        == r["independent_solar_correction_vectors_added"]
        == 0
    )
    assert (
        not r["classical_clock_policy_verified"]
        and not r["full_calendar_acceptance_passed"]
    )


def test_changing_actual_instant_is_detected_without_rewriting_expected_values(
    monkeypatch,
):
    import scripts.ziwei.audit_ziwei_civil_fold as audit

    original = audit.calculate_ziwei_birth

    def wrong(*a, **kw):
        r = original(*a, **kw)
        r["ziwei_birth"]["calendar_basis"]["civil_clock"][
            "instant_utc"
        ] = "1991-09-14T00:00:00+00:00"
        return r

    monkeypatch.setattr(audit, "calculate_ziwei_birth", wrong)
    assert len(audit.audit_civil_fold()["differences"]) == 16


def test_original_timezone_rule_bytes_are_required(tmp_path):
    shutil.copytree(FIXTURES / "ziwei_civil_fold_v1", tmp_path / "ziwei_civil_fold_v1")
    (tmp_path / "ziwei_civil_fold_v1/iana-2025b-asia.txt").write_bytes(b"changed")
    with pytest.raises(ValueError, match="source checksum mismatch"):
        audit_civil_fold(tmp_path)


@pytest.mark.parametrize("solar", [False, True])
@pytest.mark.parametrize(
    "offset,fold,utc",
    [
        ("+09:00", 0, "1991-09-14T16:30:00+00:00"),
        ("+08:00", 1, "1991-09-14T17:30:00+00:00"),
    ],
)
def test_explicit_offset_retains_named_zone_and_physical_solar_input(
    solar, offset, fold, utc, monkeypatch
):
    import fatebridge.utils.solar_time as module

    seen = []

    def eot(t):
        seen.append(t.astimezone(__import__("datetime").timezone.utc).isoformat())
        return 0.0

    monkeypatch.setattr(module, "calculate_equation_of_time_minutes", eot)
    r = calculate_ziwei_birth(
        create_person_info(**{**BIRTH, "use_true_solar_time": solar}),
        birth_utc_offset=offset,
    )
    assert "error" not in r, r
    b = r["ziwei_birth"]["calendar_basis"]
    c = b["civil_clock"]
    assert (c["fold"], c["instant_utc"], c["timezone"]) == (fold, utc, "Asia/Shanghai")
    assert (
        b["placement_datetime"]
        == f"1991-09-15 {'00' if solar and fold == 0 else '01'}:30:00"
    )
    if solar:
        assert seen[0] == utc
    else:
        assert not seen
    assert c["resolved_utc_offset"] in r["snapshot_text"]
    assert utc in r["snapshot_text"]


@pytest.mark.parametrize("tool", ["birth", "horoscope"])
@pytest.mark.parametrize("offset", [None, "+07:00", "+08:30", "bad"])
def test_ambiguity_or_mismatching_offset_is_rejected(tool, offset):
    p = create_person_info(**BIRTH)
    r = (
        calculate_ziwei_birth(p, birth_utc_offset=offset)
        if tool == "birth"
        else calculate_ziwei_horoscope(
            p, **TARGET, birth_utc_offset=offset, target_utc_offset="+08:00"
        )
    )
    assert r.get("status_code") == 400
    assert (
        "ambiguous" in r["error"]
        if offset is None
        else "birth_utc_offset" in r["error"]
    )


@pytest.mark.parametrize("offset", ["+08:00", "+09:00"])
@pytest.mark.parametrize("which", ["birth", "target"])
def test_explicit_offset_cannot_make_a_nonexistent_wall_time_real(offset, which):
    if which == "birth":
        p = create_person_info(
            **{**BIRTH, "birth_month": 4, "birth_day": 14, "birth_hour": 2}
        )
        r = calculate_ziwei_birth(p, birth_utc_offset=offset)
    else:
        p = create_person_info(**{**BIRTH, "birth_year": 1990})
        r = calculate_ziwei_horoscope(
            p,
            **{**TARGET, "target_month": 4, "target_day": 14, "target_hour": 2},
            target_utc_offset=offset,
        )
    assert r.get("status_code") == 400 and "nonexistent" in r["error"]


def test_missing_target_offset_still_rejects_ambiguous_target():
    p = create_person_info(**{**BIRTH, "birth_year": 1990})
    assert "ambiguous" in calculate_ziwei_horoscope(p, **TARGET)["error"]


def test_minute_endpoint_preserves_second_occurrence_and_utc_progress():
    r = calculate_ziwei_birth(
        create_person_info(
            **{**BIRTH, "use_true_solar_time": False, "birth_minute": 59}
        ),
        birth_utc_offset="+08:00",
    )
    e = r["ziwei_birth"]["calendar_basis"]["time_input"]["minute_sensitivity"][
        "endpoint_placement_datetimes"
    ]
    assert e == ["1991-09-15 01:59:00", "1991-09-15 01:59:59.999999"]


def test_no_offset_and_redundant_correct_offset_keep_actual_natal_facts_equal():
    p = create_person_info(**{**BIRTH, "birth_day": 16})
    a = calculate_ziwei_birth(p)
    b = calculate_ziwei_birth(p, birth_utc_offset="+08:00")
    ac, bc = a["ziwei_birth"], b["ziwei_birth"]
    ac.pop("calendar_basis")
    bc.pop("calendar_basis")
    assert ac == bc
    assert normalize_birth_time(p).input_datetime.tzinfo is None


@pytest.mark.parametrize("tool", ["ziwei_birth", "ziwei_horoscope"])
@pytest.mark.parametrize("source", ["rule_profile", "naj_ming_v1"])
@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
def test_explicit_birth_and_target_instants_match_rest_native_mcp_cli(
    tool, source, profile, monkeypatch, capsys
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    spec = next(s for s in CATALOG if s.key == tool)
    inputs = {
        **BIRTH,
        "birth_utc_offset": "+09:00",
        "sihua_source": source,
        "rule_profile": profile,
    }
    if tool == "ziwei_horoscope":
        inputs.update(**TARGET, target_utc_offset="+08:00")
    fields = evidence_views(spec)["calendar"]["fields"]
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
    assert run(args) == 0
    cli = json.loads(capsys.readouterr().out)
    bodies = [
        {k: v for k, v in p.items() if k not in ("run_metadata", "result_delivery")}
        for p in [rest.json(), native, cli]
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    basis = bodies[0][tool]["calendar_basis"]
    birth = basis["birth"] if tool == "ziwei_horoscope" else basis
    assert birth["civil_clock"]["instant_utc"] == "1991-09-14T16:30:00+00:00"
    if tool == "ziwei_horoscope":
        assert (
            basis["target"]["civil_clock"]["instant_utc"] == "1991-09-14T17:30:00+00:00"
        )


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
def test_explicit_birth_clock_default_view_keeps_all_stars_inline(profile):
    spec = next(s for s in CATALOG if s.key == "ziwei_birth")

    async def call():
        async with Client(create_mcp_app(families="metaphysics")) as client:
            r = await client.call_tool(
                "ziwei_birth",
                {
                    **BIRTH,
                    "birth_utc_offset": "+08:00",
                    "rule_profile": profile,
                    "sihua_source": "naj_ming_v1",
                    "fields": suggested_fields(spec),
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "as_of": "2026-10-22T12:00:00+08:00",
                },
            )
            assert not r.is_error
            return await verified_inline_business(client, r.structured_content)

    p = asyncio.run(call())
    assert p["analysis_context"]["civil_instant_utc"] == "1991-09-14T17:30:00+00:00"
    stars = [
        s
        for palace in p["ziwei_birth"]["reading_view"]["palaces"]
        for s in palace["stars"]
    ]
    assert len(stars) == (67 if profile == "quanshu_v2_excerpt" else 66)
    assert len([s for s in stars if s.get("mutagen")]) == 4

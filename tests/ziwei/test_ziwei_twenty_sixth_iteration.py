"""A horoscope carries its actual natal bureau derivation in the same run."""

import asyncio
import json
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from pydantic import ValidationError

import fatebridge.api as api
import scripts.ziwei.audit_ziwei_natal_prerequisites as linkage_audit
from fatebridge.application.examples import evidence_views
from fatebridge.application.result_delivery import RESULT_STORE
from fatebridge.cli import run
from fatebridge.core.metaphysics.ziwei import build_ziwei_chart
from fatebridge.core.output_chinese import ZiweiHoroscopeNatalPrerequisites
from fatebridge.core.ziwei_evidence import horoscope_natal_prerequisites
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.metaphysics import (
    _build_person_seed,
    calculate_ziwei_horoscope,
)
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.birth_input import create_person_info


def test_existing_clock_inputs_check_both_profiles_and_sihua_sources():
    report = linkage_audit.audit_natal_prerequisites()
    assert report["reused_frozen_birth_inputs"] == 9
    assert report["profile_source_natal_charts"] == 36
    assert report["conditional_horoscope_receipts_checked"] == 216
    assert not report["differences"]
    assert report["new_independent_calendar_observations"] == 0
    assert report["new_classical_witnesses"] == 0
    assert (
        report["upstream_natal_placement_independently_verified_by_this_audit"] is False
    )


def test_linkage_audit_rejects_foreign_year_stems_and_false_run_metadata(monkeypatch):
    original = linkage_audit.build_ziwei_horoscope

    def corrupted(*args, **kwargs):
        result = original(*args, **kwargs)
        receipt = result["natal_prerequisites"]
        receipt["year_stem"] = "FORGED"
        receipt["separate_birth_run"] = True
        receipt["rule_trace"][2]["inputs"]["year_stem"] = "FORGED"
        return result

    monkeypatch.setattr(linkage_audit, "build_ziwei_horoscope", corrupted)
    report = linkage_audit.audit_natal_prerequisites()
    assert len(report["differences"]) == 216


def _person(**overrides):
    return create_person_info(
        **{
            "birth_year": 2022,
            "birth_month": 7,
            "birth_day": 7,
            "birth_hour": 13,
            "birth_minute": 15,
            "birth_timezone": "Asia/Taipei",
            "gender": "男",
            "use_true_solar_time": False,
            **overrides,
        }
    )


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
@pytest.mark.parametrize("sihua", ["rule_profile", "naj_ming_v1"])
def test_known_r25_bureau_chain_is_available_without_a_second_birth_run(profile, sihua):
    person = _person()
    chart = build_ziwei_chart(
        _build_person_seed(person), "男", rule_profile=profile, sihua_source=sihua
    )
    result = calculate_ziwei_horoscope(
        person,
        target_year=2023,
        target_month=7,
        target_day=8,
        target_hour=10,
        target_minute=5,
        target_timezone="Asia/Taipei",
        rule_profile=profile,
        sihua_source=sihua,
    )["ziwei_horoscope"]
    chain = result["natal_prerequisites"]
    # Previously frozen R25 case 06: a known regression, not a new date oracle.
    assert chain["year_stem"] == "壬"
    assert chain["ming_gong"] == {"name": "命宫", "branch": "子", "ganzhi": "壬子"}
    assert chain["wuxing_ju"] == {
        "number": 3,
        "element": "木",
        "label": "木三局",
        "nayin": "桑柘木",
    }
    assert chain["origin"] == "same_calculation_internal_natal_chart"
    assert chain["separate_birth_run"] is False
    assert chain["classical_birth_year_boundary_verified"] is False
    assert chain["lunar_date"] == chart["lunar_date"]
    assert chain["rule_trace"] == chart["rule_trace"][:3]
    assert chain["ruleset"] == {
        k: v
        for k, v in chart["ruleset"].items()
        if k in {"id", "version", "sihua_source"}
    }
    decade = next(s for s in result["scopes"] if s["scope"] == "大限")
    assert result["nominal_age"] == 2
    assert decade["status"] == "not_started" and decade["first_age"] == 3


def test_default_ruleset_omission_is_preserved_and_nested_traces_are_detached():
    chart = build_ziwei_chart(_build_person_seed(_person()), "男")
    original = deepcopy(chart)
    chain = horoscope_natal_prerequisites(chart)
    assert "sihua_source" not in chart["ruleset"]
    assert "sihua_source" not in chain["ruleset"]
    chain["rule_trace"][2]["outputs"]["source_comparison"]["actual"]["ju_number"] = 99
    chain["ming_gong"]["branch"] = "丑"
    chain["lunar_date"]["year"] = 1900
    assert chart == original
    assert horoscope_natal_prerequisites(chart)["wuxing_ju"]["number"] == 3


@pytest.mark.parametrize("duplicate", [False, True])
def test_missing_or_duplicate_source_steps_are_not_silently_recreated(duplicate):
    chart = build_ziwei_chart(_build_person_seed(_person()), "男")
    if duplicate:
        chart["rule_trace"].append(deepcopy(chart["rule_trace"][0]))
    else:
        chart["rule_trace"].pop(0)
    with pytest.raises(ValueError, match="前置链缺少或重复"):
        horoscope_natal_prerequisites(chart)


@pytest.mark.parametrize(
    "field", ["separate_birth_run", "classical_birth_year_boundary_verified"]
)
def test_receipt_cannot_claim_a_separate_run_or_classical_year_boundary(field):
    with pytest.raises(ValidationError):
        ZiweiHoroscopeNatalPrerequisites.model_validate({field: True})


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
def test_birth_placement_year_stays_distinct_from_age_reference_and_target_year(
    profile,
):
    person = _person(
        birth_year=1984,
        birth_month=2,
        birth_day=1,
        birth_hour=23,
        birth_minute=55,
        birth_timezone="Asia/Shanghai",
        birth_longitude=150,
        use_true_solar_time=True,
    )
    records = []
    for minute, zone, hour, day in [
        (59, "Asia/Shanghai", 23, 1),
        (59, "UTC", 15, 1),
        (0, "Asia/Shanghai", 0, 2),
    ]:
        h = calculate_ziwei_horoscope(
            person,
            target_year=1984,
            target_month=2,
            target_day=day,
            target_hour=hour,
            target_minute=minute,
            target_timezone=zone,
            rule_profile=profile,
        )["ziwei_horoscope"]
        chain = h["natal_prerequisites"]
        assert chain["lunar_date"]["year"] == 1984 and chain["year_stem"] == "甲"
        assert h["nominal_age_calendar"]["birth_lunar_year"] == 1983
        records.append(chain)
    assert records[0] == records[1] == records[2]


def _read_chain(reply):
    assert len(json.dumps(reply, ensure_ascii=False, separators=(",", ":"))) <= 8192
    ref = reply.get("result_delivery")
    if ref is None:
        return reply["ziwei_horoscope"]["natal_prerequisites"]
    offset, parts = 0, []
    while True:
        page = RESULT_STORE.verified_page(
            ref["result_id"],
            ref["sha256"],
            reply["run_metadata"]["run_id"],
            offset=offset,
            path="ziwei_horoscope.natal_prerequisites",
        )
        parts.append(page["text"])
        offset = page["next_offset"]
        if offset is None:
            break
    return json.loads("".join(parts))


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
def test_published_natal_chain_view_is_equal_in_rest_mcp_and_cli(
    profile, monkeypatch, capsys
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    inputs = dict(
        birth_year=2022,
        birth_month=7,
        birth_day=7,
        birth_hour=13,
        birth_minute=15,
        birth_timezone="Asia/Taipei",
        gender="男",
        use_true_solar_time=False,
        target_year=2023,
        target_month=7,
        target_day=8,
        target_hour=10,
        target_minute=5,
        target_timezone="Asia/Taipei",
        rule_profile=profile,
    )
    spec = next(s for s in CATALOG if s.key == "ziwei_horoscope")
    fields = evidence_views(spec)["natal_prerequisites"]["fields"]
    flags = dict(
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=8192,
        as_of="2026-10-22T12:00:00+08:00",
    )
    params = [
        (k, str(v).lower() if isinstance(v, bool) else str(v))
        for k, v in flags.items()
        if k != "fields"
    ]
    params += [("fields", f) for f in fields]
    response = TestClient(api.app).post(spec.rest_path, json=inputs, params=params)
    assert response.status_code == 200, response.text

    async def native():
        async with Client(create_mcp_app(families="metaphysics")) as client:
            r = await client.call_tool("ziwei_horoscope", {**inputs, **flags})
            assert not r.is_error
            return r.structured_content

    args = ["ziwei_horoscope"]
    for key, value in inputs.items():
        args += ["--" + key.replace("_", "-"), str(value)]
    args += [
        "--fields",
        *fields,
        "--strict-fields",
        "--no-include-snapshot-text",
        "--response-char-limit",
        "8192",
        "--as-of",
        flags["as_of"],
    ]
    capsys.readouterr()
    assert run(args) == 0
    cli = json.loads(capsys.readouterr().out)
    values = [_read_chain(r) for r in (response.json(), asyncio.run(native()), cli)]
    assert values[0] == values[1] == values[2]
    assert values[0]["year_stem"] == "壬" and values[0]["wuxing_ju"]["number"] == 3

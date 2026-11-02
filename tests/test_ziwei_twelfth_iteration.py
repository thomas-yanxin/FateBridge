"""Input precision is conditional; receipt checks are not astronomy oracles."""

import asyncio
import json
import shutil
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
import scripts.audit_ziwei_time_input as audit
from fatebridge.application.examples import evidence_views
from fatebridge.cli import run
from fatebridge.core.ziwei_calendar import calendar_basis
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.metaphysics import (
    _build_person_seed,
    calculate_ziwei_birth,
    calculate_ziwei_horoscope,
)
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.birth_input import create_person_info
from fatebridge.utils.solar_time import normalize_birth_time
from scripts.audit_ziwei_limits import _seed
from tests.fixtures.mcp_receipt import verified_inline_business

BIRTH = dict(
    birth_year=2000,
    birth_month=12,
    birth_day=10,
    birth_hour=10,
    birth_minute=54,
    gender="男",
)


def test_receipt_audit_does_not_count_propagation_as_astronomical_certification():
    r = audit.audit_time_input()
    assert r["conditional_input_cases"] == 9
    assert r["profile_receipts_checked"] == 18
    assert not r["differences"]
    assert r["independent_astronomical_vectors"] == 0
    assert not r["historical_birth_clock_certified"]
    assert not r["full_calendar_acceptance_passed"]


def test_false_applied_status_cannot_pass_audit(monkeypatch):
    original = audit.calculate_ziwei_birth

    def wrong(*args, **kwargs):
        r = deepcopy(original(*args, **kwargs))
        r["ziwei_birth"]["calendar_basis"]["time_input"]["applied"] = True
        return r

    monkeypatch.setattr(audit, "calculate_ziwei_birth", wrong)
    assert len(audit.audit_time_input()["differences"]) == 8


def test_time_input_source_checksum_is_required(tmp_path):
    shutil.copy(audit.FIXTURES / "time_input_manifest.json", tmp_path)
    manifest = json.loads((tmp_path / "time_input_manifest.json").read_text())
    (tmp_path / manifest["source_documents"][0]["path"]).write_text("changed")
    with pytest.raises(ValueError, match="Time input source checksum mismatch"):
        audit.audit_time_input(tmp_path)


def receipt(**kwargs):
    result = calculate_ziwei_birth(create_person_info(**{**BIRTH, **kwargs}))
    assert "error" not in result, result
    return result, result["ziwei_birth"]["calendar_basis"]["time_input"]


@pytest.mark.parametrize(
    "extra,source,assumed",
    [
        ({"birth_timezone": "Asia/Shanghai"}, "birth_timezone", False),
        ({"birth_place": "杭州"}, "birth_place", False),
        ({"birth_longitude": 120.47}, "longitude_standard_meridian_assumption", True),
        ({}, "default_timezone", True),
    ],
)
def test_receipt_preserves_actual_timezone_selection(extra, source, assumed):
    _, r = receipt(use_true_solar_time=False, **extra)
    assert r["timezone_source"] == source
    assert r["timezone_assumed"] is assumed
    assert bool(r["advisories"]) is assumed
    assert r["components_computed"] is False
    assert r["equation_of_time_minutes"] is None
    assert r["daylight_saving_minutes"] is None
    assert r["total_correction_minutes"] == r["applied_delta_seconds"] == 0
    assert r["seconds_are_derived_not_birth_accuracy"]


def test_explicit_longitude_does_not_hide_place_resolved_timezone():
    _, r = receipt(birth_place="杭州", birth_longitude=120.47)
    assert r["longitude_source"] == "birth_longitude"
    assert r["resolved_place"] is None
    assert r["timezone_source"] == "birth_place"
    assert "杭州" in r["timezone_resolved_place"]
    _, explicit = receipt(
        birth_place="杭州", birth_timezone="+09:00", birth_longitude=120.47
    )
    assert explicit["timezone_source"] == "birth_timezone"
    assert explicit["timezone"] == "+09:00"
    assert explicit["timezone_resolved_place"] is None


def test_shared_normalizer_serialization_remains_opt_in():
    p = create_person_info(**BIRTH, birth_place="杭州")
    n = normalize_birth_time(p)
    assert "timezone_source" not in n.as_dict()
    expanded = n.as_dict(include_timezone_resolution=True)
    assert expanded.pop("timezone_source") == "birth_place"
    assert expanded.pop("timezone_resolved_place")
    assert expanded == n.as_dict()


def test_requested_solar_fallback_differs_from_explicit_civil_clock():
    result, fallback = receipt(
        birth_timezone="Asia/Shanghai",
        use_true_solar_time=True,
        true_solar_explicit=False,
    )
    assert fallback["status"] == "solar_unavailable"
    assert fallback["requested"] and not fallback["explicitly_requested"]
    assert not fallback["applied"] and not fallback["components_computed"]
    assert fallback["advisories"]
    assert result["analysis_context"]["time_input_status"] == "solar_unavailable"
    assert fallback["advisories"][0] in result["snapshot_text"]
    _, civil = receipt(birth_timezone="Asia/Shanghai", use_true_solar_time=False)
    assert civil["status"] == "civil_clock_selected"
    assert not civil["requested"] and not civil["advisories"]
    # None means not evaluated, not an assertion of astronomical zero.
    assert (
        fallback["equation_of_time_minutes"]
        is civil["equation_of_time_minutes"]
        is None
    )


def test_explicit_solar_without_longitude_still_rejects_missing_input():
    result = calculate_ziwei_birth(
        create_person_info(**BIRTH, use_true_solar_time=True, true_solar_explicit=True)
    )
    assert "error" in result
    assert "birth_longitude" in result["error"]


def test_province_approximation_can_change_hour_and_must_not_claim_error_bound():
    coarse, c = receipt(
        birth_place="江苏省未收录地点",
        birth_timezone="Asia/Shanghai",
        use_true_solar_time=True,
    )
    precise, p = receipt(
        birth_place="江苏省未收录地点",
        birth_timezone="Asia/Shanghai",
        birth_longitude=120.47,
        use_true_solar_time=True,
    )
    assert c["status"] == "province_longitude"
    assert c["resolution_level"] == "province"
    assert "误差界未量化" in c["resolution_advisory"]
    assert c["resolution_advisory"] in coarse["snapshot_text"]
    assert coarse["ziwei_birth"]["hour_branch"] == "巳"
    assert precise["ziwei_birth"]["hour_branch"] == "午"
    assert p["status"] == "solar_applied" and not p["advisories"]
    # Equal physical clock => equal EOT. Longitude sensitivity is 4 min/degree.
    assert p["equation_of_time_minutes"] == c["equation_of_time_minutes"]
    assert (
        p["applied_delta_seconds"] - c["applied_delta_seconds"]
    ) / 60 == pytest.approx(4 * (p["longitude"] - c["longitude"]), abs=1e-6)


def test_receipt_carries_actual_dst_and_pinned_timezone_rules():
    result, r = receipt(
        birth_year=1990,
        birth_month=7,
        birth_day=1,
        birth_timezone="Asia/Shanghai",
        birth_longitude=120,
        use_true_solar_time=True,
    )
    assert r["daylight_saving_minutes"] == 60
    assert r["timezone_rules"]["database"] == "pytz"
    assert len(r["timezone_rules"]["tzif_sha256"]) == 64
    assert r["equation_of_time_time_scale"] == "UTC_as_UT1"
    assert not result["ziwei_birth"]["calendar_basis"]["classical_clock_rule_verified"]


def test_receipt_is_copied_and_synthetic_inputs_do_not_fabricate_provenance():
    seed = _build_person_seed(
        create_person_info(**BIRTH, birth_place="杭州", use_true_solar_time=True)
    )
    expected = deepcopy(seed.birth_time_normalization)
    b = calendar_basis(seed)
    assert b["time_input"] == expected
    b["time_input"]["advisories"].append("changed")
    assert seed.birth_time_normalization == expected
    assert calendar_basis(_seed(1984))["time_input"] is None


@pytest.mark.parametrize("tool", ["ziwei_birth", "ziwei_horoscope"])
@pytest.mark.parametrize(
    "extra,status",
    [
        ({}, "solar_unavailable"),
        ({"use_true_solar_time": False}, "civil_clock_selected"),
        ({"birth_place": "江苏省未收录地点"}, "province_longitude"),
    ],
)
def test_default_input_and_receipt_survive_rest_mcp_cli(
    tool, extra, status, monkeypatch, capsys
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    fields = evidence_views(next(s for s in CATALOG if s.key == tool))["time_input"][
        "fields"
    ]
    inputs = {**BIRTH, "birth_timezone": "Asia/Shanghai", **extra}
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
            *[("fields", f) for f in fields],
        ],
    )

    async def call():
        async with Client(create_mcp_app(families="metaphysics")) as client:
            native = await client.call_tool(
                tool, {**inputs, **opts}, raise_on_error=False
            )
            assert not native.is_error, native.content
            return await verified_inline_business(client, native.structured_content)

    native = asyncio.run(call())
    args = [tool]
    for name, value in inputs.items():
        args += ["--" + name.replace("_", "-"), str(value)]
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
    basis = bodies[0][tool]["calendar_basis"]
    r = (basis if tool == "ziwei_birth" else basis["birth"])["time_input"]
    assert r["status"] == status
    assert r["requested"] == (extra.get("use_true_solar_time") is not False)
    assert not r["explicitly_requested"]


def test_horoscope_reuses_birth_receipt_without_inventing_target_precision():
    p = create_person_info(
        **BIRTH, birth_timezone="Asia/Shanghai", use_true_solar_time=False
    )
    r = calculate_ziwei_horoscope(
        p, target_year=2026, target_month=10, target_day=22, target_hour=12
    )
    b = r["ziwei_horoscope"]["calendar_basis"]
    assert b["birth"]["time_input"]["status"] == "civil_clock_selected"
    assert b["target"]["time_input"] is None

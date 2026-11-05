"""Civil/reference dates and solar placement labels must stay distinguishable."""

import asyncio
import json
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
import scripts.audit_ziwei_clock as audit
from fatebridge.application.examples import evidence_views
from fatebridge.cli import run
from fatebridge.core.almanac import get_adjacent_solar_terms
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.metaphysics import (
    _build_person_seed,
    calculate_ziwei_birth,
    calculate_ziwei_horoscope,
)
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.birth_input import create_person_info
from scripts.audit_ziwei import FIXTURES, hko_rows

MANIFEST = json.loads((FIXTURES / "clock_manifest.json").read_text())
BIRTH = MANIFEST["cases"][0]["input"]
TARGET = dict(target_year=2027, target_month=6, target_day=15, target_hour=12)


def test_clock_receipts_keep_external_day_cells_and_unverified_age_boundary():
    r = audit.audit_clock_basis(hko_rows, FIXTURES)
    assert r["independent_input_cases"] == 9
    assert r["profile_receipts_checked"] == 18
    assert not r["differences"]
    assert not r["full_clock_acceptance_passed"]
    assert not r["classical_clock_policy_verified"]
    assert len(r["civil_age_boundary_receipts"]) == 2
    assert all(all(x["checks"].values()) for x in r["civil_age_boundary_receipts"])


def test_clock_audit_rejects_wrong_reference_date_instead_of_learning_it(monkeypatch):
    original = audit.calculate_ziwei_birth

    def wrong(*args, **kwargs):
        result = deepcopy(original(*args, **kwargs))
        result["ziwei_birth"]["calendar_basis"]["reference_lunar_date"]["day"] = 17
        return result

    monkeypatch.setattr(audit, "calculate_ziwei_birth", wrong)
    assert len(audit.audit_clock_basis(hko_rows, FIXTURES)["differences"]) == 18


def test_clock_source_checksum_is_required(tmp_path):
    (tmp_path / "clock_manifest.json").write_bytes(
        (FIXTURES / "clock_manifest.json").read_bytes()
    )
    (tmp_path / "calendar_manifest.json").write_bytes(
        (FIXTURES / "calendar_manifest.json").read_bytes()
    )
    (tmp_path / MANIFEST["source_documents"][0]["path"]).write_text("changed")
    with pytest.raises(ValueError, match="Clock source checksum mismatch"):
        audit.audit_clock_basis(hko_rows, tmp_path)


def test_solar_label_is_not_reinterpreted_as_a_different_seasonal_instant():
    seed = _build_person_seed(
        create_person_info(
            birth_year=2024,
            birth_month=2,
            birth_day=4,
            birth_hour=17,
            birth_timezone="Asia/Shanghai",
            birth_longitude=75,
            use_true_solar_time=True,
            gender="男",
        )
    )
    assert seed.corrected_datetime.hour < 15
    assert seed.calendar_context["current_solar_term"]["name"] == "立春"
    # Treating that solar label as a second civil instant gives a different
    # seasonal result. This is an invariant check, not a new term-time oracle.
    previous, _ = get_adjacent_solar_terms(seed.corrected_datetime, seed.timezone)
    assert previous.name == "大寒"


def test_cny_receipt_does_not_overwrite_calculated_chart_or_hide_date_difference():
    result = calculate_ziwei_birth(create_person_info(**BIRTH))
    chart, context = result["ziwei_birth"], result["analysis_context"]
    b = chart["calendar_basis"]
    assert (
        b["placement_lunar_date"]
        == chart["lunar_date"]
        == dict(year=1984, month=1, day=1, is_leap_month=False)
    )
    assert b["civil_date_lunar_date"] == dict(
        year=1983, month=12, day=30, is_leap_month=False
    )
    assert b["reference_lunar_date"] == b["civil_date_lunar_date"]
    assert context["calendar_date_shift_days"] == 1
    assert context["lunar_date_basis"] == "apparent_solar_date_label_at_midnight"
    assert "相对钟表日期偏移+1日" in result["snapshot_text"]
    assert not b["classical_clock_rule_verified"]


def test_physical_prebirth_guard_and_current_civil_age_use_actual_endpoints():
    person = create_person_info(**BIRTH)
    earlier = calculate_ziwei_horoscope(
        person,
        target_year=1984,
        target_month=2,
        target_day=1,
        target_hour=23,
        target_minute=54,
    )
    later = calculate_ziwei_horoscope(
        person,
        target_year=1984,
        target_month=2,
        target_day=1,
        target_hour=23,
        target_minute=59,
    )
    assert "目标时刻早于出生时刻" in earlier["error"]
    horoscope = later["ziwei_horoscope"]
    receipt = horoscope["nominal_age_calendar"]
    assert horoscope["nominal_age"] == 1
    assert receipt["basis"] == "birth_civil_timezone"
    assert receipt["birth_placement_lunar_year"] == 1984
    assert receipt["birth_lunar_year"] == receipt["target_lunar_year"] == 1983
    assert receipt["physical_order_checked"]
    assert not receipt["age_boundary_classically_verified"]


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
@pytest.mark.parametrize(
    "key,path", [("ziwei_birth", "birth"), ("ziwei_horoscope", "horoscope")]
)
def test_calendar_evidence_is_typed_and_equal_in_rest_native_mcp_cli(
    profile, key, path, monkeypatch, capsys
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    spec = next(s for s in CATALOG if s.key == key)
    fields = evidence_views(spec)["calendar"]["fields"]
    inputs = {
        **BIRTH,
        "rule_profile": profile,
        **(TARGET if path == "horoscope" else {}),
    }
    options = dict(
        as_of="2026-10-22T12:00:00+08:00",
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
    )
    rest = TestClient(api.app).post(
        "/api/cn/ziwei/" + path,
        json=inputs,
        params=[
            ("as_of", options["as_of"]),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
            *[("fields", f) for f in fields],
        ],
    )

    async def call():
        async with Client(create_mcp_app(families="metaphysics")) as client:
            return await client.call_tool(
                key, {**inputs, **options}, raise_on_error=False
            )

    native = asyncio.run(call())
    args = [key]
    for name, value in inputs.items():
        args += ["--" + name.replace("_", "-"), str(value)]
    args += [
        "--as-of",
        options["as_of"],
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
    bodies = [
        {k: v for k, v in payload.items() if k != "run_metadata"}
        for payload in (rest.json(), native.structured_content, cli)
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    b = bodies[0][key]["calendar_basis"]
    if path == "horoscope":
        assert b["target"]["placement_clock"] == "civil"
        assert (
            b["nominal_age_rule"]
            == "target_lunar_year_in_birth_timezone_minus_birth_civil_lunar_year_plus_one"
        )
        b = b["birth"]
    assert b["date_shift_days"] == 1
    assert b["placement_lunar_date"]["year"] == 1984
    assert b["civil_date_lunar_date"]["year"] == 1983

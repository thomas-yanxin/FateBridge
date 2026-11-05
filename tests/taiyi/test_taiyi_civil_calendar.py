"""Independent civil labels, same-board source fidelity and actual transports."""

import asyncio
import hashlib
import json
import shutil
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from pydantic import ValidationError

import fatebridge.api as api
from fatebridge.application.examples import suggested_fields
from fatebridge.core.almanac import get_lunar_context
from fatebridge.core.metaphysics import taiyi_year
from fatebridge.core.output_chinese import Taiyi
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.metaphysics import calculate_taiyi_analysis
from scripts.taiyi.audit_taiyi_civil_calendar import (
    CORPUS,
    audit,
    public_input,
    verify_sources,
)
from tests.support.transports import SPECS, business, call_cli
from tests.taiyi.test_taiyi_periods import seed_at
from tests.taiyi.test_taiyi_transports import _same_run_payload

CASES = json.loads((CORPUS / "cases.json").read_text())["cases"]


@pytest.fixture
def rest(monkeypatch):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    return TestClient(api.app)


def test_frozen_institutional_rows_and_original_cases_are_retained():
    verify_sources()
    assert [c["id"] for c in CASES] == [
        "prefix_1900",
        "new_year_2026",
        "supplement_2100",
    ]
    for year, month, day in [(2026, 2, 17), (2100, 2, 9)]:
        rows = (CORPUS / f"hko-{year}.txt").read_text()
        row = next(
            s for s in rows.splitlines() if s.startswith(f"{year}年{month}月{day}日 ")
        )
        assert "正月" in row
    pmo = (CORPUS / "pmo-1900-source-pages.txt").read_text()
    assert "1    十二月 初一 甲戌" in pmo and "己亥年 ~ 庚子年" in pmo


@pytest.mark.parametrize("update_freeze", [False, True])
def test_source_or_expectation_tampering_cannot_change_original_acceptance(
    tmp_path, update_freeze
):
    corpus = tmp_path / "corpus"
    shutil.copytree(CORPUS, corpus)
    target = corpus / "cases.json"
    data = json.loads(target.read_text())
    data["cases"][0]["expected_lunar"][0] = 1900
    target.write_text(json.dumps(data))
    if update_freeze:
        path = corpus / "freeze.json"
        freeze = json.loads(path.read_text())
        freeze["files"][target.name] = hashlib.sha256(target.read_bytes()).hexdigest()
        path.write_text(json.dumps(freeze))
    with pytest.raises(ValueError, match="V27"):
        verify_sources(corpus)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
@pytest.mark.parametrize("solar", [False, True])
def test_year_uses_input_civil_lunar_date_and_keeps_actual_source(case, solar):
    result = calculate_taiyi_analysis(**public_input(case, solar=solar))
    assert "taiyi" in result, result
    board = result["taiyi"]
    lunar = board["calendar_rules"]["civil_lunar_calendar"]
    assert [lunar[k] for k in ("year", "month", "day", "is_leap_month")] == case[
        "expected_lunar"
    ]
    shared = get_lunar_context(
        datetime(case["year"], case["month"], case["day"]), timezone_name="+08:00"
    )
    assert lunar["conversion_source"] == shared.get("conversion_source")
    assert (lunar["conversion_source"] or {}).get("method_id") == case[
        "expected_source"
    ]
    assert board["calendar_rules"]["year"] == case["expected_lunar"][0]
    assert board["calendar_summary"]["used_lunar_date"] == lunar["display"]
    text = result["snapshot_text"]
    assert text.startswith(f"[起盘信息]\n年计所用农历：{lunar['display']}\n输入钟时：")
    assert (
        f"输入钟时：{result['analysis_context']['input_datetime'].replace(' ', 'T')}"
        in text
    )
    assert f"计算钟面：{result['analysis_context']['corrected_datetime']}" in text
    assert "\n直接时间：" not in text
    if solar:
        assert (
            result["analysis_context"]["corrected_datetime"][:10] < lunar["civil_date"]
        )
        assert (
            result["analysis_context"]["lunar_display"]
            != lunar["display"].split("年", 1)[1]
        )
    Taiyi.model_validate(board)
    assert board["ruleset"]["classical_acceptance_passed"] is False


def test_stored_source_is_a_copy_of_the_one_conversion_already_used(monkeypatch):
    seed = seed_at(datetime(2026, 2, 17, 0, 5), zone="+08:00", solar=True, longitude=0)
    source = get_lunar_context(seed.input_datetime, timezone_name=seed.timezone)
    source["conversion_source"] = {
        "publisher": "test provider",
        "title": "fictional",
        "url": "https://example.invalid",
        "extension": {"untouched": [1, 2, 3]},
    }
    calls = []

    def selected_lunar(*args, **kwargs):
        calls.append((args, kwargs))
        return source

    monkeypatch.setattr(taiyi_year, "get_lunar_context", selected_lunar)
    board = taiyi_year.build_year_board(seed, "未知")
    assert len(calls) == 1
    evidence = board["calendar_rules"]["civil_lunar_calendar"]
    assert evidence["conversion_source"] == source["conversion_source"]
    source["conversion_source"]["extension"]["untouched"].append(4)
    assert evidence["conversion_source"]["extension"]["untouched"] == [1, 2, 3]
    # Rendering reads the same board; no hidden recalculation for the text.
    assert "2026年正月初一" in taiyi_year.evidence_text(board)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("year", "2026"),
        ("year", True),
        ("month", False),
        ("day", "1"),
        ("is_leap_month", 0),
        ("conversion_source", "HKO"),
    ],
)
def test_new_output_facts_are_strict_and_projection_compatible(field, value):
    Taiyi.model_validate({"calendar_rules": {"civil_lunar_calendar": {"year": 2026}}})
    with pytest.raises(ValidationError):
        Taiyi.model_validate(
            {"calendar_rules": {"civil_lunar_calendar": {field: value}}}
        )


def test_boundary_audit_separates_local_fix_from_full_calendar_acceptance():
    report = audit()
    assert report["fictional_boundary_cases"] == report["matching_calendar_dates"] == 3
    assert report["civil_date_evidence_and_text_checks_passed"] is True
    assert report["new_dated_classical_cases"] == 0
    assert (
        report["whole_goal_complete"]
        is report["full_ancient_calendar_reconstructed"]
        is False
    )


@pytest.mark.parametrize("key", ["taiyi", "sanshiunited"])
@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_actual_rest_mcp_cli_preserve_calendar_evidence_and_both_clocks(
    rest, tmp_path, capsys, key, case
):
    spec = SPECS[key]
    data = (
        public_input(case)
        if key == "taiyi"
        else {
            "date": f"{case['year']:04}-{case['month']:02}-{case['day']:02}",
            "time": "00:05:00",
            "zone": "+08:00",
            "gps_lon": 0.0,
            "use_true_solar_time": True,
        }
    )
    view = "year_calendar" if key == "taiyi" else "taiyi_year_calendar"
    fields = suggested_fields(spec, view=view)
    flags = [
        "--strict-fields",
        "true",
        "--include-snapshot-text",
        "false",
        "--fields",
        *fields,
    ]
    params = [
        ("as_of", "2026-10-12T02:00:00Z"),
        ("strict_fields", "true"),
        ("include_snapshot_text", "false"),
        *[("fields", f) for f in fields],
    ]
    http = rest.post(spec.rest_path, json=data, params=params)
    code, cli = call_cli(spec, data, tmp_path, capsys, flags=flags)
    assert http.status_code == 200 and code == 0

    async def protocol():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                spec.tool_name,
                {
                    **data,
                    "as_of": "2026-10-12T02:00:00Z",
                    "fields": fields,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
                raise_on_error=False,
            )
            body = await _same_run_payload(client, result, require_business_inline=True)
            # Separately fetch snapshot evidence from its own same-run payload.
            result_text = await client.call_tool(
                spec.tool_name,
                {**data, "fields": [*fields, "snapshot_text"], "strict_fields": True},
                raise_on_error=False,
            )
            full_text = await _same_run_payload(client, result_text)
            return body, full_text

    protocol_body, text_body = asyncio.run(protocol())
    # REST/CLI delivery references are transport-specific, so retrieve using the
    # retained application run rather than comparing references or recomputing.
    from fatebridge.application.result_delivery import RESULT_STORE

    def retained(body):
        ref = body.get("result_delivery")
        return RESULT_STORE.get(ref["result_id"]) if ref else body

    bodies = [retained(http.json()), retained(cli), protocol_body]
    assert business(bodies[0]) == business(bodies[1]) == business(bodies[2])
    lunar = protocol_body["taiyi"]["calendar_rules"]["civil_lunar_calendar"]
    assert [lunar[k] for k in ("year", "month", "day", "is_leap_month")] == case[
        "expected_lunar"
    ]
    assert f"年计所用农历：{lunar['display']}" in text_body["snapshot_text"]
    assert (
        "输入钟时：" in text_body["snapshot_text"]
        and "计算钟面：" in text_body["snapshot_text"]
    )


@pytest.mark.parametrize("key", ["taiyi", "sanshiunited"])
def test_new_year_view_preserves_selected_historical_calendar(key):
    from tests.taiyi.test_taiyi_year_calendar import payload

    spec = SPECS[key]
    data = payload(key, day="0385-01-28")
    view = "year_calendar" if key == "taiyi" else "taiyi_year_calendar"

    async def protocol():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                spec.tool_name,
                {
                    **data,
                    "fields": suggested_fields(spec, view=view),
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
                raise_on_error=False,
            )
            return await _same_run_payload(client, result, require_business_inline=True)

    body = asyncio.run(protocol())
    calendar = body["taiyi"]["calendar_rules"]
    assert "civil_lunar_calendar" not in calendar
    assert calendar["historical_calendar"]["year"] == calendar["year"] == 385
    assert calendar["historical_calendar"]["civil_date"] == "0385-01-28"
    assert (
        body["taiyi"]["calendar_summary"]["used_lunar_date"]
        == calendar["historical_calendar"]["display"]
    )
    Taiyi.model_validate(body["taiyi"])

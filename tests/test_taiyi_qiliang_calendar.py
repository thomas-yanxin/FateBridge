"""Printed Qi/Liang dates and faithful source conflicts across public surfaces."""

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
from fatebridge.core.metaphysics.taiyi_year_calendar import (
    HISTORICAL_YEAR_PROFILE,
    QILIANG_YEAR_PROFILE,
    historical_year_context,
)
from fatebridge.core.output_chinese import Taiyi
from fatebridge.core.output_taiyi_year_calendar import (
    TaiyiHistoricalCalendarDisagreement,
    TaiyiHistoricalLeapHypothesis,
)
from fatebridge.core.requests.metaphysics import TaiyiAnalysisRequest
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.metaphysics import calculate_taiyi_analysis
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import ParameterError
from scripts.audit_taiyi_qiliang_calendar import (
    CORPUS,
    FREEZE_SHA256,
    audit,
    public_case,
    verify_sources,
)
from tests.test_taiyi_enclosures import resolve
from tests.test_taiyi_transports import _same_run_payload


@pytest.fixture(scope="module")
def report():
    return audit()


def payload(key, day="0502-05-24", mode="year"):
    d = date.fromisoformat(day)
    if key == "taiyi":
        return {
            "analysis_year": d.year,
            "analysis_month": d.month,
            "analysis_day": d.day,
            "analysis_hour": 12,
            "analysis_timezone": "+08:00",
            "use_true_solar_time": False,
            "calculation_mode": mode,
            "year_profile": QILIANG_YEAR_PROFILE,
        }
    return {
        "date": day,
        "time": "12:00:00",
        "zone": "+08:00",
        "use_true_solar_time": False,
        "taiyi_options": {
            "calculation_mode": mode,
            "year_profile": QILIANG_YEAR_PROFILE,
        },
    }


def cli_args(key, values):
    args = [key]
    for name, value in values.items():
        args += [
            "--" + name.replace("_", "-"),
            json.dumps(value) if isinstance(value, dict) else str(value),
        ]
    return args


def rest_client(monkeypatch):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    return TestClient(api.app)


def test_full_source_mapping_is_separate_from_ancient_calendar_acceptance(report):
    frozen = verify_sources()
    assert (
        hashlib.sha256((CORPUS / "freeze.json").read_bytes()).hexdigest()
        == FREEZE_SHA256
    )
    assert len(frozen["files"]) == 2 and len(frozen["prior_sources"]) == 71
    assert (
        len(report["source_mapping"]) == len(report["month_first_observations"]) == 63
    )
    assert report["required_days"] == report["matching_dates"] == 1831
    assert report["selected_printed_table_mapping_passed"]
    assert len(report["software_baseline_comparisons"]) == 16
    for comparison in report["software_baseline_comparisons"]:
        assert (
            comparison["full_result_identical"]
            is comparison["before_repair_historical_identical"]
        )
        assert comparison["before_repository_repair_full_result_identical"]
    assert not any(
        r["full_result_identical"] for r in report["software_baseline_comparisons"]
    )
    assert all(
        r["passed"] and not r["classic_acceptance_passed"]
        for r in report["new_public_service_examples"]
    )
    assert (
        report["new_independent_taiyi_cases"]
        == report["new_complete_dated_classical_cases_passed"]
        == 0
    )
    assert not report["wang_day_accumulation_restored"]
    assert (
        not report["whole_calendar_acceptance_passed"]
        and not report["whole_goal_complete"]
    )


@pytest.mark.parametrize("rewrite_manifest", [False, True])
def test_software_capture_or_source_expectations_cannot_be_rewritten(
    tmp_path, rewrite_manifest
):
    copied = tmp_path / "corpus"
    shutil.copytree(CORPUS, copied)
    p = copied / "readings.json"
    data = json.loads(p.read_text())
    data["known_leaps"][0] = [502, 5]
    p.write_text(json.dumps(data))
    if rewrite_manifest:
        manifest = json.loads((copied / "freeze.json").read_text())
        manifest["files"][p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
        (copied / "freeze.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="V36"):
        verify_sources(copied)


@pytest.mark.parametrize(
    "day,year",
    [
        ("0501-02-06", 501),
        ("0502-01-26", 502),
        ("0503-02-14", 503),
        ("0504-02-03", 504),
        ("0505-01-23", 505),
    ],
)
def test_each_year_boundary_uses_input_civil_date_on_public_service(day, year):
    d = date.fromisoformat(day)
    after = public_case(d)["taiyi"]
    assert after["calendar_rules"]["year"] == year
    current = after["calendar_rules"]["historical_calendar"]
    assert (current["month"], current["day"], current["is_leap_month"]) == (1, 1, False)
    before = public_case(d - timedelta(days=1))
    if year == 501:
        assert "taiyi" not in before and "仅覆盖" in before["error"]
    else:
        assert before["taiyi"]["calendar_rules"]["year"] == year - 1
        assert (
            after["core_board"]["accumulation"]
            - before["taiyi"]["core_board"]["accumulation"]
            == 1
        )


@pytest.mark.parametrize(
    "day,month,expected_ganzhi", [("0502-05-24", 4, "戊子"), ("0505-03-23", 2, "壬寅")]
)
def test_printed_leap_month_and_unadjudicated_alternatives_are_both_visible(
    day, month, expected_ganzhi
):
    result = public_case(date.fromisoformat(day))
    h = result["taiyi"]["calendar_rules"]["historical_calendar"]
    assert (h["month"], h["day"], h["is_leap_month"], h["day_ganzhi"]) == (
        month,
        1,
        True,
        expected_ganzhi,
    )
    disagreement = h["source_disagreements"][0]
    assert disagreement["printed_leap_month"] == 4
    assert [r["leap_month"] for r in disagreement["alternative_hypotheses"]] == [5, 6]
    assert not disagreement["adjudicated"]
    assert disagreement["affects_selected_year"] == (h["year"] == 502)
    assert "历表分歧" in result["snapshot_text"] and "未裁定" in result["snapshot_text"]
    assert "不裁定朝代移交及改元发生日" == h["year_label_basis"].split("；")[1]
    assert "史历表" in h["display"] and "晋太元" not in h["display"]


def test_liang_day8_calendar_fact_is_not_relabelled_as_a_restored_wang_day_chart():
    r = public_case(date(504, 7, 7))
    b = r["taiyi"]
    h = b["calendar_rules"]["historical_calendar"]
    assert (h["month"], h["day"], h["day_ganzhi"]) == (6, 8, "癸未")
    assert b["calendar_summary"]["calculation_mode"] == "year"
    assert b["calendar_rules"]["year_profile"] == QILIANG_YEAR_PROFILE
    assert not b["ruleset"]["classical_acceptance_passed"]
    assert h["source_month_start_julian"] == "0504-06-28"
    assert (
        public_case(date(504, 7, 5))["taiyi"]["calendar_rules"]["historical_calendar"][
            "day"
        ]
        == 6
    )


def test_solar_clock_crossing_does_not_replace_source_year_or_auto_select_profile():
    r = calculate_taiyi_analysis(
        analysis_year=504,
        analysis_month=2,
        analysis_day=3,
        analysis_hour=0,
        analysis_minute=1,
        analysis_timezone="+08:00",
        analysis_longitude=0,
        use_true_solar_time=True,
        year_profile=QILIANG_YEAR_PROFILE,
    )
    assert r["taiyi"]["calendar_rules"]["year"] == 504
    assert (
        r["taiyi"]["calendar_rules"]["historical_calendar"]["civil_date"]
        == "0504-02-03"
    )
    assert r["taiyi"]["calendar_rules"]["solar_correction_affects_year"] is False
    default = calculate_taiyi_analysis(
        analysis_year=504,
        analysis_month=2,
        analysis_day=3,
        analysis_hour=12,
        analysis_timezone="+08:00",
    )
    assert "taiyi" not in default and "error" in default
    with pytest.raises(ValueError, match="仅覆盖"):
        historical_year_context(date(504, 7, 7), profile=HISTORICAL_YEAR_PROFILE)
    old = historical_year_context(date(385, 7, 1))
    assert "source_disagreements" not in old and "晋太元" in old["display"]


def test_mutating_a_public_response_cannot_pollute_cached_source_evidence():
    first = calculate_taiyi_analysis(**payload("taiyi"))
    evidence = first["taiyi"]["calendar_rules"]["historical_calendar"]
    digest = evidence["source_data_sha256"]
    evidence["source_disagreements"][0]["alternative_hypotheses"][0]["leap_month"] = 99
    evidence["source_disagreements"][0]["alternative_hypotheses"].append(
        {"method": "caller_note", "leap_month": 12}
    )
    evidence["source_disagreements"].clear()
    second = calculate_taiyi_analysis(**payload("taiyi"))
    fresh = second["taiyi"]["calendar_rules"]["historical_calendar"]
    assert fresh["source_data_sha256"] == digest
    assert len(fresh["source_disagreements"]) == 1
    disagreement = fresh["source_disagreements"][0]
    assert disagreement["printed_leap_month"] == 4
    assert [h["leap_month"] for h in disagreement["alternative_hypotheses"]] == [5, 6]
    assert not disagreement["adjudicated"]
    assert "闰五月／六月" in second["snapshot_text"]
    Taiyi.model_validate(second["taiyi"])


def test_mutating_mcp_evidence_cannot_change_the_next_sanshi_response():
    fields = ["taiyi.calendar_rules.historical_calendar"]

    async def invoke():
        async with Client(create_mcp_app()) as client:
            first = await client.call_tool(
                "taiyi",
                {
                    **payload("taiyi"),
                    "fields": fields,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            )
            assert not first.is_error
            evidence = first.structured_content["taiyi"]["calendar_rules"][
                "historical_calendar"
            ]
            source_digest = evidence["source_data_sha256"]
            evidence["source_disagreements"][0]["alternative_hypotheses"][0][
                "leap_month"
            ] = 99
            second = await client.call_tool(
                "sanshiunited",
                {
                    **payload("sanshiunited"),
                    "fields": fields,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            )
            assert not second.is_error
            actual = second.structured_content["taiyi"]["calendar_rules"][
                "historical_calendar"
            ]
            assert actual["source_data_sha256"] == source_digest
            assert [
                h["leap_month"]
                for h in actual["source_disagreements"][0]["alternative_hypotheses"]
            ] == [5, 6]

    asyncio.run(invoke())


def test_every_new_source_leaf_can_be_projected_and_is_typed():
    board = public_case(date(502, 5, 24))["taiyi"]
    h = board["calendar_rules"]["historical_calendar"]
    paths = ["taiyi.calendar_rules.historical_calendar." + key for key in h]
    for path in paths:
        projected = project_fields({"taiyi": board}, [path], strict_fields=True)
        Taiyi.model_validate(projected["taiyi"])
        assert resolve(projected, path) == resolve({"taiyi": board}, path)
    # Shared projection traverses objects only; arrays are selected whole.
    for key, value in h["source_disagreements"][0].items():
        TaiyiHistoricalCalendarDisagreement.model_validate({key: value})
        with pytest.raises(ParameterError, match="输出字段投影无效"):
            project_fields(
                {"taiyi": board},
                [
                    "taiyi.calendar_rules.historical_calendar.source_disagreements."
                    + key
                ],
                strict_fields=True,
            )
    for hypothesis in h["source_disagreements"][0]["alternative_hypotheses"]:
        for key, value in hypothesis.items():
            TaiyiHistoricalLeapHypothesis.model_validate({key: value})
    bad = json.loads(json.dumps(board))
    bad["calendar_rules"]["historical_calendar"]["source_disagreements"][0][
        "adjudicated"
    ] = True
    with pytest.raises(ValueError):
        Taiyi.model_validate(bad)
    schema = TaiyiAnalysisRequest.model_json_schema()["properties"]["year_profile"]
    assert QILIANG_YEAR_PROFILE in schema["anyOf"][0]["enum"]


@pytest.mark.parametrize("key", ["taiyi", "sanshiunited"])
@pytest.mark.parametrize(
    "day,expected",
    [
        ("0501-02-06", [501, 1, 1, False]),
        ("0502-05-24", [502, 4, 1, True]),
        ("0504-02-02", [503, 12, 29, False]),
        ("0504-02-03", [504, 1, 1, False]),
        ("0504-07-07", [504, 6, 8, False]),
        ("0505-03-23", [505, 2, 1, True]),
        ("0506-02-10", [505, 12, 30, False]),
    ],
)
def test_source_date_disagreement_and_numeric_facts_match_rest_mcp_cli(
    monkeypatch, capsys, key, day, expected
):
    p = payload(key, day)
    fields = [
        "taiyi.calendar_rules",
        "taiyi.calendar_summary",
        "taiyi.core_board",
        "snapshot_text",
    ]
    if key == "sanshiunited":
        fields += ["synthesis.limitations"]
    route = "/api/cn/taiyi" if key == "taiyi" else "/api/divination/sanshiunited"
    rest = rest_client(monkeypatch).post(
        route,
        json=p,
        params=[
            ("strict_fields", "true"),
            ("response_char_limit", "0"),
            *[("fields", f) for f in fields],
        ],
    )
    assert rest.status_code == 200, rest.text

    async def invoke():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                key,
                {
                    **p,
                    "fields": fields,
                    "strict_fields": True,
                    "response_char_limit": 0,
                },
            )
            assert not result.is_error
            return result.structured_content

    mcp = asyncio.run(invoke())
    capsys.readouterr()
    assert (
        run(
            cli_args(key, p)
            + ["--strict-fields", "--response-char-limit", "0", "--fields", *fields]
        )
        == 0
    )
    cli = json.loads(capsys.readouterr().out)
    for field in fields:
        assert resolve(rest.json(), field) == resolve(mcp, field) == resolve(cli, field)
    h = mcp["taiyi"]["calendar_rules"]["historical_calendar"]
    assert [h["year"], h["month"], h["day"], h["is_leap_month"]] == expected
    assert mcp["taiyi"]["calendar_summary"]["used_lunar_date"] == h["display"]
    assert "历表分歧" in cli["snapshot_text"]
    if key == "sanshiunited":
        assert (
            "齐梁" in mcp["synthesis"]["limitations"][0]
            and "未认证三式共同古历" in mcp["synthesis"]["limitations"][0]
        )


@pytest.mark.parametrize("key", ["taiyi", "sanshiunited"])
@pytest.mark.parametrize("mode", ["month", "day", "hour"])
def test_new_year_profile_cannot_be_used_to_switch_month_day_or_hour_algorithms(
    monkeypatch, capsys, key, mode
):
    p = payload(key, mode=mode)
    route = "/api/cn/taiyi" if key == "taiyi" else "/api/divination/sanshiunited"
    assert rest_client(monkeypatch).post(route, json=p).status_code == 400

    async def invoke():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(key, p, raise_on_error=False)

    assert asyncio.run(invoke()).is_error
    capsys.readouterr()
    assert run(cli_args(key, p)) != 0


@pytest.mark.parametrize("key", ["taiyi", "sanshiunited"])
@pytest.mark.parametrize(
    "day", ["0501-02-05", "0506-02-11", "0385-07-01", "2026-04-04"]
)
def test_all_surfaces_refuse_extrapolation_or_cross_profile_fallback(
    monkeypatch, capsys, key, day
):
    p = payload(key, day)
    route = "/api/cn/taiyi" if key == "taiyi" else "/api/divination/sanshiunited"
    response = rest_client(monkeypatch).post(route, json=p)
    assert response.status_code == 400 and "仅覆盖" in response.text

    async def invoke():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(key, p, raise_on_error=False)

    assert asyncio.run(invoke()).is_error
    capsys.readouterr()
    assert run(cli_args(key, p)) != 0


@pytest.mark.parametrize("key", ["taiyi", "sanshiunited"])
@pytest.mark.parametrize("day", ["0502-05-24", "0504-07-07"])
def test_published_first_view_keeps_business_conflict_facts_under_default_budget(
    key, day
):
    spec = next(s for s in CATALOG if s.key == key)

    async def invoke():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                key,
                {
                    **payload(key, day),
                    "fields": suggested_fields(spec, view="historical_year_calendar"),
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            )
            assert not result.is_error
            original = await _same_run_payload(
                client, result, require_business_inline=True
            )
            return original

    full = asyncio.run(invoke())
    context = full["taiyi"]["calendar_rules"]["historical_calendar"]
    assert context["source_disagreements"][0]["printed_leap_month"] == 4
    assert not context["source_disagreements"][0]["adjudicated"]
    Taiyi.model_validate(full["taiyi"])


@pytest.mark.parametrize("key", ["taiyi", "sanshiunited"])
def test_full_default_budget_export_reconstructs_conflicts_from_the_same_run(key):
    async def invoke():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(key, {**payload(key), "fields": None})
            assert not result.is_error
            return await _same_run_payload(client, result)

    full = asyncio.run(invoke())
    assert full["taiyi"]["calendar_rules"]["historical_calendar"]["is_leap_month"]
    assert "历表分歧" in full["snapshot_text"]

"""Original month-cycle witnesses, independent calendar dates and real surfaces."""

import asyncio
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from pydantic import ValidationError

import fatebridge.api as api
from fatebridge.application.execution import execute_tool
from fatebridge.cli import run
from fatebridge.core.guolao import guolao_classical as c
from fatebridge.core.guolao import guolao_monthly as monthly
from fatebridge.core.requests.astrology import AstroChartPolyRequest, AstroGuolaoRequest
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.astrology import calculate_core_chart_analysis
from fatebridge.services.catalog.astro_bindings import _astro_chart_bind
from fatebridge.services.tool_catalog import CATALOG
from tests.fixtures.surface_payloads import astro_payload
from tests.support.transports import call_calculation

FIXTURES = Path(__file__).parents[1] / "fixtures" / "guolao-month-limit-v1"
SOURCE = json.loads(monthly.DATA.read_text())
HKO = json.loads((FIXTURES / "hko-reference.json").read_text())
AS_OF = "2026-10-22T12:00:00+08:00"


def test_raw_original_witness_and_independent_calendar_receipts_are_preserved() -> None:
    fetch = json.loads((FIXTURES / "source-fetch.json").read_text())
    assert fetch["sha256"] == SOURCE["source_image_sha256"]
    assert (
        hashlib.sha256((FIXTURES / fetch["source_file"]).read_bytes()).hexdigest()
        == fetch["sha256"]
    )
    assert fetch["canvas"]["label"] == "9"
    assert SOURCE["collation"]["full_month_cycle_collated"]
    assert not SOURCE["collation"]["calendar_basis_adjudicated"]
    assert not SOURCE["collation"]["leap_month_policy_adjudicated"]
    for ref in HKO["source_files"]:
        assert (
            hashlib.sha256((FIXTURES / ref["file"]).read_bytes()).hexdigest()
            == ref["sha256"]
        )


@pytest.mark.parametrize("number,branch", SOURCE["example"]["month_branches"].items())
def test_monthly_cycle_matches_every_month_actually_printed_in_the_example(
    number, branch
) -> None:
    e = SOURCE["example"]
    annual = c.small_limit_branch(
        e["life_branch"], e["birth_year_branch"], e["target_year_branch"]
    )
    assert annual == e["annual_branch"] == "戌"
    assert c.month_limit_branch(annual, e["birth_month"], int(number)) == branch


def test_month_cycle_preserves_birth_month_anchor_and_reverse_adjacent_steps() -> None:
    for branch in c.BRANCHES:
        for month in range(1, 13):
            assert c.month_limit_branch(branch, month, month) == branch
            cycle = [
                c.month_limit_branch(branch, month, (month - 1 + n) % 12 + 1)
                for n in range(12)
            ]
            assert len(set(cycle)) == 12
            assert all(
                c.BRANCHES[(c.BRANCHES.index(a) - 1) % 12] == b
                for a, b in zip(cycle, cycle[1:])
            )


@pytest.mark.parametrize("bad", [True, None, 1.0, "5", 0, 13])
@pytest.mark.parametrize("index", [0, 1])
def test_month_ordinals_reject_missing_coerced_and_out_of_range_inputs(
    bad: bool | float | int | str | None, index: int
) -> None:
    months = [5, 6]
    months[index] = bad
    with pytest.raises(ValueError):
        c.month_limit_branch("戌", *months)


@pytest.mark.parametrize("case", HKO["cases"], ids=lambda c: c["date"])
def test_utc8_lunar_month_and_leap_flag_against_independent_hko_table(case) -> None:
    actual = monthly.month_context(
        datetime.fromisoformat(case["date"] + "T12:00:00+08:00"), "chinese_lunar_utc8"
    )
    assert actual["lunar_year"] == case["year"]
    assert actual["month_number"] == case["month"]
    assert actual["lunar_day"] == case["day"]
    assert actual["is_leap_month"] == case["is_leap_month"]
    assert actual["timezone"] == "UTC+08:00"


def test_lunar_calendar_uses_fixed_utc8_rather_than_historical_shanghai_dst() -> None:
    # HKO: leap fifth month begins 1990-06-23. Shanghai then used UTC+09.
    before = monthly.month_context(
        datetime.fromisoformat("1990-06-22T15:30:00+00:00"), "chinese_lunar_utc8"
    )
    after = monthly.month_context(
        datetime.fromisoformat("1990-06-22T16:00:00+00:00"), "chinese_lunar_utc8"
    )
    assert before["calendar_datetime"] == "1990-06-22T23:30:00+08:00"
    assert not before["is_leap_month"] and before["lunar_day"] == 30
    assert after["is_leap_month"] and after["lunar_day"] == 1


def test_jie_month_change_brackets_independent_hko_minute_and_consumes_exact_boundary() -> (
    None
):
    # HKO's retained raw XML replaces the retired duplicate JSON transcription.
    raw = (
        Path(__file__).parents[1] / "fixtures/calendar_hko_v1/24SolarTerms_2026.xml"
    ).read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == "3af98679f43d4d689941c55ba2a19f146ff111a6dff681235dc2b7110974ac74"
    )
    assert b"<Data><M>02</M><D>04</D><hm>04:02</hm></Data>" in raw
    published = datetime.fromisoformat("2026-02-04T04:02:00+08:00")
    before = monthly.month_context(published - timedelta(minutes=3), "jie_month")
    after = monthly.month_context(published + timedelta(minutes=3), "jie_month")
    assert (before["month_number"], after["month_number"]) == (12, 1)
    # Independent published minute and exact consumed endpoint are separate checks.
    edge = datetime.fromisoformat(after["start_boundary"]["datetime"]).replace(
        tzinfo=timezone(timedelta(hours=8))
    )
    assert (
        monthly.month_context(edge - timedelta(microseconds=1), "jie_month")[
            "month_number"
        ]
        == 12
    )
    assert monthly.month_context(edge, "jie_month")["month_number"] == 1


def test_lunar_month_turns_at_utc8_midnight_not_the_request_offset_midnight() -> None:
    edge = datetime.fromisoformat("2027-06-05T00:00:00+08:00")
    assert (
        monthly.month_context(edge - timedelta(microseconds=1), "chinese_lunar_utc8")[
            "month_number"
        ]
        == 4
    )
    assert monthly.month_context(edge, "chinese_lunar_utc8")["month_number"] == 5
    assert monthly.month_context(edge, "chinese_lunar_utc8") == monthly.month_context(
        edge.astimezone(timezone.utc), "chinese_lunar_utc8"
    )


@pytest.mark.parametrize("basis", ["jie_month", "chinese_lunar_utc8"])
def test_unknown_or_naive_month_inputs_do_not_pick_a_calendar(basis: str) -> None:
    with pytest.raises(ValueError):
        monthly.month_context(datetime(2027, 6, 5), basis)
    with pytest.raises(ValueError):
        monthly.month_context(
            datetime.fromisoformat("2027-06-05T00:00:00+08:00"), "gregorian"
        )


@pytest.mark.parametrize("request_model", [AstroGuolaoRequest, AstroChartPolyRequest])
def test_selected_month_basis_requires_target_and_correct_variant(
    request_model,
) -> None:
    with pytest.raises(ValidationError, match="guolao_month_basis"):
        request_model.model_validate(
            {**astro_payload(), "guolao_month_basis": "jie_month"}
        )
    with pytest.raises(ValidationError):
        request_model.model_validate(
            {
                **astro_payload(),
                "guolao_month_basis": "gregorian",
                "analysis_datetime": "2027-06-05T12:00:00+08:00",
            }
        )
    if request_model is AstroChartPolyRequest:
        with pytest.raises(ValidationError, match="guolao_month_basis"):
            request_model.model_validate(
                {
                    **astro_payload(),
                    "chart_variant": "germany",
                    "guolao_month_basis": "jie_month",
                    "analysis_datetime": "2027-06-05T12:00:00+08:00",
                }
            )
    else:
        pass


def chart(*, basis=None, target="2027-06-05T12:00:00+08:00", **kwargs):
    return calculate_core_chart_analysis(
        chart_variant="guolao_chart",
        **{**astro_payload(), **kwargs},
        analysis_datetime=datetime.fromisoformat(target),
        guolao_month_basis=basis,
    )


def test_native_basis_changes_only_month_assignment_and_records_all_dependencies() -> (
    None
):
    plain = chart()
    assert "month_limit" not in plain["guolao"]["timing"]
    a, b = chart(basis="jie_month"), chart(basis="chinese_lunar_utc8")
    for r, target_month, branch in [(a, 4, "午"), (b, 5, "巳")]:
        m = r["guolao"]["timing"]["month_limit"]
        assert m["birth_month"]["month_number"] == 3
        assert (m["target_month"]["month_number"], m["branch"]) == (
            target_month,
            branch,
        )
        assert (
            m["annual_branch"]
            == plain["guolao"]["timing"]["small_limit"]["branch"]
            == "未"
        )
        assert (
            m["ordinal_rule_collated"]
            and not m["calendar_mapping_classical_acceptance"]
        )
        assert f"月限（{m['month_basis']}）：{branch}。" in r["snapshot_text"]
        assert r["guolao"]["rule_trace"][:-1] == plain["guolao"]["rule_trace"]
        assert r["guolao"]["rule_trace"][-1]["outputs"]["month_limit_branch"] == branch
        assert r["guolao"]["rulesets"][:-1] == plain["guolao"]["rulesets"]
        for key in ["small_limit", "transit_bodies", "mansion_boundaries", "profile"]:
            assert r["guolao"]["timing"][key] == plain["guolao"]["timing"][key]
        for key in ["person_info", "chart_profile", "planets", "houses", "angles"]:
            assert r[key] == plain[key]


@pytest.mark.parametrize(
    "longitude,lunar_month,lunar_day,branch",
    [
        (120 + 2**-30, 4, 29, "巳"),
        (120, 5, 1, "午"),
        (120 - 2**-30, 5, 1, "午"),
    ],
)
def test_lunar_month_uses_exact_pre_atomic_mean_solar_source_date(
    longitude, lunar_month: int, lunar_day: int, branch: str
) -> None:
    # HKO 1950, p. 1: June 14/15 are lunar 4/29 and 5/1 respectively.
    # A longitude step of 2**-30 degrees shifts UTC+08 by less than 0.5 us.
    result = calculate_core_chart_analysis(
        chart_variant="guolao_chart",
        birth_year=1950,
        birth_month=6,
        birth_day=15,
        birth_hour=0,
        birth_latitude=25,
        birth_longitude=longitude,
        birth_clock_basis="local_mean_solar",
        analysis_datetime=datetime.fromisoformat("2027-06-05T12:00:00+08:00"),
        guolao_month_basis="chinese_lunar_utc8",
    )
    monthly = result["guolao"]["timing"]["month_limit"]
    birth = monthly["birth_month"]
    assert birth["calendar_datetime"] == "1950-06-15T00:00:00+08:00"
    assert (birth["month_number"], birth["lunar_day"], monthly["branch"]) == (
        lunar_month,
        lunar_day,
        branch,
    )
    if lunar_month == 4:
        assert birth["calendar_date"] == "1950-06-14"
        assert (
            birth["calendar_lookup_basis"]
            == "retained_nominal_source_point_fixed_utc8_date"
        )
    else:
        pass


@pytest.mark.parametrize("basis", ["jie_month", "chinese_lunar_utc8"])
def test_true_solar_display_cannot_change_the_month_calendar_inputs(basis: str) -> None:
    a, b = chart(basis=basis), chart(
        basis=basis, use_true_solar_time=True, birth_longitude=-170
    )
    for key in ["birth_month", "target_month"]:
        assert (
            a["guolao"]["timing"]["month_limit"][key]
            == b["guolao"]["timing"]["month_limit"][key]
        )
    assert (
        a["guolao"]["timing"]["transit_bodies"][0]["longitude"]
        == b["guolao"]["timing"]["transit_bodies"][0]["longitude"]
    )


@pytest.mark.parametrize("birth_leap", [False, True])
def test_intercalary_month_stays_unassigned_while_year_and_sky_remain_available(
    birth_leap: bool,
) -> None:
    r = chart(
        basis="chinese_lunar_utc8",
        target="2025-07-25T12:00:00+08:00",
        **({"birth_month": 6, "birth_day": 23} if birth_leap else {}),
    )
    g = r["guolao"]
    m = g["timing"]["month_limit"]
    assert m["status"] == "unassigned_intercalary_policy_unresolved"
    assert m["target_month"]["is_leap_month"]
    assert m["birth_month"]["is_leap_month"] is birth_leap
    assert m["branch"] is None and m["natal_functional_palace"] is None
    assert "月限（chinese_lunar_utc8）：未分配。" in r["snapshot_text"]
    assert g["timing"]["small_limit"]["branch"] in c.BRANCHES
    assert len(g["timing"]["transit_bodies"]) == 11


def test_unavailable_lunar_table_does_not_fabricate_a_month() -> None:
    m = monthly.build_month_limit(
        annual_branch="戌",
        birth_instant=datetime.fromisoformat("1990-04-06T09:33:00+08:00"),
        target_instant=datetime.fromisoformat("3000-06-01T00:00:00+08:00"),
        basis="chinese_lunar_utc8",
        palaces=[],
    )
    assert m["status"] == "unassigned_calendar_unavailable"
    assert m["branch"] is None and m["target_month"]["month_number"] is None


@pytest.mark.parametrize("basis", ["jie_month", "chinese_lunar_utc8"])
@pytest.mark.parametrize(
    "target", ["2027-06-05T12:00:00+08:00", "2025-07-25T12:00:00+08:00"]
)
def test_selected_month_layer_projects_identically_on_rest_native_mcp_cli(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    basis: str,
    target: str,
) -> None:
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    spec = next(s for s in CATALOG if s.key == "astro_guolao")
    payload = {
        **astro_payload(),
        "analysis_datetime": target,
        "guolao_month_basis": basis,
    }
    fields = [
        "guolao.timing.month_limit",
        "guolao.timing.small_limit",
    ]
    options = {
        "as_of": AS_OF,
        "fields": fields,
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 0,
    }
    response = TestClient(api.app).post(
        spec.rest_path,
        json=payload,
        params=[
            ("as_of", AS_OF),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
            *[("fields", f) for f in fields],
        ],
    )
    assert response.status_code == 200, response.text

    async def protocol():
        async with Client(create_mcp_app()) as client:
            return await call_calculation(
                client, spec.tool_name, {**payload, **options}, raise_on_error=False
            )

    native = asyncio.run(protocol())
    assert not native.is_error, native
    args = [spec.tool_name]
    for key, value in payload.items():
        args += ["--" + key.replace("_", "-"), str(value)]
    args += [
        "--as-of",
        AS_OF,
        "--strict-fields",
        "--no-include-snapshot-text",
        "--response-char-limit",
        "0",
        "--fields",
        *fields,
    ]
    capsys.readouterr()
    assert run(args) == 0
    cli = json.loads(capsys.readouterr().out)
    values = [
        {k: v for k, v in body.items() if k != "run_metadata"}
        for body in [response.json(), native.structured_content, cli]
    ]
    assert values[0] == values[1] == values[2]
    m = values[0]["guolao"]["timing"]["month_limit"]
    assert m["month_basis"] == basis and not m["calendar_mapping_classical_acceptance"]


@pytest.mark.parametrize("basis", ["jie_month", "chinese_lunar_utc8"])
def test_generic_guolao_entry_matches_dedicated_and_germany_default_binding_still_works(
    basis: str,
) -> None:
    specs = {s.key: s for s in CATALOG}
    p = {
        **astro_payload(),
        "analysis_datetime": "2027-06-05T12:00:00+08:00",
        "guolao_month_basis": basis,
    }
    a = execute_tool(
        specs["astro_guolao"],
        specs["astro_guolao"].request_model.model_validate(p),
        include_metadata=False,
    )
    b = execute_tool(
        specs["astro_chart"],
        specs["astro_chart"].request_model.model_validate(
            {**p, "chart_variant": "guolao_chart"}
        ),
        include_metadata=False,
    )
    assert a == b

    req = AstroChartPolyRequest.model_validate(
        {**astro_payload(), "chart_variant": "germany"}
    )
    _, _, kwargs = _astro_chart_bind(req)
    assert "guolao_month_basis" not in kwargs

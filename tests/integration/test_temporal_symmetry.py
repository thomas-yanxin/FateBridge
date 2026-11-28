"""Regression and contract tests for temporal symmetry, range scanning, parameter symmetry, and output hygiene."""

from __future__ import annotations

import subprocess
import sys

import pytest
from pydantic import ValidationError

from fatebridge.application.batch import SubjectProfile
from fatebridge.application.execution import execute_with_receipt
from fatebridge.application.response_delivery import deliver_response
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.core.fengshui.bazhai import minggua
from fatebridge.core.fengshui.models import MingguaRequest
from fatebridge.core.requests.birth import AstroBirthRequest
from fatebridge.core.requests.timing import LiunianAnalysisRequest
from fatebridge.core.response_models import output_model_for
from fatebridge.services.tool_catalog import CATALOG

SPECS = {spec.name: spec for spec in CATALOG}

BIRTH_ARGS = {
    "name": "测试甲",
    "gender": "男",
    "birth_year": 1990,
    "birth_month": 5,
    "birth_day": 15,
    "birth_hour": 10,
    "birth_minute": 30,
    "birth_timezone": "Asia/Shanghai",
    "birth_place": "北京",
    "birth_longitude": 116.4074,
}


def _call_tool(
    tool_name: str,
    arguments: dict[str, object],
    *,
    include: list[str] | None = None,
    as_of: str = "2026-10-12T12:00:00+08:00",
) -> dict[str, object]:
    spec = SPECS[tool_name]
    request = spec.request_model.model_validate(arguments)
    raw = execute_with_receipt(
        spec,
        request,
        options=ExecutionOptions(as_of=as_of),
    )
    return deliver_response(raw, spec=spec, include=include)


@pytest.mark.parametrize(
    "policy,expected_pillar,expected_year,expected_basis",
    [
        ("lichun", "丙午", 2026, "lichun_exact_moment"),
        ("gregorian", "丁未", 2027, "gregorian_year_integer"),
    ],
)
@pytest.mark.parametrize(
    "tool_name",
    ["bazi_timing", "bazi_yearly_timing", "bazi_monthly_timing"],
)
def test_2027_january_year_boundary_policy_is_consistent_across_tools(
    tool_name: str,
    policy: str,
    expected_pillar: str,
    expected_year: int,
    expected_basis: str,
) -> None:
    result = _call_tool(
        tool_name,
        {
            **BIRTH_ARGS,
            "analysis_year": 2027,
            "analysis_month": 1,
            "year_boundary_policy": policy,
        },
    )
    assert "error" not in result, result
    liunian = result["liunian"]
    assert isinstance(liunian, dict)
    assert liunian["pillar"] == expected_pillar
    assert liunian["year"] == expected_year
    assert liunian["year_boundary_policy"] == policy
    assert liunian["year_boundary_basis"] == expected_basis
    window = liunian["solar_year_window"]
    assert isinstance(window, dict)
    assert window["start_lichun"].startswith(f"{expected_year}-02-")
    assert window["end_lichun"].startswith(f"{expected_year + 1}-02-")


def test_bazi_yearly_timing_year_only_vs_clock_default_symmetry() -> None:
    year_only = _call_tool(
        "bazi_yearly_timing",
        {**BIRTH_ARGS, "analysis_year": 2027, "year_boundary_policy": "lichun"},
    )
    assert year_only["liunian"]["pillar"] == "丁未"
    assert year_only["liunian"]["year"] == 2027
    assert year_only["liunian"]["year_boundary_basis"] == "lichun_solar_year"
    assert year_only["analysis_context"]["provided_fields"] == ["analysis_year"]

    clock_defaulted = _call_tool(
        "bazi_yearly_timing",
        {**BIRTH_ARGS, "year_boundary_policy": "lichun"},
        as_of="2027-01-15T12:00:00+08:00",
    )
    assert clock_defaulted["liunian"]["pillar"] == "丙午"
    assert clock_defaulted["liunian"]["year"] == 2026
    assert clock_defaulted["liunian"]["year_boundary_basis"] == "lichun_exact_moment"
    assert (
        "analysis_year" in clock_defaulted["analysis_context"]["defaulted_from_clock"]
    )
    assert "current_time_frozen" in clock_defaulted["run_metadata"]["warnings"]


def test_solar_term_timeline_emits_analysis_context() -> None:
    result = _call_tool(
        "solar_term_timeline",
        {**BIRTH_ARGS, "analysis_year": 2026},
    )
    assert result["analysis_context"]["provided_fields"] == ["analysis_year"]
    assert result["analysis_context"]["timezone"] == "Asia/Shanghai"


def test_bazi_timing_include_timelines_default_and_summary() -> None:
    default_out = _call_tool(
        "bazi_timing",
        {
            **BIRTH_ARGS,
            "analysis_year": 2026,
            "analysis_month": 10,
            "include_timelines": True,
        },
    )
    cal = default_out["analysis_calendar"]
    assert len(cal["liuyue_timeline"]) == 12
    assert len(cal["jieqi_timeline"]) == 24
    solar_term_default_keys = {
        "name",
        "resolution_provider",
        "ephemeris_model",
        "timezone",
        "datetime",
        "datetime_utc",
        "date_key",
        "day_ganzhi",
        "datetime_with_offset",
        "utc_offset_seconds",
        "fold",
    }
    first_month = cal["liuyue_timeline"][0]
    assert set(first_month["start_term"]) <= solar_term_default_keys
    assert "civil_point" not in first_month["start_term"]
    assert "comparison_policy" not in first_month["start_term"]
    first_jieqi = cal["jieqi_timeline"][0]
    assert set(first_jieqi["jieqi"]) <= solar_term_default_keys
    assert "civil_point" not in first_jieqi["jieqi"]
    assert "comparison_policy" not in first_jieqi["jieqi"]

    full_out = _call_tool(
        "bazi_timing",
        {**BIRTH_ARGS, "analysis_year": 2026, "analysis_month": 10},
        include=["*"],
    )
    assert isinstance(full_out["summary"], dict)
    assert full_out["summary"]["liunian"] == full_out["liunian"]["pillar"]
    assert full_out["summary"]["liuyue"] == full_out["liuyue"]["pillar"]


def test_bazi_range_scans_yearly_monthly_daily_and_dayun_timeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fatebridge.services.timing_periods as timing_periods

    context_calls = 0
    original_builder = timing_periods.build_birth_computation_context

    def counting_builder(*args, **kwargs):
        nonlocal context_calls
        context_calls += 1
        return original_builder(*args, **kwargs)

    monkeypatch.setattr(
        timing_periods, "build_birth_computation_context", counting_builder
    )

    with pytest.raises(ValidationError) as exc_bad_order:
        LiunianAnalysisRequest.model_validate(
            {**BIRTH_ARGS, "analysis_year": 2028, "end_year": 2026}
        )
    assert exc_bad_order.value.errors()[0]["type"] == "invalid_year_range"

    with pytest.raises(ValidationError) as exc_too_wide:
        LiunianAnalysisRequest.model_validate(
            {**BIRTH_ARGS, "analysis_year": 2020, "end_year": 2040}
        )
    assert exc_too_wide.value.errors()[0]["type"] == "year_range_too_large"

    yearly = _call_tool(
        "bazi_yearly_timing",
        {**BIRTH_ARGS, "analysis_year": 2026, "end_year": 2030},
    )
    assert context_calls == 1
    assert [row["year"] for row in yearly["yearly_timeline"]] == [
        2026,
        2027,
        2028,
        2029,
        2030,
    ]

    monthly = _call_tool(
        "bazi_monthly_timing",
        {**BIRTH_ARGS, "analysis_year": 2026, "analysis_month": 2, "scan_months": 3},
    )
    assert context_calls == 2
    assert [row["branch"] for row in monthly["monthly_timeline"]] == ["寅", "卯", "辰"]
    assert "solar_term_window" in monthly["liuyue"]
    assert set(monthly["liuyue"]["solar_term_window"]["start_term"]) <= {
        "name",
        "resolution_provider",
        "ephemeris_model",
        "timezone",
        "datetime",
        "datetime_utc",
        "date_key",
        "day_ganzhi",
        "datetime_with_offset",
        "utc_offset_seconds",
        "fold",
    }
    assert "civil_point" not in monthly["liuyue"]["solar_term_window"]["start_term"]
    assert (
        "comparison_policy" not in monthly["liuyue"]["solar_term_window"]["start_term"]
    )

    daily = _call_tool(
        "bazi_daily_timing",
        {
            **BIRTH_ARGS,
            "analysis_year": 2026,
            "analysis_month": 10,
            "analysis_day": 12,
            "scan_days": 5,
        },
    )
    assert context_calls == 3
    assert [row["date"] for row in daily["daily_timeline"]] == [
        "2026-10-12",
        "2026-10-13",
        "2026-10-14",
        "2026-10-15",
        "2026-10-16",
    ]

    luck = _call_tool(
        "bazi_luck_cycles",
        {**BIRTH_ARGS, "analysis_year": 2026},
    )
    assert len(luck["dayun_timeline"]) == 12
    assert luck["dayun_timeline"][0]["period"] == 1


def test_ziwei_timing_optional_and_partial_dates_with_reproducibility() -> None:
    partial = _call_tool(
        "ziwei_timing",
        {
            "gender": "男",
            "birth_year": 1994,
            "birth_month": 8,
            "birth_day": 23,
            "birth_hour": 14,
            "analysis_year": 2026,
        },
    )
    assert partial["analysis_context"]["analysis_datetime"] == "2026-01-01 00:00:00"
    assert partial["analysis_context"]["basis"] == "declared_partial_components"
    assert "current_time_frozen" not in partial["run_metadata"]["warnings"]

    omitted = _call_tool(
        "ziwei_timing",
        {
            "gender": "男",
            "birth_year": 1994,
            "birth_month": 8,
            "birth_day": 23,
            "birth_hour": 14,
        },
        as_of="2026-10-12T15:30:00+08:00",
    )
    assert omitted["analysis_context"]["analysis_datetime"] == "2026-10-12 15:30:00"
    assert omitted["analysis_context"]["basis"] == "implicit_execution_clock"
    assert "current_time_frozen" in omitted["run_metadata"]["warnings"]


def test_astro_birth_request_place_and_gender_symmetry_without_eager_catalog() -> None:
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import fatebridge.core.requests.birth; "
                "assert 'fatebridge.utils.place_catalog' not in sys.modules"
            ),
        ],
        check=True,
    )
    assert probe.returncode == 0

    with pytest.raises(ValidationError) as exc_missing:
        AstroBirthRequest.model_validate(
            {
                "birth_year": 1990,
                "birth_month": 5,
                "birth_day": 15,
                "birth_hour": 10,
                "birth_timezone": "Asia/Shanghai",
            }
        )
    assert exc_missing.value.errors()[0]["type"] == "missing_coordinates"

    western = _call_tool(
        "western_timing",
        {
            "name": "测试甲",
            "gender": "男",
            "birth_year": 1990,
            "birth_month": 5,
            "birth_day": 15,
            "birth_hour": 10,
            "birth_minute": 30,
            "birth_place": "北京",
            "analysis_year": 2026,
            "analysis_month": 10,
            "analysis_day": 12,
        },
        include=["*"],
    )
    assert "error" not in western, western
    assert western["natal_reference"]["ascendant"]


def test_minggua_and_subject_profile_accept_chinese_gender() -> None:
    req_zh = MingguaRequest(birth_year=1990, gender="男")
    req_en = MingguaRequest(birth_year=1990, gender="male")
    assert req_zh.gender == "male"
    assert minggua(req_zh) == minggua(req_en)

    profile = SubjectProfile.model_validate({"gender": "女", "birth_year": 1992})
    assert profile.gender == "女"


def test_cross_tool_output_hygiene_contracts() -> None:
    for tool_name in (
        "hellenistic_chart",
        "guolao_chart",
        "vedic_chart",
        "vimshottari_dasha",
    ):
        model = output_model_for(tool_name)
        assert "person_info" in model.model_fields

    balbillus = _call_tool(
        "balbillus_periods",
        {
            "birth_year": 1990,
            "birth_month": 5,
            "birth_day": 15,
            "birth_hour": 10,
            "birth_minute": 30,
            "birth_place": "北京",
        },
        include=["*"],
    )
    first_period = balbillus["balbillus"]["periods"][0]
    assert "subperiods" in first_period
    assert "sub_periods" not in first_period

    chart13 = _call_tool(
        "thirteen_sector_chart",
        {
            "birth_year": 1990,
            "birth_month": 5,
            "birth_day": 15,
            "birth_hour": 10,
            "birth_minute": 30,
            "birth_place": "北京",
            "birth_timezone": "Asia/Shanghai",
            "birth_time_uncertainty_minutes": 10,
        },
    )
    assert "birth_time_sensitivity" in chart13
    assert "time_sensitivity" not in chart13

    hamburg = _call_tool(
        "hamburg_midpoint_chart",
        {
            "birth_year": 1990,
            "birth_month": 5,
            "birth_day": 15,
            "birth_hour": 10,
            "birth_minute": 30,
            "birth_place": "北京",
            "birth_timezone": "Asia/Shanghai",
            "birth_time_uncertainty_minutes": 10,
        },
    )
    assert "birth_time_sensitivity" in hamburg["midpoint_analysis"]
    assert "time_sensitivity" not in hamburg["midpoint_analysis"]

    hd = _call_tool(
        "human_design",
        {
            "birth_year": 1990,
            "birth_month": 5,
            "birth_day": 15,
            "birth_hour": 10,
            "birth_minute": 30,
            "birth_timezone": "Asia/Shanghai",
            "birth_time_uncertainty_minutes": 10,
        },
    )
    assert "birth_time_sensitivity" in hd
    assert "time_sensitivity" not in hd

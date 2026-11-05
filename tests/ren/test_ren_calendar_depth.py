"""Independent date/hour sources, fallback rejection and actual clock fidelity."""

import asyncio
import importlib.util
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fatebridge.core import almanac
from fatebridge.core.calendar import BaZiCalendar
from fatebridge.core.metaphysics.ren_calendar import require_ren_calendar
from fatebridge.services.metaphysics import (
    _build_analysis_seed,
    calculate_jinkou_analysis,
    calculate_liureng_gods,
)
from tests.evaluation.test_agentic_nested_outputs import SPECS, call_cli, native, rest
from tests.ren.test_ren_transports import PAYLOAD

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "audit_ren_calendar", ROOT / "scripts/ren/audit_ren_calendar_models.py"
)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


@pytest.fixture
def linear_failure(monkeypatch):
    # This fault targets the native solver, not the independent DE440 solver.
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    almanac.get_solar_terms_for_year.cache_clear()
    BaZiCalendar._get_four_pillars_cached.cache_clear()
    monkeypatch.setattr(almanac, "_solar_term_utc_via_swe", lambda *a, **kw: None)
    try:
        yield
    finally:
        almanac.get_solar_terms_for_year.cache_clear()
        BaZiCalendar._get_four_pillars_cached.cache_clear()


@pytest.mark.parametrize("key", ["liureng_gods", "liureng_runyear", "jinkou"])
def test_failed_astronomical_terms_never_publish_a_fallback_board_in_any_transport(
    key, rest, tmp_path, capsys, linear_failure
):
    spec = SPECS[key]
    payload = {
        **PAYLOAD,
        "analysis_month": 2,
        "analysis_day": 19,
        "analysis_hour": 0,
        "analysis_minute": 15,
    }
    if key == "liureng_runyear":
        payload.update(
            birth_year=1994, birth_month=8, birth_day=23, birth_hour=14, gender="女"
        )
    http = rest.post(spec.rest_path, json=payload)
    code, cli = call_cli(spec, payload, tmp_path, capsys)
    protocol = asyncio.run(native(spec, payload))
    assert http.status_code == 503 and code != 0 and protocol.is_error
    for body in (http.json(), cli, protocol.structured_content):
        assert body["error_code"] == "dependency_missing"
        assert "liureng" not in body and "jinkou" not in body


@pytest.mark.parametrize(
    "mode,provider", [("native", "swisseph"), ("de440", "jpl_de440")]
)
def test_real_rainwater_case_uses_new_month_general_and_observed_dependencies(
    mode, provider, monkeypatch
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    kwargs = dict(
        analysis_year=2026,
        analysis_month=2,
        analysis_day=19,
        analysis_hour=0,
        analysis_minute=15,
        analysis_timezone="Asia/Shanghai",
        use_true_solar_time=False,
    )
    for operation in (calculate_liureng_gods, calculate_jinkou_analysis):
        result = operation(**kwargs)
        assert "error" not in result
        assert result["liureng"]["month_general"]["branch"] == "亥"
        policy = result["liureng"]["calendar_policy"]
        assert policy["day_boundary"] == "23:00"
        assert policy["effective_day_date"] == "2026-02-19"
        assert policy["effective_day_ganzhi"] == "甲子"
        assert {r["provider"] for r in policy["solar_term_dependencies"]} == {provider}
        assert {r["role"] for r in policy["solar_term_dependencies"]} == {
            "current_term",
            "next_term",
            "month_start",
            "next_month_start",
            "year_boundary",
        }
        if "jinkou" in result:
            assert result["jinkou"]["calendar_policy"] == policy


def test_solar_clock_late_zi_crossing_does_not_advance_civil_month_boundary():
    kwargs = dict(
        analysis_year=2026,
        analysis_month=4,
        analysis_day=4,
        analysis_hour=22,
        analysis_minute=57,
        analysis_timezone="Asia/Shanghai",
        analysis_longitude=121.5,
        use_true_solar_time=True,
    )
    result = calculate_jinkou_analysis(**kwargs)
    policy = result["jinkou"]["calendar_policy"]
    assert policy["day_hour_clock"] == "apparent_solar"
    assert policy["corrected_clock"].startswith("2026-04-04T23:00")
    assert policy["civil_datetime"].startswith("2026-04-04T22:57")
    assert policy["effective_day_date"] == "2026-04-05"
    assert result["four_pillars"]["day"] == {"stem": "己", "branch": "酉"}
    assert result["four_pillars"]["month"]["branch"] == "卯"
    assert result["liureng"]["month_general"]["branch"] == "戌"
    for snapshot in (
        result["snapshot_text"],
        calculate_liureng_gods(**kwargs)["snapshot_text"],
    ):
        assert "输入民用时间：2026-04-04T22:57" in snapshot
        assert "日时取用钟：2026-04-04T23:00" in snapshot
        assert "日柱归属日期：2026-04-05（己酉）" in snapshot
        assert "直接时间：2026-04-04 23:00" not in snapshot


@pytest.mark.parametrize("at", [datetime(2026, 3, 7, 12), datetime(2026, 3, 9, 12)])
def test_solar_term_elapsed_fields_measure_physical_days_across_dst(at):
    seed = _build_analysis_seed(
        analysis_year=at.year,
        analysis_month=at.month,
        analysis_day=at.day,
        analysis_hour=at.hour,
        analysis_timezone="America/New_York",
        use_true_solar_time=False,
    )
    context = seed.calendar_context
    actual = almanac.localize_datetime(at, "America/New_York")
    previous = almanac.localize_datetime(
        datetime.fromisoformat(context["current_solar_term"]["datetime"]),
        "America/New_York",
    )
    following = almanac.localize_datetime(
        datetime.fromisoformat(context["next_solar_term"]["datetime"]),
        "America/New_York",
    )
    since = (
        actual.astimezone(timezone.utc) - previous.astimezone(timezone.utc)
    ).total_seconds() / 86400
    until = (
        following.astimezone(timezone.utc) - actual.astimezone(timezone.utc)
    ).total_seconds() / 86400
    assert context["solar_term_delta"]["days_since_current"] == round(since, 4)
    assert context["solar_term_delta"]["days_until_next"] == round(until, 4)
    assert context["lunar_calendar"]["days_until_next_jieqi"] == round(until, 4)
    assert (
        max(
            abs(since - (actual - previous).total_seconds() / 86400),
            abs(until - (following - actual).total_seconds() / 86400),
        )
        > 0.04
    )


@pytest.mark.parametrize("solar", [False, True])
@pytest.mark.parametrize("month,day,hour", [(3, 8, 2), (11, 1, 1)])
def test_physical_dst_gaps_and_folds_fail_before_apparent_solar_correction(
    solar, month, day, hour
):
    result = calculate_liureng_gods(
        analysis_year=2026,
        analysis_month=month,
        analysis_day=day,
        analysis_hour=hour,
        analysis_minute=30,
        analysis_timezone="America/New_York",
        analysis_longitude=-74,
        use_true_solar_time=solar,
    )
    assert result["error_code"] == "validation_error" and result["status_code"] == 400
    assert "liureng" not in result


def test_every_hour_stem_group_matches_the_frozen_hko_table():
    ref = AUDIT.reference()
    start = datetime(2000, 1, 1)
    for day in range(10):
        for hour in range(24):
            moment = start + timedelta(days=day, hours=hour)
            expected_day = AUDIT.expected_day(moment.date(), ref, hour == 23)
            branch_index = ((hour + 1) // 2) % 12
            expected_hour = (
                AUDIT.table_stem(ref["hour_stems"], expected_day[0], branch_index)
                + AUDIT.BRANCHES[branch_index]
            )
            result = BaZiCalendar.get_four_pillars(moment, timezone_name="+08:00")
            assert "".join(result["day"]) == expected_day
            assert "".join(result["hour"]) == expected_hour


@pytest.mark.parametrize("mode", ["native", "de440"])
def test_independent_2026_cohort_retains_date_precision_limits(mode, monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    report = AUDIT.audit([2026], progress=False)
    assert report["totals"]["civil_dates"] == 365
    assert report["totals"]["day_checks"] == 730
    assert report["totals"]["year_month_underdetermined"] == 24
    assert report["totals"]["month_general_underdetermined"] == 24
    assert report["all_performed_comparisons_passed"]
    assert (
        report["term_date_mismatch_count"] == report["term_source_failure_count"] == 0
    )
    assert report["legacy_swiss_only_provider_failure_count"] == (
        24 if mode == "de440" else 0
    )
    assert report["legacy_swiss_only_comparison_passed"] is (mode == "native")
    assert not report["full_hko_cohort"]
    assert (
        not report["full_supported_calendar_domain_certified"]
        and not report["goal_complete"]
    )


def test_source_parser_rejects_omitted_rows_and_the_frozen_bundle_rejects_tampering(
    tmp_path,
):
    source = (ROOT / "tests/data/ziwei_independent/hko/T2026c.txt").read_text(
        encoding="utf-8-sig"
    )
    with pytest.raises(ValueError, match="missing"):
        AUDIT.annual_rows(
            source.replace(
                next(
                    line
                    for line in source.splitlines()
                    if line.startswith(("2026年01月02日", "2026年1月2日"))
                ),
                "",
            ),
            2026,
            (2025, 11, False),
        )
    target = tmp_path / "calendar"
    shutil.copytree(AUDIT.CORPUS, target)
    (target / "reference.json").write_text("{}")
    with pytest.raises(ValueError, match="reference changed"):
        AUDIT.reference(target)

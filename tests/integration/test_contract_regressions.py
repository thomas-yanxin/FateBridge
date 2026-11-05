"""Related contract regressions with shared imports; original cases retained."""

from __future__ import annotations

import logging

from fatebridge.services.metaphysics import (
    calculate_taiyi_analysis,
    calculate_ziwei_birth,
)
from fatebridge.utils.birth_input import create_person_info
from fatebridge.utils.places import (
    _resolve_birth_place_context_cached,
    resolve_birth_place_context,
)


def test_uncatalogued_birth_place_emits_warning(caplog):
    # The resolver is lru_cached; clear it so the warning path actually runs.
    _resolve_birth_place_context_cached.cache_clear()

    with caplog.at_level(logging.WARNING):
        result = resolve_birth_place_context("齐天大圣花果山水帘洞")

    assert result.longitude is None
    assert result.canonical_name is None
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert warnings, "uncatalogued birth place should emit a WARNING"


def test_empty_birth_place_stays_silent(caplog):
    # The "not provided" sentinel is not a failure to resolve — no warning noise.
    _resolve_birth_place_context_cached.cache_clear()

    with caplog.at_level(logging.WARNING):
        result = resolve_birth_place_context("未提供")

    assert result.longitude is None
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_ziwei_rejects_missing_lunar_data_instead_of_defaulting(monkeypatch):
    # The prefix is now supplied by PMO; missing data must still never turn
    # into a fabricated first day of the first month.
    monkeypatch.setattr("fatebridge.core.almanac.LunarDate", None)
    person = create_person_info(
        birth_year=1900,
        birth_month=1,
        birth_day=1,
        birth_hour=14,
        name="超范围",
        gender="男",
        birth_place="上海",
        birth_minute=0,
        birth_timezone="Asia/Shanghai",
    )

    result = calculate_ziwei_birth(person)

    assert result.get("error_code") == "validation_error"
    assert result.get("status_code") == 400
    assert "农历" in result.get("error", "")
    # 关键：不再悄悄返回一张（错误的）命盘。
    assert "ziwei_birth" not in result


def test_taiyi_rejects_date_outside_lunar_range():
    result = calculate_taiyi_analysis(
        analysis_year=2150,
        analysis_month=4,
        analysis_day=4,
        analysis_hour=21,
        analysis_minute=18,
        analysis_timezone="Asia/Shanghai",
        analysis_longitude=121.4737,
        gender="男",
        use_true_solar_time=True,
    )

    assert result.get("error_code") == "validation_error"
    assert result.get("status_code") == 400
    assert "农历" in result.get("error", "")
    assert "taiyi" not in result

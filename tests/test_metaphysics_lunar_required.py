"""紫微 / 太乙 在农历不可用时必须显式拒绝，而非静默按正月初一起盘。

离线农历换算支持公历 1900-01-01 ~ 2100-12-31。落在该区间之外或缺少 lunardate 时，
``lunar_calendar`` 为空。旧实现 ``int(lunar.get("month") or 1)`` 会悄悄
退化到正月初一，算出一张看似正常却整体错位的盘。现在应返回 400 校验错误。
"""

from __future__ import annotations

from fatebridge.services.metaphysics import (
    calculate_taiyi_analysis,
    calculate_ziwei_birth,
)
from fatebridge.utils.birth_input import create_person_info


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

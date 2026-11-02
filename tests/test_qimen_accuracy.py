from __future__ import annotations

from datetime import datetime

from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.core.metaphysics.qimen import build_qimen_board, qimen_futou_for_ganzhi
from fatebridge.services.divination import calculate_sanshiunited_analysis
from fatebridge.services.metaphysics import calculate_qimen_analysis


def _make_seed(
    *,
    day_ganzhi: str,
    time_ganzhi: str,
    current_term: str,
    days_since_current: float,
    term_day_ganzhi: str | None = None,
) -> MetaphysicsSeed:
    return MetaphysicsSeed(
        input_datetime=datetime(2028, 4, 6, 9, 33, 0),
        corrected_datetime=datetime(2028, 4, 6, 9, 33, 0),
        timezone="+08:00",
        longitude=121.4737,
        applied_true_solar=False,
        total_correction_minutes=0.0,
        pillars={
            "year": ("戊", "申"),
            "month": ("丙", "辰"),
            "day": (day_ganzhi[0], day_ganzhi[1]),
            "hour": (time_ganzhi[0], time_ganzhi[1]),
        },
        calendar_context={
            "current_solar_term": {
                "name": current_term,
                "day_ganzhi": term_day_ganzhi,
            },
            "solar_term_delta": {
                "days_since_current": days_since_current,
            },
        },
    )


def test_build_qimen_board_uses_day_ganzhi_for_sanyuan() -> None:
    seed = _make_seed(
        day_ganzhi="辛酉",
        time_ganzhi="癸巳",
        current_term="清明",
        days_since_current=2.0,
    )

    result = build_qimen_board(seed)

    assert result["yuan"] == "下元"
    assert result["ju_number"] == 6
    assert result["ju_text"] == "阳遁六局下元"


def test_build_qimen_board_resolves_futou_from_day_ganzhi() -> None:
    seed = _make_seed(
        day_ganzhi="辛酉",
        time_ganzhi="癸巳",
        current_term="清明",
        days_since_current=2.0,
        term_day_ganzhi="乙丑",
    )

    result = build_qimen_board(seed)

    assert result["fu_tou"] == qimen_futou_for_ganzhi("辛酉")
    assert result["fu_tou"] != "乙丑"


def test_sanshiunited_qimen_matches_dedicated_qimen_service() -> None:
    dedicated = calculate_qimen_analysis(
        analysis_year=2028,
        analysis_month=4,
        analysis_day=6,
        analysis_hour=9,
        analysis_minute=33,
        analysis_timezone="+08:00",
        analysis_longitude=121.4667,
    )
    aggregate = calculate_sanshiunited_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        lat="31n13",
        lon="121e28",
    )

    assert aggregate["qimen"]["ju_text"] == dedicated["qimen"]["ju_text"]
    assert aggregate["qimen"]["fu_tou"] == dedicated["qimen"]["fu_tou"]


def test_calculate_qimen_analysis_keeps_day_reference_and_uses_hour_xun() -> None:
    result = calculate_qimen_analysis(
        analysis_year=2028,
        analysis_month=4,
        analysis_day=6,
        analysis_hour=9,
        analysis_minute=33,
        analysis_timezone="+08:00",
        analysis_longitude=121.4667,
    )

    assert result["qimen"]["ju_text"] == "阳遁六局下元"
    assert result["qimen"]["yuan"] == "下元"
    assert result["qimen"]["ju_number"] == 6
    assert result["qimen"]["fu_tou"] == "己未"
    assert result["qimen"]["day_xun_head"] == "甲寅"
    assert result["qimen"]["xun_head"] == "甲申"
    assert result["qimen"]["day_kongwang"] == "子丑空"
    assert result["qimen"]["kongwang"] == "午未空"
    assert result["qimen"]["zhifu"]["star"] == "天任"
    assert result["qimen"]["zhishi"]["door"] == "生门"

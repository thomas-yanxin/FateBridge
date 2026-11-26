from __future__ import annotations

from datetime import datetime, timedelta, timezone
from itertools import product

import pytest

from fatebridge.core.metaphysics import qimen as engine
from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.core.metaphysics.qimen import build_qimen_board, qimen_futou_for_ganzhi
from fatebridge.services.divination import calculate_sanshiunited_analysis
from fatebridge.services.metaphysics import calculate_qimen_analysis
from fatebridge.utils.civil_time import NominalClockLabel
from tests.support.transports import AS_OF, SPECS, business


def _make_seed(
    *,
    day_ganzhi: str,
    time_ganzhi: str,
    current_term: str,
    days_since_current: float,
    term_day_ganzhi: str | None = None,
) -> MetaphysicsSeed:
    civil = datetime(2028, 4, 6, 9, 33, tzinfo=timezone(timedelta(hours=8)))
    return MetaphysicsSeed(
        input_datetime=civil,
        clock=NominalClockLabel.from_local_datetime(civil),
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
        input_offset_visible=False,
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
        timezone="+08:00",
        latitude="31n13",
        longitude="121e28",
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


@pytest.mark.parametrize("dun,ju", list(product(["阳遁", "阴遁"], range(1, 10))))
def test_all_1080_boards_preserve_stars_stems_doors_gods_and_leaders(dun, ju) -> None:
    stems, branches = "甲乙丙丁戊己庚辛壬癸", "子丑寅卯辰巳午未申酉戌亥"
    for i in range(60):
        hour = stems[i % 10] + branches[i % 12]
        text = f'{dun}{"一二三四五六七八九"[ju-1]}局上元'
        earth = engine._qimen_pan_earth(text)
        leader = engine._qimen_zhifu_zhishi(hour, earth, dun_type=dun)
        palaces = engine._qimen_build_palaces(earth=earth, leader=leader)
        outer = [p for p in palaces if p["trigram"] != "中"]
        assert sorted(
            s for p in outer for s in [p["star"], *p["hosted_stars"]]
        ) == sorted(["天蓬", "天芮", "天冲", "天辅", "天禽", "天心", "天柱", "天任", "天英"])
        assert sorted(s for p in outer for s in p["heaven_stems"]) == sorted(
            "戊己庚辛壬癸丁丙乙"
        )
        assert len({p["door"] for p in outer}) == 8
        assert len({p["god"] for p in outer}) == 8
        assert sum(p["god"] == "值符" for p in palaces) == 1
        center = palaces[4]
        assert (
            center["door"]
            is center["god"]
            is center["star"]
            is center["heaven_stem"]
            is None
        )
        at = next(p for p in outer if p["trigram"] == leader["star_gong"])
        assert engine.QIMEN_STAR_DISPLAY[leader["star"]] in [
            at["star"],
            *at["hosted_stars"],
        ]
        assert leader["zhifu_heaven_stem"] in at["heaven_stems"]
        assert at["god"] == "值符"
        if i % 10 == 0:
            assert all(p["heaven_stem"] == p["earth_stem"] for p in outer)
        else:
            pass


@pytest.mark.parametrize(
    "method,month,day,hour,term,ju,conflicts",
    [
        ("zhirun", 1, 19, 23, "大寒", "阳遁三局上元", []),
        ("chaibu", 1, 19, 23, "小寒", "阳遁二局上元", []),
        ("zhirun", 7, 5, 8, "小暑", "阴遁八局上元", []),
        (
            "chaibu",
            7,
            5,
            8,
            "夏至",
            "阴遁九局上元",
            [
                (
                    "vol4-yin9-gengchen-door",
                    "坎",
                    "坤",
                    "unresolved_print_rule_disagreement",
                )
            ],
        ),
        (
            "chaibu",
            6,
            26,
            8,
            "夏至",
            "阴遁三局中元",
            [
                (
                    "de-shi-yin3-renchen",
                    "杜门",
                    "开门",
                    "unresolved_scan_rule_disagreement",
                )
            ],
        ),
    ],
)
def test_ju_method_keeps_printed_conflicts_visible_across_transports(
    method: str,
    month: int,
    day: int,
    hour: int,
    term: str,
    ju: str,
    conflicts: list[tuple[str, str, str, str]],
    surface_calls,
) -> None:
    http, mcp, code, cli = surface_calls(
        SPECS["qimen"],
        {
            "analysis_year": 2026,
            "analysis_month": month,
            "analysis_day": day,
            "analysis_hour": hour,
            "analysis_timezone": "+08:00",
            "use_true_solar_time": False,
            "qimen_options": {"ju_method": method},
        },
        projection={
            "detail": "audit",
            "fields": [
                f"qimen.{name}"
                for name in ("ju_method", "ju_term", "ju_text", "source_disagreements")
            ],
        },
        rest_as_of=AS_OF,
    )
    assert http.status_code == 200, http.text
    assert not mcp.is_error and code == 0
    assert business(http.json()) == business(mcp.structured_content) == business(cli)
    board = cli["qimen"]
    assert (board["ju_method"], board["ju_term"], board["ju_text"]) == (
        method,
        term,
        ju,
    )
    assert [
        (row["case_id"], row["source_value"], row["computed_value"], row["status"])
        for row in board["source_disagreements"]
    ] == conflicts

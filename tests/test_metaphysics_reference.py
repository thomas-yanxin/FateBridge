"""Regressions anchored to independent calendars/boards and physical time."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fatebridge.api import app
from fatebridge.core.almanac import get_lunar_context
from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.core.metaphysics.liureng import build_liureng_board
from fatebridge.services.metaphysics import (
    _build_analysis_seed,
    _build_person_seed,
    calculate_ziwei_horoscope,
)
from fatebridge.utils.birth_input import create_person_info


@pytest.mark.parametrize(
    "solar,lunar",
    [
        ((1933, 7, 21), (1933, 5, 29, True)),
        ((1933, 7, 22), (1933, 5, 30, True)),
        ((1933, 7, 23), (1933, 6, 1, False)),
        ((1933, 8, 20), (1933, 6, 29, False)),
        ((1933, 8, 21), (1933, 7, 1, False)),
        ((1954, 11, 24), (1954, 10, 29, False)),
        ((1954, 11, 25), (1954, 11, 1, False)),
        ((1954, 12, 1), (1954, 11, 7, False)),
        ((1954, 12, 24), (1954, 11, 30, False)),
        ((1954, 12, 25), (1954, 12, 1, False)),
        ((1978, 9, 1), (1978, 7, 29, False)),
        ((1978, 9, 2), (1978, 7, 30, False)),
        ((1978, 9, 3), (1978, 8, 1, False)),
        ((1978, 10, 1), (1978, 8, 29, False)),
        ((1978, 10, 2), (1978, 9, 1, False)),
    ],
)
def test_hko_sxtwl_historical_month_lengths(solar, lunar):
    got = get_lunar_context(datetime(*solar, 10), timezone_name="+08:00")
    assert (got["year"], got["month"], got["day"], got["is_leap_month"]) == lunar


def test_historical_correction_does_not_mutate_dependency():
    import lunardate

    year_infos = getattr(lunardate, "yearInfos", None)
    if year_infos is None:  # lunardate 0.3 uses uppercase table names.
        year_infos = lunardate.YEAR_INFOS
    before = tuple(year_infos)
    get_lunar_context(datetime(1954, 12, 1, 10), timezone_name="+08:00")
    assert tuple(year_infos) == before


def test_liureng_all_day_hour_month_general_combinations_against_independent_oracle():
    # 60 day stems/branches × 12 sky offsets are the complete board space.
    # Check all twelve absolute hour positions as well: changing 月将/时支
    # together must preserve transmissions for the same day and sky board.
    fixture = json.loads(
        (
            Path(__file__).parent / "fixtures/liureng_transmissions_reference.json"
        ).read_text()
    )
    branches, stems = "子丑寅卯辰巳午未申酉戌亥", "甲乙丙丁戊己庚辛壬癸"
    assert len(fixture["cases"]) == 720
    for case in fixture["cases"]:
        stem, branch = case["day"]
        for hour in range(12):
            dt = datetime(2026, 1, 1, hour * 2)
            seed = MetaphysicsSeed(
                input_datetime=dt,
                corrected_datetime=dt,
                timezone="+08:00",
                longitude=None,
                applied_true_solar=False,
                total_correction_minutes=0,
                pillars={
                    "year": ("丙", "午"),
                    "month": ("戊", "子"),
                    "day": (stem, branch),
                    "hour": (
                        stems[(stems.index(stem) * 2 + hour) % 10],
                        branches[hour],
                    ),
                },
                calendar_context={"current_solar_term": {"name": "冬至"}},
            )
            got = build_liureng_board(
                seed, month_general_override=branches[(hour + case["offset"]) % 12]
            )
            actual = [
                got["three_transmissions"][k]["branch"]
                for k in ("initial", "middle", "final")
            ]
            assert actual == case["transmissions"], (case["day"], hour, case["offset"])
            selected = got["meta"]["selected_lesson_index"]
            marked = [l for l in got["four_lessons"] if l["use_candidate"]]
            if got["board_style"] in {"昴星", "别责", "八专"} or (
                got["board_style"] == "返吟" and got["board_style_detail"] == "无依"
            ):
                # A derived initial god can coincide with a lesson's upper
                # god (e.g. 己巳/offset=1 昴星); that is not lesson selection.
                assert selected is None
                assert got["meta"]["selected_lesson_relation"] is None
                assert marked == []
            else:
                assert [l["index"] for l in marked] == [selected]
                assert marked[0]["upper_branch"] == actual[0]
                assert (
                    got["meta"]["selected_lesson_relation"]
                    == marked[0]["upper_lower_relation"]
                )


def test_liureng_first_lesson_uses_day_stem_not_house_element():
    seed = _build_analysis_seed(
        analysis_year=2026, analysis_month=9, analysis_day=1, analysis_hour=2
    )
    first = build_liureng_board(seed)["four_lessons"][0]
    assert first["text"] == "酉加戊"
    assert first["upper_lower_relation"] == "下生上"  # 戊土生酉金


def test_jinkou_duplicate_upper_god_preserves_actual_selected_lesson():
    with TestClient(app) as client:
        response = client.post(
            "/api/cn/jinkou",
            json={
                "analysis_year": 2026,
                "analysis_month": 9,
                "analysis_day": 8,
                "analysis_hour": 20,
                "use_true_solar_time": False,
                "di_fen": "丑",
            },
        )
    assert response.status_code == 200
    result = response.json()
    board = result["liureng"]
    assert board["board_style"] == "比用"
    first, _, _, fourth = board["four_lessons"]
    assert first["upper_branch"] == fourth["upper_branch"] == "亥"
    assert first["upper_lower_relation"] == "上生下"
    assert fourth["upper_lower_relation"] == "下贼上"
    assert board["meta"]["selected_lesson_index"] == 4
    assert board["meta"]["selected_lesson_relation"] == "下贼上"
    assert [l["index"] for l in board["four_lessons"] if l["use_candidate"]] == [4]
    assert result["jinkou"]["overview"]["use_position"] == "地分"


def test_liureng_god_rotation_includes_earth_xu():
    seed = _build_analysis_seed(
        analysis_year=2026, analysis_month=9, analysis_day=4, analysis_hour=2
    )
    board = build_liureng_board(seed)
    assert board["meta"]["guiren_earth_branch"] == "戌"
    assert board["board_order"] == "天盘逆布"
    gods = {p["earth_branch"]: p["god"] for p in board["twelve_board"]}
    assert gods["戌"] == "贵人"
    assert gods["酉"] == "螣蛇"
    assert gods["亥"] == "天后"


def test_apparent_solar_time_shared_by_birth_and_analysis():
    # JPL/Skyfield independent apparent solar clock is 01:06:26.6 here.
    # A low-precision equation of time is acceptable; omitting it is not.
    seed = _build_analysis_seed(
        analysis_year=2026,
        analysis_month=11,
        analysis_day=3,
        analysis_hour=0,
        analysis_minute=50,
        analysis_timezone="+08:00",
        analysis_longitude=120,
        use_true_solar_time=True,
    )
    person = create_person_info(
        birth_year=2026,
        birth_month=11,
        birth_day=3,
        birth_hour=0,
        birth_minute=50,
        birth_timezone="+08:00",
        birth_longitude=120,
        use_true_solar_time=True,
    )
    natal = _build_person_seed(person)
    assert seed.corrected_datetime == natal.corrected_datetime
    assert seed.pillars["hour"] == natal.pillars["hour"] == ("己", "丑")
    assert (
        abs(
            (
                seed.corrected_datetime - datetime(2026, 11, 3, 1, 6, 26, 600000)
            ).total_seconds()
        )
        < 10
    )


def test_public_rest_historical_lunar_and_solar_hour_regressions():
    with TestClient(app) as client:
        lunar = client.post(
            "/api/cn/nongli/time",
            json={
                "date": "1954-12-01",
                "time": "10:00",
                "zone": "+08:00",
                "time_alg": 0,
            },
        )
        assert lunar.status_code == 200
        assert lunar.json()["day"] == "初七"
        response = client.post(
            "/api/cn/qimen",
            json={
                "analysis_year": 2026,
                "analysis_month": 11,
                "analysis_day": 3,
                "analysis_hour": 0,
                "analysis_minute": 50,
                "analysis_timezone": "+08:00",
                "analysis_longitude": 120,
                "use_true_solar_time": True,
            },
        )
        assert response.status_code == 200
        assert response.json()["four_pillars"]["hour"] == {"stem": "己", "branch": "丑"}


def test_ziwei_horoscope_rejects_unavailable_target_lunar_calendar():
    person = create_person_info(
        birth_year=1990, birth_month=5, birth_day=15, birth_hour=10, gender="男"
    )
    result = calculate_ziwei_horoscope(
        person, target_year=2100, target_month=3, target_day=1, target_hour=10
    )
    assert result["status_code"] == 400
    assert "农历" in result["error"]

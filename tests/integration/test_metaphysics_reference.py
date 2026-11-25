"""Regressions anchored to independent calendars/boards and physical time."""

from __future__ import annotations

import gzip
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fatebridge.api import app
from fatebridge.core.almanac import get_lunar_context
from fatebridge.core.metaphysics import common
from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.core.metaphysics.liureng import build_liureng_board, twelve_god_layout
from fatebridge.core.metaphysics.ren_gods import noble_start
from fatebridge.core.metaphysics.seed import build_analysis_seed
from fatebridge.services.metaphysics import (
    _build_person_seed,
    calculate_ziwei_horoscope,
)
from fatebridge.utils.birth_input import create_person_info
from fatebridge.utils.civil_time import NominalClockLabel


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
def test_hko_sxtwl_historical_month_lengths(solar, lunar) -> None:
    got = get_lunar_context(datetime(*solar, 10), timezone_name="+08:00")
    assert (got["year"], got["month"], got["day"], got["is_leap_month"]) == lunar


def test_historical_correction_does_not_mutate_dependency() -> None:
    import lunardate

    year_infos = getattr(lunardate, "yearInfos", None)
    if year_infos is None:  # lunardate 0.3 uses uppercase table names.
        year_infos = lunardate.YEAR_INFOS
    else:
        pass
    before = tuple(year_infos)
    get_lunar_context(datetime(1954, 12, 1, 10), timezone_name="+08:00")
    assert tuple(year_infos) == before


def test_liureng_all_day_hour_month_general_combinations_against_independent_oracle() -> (
    None
):
    # 60 day stems/branches × 12 sky offsets are the complete board space.
    # Check all twelve absolute hour positions as well: changing 月将/时支
    # together must preserve transmissions for the same day and sky board.
    fixture = json.loads(
        (
            Path(__file__).parents[1] / "fixtures/liureng_transmissions_reference.json"
        ).read_text()
    )
    branches, stems = "子丑寅卯辰巳午未申酉戌亥", "甲乙丙丁戊己庚辛壬癸"
    assert len(fixture["cases"]) == 720
    for case in fixture["cases"]:
        stem, branch = case["day"]
        for hour in range(12):
            dt = datetime(2026, 1, 1, hour * 2, tzinfo=timezone(timedelta(hours=8)))
            seed = MetaphysicsSeed(
                input_datetime=dt,
                clock=NominalClockLabel.from_local_datetime(dt),
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
                input_offset_visible=False,
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
                got["board_style"] == "返吟"
                and got["three_transmissions"]["method"] == "返吟无亲"
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


def test_liureng_first_lesson_uses_day_stem_not_house_element() -> None:
    seed = build_analysis_seed(
        analysis_year=2026, analysis_month=9, analysis_day=1, analysis_hour=2
    )
    first = build_liureng_board(seed)["four_lessons"][0]
    assert first["text"] == "酉加戊"
    assert first["upper_lower_relation"] == "下生上"  # 戊土生酉金


def test_jinkou_duplicate_upper_god_preserves_actual_selected_lesson() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/jinkou",
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
    # Jin Kou has its own 四位阴阳 rule, independent of the selected Liu Ren lesson.
    assert result["jinkou"]["overview"]["board_style_detail"] == "二阴二阳"
    assert result["jinkou"]["overview"]["use_position"] == "将神"


def test_liureng_god_rotation_includes_earth_xu() -> None:
    seed = build_analysis_seed(
        analysis_year=2026, analysis_month=9, analysis_day=4, analysis_hour=2
    )
    board = build_liureng_board(seed)
    assert board["meta"]["guiren_earth_branch"] == "戌"
    assert board["board_order"] == "天盘顺布"
    assert board["guiren_order"] == "逆"
    gods = {p["earth_branch"]: p["god"] for p in board["twelve_board"]}
    assert gods["戌"] == "贵人"
    assert gods["酉"] == "螣蛇"
    assert gods["亥"] == "天后"


def test_apparent_solar_time_shared_by_birth_and_analysis() -> None:
    # JPL/Skyfield independent apparent solar clock is 01:06:26.6 here.
    # A low-precision equation of time is acceptable; omitting it is not.
    seed = build_analysis_seed(
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
    assert seed.clock == natal.clock
    assert seed.pillars["hour"] == natal.pillars["hour"] == ("己", "丑")
    reference = NominalClockLabel.from_local_datetime(
        datetime(2026, 11, 3, 1, 6, 26, 600000)
    )
    assert (
        abs(
            (seed.clock.ordinal - reference.ordinal) * 86_400_000_000
            + seed.clock.microseconds_of_day
            - reference.microseconds_of_day
        )
        < 10_000_000
    )


def test_public_rest_historical_lunar_and_solar_hour_regressions() -> None:
    with TestClient(app) as client:
        lunar = client.post(
            "/api/calendar/lunar-time",
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
            "/api/qimen",
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


def test_ziwei_horoscope_rejects_unavailable_target_lunar_calendar() -> None:
    person = create_person_info(
        birth_year=1990, birth_month=5, birth_day=15, birth_hour=10, gender="男"
    )
    result = calculate_ziwei_horoscope(
        person, target_year=2101, target_month=1, target_day=1, target_hour=10
    )
    assert result["status_code"] == 400
    assert "农历" in result["error"]


@pytest.fixture(scope="module")
def primitive_reference():
    folder = Path(__file__).parents[1] / "data/metaphysics_primitives_reference_v1"
    raw = gzip.decompress((folder / "reference.json.gz").read_bytes())
    assert (
        hashlib.sha256(raw).hexdigest()
        == (folder / "reference.json.sha256").read_text().strip()
    )
    return json.loads(raw)


def test_shared_primitives_keep_all_pinned_formal_reference_states(
    primitive_reference,
) -> None:
    reference = primitive_reference
    assert len(reference["cycles"]) == 60
    for row in reference["cycles"]:
        text = row["text"]
        assert common.sexagenary_text(row["index"]) == text
        assert common.sexagenary_index_for(text) == row["index"]
        assert common.ganzhi_text((text[0], text[1])) == text
        assert common.xun_head_for_ganzhi(text) == row["xun"]
        assert common.kongwang_for_ganzhi(text) == row["kongwang"] + "空"
    assert len(reference["stem_elements"]) == 10
    assert len(reference["branch_elements"]) == 12
    for stem, element in reference["stem_elements"].items():
        assert common.stem_element_text(stem) == element
    for branch, element in reference["branch_elements"].items():
        assert common.branch_element_text(branch) == element
    assert len(reference["relations"]) == len(reference["seasonal_states"]) == 25
    for row in reference["relations"]:
        assert common.liuqin_against_day(row["left"], row["right"]) == row["expected"]
    for row in reference["seasonal_states"]:
        assert (
            common.status_against_anchor(row["anchor"], row["target"])
            == row["expected"]
        )
    ten_to_kin = {
        "比肩": "兄弟",
        "劫财": "兄弟",
        "食神": "子孙",
        "伤官": "子孙",
        "正财": "妻财",
        "偏财": "妻财",
        "正官": "官鬼",
        "七杀": "官鬼",
        "正印": "父母",
        "偏印": "父母",
    }
    assert len(reference["ten_gods"]) == 100
    for row in reference["ten_gods"]:
        assert (
            common.liuqin_against_day(
                common.stem_element_text(row["day"]),
                common.stem_element_text(row["target"]),
            )
            == ten_to_kin[row["ten_god"]]
        )
    assert len(reference["branch_relations"]) == 144
    for row in reference["branch_relations"]:
        assert (common.SIX_HARMONY_BRANCHES[row["left"]] == row["right"]) is row[
            "harmony"
        ]
        assert (common.SIX_CLASH_BRANCHES[row["left"]] == row["right"]) is row["clash"]
    assert len(reference["rotations"]) == 24
    for row in reference["rotations"]:
        assert (
            common.rotate_sequence(
                "子丑寅卯辰巳午未申酉戌亥", row["start"], row["reverse"]
            )
            == row["sequence"]
        )
    assert len(reference["noble_starts"]) == 40
    for row in reference["noble_starts"]:
        assert (
            noble_start(row["stem"], row["diurnal"], row["profile"]) == row["expected"]
        )
    assert len(reference["numerals"]) == 72
    for row in reference["numerals"]:
        assert common.chinese_numeral(row["value"]) == row["expected"]


def test_tanyuan_all_explicit_diurnal_layouts_keep_pinned_Go_reference(
    primitive_reference,
) -> None:
    reference = primitive_reference
    assert reference["metadata"]["layouts_profile"] == "tanyuan_xieji_v1"
    assert len(reference["layouts"]) == 2880
    assert (
        len(
            {
                (r["stem"], r["general"], r["hour"], r["diurnal"])
                for r in reference["layouts"]
            }
        )
        == 2880
    )
    for row in reference["layouts"]:
        assert (
            twelve_god_layout(
                hour_branch=row["hour"],
                month_general_branch=row["general"],
                day_stem=row["stem"],
                is_diurnal=row["diurnal"],
                guiren_profile="tanyuan_xieji_v1",
            )
            == row["expected"]
        )

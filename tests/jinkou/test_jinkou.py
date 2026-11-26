"""Tests for Jin Kou Jue decoupling, §7 oracle, 64/64 pattern resolution, and size."""

import json

from fatebridge.core.contracts.output_jinkou_board import JinkouCourse
from fatebridge.core.contracts.output_jinkou_year_fate import Jinkou
from fatebridge.core.metaphysics.jinkou import build_jinkou_board
from fatebridge.core.metaphysics.jinkou.patterns import structural_patterns
from fatebridge.core.metaphysics.jinkou.year_fate import (
    build_jinkou_year_fate,
    build_natal_course,
)
from fatebridge.core.metaphysics.seed import build_analysis_seed


def test_jinkou_oracle_2024_05_20_1430_and_decoupling() -> None:
    seed = build_analysis_seed(
        analysis_year=2024,
        analysis_month=5,
        analysis_day=20,
        analysis_hour=14,
        analysis_minute=30,
        analysis_second=0,
        analysis_timezone="Asia/Shanghai",
        use_true_solar_time=False,
    )
    # Build directly without passing liureng board
    board = build_jinkou_board(seed, None, di_fen="申", gender="男")
    JinkouCourse.model_validate(board)

    assert board["overview"]["month_general"]["branch"] == "酉"
    assert board["overview"]["di_fen"] == "申"
    assert board["overview"]["use_position"] == "贵神"
    rows = {r["label"]: r for r in board["rows"]}
    assert rows["人元"]["content"] == "壬"
    assert rows["贵神"]["content"] == "申"
    assert rows["贵神"]["shenjiang"] == "白虎"
    assert rows["贵神"]["dun_stem"] == "壬"
    assert rows["将神"]["content"] == "戌"
    assert rows["将神"]["shenjiang"] == "河魁"
    assert rows["地分"]["content"] == "申"
    assert [m["name"] for m in board["motions"]] == ["父母动"]

    # Size budget check (< 20 KB)
    assert len(json.dumps(board, ensure_ascii=False)) < 20480


def test_all_64_patterns_resolved_including_formerly_unresolved_ids() -> None:
    rows = [
        {
            "label": "人元",
            "content": "丁",
            "element": "火",
            "dun_stem": None,
            "xun_kong": False,
            "si_da_kong": False,
        },
        {
            "label": "贵神",
            "content": "巳",
            "element": "火",
            "dun_stem": "己",
            "xun_kong": False,
            "si_da_kong": False,
        },
        {
            "label": "将神",
            "content": "卯",
            "element": "木",
            "dun_stem": "丁",
            "xun_kong": False,
            "si_da_kong": False,
        },
        {
            "label": "地分",
            "content": "亥",
            "element": "水",
            "dun_stem": None,
            "xun_kong": False,
            "si_da_kong": False,
        },
    ]
    res = structural_patterns(
        rows, day_ganzhi="甲子", hour_branch="巳", is_diurnal=True
    )
    assert res["catalog_count"] == 64
    assert res["evaluation_counts"]["unresolved"] == 0
    assert res["unresolved"] == []
    assert res["complete_classical_conformance"] is True
    by_id = {e["id"]: e for e in res["evaluations"]}
    for pid in ("P52", "P53", "P56", "P57", "P58", "P59"):
        assert type(by_id[pid]["matched"]) is bool


def test_jinkou_full_contract_with_natal_and_year_fate_and_sunrise_mode() -> None:
    seed = build_analysis_seed(
        analysis_year=2024,
        analysis_month=5,
        analysis_day=20,
        analysis_hour=12,
        analysis_minute=30,
        analysis_second=0,
        analysis_timezone="Asia/Shanghai",
        use_true_solar_time=False,
        analysis_longitude=116.4074,
    )
    board = build_jinkou_board(
        seed,
        None,
        di_fen="申",
        gender="男",
        diurnal_mode="sunrise_sunset",
        month_general_mode="true_solar_longitude",
        latitude=39.9042,
        longitude=116.4074,
    )
    assert board["overview"]["is_diurnal"] is True
    assert board["overview"]["month_general"]["branch"] == "酉"
    natal_course = build_natal_course(
        seed, board, birth_year_ganzhi="庚午", gender="男"
    )
    year_fate = build_jinkou_year_fate(
        seed, board, birth_year_ganzhi="庚午", age=35, gender="男"
    )
    full = {**board, "natal_course": natal_course, "year_fate": year_fate}
    Jinkou.model_validate(full)

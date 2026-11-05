"""Daily accumulation, source disagreements, ten-essence and clock boundaries."""

import hashlib
import json
import shutil
from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from fatebridge.application.projection import project_fields
from fatebridge.core.almanac import get_solar_terms_for_year
from fatebridge.core.metaphysics.taiyi import build_taiyi_board
from fatebridge.core.metaphysics.taiyi_day import (
    KEY_DAY_PROFILE,
    key_day_numeric_board,
    key_day_origin,
)
from fatebridge.core.metaphysics.taiyi_ten_jing import key_ten_jing
from fatebridge.core.output_chinese import Taiyi
from fatebridge.core.output_taiyi_day import TaiyiDayOrigin, TaiyiTenJing
from fatebridge.services.metaphysics import calculate_taiyi_analysis
from scripts.taiyi.audit_taiyi_day import CORPUS, audit
from tests.taiyi.test_taiyi_periods import seed_at


def test_complete_frozen_observations_keep_all_prose_chart_conflicts_and_unknowns():
    report = audit()
    assert report["required_observations"] == 34
    assert report["evaluated_observations"] == 33
    assert report["matching_observations"] == 28
    assert {r["id"] for r in report["disagreements"]} == {
        "main_chart",
        "heshen_chart",
        "eight_winds_prose",
        "eight_winds_chart",
        "heaven_time",
    }
    assert {r["id"] for r in report["unadjudicated"]} == {
        "ordinal_palace_prose",
    }
    assert report["source_example_acceptance_passed"] is False
    assert report["ancient_date_conversion_validated"] is False
    assert report["full_judgment_validated"] is False


def test_source_numeric_chain_is_the_actual_day_chain_and_keeps_positions_separate():
    d = key_day_numeric_board(44, "未", False)
    core = d["core_board"]
    assert core["accumulation"] == 44 and core["kook_number"] == 44
    assert (core["main_count"], core["guest_count"], core["set_count"]) == (33, 14, 32)
    assert (core["heshen"], core["dingmu"]) == ("午", "艮")
    assert d["gates"]["counter"]["duty_gate"] == "生"
    assert d["gates"]["counter"]["unit_in_gate"] == 14
    assert d["gates"]["counter"]["cycle_unit"] == "day"
    assert d["gates"]["counter"]["source_modulus"] == 240
    assert d["condition_assessment"]["five_generals"]["conditions_satisfied"] is False
    assert d["condition_assessment"]["three_gates"]["conditions_satisfied"] is None
    assert d["condition_assessment"]["menju_jiangfa"] is False
    assert d["ten_jing"]["records"]["heaven_time"]["palace"] == "酉"
    assert d["ten_jing"]["records"]["taiyi_ordinal"]["ordinal"] == 44
    assert d["ten_jing"]["records"]["taiyi_ordinal"]["palace"] is None
    assert d["ten_jing"]["records"]["eight_winds"]["palace"] == "巽"
    assert [
        r["source_value"]
        for r in d["ten_jing"]["records"]["eight_winds"]["source_comparisons"]
    ] == ["乾", "艮"]
    Taiyi.model_validate(d)
    assert all(
        "太乙数" not in p["markers"] for p in d["palace_marks"] + [d["center_marks"]]
    )


def test_every_new_day_evidence_leaf_can_be_read_without_required_siblings():
    board = key_day_numeric_board(44, "未", False)

    def leaves(value, path):
        if isinstance(value, dict) and value:
            for key, child in value.items():
                yield from leaves(child, (*path, key))
        else:
            yield ".".join(path)

    for field in leaves(board, ("taiyi",)):
        Taiyi.model_validate(
            project_fields({"taiyi": board}, [field], strict_fields=True)["taiyi"]
        )


@pytest.mark.parametrize(
    "count,expected",
    [
        (1, (1, 1, 3, 2)),
        (8, (8, 6, 4, 9)),
        (9, (9, 8, 8, 1)),
        (10, (1, 1, 3, 2)),
        (29, (2, 3, 7, 3)),
    ],
)
def test_source_nine_palace_rules_include_terminal_and_middle_palaces(count, expected):
    d = key_ten_jing(count, False)["records"]
    assert (
        tuple(
            d[k]["palace_number"]
            for k in ("flying_bird", "five_winds", "three_winds", "eight_winds")
        )
        == expected
    )
    assert all(
        d[k]["period"] == 9
        for k in ("flying_bird", "five_winds", "three_winds", "eight_winds")
    )


def test_held_positions_and_yin_opposition_never_invent_a_center_opposite():
    for a, b, key, position in [
        (4, 5, "emperor", "乾"),
        (19, 20, "emperor", "坤"),
        (4, 5, "earth", "子"),
        (19, 20, "earth", "酉"),
    ]:
        assert (
            key_ten_jing(a, False)["records"][key]["palace"]
            == key_ten_jing(b, False)["records"][key]["palace"]
            == position
        )
    assert key_ten_jing(21, False)["records"]["emperor"]["palace"] == "申"
    assert key_ten_jing(44, True)["records"]["emperor"]["palace"] == "巽"
    center = key_ten_jing(5, True)["records"]["flying_bird"]
    assert center["yang_position"] == "中" and center["palace"] is None
    assert center["status"] == "not_assessed" and "中五" in center["reason"]
    TaiyiTenJing.model_validate(key_ten_jing(5, True))


def test_daily_midnight_boundary_does_not_use_hourly_zi_boundary_or_multiply_by_twelve():
    winter = datetime(2025, 12, 21, 23, 3)
    a, b, c = [
        key_day_origin(winter, datetime.fromisoformat(s))
        for s in ("2026-01-08T22:59:59", "2026-01-08T23:00:00", "2026-01-09T00:00:00")
    ]
    assert a["accumulation"] == b["accumulation"] == 19
    assert c["accumulation"] == 20
    assert a["target_day_ganzhi"] == b["target_day_ganzhi"] == "壬午"
    assert c["target_day_ganzhi"] == "癸未"
    assert a["alternative_strict_previous_count"] == 79
    assert a["same_day_selection_adjudicated"] is False
    assert (
        key_day_numeric_board(19, "午", False)["core_board"]["kook_number"]
        != key_day_numeric_board(79, "午", False)["core_board"]["kook_number"]
    )
    TaiyiDayOrigin.model_validate(a)


@pytest.mark.parametrize("term_name", ["冬至", "夏至"])
def test_daily_dun_changes_at_exact_solstice_but_does_not_use_hour_count(term_name):
    t = next(t for t in get_solar_terms_for_year(2026, "UTC") if t.name == term_name)
    moments = [
        (t.moment + timedelta(microseconds=n)).replace(tzinfo=None) for n in (-1, 1)
    ]
    boards = [
        build_taiyi_board(
            replace(seed_at(moment, zone="UTC"), input_datetime=moment),
            "未知",
            calculation_mode="day",
        )
        for moment in moments
    ]
    assert boards[0]["rotation"] != boards[1]["rotation"]
    for d in boards:
        assert d["ruleset"]["id"] == KEY_DAY_PROFILE
        assert (
            d["calendar_rules"]["counter"]
            == d["calendar_rules"]["day_origin"]["accumulation"]
        )
        assert "hour_origin" not in d["calendar_rules"]
        Taiyi.model_validate(d)


def test_apparent_day_origin_is_invariant_under_timezone_representation():
    instant = datetime(2026, 8, 1, 12, 34, 56)
    boards = [
        build_taiyi_board(
            seed_at(
                instant + timedelta(hours=offset),
                zone=zone,
                solar=True,
                longitude=121.47,
            ),
            "未知",
            calculation_mode="day",
        )
        for offset, zone in [(0, "UTC"), (8, "Asia/Shanghai"), (-4, "America/New_York")]
    ]
    assert (
        boards[0]["calendar_rules"]["day_origin"]
        == boards[1]["calendar_rules"]["day_origin"]
        == boards[2]["calendar_rules"]["day_origin"]
    )
    assert boards[0]["core_board"] == boards[1]["core_board"] == boards[2]["core_board"]


@pytest.mark.parametrize("month,day,hour", [(3, 8, 2), (11, 1, 1)])
def test_daily_dst_input_ambiguity_is_rejected(month, day, hour):
    with pytest.raises(ValueError, match="local time"):
        build_taiyi_board(
            seed_at(datetime(2026, month, day, hour, 30), zone="America/New_York"),
            "未知",
            calculation_mode="day",
        )


def test_modern_same_phase_snapshot_shows_both_sources_and_actual_calculation():
    result = calculate_taiyi_analysis(
        analysis_year=2026,
        analysis_month=2,
        analysis_day=2,
        analysis_hour=12,
        analysis_timezone="Asia/Shanghai",
        calculation_mode="day",
        use_true_solar_time=False,
    )
    assert "error" not in result
    board = result["taiyi"]
    assert board["core_board"]["accumulation"] == 44
    assert board["core_board"]["main_count"] == 33
    text = result["snapshot_text"]
    assert "main_count原文32" in text and "heshen原文艮" in text
    assert "本盘规则推算33" in text and "本盘规则推算午" in text
    assert "天时：酉" in text and "第44局（非宫位）" in text
    assert "阴德作乾；本盘规则推算巽" in text
    assert "三宫作艮；本盘规则推算巽" in text


@pytest.mark.parametrize("mutation", ["drop_conflict", "drop_unknown", "alter_scan"])
def test_day_oracle_cannot_drop_disagreements_or_unknowns_even_after_rehash(
    tmp_path, mutation
):
    c = tmp_path / "corpus"
    shutil.copytree(CORPUS, c)
    if mutation == "alter_scan":
        p = c / "key-page43.jpg"
        p.write_bytes(p.read_bytes() + b"x")
        with pytest.raises(ValueError, match="指纹"):
            audit(c)
        return
    p = c / "day-worked.json"
    d = json.loads(p.read_text())
    drop = "main_chart" if mutation == "drop_conflict" else "heaven_time"
    d["observations"] = [r for r in d["observations"] if r["id"] != drop]
    p.write_text(json.dumps(d))
    p = c / "manifest.json"
    m = json.loads(p.read_text())
    m["source_files"] = [
        {**s, "sha256": hashlib.sha256((c / s["file"]).read_bytes()).hexdigest()}
        for s in m["source_files"]
    ]
    p.write_text(json.dumps(m))
    with pytest.raises(ValueError, match="34观察"):
        audit(c)

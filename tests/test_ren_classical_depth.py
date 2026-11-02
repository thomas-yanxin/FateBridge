"""Source cases, reference integrity and observable calculation boundaries."""

import importlib.util
import json
import shutil
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.metaphysics.common import SEXAGENARY_CYCLE
from fatebridge.core.metaphysics.jinkou import build_jinkou_board
from fatebridge.core.metaphysics.liureng import (
    build_liureng_board,
    build_liureng_runyear,
)
from fatebridge.core.metaphysics.ren_evidence import xun_dun_stems
from fatebridge.core.requests.metaphysics import JinkouAnalysisRequest
from fatebridge.services.metaphysics import (
    _build_analysis_seed,
    calculate_liureng_runyear,
)
from fatebridge.utils.birth_input import create_person_info

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "audit_ren_classical", ROOT / "scripts/audit_ren_classical.py"
)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def test_frozen_examples_and_selected_rule_audit_keep_full_gates_closed():
    report = AUDIT.audit()
    assert report["selected_checks_passed"]
    assert len(report["checks"]) == 73
    assert len(report["calendar"]) == 12
    assert report["software_oracle"]["case_count"] == 720
    assert not report["software_oracle"]["failures"]
    assert len(report["unresolved"]) == 2
    assert report["unresolved"][0]["observed_god"] == "朱雀"
    assert report["unresolved"][0]["source_god"] == "勾陈"
    assert not report["classical_acceptance_passed"]
    assert not report["authority_certified"]
    assert not report["universal_perfect_prediction_established"]
    assert report["four_axes"]["real_world_prediction"] == "not_tested"


@pytest.mark.parametrize("change", ["edit", "missing", "extra"])
def test_source_drift_cannot_silently_improve_coverage(tmp_path, change):
    corpus = tmp_path / "corpus"
    shutil.copytree(AUDIT.CORPUS, corpus)
    if change == "edit":
        data = json.loads((corpus / "cases.json").read_text())
        data["unresolved"] = []
        (corpus / "cases.json").write_text(json.dumps(data))
    elif change == "missing":
        (corpus / "calendar.json").unlink()
    else:
        (corpus / "extra.json").write_text("{}")
    with pytest.raises(ValueError, match="Reference"):
        AUDIT.load_frozen_corpus(corpus)


def source_case():
    return AUDIT.load_frozen_corpus()["cases"]["cases"][0]


def test_jinkou_uses_ground_and_inherent_god_without_liuren_lessons():
    case = source_case()
    board = AUDIT.observe_jinkou(case)
    assert board["overview"]["guishen"]["branch"] == "子"  # 玄武壬子, not 占时午.
    assert board["overview"]["guishen"]["earth_branch"] == "申"
    assert (
        board["overview"]["use_position"] == "贵神"
    )  # four yang, not a strongest-rank guess.
    assert [r["power"] for r in board["rows"]] == ["相", "休", "休", "囚"]
    assert [r["si_da_kong"] for r in board["rows"]] == [False, True, True, False]
    assert {m["name"] for m in board["motions"]} == {"妻动", "官动"}
    assert next(m for m in board["motions"] if m["name"] == "官动")[
        "empty_positions"
    ] == ["贵神"]
    poisoned = {
        "month_general": {"branch": "戌"},
        "board_style_detail": "元首",
        "three_transmissions": {"method": "FAKE"},
        "kongwang": "FAKE",
        "twelve_board": [],
    }
    assert build_jinkou_board(AUDIT.make_seed(case), poisoned, di_fen="申") == board
    other_ground = build_jinkou_board(AUDIT.make_seed(case), poisoned, di_fen="酉")
    assert other_ground["overview"]["guishen"]["name"] == "太阴"
    assert other_ground["overview"]["yuejiang"]["branch"] == "丑"


@pytest.mark.parametrize("bad", ["", "寅卯", "申 ", "北", "unknown"])
def test_invalid_ground_cannot_silently_fall_back(bad):
    with pytest.raises(ValidationError):
        JinkouAnalysisRequest(
            analysis_year=2026,
            analysis_month=1,
            analysis_day=1,
            analysis_hour=12,
            di_fen=bad,
        )
    with pytest.raises(ValueError, match="di_fen"):
        build_jinkou_board(
            AUDIT.make_seed(source_case()),
            {"month_general": {"branch": "戌"}},
            di_fen=bad,
        )


def test_unobserved_ground_fallback_is_explicit():
    case = source_case()
    board = build_jinkou_board(
        AUDIT.make_seed(case), {"month_general": {"branch": "戌"}}
    )
    assert board["overview"]["di_fen"] == "午"
    assert (
        board["overview"]["di_fen_source"]
        == "hour_branch_fallback_not_observed_direction"
    )
    assert "星没" in board["ruleset"]["unresolved"][1]


def test_explicit_day_night_can_override_hour_convention_without_relocating_gods():
    case = source_case()
    seed = AUDIT.make_seed({**case, "hour": "子"})
    inputs = {"month_general": {"branch": "戌"}}
    night = build_jinkou_board(seed, inputs, di_fen="申")
    day = build_jinkou_board(seed, inputs, di_fen="申", is_diurnal_override=True)
    assert night["overview"]["guishen"]["start_branch"] == "酉"
    assert night["overview"]["guishen"]["name"] == "螣蛇"
    assert day["overview"]["guishen"]["start_branch"] == "亥"
    assert day["overview"]["guishen"]["name"] == "玄武"
    assert day["overview"]["diurnal_basis"] == "explicit_override"


def test_liuren_xun_stems_are_not_two_branch_strings_and_empty_is_not_filled():
    for day in SEXAGENARY_CYCLE:
        stems = xun_dun_stems(day)
        assert len(stems) == 10
        assert set(stems.values()) == set("甲乙丙丁戊己庚辛壬癸")
        seed = AUDIT.make_seed({"day": day, "hour": "午"})
        for general in "子丑寅卯辰巳午未申酉戌亥":
            board = build_liureng_board(seed, month_general_override=general)
            assert board["board_order"] == "天盘顺布"
            for key in ("initial", "middle", "final"):
                item = board["three_transmissions"][key]
                if item["xun_kong"]:
                    assert item["ganzhi"] is item["dun_stem"] is None
                else:
                    assert item["ganzhi"] in SEXAGENARY_CYCLE
                    assert item["ganzhi"] == stems[item["branch"]] + item["branch"]
    assert xun_dun_stems("丙寅")["申"] == "壬"  # 日旬遁, not 五子遁的丙申.
    assert "戌" not in xun_dun_stems("丙寅")


def test_unknown_term_does_not_use_month_building_as_general():
    seed = replace(
        AUDIT.make_seed(source_case()),
        calendar_context={"current_solar_term": {"name": "missing"}},
    )
    with pytest.raises(ValueError, match="月建"):
        build_liureng_board(seed)


def test_lesson_with_day_branch_means_actual_day_branch_not_stem_house():
    seed = AUDIT.make_seed({"day": "甲子", "hour": "子"})
    board = build_liureng_board(seed, month_general_override="酉")
    first = board["four_lessons"][0]
    assert first["upper_branch"] == "亥"
    assert first["anchor_branch"] == "寅"  # 寄宫 only positions the first lesson.
    assert first["relations"]["with_day_branch"] == "平"  # 亥 vs 子, not 寅亥六合.


@pytest.mark.parametrize("zone,longitude", [("UTC", 15), ("America/New_York", -60)])
def test_zhongqi_is_an_instant_even_when_solar_hour_and_civil_date_differ(
    zone, longitude
):
    from zoneinfo import ZoneInfo

    published = datetime.fromisoformat("2026-02-18T23:52:00+08:00")
    for minutes, expected in [(-2, "子"), (2, "亥")]:
        dt = (published + timedelta(minutes=minutes)).astimezone(ZoneInfo(zone))
        seed = _build_analysis_seed(
            analysis_year=dt.year,
            analysis_month=dt.month,
            analysis_day=dt.day,
            analysis_hour=dt.hour,
            analysis_minute=dt.minute,
            analysis_timezone=zone,
            analysis_longitude=longitude,
            use_true_solar_time=True,
        )
        assert build_liureng_board(seed)["month_general"]["branch"] == expected


@pytest.mark.parametrize(
    "gender,expected", [("男", ["丙寅", "丁卯"]), ("女", ["壬申", "辛未"])]
)
def test_runyear_uses_lunar_new_year_and_correct_first_year(gender, expected):
    # Born before 2026's lunar new year: lunar birth year is 2025.
    person = create_person_info(
        birth_year=2026, birth_month=1, birth_day=10, birth_hour=12, gender=gender
    )
    for day, age, pair in zip((16, 17), (1, 2), expected):
        r = calculate_liureng_runyear(
            person,
            analysis_year=2026,
            analysis_month=2,
            analysis_day=day,
            analysis_hour=12,
            use_true_solar_time=False,
        )
        assert r["runyear"]["age"] == age
        assert r["runyear"]["ganzhi"] == pair
        assert r["runyear"]["birth_lunar_year"] == 2025


def test_unknown_gender_is_not_a_male_runyear_and_future_birth_is_rejected():
    seed = _build_analysis_seed(
        analysis_year=2026, analysis_month=5, analysis_day=1, analysis_hour=12
    )
    result = build_liureng_runyear(seed, "未知", 2000, birth_lunar_year=2000)
    assert result["ganzhi"] is None and result["status"] == "not_calculated"
    with pytest.raises(ValueError):
        build_liureng_runyear(seed, "男", 2027, birth_lunar_year=2027)


def test_wrong_output_cannot_pass_selected_reference_audit(monkeypatch):
    import fatebridge.core.metaphysics.jinkou as module

    previous = module.build_jinkou_board

    def corrupted(*args, **kwargs):
        result = deepcopy(previous(*args, **kwargs))
        result["rows"][0]["content"] = "错"
        return result

    monkeypatch.setattr(module, "build_jinkou_board", corrupted)
    report = AUDIT.audit()
    assert not report["selected_checks_passed"]
    assert any(not c["matched"] for c in report["checks"])

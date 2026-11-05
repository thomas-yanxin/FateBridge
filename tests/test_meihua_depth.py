"""Independent examples, boundary errors and faithful Mei Hua evidence."""

import json
import shutil
from datetime import datetime
from itertools import product
from pathlib import Path

import pytest

from fatebridge.core.almanac import get_lunar_context
from fatebridge.core.calendar import BaZiCalendar
from fatebridge.core.divination import (
    build_changed_hexagram,
    build_hexagram,
    build_meihua_interpretation,
    build_mutual_hexagram,
    derive_meihua_hexagram,
)
from fatebridge.core.meihua import build_meihua_evidence, meihua_ruleset
from fatebridge.services.divination import calculate_meihua_analysis
from fatebridge.validation.meihua import audit_meihua, reference_bundle

REFERENCES = Path(__file__).parent / "fixtures/meihua_v1"
CASES = json.loads((REFERENCES / "cases.json").read_text())["cases"]
# Literal trigram diagrams in bottom-to-top order, independently read from
# 卷一「八卦象例」; expected diagrams do not come from BAGUA_BY_NAME.
DIAGRAMS = {
    "乾": "111",
    "兑": "110",
    "离": "101",
    "震": "100",
    "巽": "011",
    "坎": "010",
    "艮": "001",
    "坤": "000",
}


def calculate(**overrides):
    return calculate_meihua_analysis(
        **{
            "analysis_year": 2026,
            "analysis_month": 2,
            "analysis_day": 5,
            "analysis_hour": 12,
            "analysis_timezone": "Asia/Shanghai",
            **overrides,
        }
    )


def enriched(case, month_branch="寅"):
    cast = derive_meihua_hexagram(**case["input"])
    cast.update(
        build_meihua_evidence(
            cast,
            lunar_year=None,
            is_leap_month=False,
            timezone_name="unspecified_classical_instant",
            month_branch=month_branch,
        )
    )
    return cast


def test_frozen_audit_does_not_promote_regression_pass_to_authority():
    report = audit_meihua(REFERENCES)
    assert report["selected_checks_passed"]
    assert sum(r["date_count"] for r in report["calendar"]["reports"]) == 72723
    assert not report["classical_rules"]["full_text_conformance_established"]
    assert report["interpretation"]["real_model_semantic_acceptance"] == "not_tested"
    assert report["real_world_prediction"]["prospective_case_count"] == 0
    assert report["real_world_prediction"]["authority_certified"] is False


def test_changed_reference_cannot_be_silently_accepted(tmp_path):
    shutil.copytree(REFERENCES, tmp_path / "refs")
    path = tmp_path / "refs/cases.json"
    path.write_text(path.read_text() + " ")
    with pytest.raises(ValueError, match="Frozen reference changed"):
        reference_bundle(tmp_path / "refs")


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_original_examples_and_explicit_pure_hexagram_rule(case):
    cast = enriched(case)
    expected = case["expected"]
    for key, field in [
        ("base_hexagram", "base_code"),
        ("changed_hexagram", "changed_code"),
        ("mutual_hexagram", "mutual_code"),
    ]:
        assert cast[key]["binary_code"] == expected[field]
    assert cast["seed"]["moving_line"] == expected["moving_line"]
    stages = {r["role"]: r for r in cast["stage_relations"]}
    assert stages["changed_use"]["relation"] == expected["changed_relation"]
    assert stages["body_mutual"]["trigram"] == expected["body_mutual"]
    assert stages["use_mutual"]["trigram"] == expected["use_mutual"]
    for row in stages.values():
        actual = {"meihua": cast}
        for key in row["fact_path"].split("."):
            actual = actual[key]
        assert (actual["name"], actual["element"]) == (row["trigram"], row["element"])
        assert row["body"] == cast["body_trigram"]["name"]


@pytest.mark.parametrize("upper,lower", tuple(product(DIAGRAMS, repeat=2)))
def test_all_64_diagrams_and_all_384_single_line_changes(upper, lower):
    base = build_hexagram(upper, lower)
    expected = DIAGRAMS[lower] + DIAGRAMS[upper]
    assert base["binary_code"] == expected
    for moving_line in range(1, 7):
        actual = build_changed_hexagram(base, moving_line)["binary_code"]
        assert len([i for i in range(6) if actual[i] != expected[i]]) == 1
        assert actual[moving_line - 1] != expected[moving_line - 1]
    # The generic mathematical operator is separate from Mei Hua's special
    # rule for pure Qian/Kun; these are not 384 historical validation cases.
    assert build_mutual_hexagram(base)["binary_code"] == expected[1:4] + expected[2:5]


@pytest.mark.parametrize(
    "day,month,year,branch,bazi_branch",
    [
        (29, 1, 2025, "巳", "辰"),
        (2, 2, 2025, "巳", "辰"),
        (5, 2, 2026, "巳", "午"),
        (16, 2, 2026, "巳", "午"),
        (17, 2, 2026, "午", "午"),
    ],
)
def test_lunar_year_never_silently_uses_lichun_year(
    day, month, year, branch, bazi_branch
):
    result = calculate(analysis_year=year, analysis_month=month, analysis_day=day)
    assert result["meihua"]["seed"]["year_branch"] == branch
    assert result["four_pillars"]["year"]["branch"] == bazi_branch
    assert result["meihua"]["calendar_policy"]["year_boundary"] == "lunar_new_year"


def test_calendar_context_does_not_take_hour_branch_from_unrelated_pillars():
    moment = datetime(2026, 2, 5, 12)
    pillars = BaZiCalendar.get_four_pillars(moment)
    pillars["hour"] = ("甲", "子")
    context = get_lunar_context(moment, pillars=pillars)
    assert context["meihua"]["seed"]["hour_branch"] == "午"


def test_leap_month_is_recorded_and_uses_nominal_month():
    result = calculate(analysis_year=2025, analysis_month=7, analysis_day=25)
    assert result["meihua"]["calendar_policy"]["is_leap_month"]
    assert result["meihua"]["seed"]["lunar_month"] == 6
    assert result["meihua"]["seed"]["lunar_day"] == 1
    assert result["meihua"]["calendar_policy"]["rule_kind"] == "software_convention"


def test_minute_role_and_midnight_are_explicit_and_not_bazi_rollover():
    a = calculate(analysis_hour=23, analysis_minute=0)
    b = calculate(analysis_hour=23, analysis_minute=59)
    next_day = calculate(analysis_day=6, analysis_hour=0)
    earlier = calculate(analysis_hour=22, analysis_minute=59)
    assert a["meihua"]["seed"] == b["meihua"]["seed"]
    assert (
        a["meihua"]["seed"]["hour_branch"]
        == next_day["meihua"]["seed"]["hour_branch"]
        == "子"
    )
    assert (
        a["meihua"]["seed"]["lunar_day"] + 1 == next_day["meihua"]["seed"]["lunar_day"]
    )
    assert earlier["meihua"]["seed"]["hour_branch"] == "亥"


@pytest.mark.parametrize("month,day,hour", [(3, 8, 2), (11, 1, 1)])
def test_dst_gap_and_fold_are_rejected_instead_of_guessing(month, day, hour):
    result = calculate(
        analysis_month=month,
        analysis_day=day,
        analysis_hour=hour,
        analysis_minute=30,
        analysis_timezone="America/New_York",
    )
    assert result["error_code"] == "validation_error"
    assert result["retryable"] is False
    explicit = calculate(
        analysis_month=month,
        analysis_day=day,
        analysis_hour=hour,
        analysis_minute=30,
        analysis_timezone="-04:00",
    )
    assert "error" not in explicit


@pytest.mark.parametrize("year,month,day", [(1899, 12, 31), (2101, 1, 1)])
def test_out_of_supported_range_is_input_error_not_missing_dependency(year, month, day):
    result = calculate(analysis_year=year, analysis_month=month, analysis_day=day)
    assert result["error_code"] == "validation_error"
    assert result["status_code"] == 422
    assert result["issues"][0]["code"] == "unsupported_calendar_date"


@pytest.mark.parametrize(
    "field,value",
    [
        ("lunar_month", 0),
        ("lunar_month", 13),
        ("lunar_month", True),
        ("lunar_day", 31),
        ("lunar_day", 0),
        ("lunar_day", 1.5),
        ("year_branch", ""),
        ("hour_branch", "甲"),
    ],
)
def test_invalid_integer_seeds_do_not_wrap_to_valid_trigrams(field, value):
    with pytest.raises(ValueError):
        derive_meihua_hexagram(**{**CASES[0]["input"], field: value})


@pytest.mark.parametrize(
    "branch,strong,weak",
    [
        ("寅", "木", "土"),
        ("午", "火", "金"),
        ("酉", "金", "木"),
        ("子", "水", "火"),
        ("辰", "土", "水"),
    ],
)
def test_seasonal_tags_do_not_invent_unstated_five_phase_weights(branch, strong, weak):
    cast = enriched(CASES[0], month_branch=branch)
    for row in cast["seasonal_strength"]["trigrams"]:
        assert row["strength"] == (
            "旺"
            if row["element"] == strong
            else "衰" if row["element"] == weak else "原文未定"
        )
    assert cast["seasonal_strength"]["convention_rule_id"] == "season_policy"


def test_actual_classical_verse_and_counterfactual_templates_stay_separate():
    cast = enriched(CASES[0])
    interpretation = build_meihua_interpretation(cast, "项目推进")
    actual = interpretation["classical_text_reference"]["moving_yaoci"]
    assert actual["position"] == 1
    assert "鞏用黃牛之革" in actual["text"]
    assert (
        sum(
            r["scenario"] == "actual_moving_line"
            for r in interpretation["line_oracles"]
        )
        == 1
    )
    assert "终应之变用艮对原体兑为用生体" in interpretation["traditional_judgement"]
    assert "当前更应把握" not in interpretation["comprehensive_judgement"]
    assert (
        interpretation["moving_line_phase"]["source_kind"]
        == "modern_editorial_position_template"
    )
    assert interpretation["evidence_scope"]["event_timing"] == "not_computed"


def test_ruleset_mutation_does_not_poison_future_calculations():
    rules = meihua_ruleset()
    rules["sources"][0]["url"] = "changed"
    assert meihua_ruleset()["sources"][0]["url"] != "changed"


def test_zero_remainder_is_sixth_line_and_question_does_not_recast():
    cast = derive_meihua_hexagram(
        year_branch="子", lunar_month=1, lunar_day=2, hour_branch="丑"
    )
    assert cast["seed"]["moving_line"] == 6  # (1 + 1 + 2 + 2) / 6
    assert cast["base_hexagram"]["binary_code"] == "010100"
    assert cast["changed_hexagram"]["binary_code"] == "010101"
    assert (
        calculate(question="项目推进")["meihua"]
        == calculate(question="学习安排")["meihua"]
    )

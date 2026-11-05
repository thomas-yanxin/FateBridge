"""Source-limited rules and explanations may not manufacture outcome claims."""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from fatebridge.analysis.education import EducationAnalysis
from fatebridge.analysis.relatives import RelativesAnalysis
from fatebridge.analysis.romance import RomanceAnalysis
from fatebridge.core.classical import (
    build_classical_overview,
    classical_snapshot_lines,
    determine_monthly_structure,
    life_stages_for_pillars,
)
from fatebridge.validation.predictions import (
    Forecast,
    Outcome,
    StudyPlan,
    evaluate_study,
)
from tests.support.transports import SPECS, business
from tests.support.transports import rest as _shared_rest
from tests.support.transports import surface_calls


def pillars(values):
    return dict(zip(("year", "month", "day", "hour"), (tuple(v) for v in values)))


rest = _shared_rest


@pytest.mark.parametrize(
    "chart",
    [
        ["甲申", "壬申", "乙巳", "戊寅"],  # 正官章原例
        ["甲戌", "壬申", "乙丑", "戊寅"],  # same finite condition, different seats
    ],
)
def test_revealed_seal_does_not_automatically_replace_primary_officer(chart):
    result = determine_monthly_structure(pillars(chart), "乙")
    assert result["label"] == "正官格"
    assert result["selection_rule"] == "officer_with_wealth_seal_support"
    assert "成败救应未完整裁定" in result["selection_source"]["scope"]


def test_completed_bureau_is_not_silently_overridden_by_officer_exception():
    result = determine_monthly_structure(
        pillars(["壬子", "壬申", "乙丑", "戊辰"]), "乙"
    )
    assert result["selection_rule"] != "officer_with_wealth_seal_support"


def test_unqualified_peer_month_is_not_a_blade_and_keeps_historical_disagreement():
    result = determine_monthly_structure(
        pillars(["壬戌", "丁未", "戊申", "乙卯"]), "戊"
    )
    assert result["label"] == "正官格"
    assert result["seat_qualification"]["is_yang_blade"] is False


@pytest.mark.parametrize("stem,branch", [("乙", "午"), ("丁", "酉")])
def test_yin_growth_stage_never_becomes_a_hidden_stem_root_in_chart_or_text(
    stem, branch
):
    chart = {name: (stem, branch) for name in ("year", "month", "day", "hour")}
    stages = life_stages_for_pillars(chart)
    assert stages["per_pillar"]["日支"] == "长生"
    assert stages["hidden_stem_roots"] == []
    text = "\n".join(classical_snapshot_lines(build_classical_overview(chart)))
    assert "强根：" not in text
    assert "同五行藏干根位置：未见" in text


def test_education_counts_are_not_iq_degrees_or_formation_decisions():
    result = EducationAnalysis.analyze_education(
        pillars(["甲子", "丙寅", "戊辰", "壬戌"])
    )
    level = result["education_level"]
    assert level["score_kind"] == "uncalibrated_rule_index"
    assert level["tier"].startswith("规则索引")
    assert result["counting_basis"].startswith("非日干每次1")
    for unsupported in (
        "本科可期",
        "学历层次高",
        "聪明又有定力",
        "如有神助",
        "学习能力强",
    ):
        assert unsupported not in json.dumps(result, ensure_ascii=False)


def test_subject_ties_are_retained_instead_of_assigning_arbitrary_aptitude():
    result = EducationAnalysis._analyze_subjects(
        pillars(["甲子", "丙寅", "戊辰", "壬戌"]),
        "戊",
        {"seal_weight": 1, "food_hurt_weight": 1, "officer_weight": 1},
    )
    assert "印、食伤、官杀计数并列最高" in result["inclination"]
    assert result["assessment_status"] == "modern_analogy_not_aptitude_measurement"


def test_no_study_signal_is_distinct_from_missing_timing():
    empty = EducationAnalysis._analyze_exam_timing("甲")
    unmatched = EducationAnalysis._analyze_exam_timing("甲", ("戊", "子"))
    assert empty["assessment_status"] == "missing_timing_input"
    assert unmatched == {"timing_signals": [], "assessment_status": "no_matching_rule"}


def test_relatives_no_match_does_not_claim_real_relationship_is_stable():
    result = RelativesAnalysis.analyze_relatives(
        pillars(["甲寅", "丙辰", "戊申", "壬戌"])
    )
    assert any("年支寅与日支申六冲" in v for v in result["palaces"]["relations"])
    for unsupported in ("缘分较厚", "母慈而助力大", "兄弟朋友多", "贵人助力有限"):
        assert unsupported not in json.dumps(result, ensure_ascii=False)


def test_peach_keeps_simultaneous_clash_and_combination_with_endpoints():
    chart = pillars(["甲子", "乙卯", "丁酉", "丙辰"])
    result = RomanceAnalysis.analyze_romance(chart, "女")
    relations = result["peach_quality"]["relations"]
    assert {r["relation"] for r in relations if r["peach_pillar"] == "day"} == {
        "六合",
        "六冲",
    }
    assert any(
        r["other_pillar"] == "month" and r["other_branch"] == "卯" for r in relations
    )
    assert any(
        r["other_pillar"] == "hour" and r["other_branch"] == "辰" for r in relations
    )
    assert "烂桃花" not in json.dumps(result, ensure_ascii=False)
    assert "追求者多" not in json.dumps(result, ensure_ascii=False)


def test_no_romance_signal_is_distinct_from_missing_timing():
    chart = pillars(["甲子", "丙寅", "甲辰", "戊戌"])
    peach = {"peach_branches": ["酉"]}
    empty = RomanceAnalysis._romance_timing(chart, "甲", "male", peach)
    unmatched = RomanceAnalysis._romance_timing(
        chart, "甲", "male", peach, ("甲", "子")
    )
    assert empty["assessment_status"] == "missing_timing_input"
    assert unmatched == {"timing_signals": [], "assessment_status": "no_matching_rule"}


INPUT = dict(
    birth_year=1990,
    birth_month=5,
    birth_day=15,
    birth_hour=10,
    birth_minute=30,
    gender="男",
    birth_timezone="America/New_York",
    use_true_solar_time=False,
)


@pytest.mark.parametrize(
    "key", ["bazi_birth", "bazi_education", "bazi_relatives", "bazi_romance"]
)
def test_correct_date_and_faithful_templates_survive_all_three_surfaces(
    key, surface_calls
):
    spec = SPECS[key]
    response, protocol, code, local = surface_calls(
        spec,
        INPUT,
        params={"as_of": "2026-10-12T02:00:00Z"},
        flags=["--response-char-limit", "0"],
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        if key == "bazi_birth":
            assert output["bazi_birth"]["analysis_date"] == "2026-10-11"
        else:
            dim = output[key.removeprefix("bazi_") + "_analysis"]
            assert dim["timing_context"]["analysis_date"] == "2026-10-11"
            assert "counting_basis" in dim


def prediction_records(**plan_changes):
    model_hash = "a" * 64
    plan = StudyPlan.model_validate(
        {
            "study_id": "synthetic-math-only",
            "data_kind": "synthetic",
            "preregistered_at": "2025-01-01T00:00:00Z",
            "window_start": "2025-02-01T00:00:00Z",
            "window_end": "2025-03-01T00:00:00Z",
            "target_definition": "Synthetic binary event, no real predictions",
            "model_sha256": model_hash,
            "baseline_probability": 0.5,
            "cohort": [
                {"case_id": str(i), "subject_id": "subject-" + str(i)} for i in range(2)
            ],
            **plan_changes,
        }
    )
    forecasts = [
        Forecast(
            case_id=str(i),
            issued_at="2025-01-02T00:00:00Z",
            model_sha256=model_hash,
            evidence_sha256="b" * 64,
            probability=p,
        )
        for i, p in enumerate((0.0, 1.0))
    ]
    outcomes = [
        Outcome(
            case_id=str(i),
            occurred=bool(i),
            event_at="2025-02-02T00:00:00Z" if i else None,
            recorded_at="2025-03-02T00:00:00Z",
            source_sha256="c" * 64,
            source_reference="synthetic fixture",
        )
        for i in range(2)
    ]
    return plan, forecasts, outcomes


def test_declared_training_overlap_cannot_be_counted_as_holdout():
    with pytest.raises(ValidationError, match="训练主体重叠"):
        prediction_records(training_subject_ids=["subject-0"])
    for declaration, expected in [
        (None, "not_declared"),
        ([], "declared_disjoint_not_externally_verified"),
    ]:
        plan, forecasts, outcomes = prediction_records(training_subject_ids=declaration)
        result = evaluate_study(
            plan, forecasts, outcomes, as_of=datetime(2026, 1, 1, tzinfo=timezone.utc)
        )
        assert result["training_overlap_check"] == expected
        assert result["authority_certified"] is False


def test_calibration_keeps_empty_bins_and_probability_endpoints_without_certifying():
    plan, forecasts, outcomes = prediction_records()
    result = evaluate_study(
        plan, forecasts, outcomes, as_of=datetime(2026, 1, 1, tzinfo=timezone.utc)
    )
    bins = result["metrics"]["calibration"]
    assert [b["count"] for b in bins] == [1, 0, 0, 0, 1]
    assert bins[0]["observed_rate"] == bins[0]["mean_probability"] == 0
    assert bins[-1]["observed_rate"] == bins[-1]["mean_probability"] == 1
    assert bins[-1]["upper_inclusive"] and bins[1]["mean_probability"] is None
    assert result["real_world_efficacy"] == "not_established_by_synthetic_data"


def test_four_axis_cli_keeps_full_marks_unestablished_even_when_finite_labels_match(
    tmp_path,
):
    path = tmp_path / "four-axes.json"
    command = (
        Path(__file__).resolve().parents[2] / "scripts/bazi/audit_bazi_authority.py"
    )
    result = subprocess.run(
        [sys.executable, str(command), "--output", str(path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, result.stderr
    report = json.loads(path.read_text())
    assert report["calendar"]["total"] == 72
    assert report["classical"]["summary"]["strength_unknown_in_source"] == 7
    assert report["interpretation_fidelity"]["model_transcripts_evaluated"] == 0
    assert report["real_world_prediction"]["real_world_efficacy"] == "not_tested"
    assert report["four_axis_full_marks"] is False and report["overall_score"] is None

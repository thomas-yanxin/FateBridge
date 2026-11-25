#!/usr/bin/env python3
"""Report four separate evidence axes; partial coverage never becomes full marks.

Exit 1 means universal acceptance has not been established, even when all
finite calendar references or template checks match. Invalid input is an error.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fatebridge.analysis.education import EducationAnalysis
from fatebridge.analysis.romance import RomanceAnalysis
from fatebridge.analysis.wealth import WealthAnalysis
from fatebridge.core.almanac import get_solar_terms_for_year
from fatebridge.validation.predictions import StudyPlan, evaluate_study

ROOT = Path(__file__).resolve().parents[2]


def calendar_axis() -> dict[str, Any]:
    fixture = ROOT / "tests/fixtures/calendar_hko_v1/reference.json"
    reference = json.loads(fixture.read_text())
    for source in reference["sources"]:
        if (
            hashlib.sha256((fixture.parent / source["file"]).read_bytes()).hexdigest()
            != source["sha256"]
        ):
            raise ValueError("Frozen HKO source hash mismatch")
    years = {c["year"] for c in reference["cases"]}
    terms = {
        year: {
            t.name: t.moment
            for t in get_solar_terms_for_year(year, reference["timezone"])
        }
        for year in years
    }
    results = []
    for case in reference["cases"]:
        expected = datetime.fromisoformat(case["at"])
        actual = terms[case["year"]][case["term"]]
        error = abs((actual - expected).total_seconds())
        results.append(
            {
                "year": case["year"],
                "term": case["term"],
                "reference": case["at"],
                "actual": actual.isoformat(),
                "absolute_error_seconds": error,
                "within_tolerance": error <= reference["tolerance_seconds"],
            }
        )
    return {
        "status": "finite_reference_comparison",
        "matched": sum(r["within_tolerance"] for r in results),
        "total": len(results),
        "sources": reference["sources"],
        "precision": reference["precision"],
        "tolerance_seconds": reference["tolerance_seconds"],
        "reference_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
        "scope": "2026–2028年共72个公布至分钟的节气时刻；不是全部支持年份或全部历法边界。",
        "not_covered": [
            "其他年份的独立逐例比较",
            "全部历法、时区史、真太阳时与换日约定的独立认证",
        ],
        "cases": results,
    }


def template_axis() -> dict[str, Any]:
    chart = dict(
        zip(
            ("year", "month", "day", "hour"),
            ((pillar[0], pillar[1]) for pillar in ("甲子", "乙卯", "丁酉", "丙辰")),
        )
    )
    education = EducationAnalysis.analyze_education(chart)
    quality = RomanceAnalysis.analyze_romance(chart)["peach_quality"]
    wealth_chart = dict(
        zip(
            ("year", "month", "day", "hour"),
            ((pillar[0], pillar[1]) for pillar in ("辛丑", "丁巳", "丙子", "乙未")),
        )
    )
    wealth = WealthAnalysis.analyze_wealth(wealth_chart, liunian_pillar=("辛", "未"))
    checks = {
        "education_is_uncalibrated_index": education["education_level"]["score_kind"]
        == "uncalibrated_rule_index",
        "education_tier_is_index_band": education["education_level"]["tier"].startswith(
            "规则索引"
        ),
        "no_signal_differs_from_missing": EducationAnalysis._analyze_exam_timing(
            "甲", ("戊", "子")
        )["assessment_status"]
        == "no_matching_rule"
        and EducationAnalysis._analyze_exam_timing("甲")["assessment_status"]
        == "missing_timing_input",
        "simultaneous_peach_combine_and_clash_retained": {
            r["relation"] for r in quality["relations"] if r["peach_pillar"] == "day"
        }
        == {"六合", "六冲"},
        "wealth_index_not_financial_probability": wealth["wealth_structure"][
            "score_kind"
        ]
        == "uncalibrated_rule_index",
        "storage_clash_not_automatically_opened": wealth["wealth_storage"][
            "storage_hits"
        ][0]["clash_present"]
        and wealth["wealth_storage"]["storage_hits"][0]["opened"] is None,
        "hidden_wealth_root_clash_retained": any(
            r["wealth_pillar"] == "year" and r["other_pillar"] == "hour"
            for r in wealth["wealth_risk"]["relations"]
        ),
    }
    return {
        "status": "finite_template_checks",
        "checks": checks,
        "matched": sum(checks.values()),
        "total": len(checks),
        "scope": "程序模板的指定反例检查；不代表九项全文已无误，也不代表真实模型逐句忠实度。",
        "model_transcripts_evaluated": 0,
        "not_covered": [
            "真实模型同一run的逐句证据归因",
            "所有九项旧解释模板的完整外部审阅",
        ],
    }


def build_report() -> dict[str, Any]:
    source = ROOT / "scripts/bazi/audit_bazi_classical.py"
    spec = importlib.util.spec_from_file_location("classical_authority_audit", source)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    classical = module.audit()
    solar_spec = importlib.util.spec_from_file_location(
        "bazi_solar_audit", ROOT / "scripts/bazi/audit_bazi_solar_accuracy.py"
    )
    assert solar_spec and solar_spec.loader
    solar = importlib.util.module_from_spec(solar_spec)
    solar_spec.loader.exec_module(solar)
    calendar = calendar_axis()
    calendar["solar_clock"] = solar.audit_solar(include_sweep=True)
    # Reuse the canonical empty workflow example; it contains no forecasts or outcomes.
    plan = StudyPlan.model_validate_json(
        (ROOT / "docs/examples/prediction-study/plan.json").read_text()
    )
    prediction = evaluate_study(
        plan, [], [], as_of=datetime(2028, 1, 2, tzinfo=timezone.utc)
    )
    prediction["scope"] = (
        "仅验证空登记流程；没有真实预测或结果。实际研究使用 scripts/evaluation/audit_prediction_study.py。"
    )
    return {
        "audit_id": "bazi_four_axes_v1",
        "overall_score": None,
        "four_axis_full_marks": False,
        "authority_certified": False,
        "calendar": calendar,
        "classical": {
            "profile_id": classical["profile_id"],
            "summary": classical["summary"],
            "independence": classical["independence"],
            "reference_hashes": classical["reference_hashes"],
            "scope": "既有十例已用于开发，名称全匹配也不再是盲测；强弱、成格和相神仍按各自分母报告。",
        },
        "interpretation_fidelity": template_axis(),
        "real_world_prediction": prediction,
        "source_fingerprints": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT / "src/fatebridge").rglob("*.py"))
        },
    }


def strength_review_axis() -> dict[str, object]:
    """Replay frozen disagreements without turning documentary gaps into passes."""
    manifest = (
        ROOT / "tests/data/bazi_disagreement_review_v1/review.json"
    ).read_bytes()
    if hashlib.sha256(manifest).hexdigest() != (
        "6943730d8c161020a276995c36d7528a5c2da56c5a1100a1e49b9e6ee25b3aa1"
    ):
        raise ValueError("Frozen strength review manifest hash mismatch")
    review = json.loads(manifest)
    for filename, fingerprint in (
        ("bazi-source-annotations.json", "source_annotations_sha256"),
        ("bazi-source-conditions.json", "source_conditions_sha256"),
    ):
        source = ROOT / "src/fatebridge/data/reference" / filename
        if hashlib.sha256(source.read_bytes()).hexdigest() != review[fingerprint]:
            raise ValueError(f"Frozen documentary source hash mismatch: {filename}")
    specification = importlib.util.spec_from_file_location(
        "source_corpus_authority_audit",
        ROOT / "scripts/bazi/audit_bazi_source_corpus.py",
    )
    assert specification and specification.loader
    source_audit = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(source_audit)
    current = source_audit.audit()
    denominators = {
        "records": current["record_count"],
        "distinct_inputs": current["distinct_inputs"],
        "unknown_strength_records": current["unknown_strength_records"],
        "disagreement_inputs": len(current["all_distinct_disagreements"]),
        "constraints": len(current["bounded_strength_constraints"]),
        "constraint_violations": len(current["bounded_strength_constraint_violations"]),
    }
    expected_groups = {tuple(record["pillars"]) for record in review["disagreements"]}
    actual_groups = {
        tuple(group["pillars"]) for group in current["all_distinct_disagreements"]
    }
    frozen_constraints = [
        {
            "constraint_id": constraint["constraint_id"],
            "reference_id": constraint["reference_id"],
            "forbidden_strengths": constraint["forbidden_strengths"],
            "actual_strength": constraint["engineering_strength"],
            "matches": constraint["constraint_matches"],
        }
        for constraint in review["constraints"]
    ]
    current_grades = {
        row["group"] + ":" + row["id"]: row["actual_strength"]
        for row in current["rows"]
    }
    changed_cases = [
        record["reference_id"]
        for record in (
            review["disagreements"]
            + review["constraints"]
            + review["previously_exposed_controls"]
        )
        if current_grades[record["reference_id"]] != record["engineering_strength"]
    ]
    changed_adjudications = [
        row["group"] + ":" + row["id"]
        for row in current["rows"]
        if row["classical_adjudication"]["status"] != "not_adjudicated"
        or row["classical_adjudication"]["body_strength"] is not None
        or row["classical_adjudication"]["ordinary_fuyi_applicable"] is not None
    ]
    return {
        "review_id": review["review_id"],
        "frozen_denominators": review["frozen_denominators"],
        "current_denominators": denominators,
        "baseline_reproduced": denominators == review["frozen_denominators"]
        and expected_groups == actual_groups
        and frozen_constraints == current["bounded_strength_constraints"]
        and not changed_cases
        and not changed_adjudications,
        "changed_case_grades": changed_cases,
        "changed_classical_adjudications": changed_adjudications,
        "rules": review["rules"],
        "documentary_disagreements": review["disagreements"],
        "documentary_constraints": review["constraints"],
        "current_disagreements": current["all_distinct_disagreements"],
        "current_constraints": current["bounded_strength_constraints"],
        "classical_grade_comparison": current["classical_grade_comparison"],
        "independent_human_double_read": "not_completed",
        "new_independent_validation_credit": 0,
        "blind_holdout_status": review["rules"]["blind_holdout_status"],
        "authority_certified": False,
        "scope": review["scope"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--strength-review-only",
        action="store_true",
        help="Replay the frozen strength disagreements and bounded constraints only.",
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.strength_review_only:
        review = strength_review_axis()
        args.output.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n")
        summary = {
            "denominators": review["current_denominators"],
            "baseline_reproduced": review["baseline_reproduced"],
            "authority_certified": False,
            "independent_human_double_read": "not_completed",
        }
    else:
        result = build_report()
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        summary = {
            "calendar": f"{result['calendar']['matched']}/{result['calendar']['total']}",
            "classical": result["classical"]["summary"],
            "real_world_prediction": result["real_world_prediction"][
                "real_world_efficacy"
            ],
            "four_axis_full_marks": False,
        }
    print(json.dumps(summary, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

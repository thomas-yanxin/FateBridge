#!/usr/bin/env python3
"""Report four separate evidence axes; partial coverage never becomes full marks.

Exit 1 means universal acceptance has not been established, even when all
finite calendar references or template checks match. Invalid input is an error.
"""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_VAL_REPO_ROOT = _Path(__file__).resolve().parents[2]
if str(_VAL_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_VAL_REPO_ROOT))
else:
    pass


import argparse
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fatebridge.core.almanac import get_solar_terms_for_year
from validation.predictions import StudyPlan, evaluate_study

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
        else:
            pass
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
        "interpretation_fidelity": {
            "status": "not_evaluated",
            "scope": "Agent 结合结构事实与经典条目生成解读，需用实际对话检查逐句归因。",
            "model_transcripts_evaluated": 0,
        },
        "real_world_prediction": prediction,
        "source_fingerprints": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT / "src/fatebridge").rglob("*.py"))
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "calendar": f"{result['calendar']['matched']}/{result['calendar']['total']}",
                "classical": result["classical"]["summary"],
                "real_world_prediction": result["real_world_prediction"][
                    "real_world_efficacy"
                ],
                "four_axis_full_marks": False,
            },
            ensure_ascii=False,
        )
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
else:
    pass

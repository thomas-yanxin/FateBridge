"""Compare yearly Taiyi arithmetic to a frozen independent text transcription.

Run: uv run --locked --extra dev python scripts/audit_taiyi_classical.py
Exit 1 on incomplete classical acceptance, even if engineering tests pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.metaphysics.taiyi_year import RULESET_ID, cyclic_core, yearly_core

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests" / "fixtures" / "taiyi_jinjing_v1"
DEPTH_CORPUS = ROOT / "tests" / "fixtures" / "taiyi_jinjing_v2"


def verify_depth_sources(corpus: Path = DEPTH_CORPUS) -> None:
    manifest = json.loads((corpus / "manifest.json").read_text())
    for item in manifest["source_files"]:
        if (
            hashlib.sha256((corpus / item["file"]).read_bytes()).hexdigest()
            != item["sha256"]
        ):
            raise ValueError("冻结来源指纹不符：" + item["file"])


def audit_yin(corpus: Path = DEPTH_CORPUS) -> dict[str, Any]:
    """Include every Yin row and both counts, including all source conflicts."""
    verify_depth_sources(corpus)
    cases_bytes = (corpus / "yin-cases.json").read_bytes()
    cases = json.loads(cases_bytes)
    if sorted(c["accumulation"] for c in cases) != list(range(1, 73)):
        raise ValueError("必须保留完整阴72局，不能删除不一致案例")
    matching_cases = matching_fields = 0
    disagreements = []
    for case in cases:
        if case["yin"] is not True or set(case["expected"]) != {
            "main_count",
            "guest_count",
        }:
            raise ValueError("每局必须验收阴遁主客两算，不能删除未匹配字段")
        core = cyclic_core(case["accumulation"], yin=True)
        checks = []
        for field, expected in case["expected"].items():
            matched = core[field] == expected
            checks.append(matched)
            matching_fields += int(matched)
            if not matched:
                disagreements.append(
                    {
                        "case_id": case["id"],
                        "ju": case["accumulation"],
                        "field": field,
                        "expected_transcription": expected,
                        "computed": core[field],
                        "source": case["source"],
                        "status": "facsimile_confirms_transcription_rule_derivation_unresolved",
                    }
                )
        matching_cases += int(all(checks))
    return {
        "oracle_kind": "frozen_manual_classical_transcription",
        "corpus_sha256": hashlib.sha256(cases_bytes).hexdigest(),
        "total_cases": 72,
        "checked_fields": 144,
        "matching_cases": matching_cases,
        "matching_fields": matching_fields,
        "disagreements": disagreements,
        "classical_acceptance_passed": not disagreements,
        "whole_book_conformance": "not_established",
    }


def audit(corpus: Path = CORPUS) -> dict[str, Any]:
    manifest = json.loads((corpus / "manifest.json").read_text())
    cases_bytes = (corpus / "cases.json").read_bytes()
    if hashlib.sha256(cases_bytes).hexdigest() != manifest["cases_sha256"]:
        raise ValueError("原典案例指纹不符，不能验收")
    for source in manifest["sources"]:
        if (
            hashlib.sha256((corpus / source["file"]).read_bytes()).hexdigest()
            != source["sha256"]
        ):
            raise ValueError("冻结来源指纹不符：" + source["file"])
    cases = json.loads(cases_bytes)
    if sorted(c["ju"] for c in cases) != list(range(1, 73)):
        raise ValueError("必须保留完整72局，不能删除不一致案例")
    disagreements = []
    passed_cases = 0
    matching_fields = 0
    checked_fields = 0
    for case in cases:
        if set(case["expected"]) != {"main_count", "guest_count"}:
            raise ValueError("每局必须验收主客两算，不能删除未匹配字段")
        computed = yearly_core(case["year"])
        if computed["kook_number"] != case["ju"]:
            raise ValueError("案例年份与局数不一致")
        ok = True
        for field, expected in case["expected"].items():
            checked_fields += 1
            if computed[field] == expected:
                matching_fields += 1
            else:
                ok = False
                disagreements.append(
                    {
                        "case_id": case["id"],
                        "ju": case["ju"],
                        "field": field,
                        "expected_transcription": expected,
                        "computed": computed[field],
                        "source": case["source"],
                        "status": "facsimile_confirmed_rule_table_disagreement_requires_external_adjudication",
                    }
                )
        passed_cases += int(ok)
    return {
        "ruleset": RULESET_ID,
        "oracle_kind": "frozen_classical_transcription_independent_of_production_code",
        "corpus_sha256": hashlib.sha256(cases_bytes).hexdigest(),
        "implementation_sha256": hashlib.sha256(
            (ROOT / "src/fatebridge/core/metaphysics/taiyi_year.py").read_bytes()
        ).hexdigest(),
        "total_cases": len(cases),
        "matching_cases": passed_cases,
        "checked_fields": checked_fields,
        "matching_fields": matching_fields,
        "disagreements": disagreements,
        "classical_acceptance_passed": not disagreements,
        "whole_book_conformance": "not_established",
        "calendar_validation": "separate_HKO_modern_boundary_tests_not_ancient_calendar_reconstruction",
        "interpretation_validation": "deterministic_trace_and_spatial_predicates_only",
        "real_world_efficacy": "not_tested",
        "authority_certified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--include-yin", action="store_true", help="纳入完整阴遁72局，不改原阳遁分母"
    )
    args = parser.parse_args()
    report = audit()
    if args.include_yin:
        yin = audit_yin()
        report = {
            "yang": report,
            "yin": yin,
            "combined": {
                "total_cases": report["total_cases"] + yin["total_cases"],
                "matching_cases": report["matching_cases"] + yin["matching_cases"],
                "checked_fields": report["checked_fields"] + yin["checked_fields"],
                "matching_fields": report["matching_fields"] + yin["matching_fields"],
            },
            "classical_acceptance_passed": report["classical_acceptance_passed"]
            and yin["classical_acceptance_passed"],
            "whole_book_conformance": "not_established",
        }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    print(rendered, end="")
    return 0 if report["classical_acceptance_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

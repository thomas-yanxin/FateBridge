"""Audit printed literal hour pairs and verify whole same-run clock evidence."""

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.metaphysics.common import SEXAGENARY_CYCLE
from fatebridge.core.qimen_time_conditions import build_hour_branch_tomb
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims


def audit_hour_branch_tombs(directory: Path) -> dict[str, Any]:
    reference = json.loads((directory / "sources-and-hours.json").read_text())
    cases = reference["cases"]
    if len(cases) != 6 or {c["hour_ganzhi"] for c in cases} != {
        "丙戌",
        "壬辰",
        "丁丑",
        "癸未",
        "戊戌",
        "己丑",
    }:
        raise ValueError("须保留卷二正文全部六时，包括歌诀未列的己丑")
    sources = reference["source_files"]
    if (
        len(sources) != 1
        or sources[0]["file"] != "siku-page33.pdf"
        or sources[0]["original_pdf_page"] != 33
    ):
        raise ValueError("须保留第33页原始影印摘页")
    if (
        hashlib.sha256((directory / sources[0]["file"]).read_bytes()).hexdigest()
        != sources[0]["sha256"]
    ):
        raise ValueError("六时入墓影印指纹不一致")
    by_hour = {c["hour_ganzhi"]: c for c in cases}
    disagreements = []
    for hour in SEXAGENARY_CYCLE:
        result = build_hour_branch_tomb(hour, source=reference["source"])
        expected = hour in by_hour
        definition = (
            {k: by_hour[hour][k] for k in ("element", "polarity", "verse_listed")}
            if expected
            else None
        )
        if result["matched"] != expected or result["matched_definition"] != definition:
            disagreements.append(
                {"hour_ganzhi": hour, "expected_match": expected, "actual": result}
            )
    return {
        "printed_literal_pair_definitions": 6,
        "verse_list_count": 5,
        "finite_hour_values_checked": 60,
        "finite_nonlisted_hour_values": 54,
        "disagreements": disagreements,
        "verse_omission_treated_as_disagreement": False,
        "heaven_stem_palace_tomb_rule_validated": False,
        "whole_book_conformance_established": False,
        "real_world_efficacy": "not_tested",
    }


def verify_qimen_time_condition_quotes(
    payload: dict[str, Any], claims: list[CalculationClaim]
) -> dict[str, Any]:
    """Require the complete clock-condition object, including its scope limits."""
    report = verify_calculation_claims(payload, claims)
    errors = list(report["errors"])
    for index, claim in enumerate(claims):
        if claim.path != "qimen.stem_context.hour_branch_tomb":
            errors.append(
                {"claim_index": index, "code": "whole_qimen_hour_branch_tomb_required"}
            )
    return {
        "method_id": "same_run_whole_qimen_time_condition_v1",
        "status": (
            "rejected" if errors or not claims else "verified_structured_time_condition"
        ),
        "checked_claim_count": len(claims),
        "errors": errors,
        "free_text_semantics_validated": False,
        "real_world_efficacy_validated": False,
        "scope": "只核同run完整回执中的整条时干支条件及其限定；不认证任意自由解释、盘宫入墓、来源真实性或预测效度。",
    }

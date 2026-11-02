"""Independent literal month tables and trusted same-run fixed position text."""

import re
from typing import Any

from fatebridge.core.fengshui.models import MonthlyRequest
from fatebridge.core.fengshui.monthly import (
    monthly_position_reading,
    monthly_provenance,
    monthly_stars,
)
from fatebridge.core.fengshui.monthly_integrity import validate_monthly_layer
from fatebridge.core.fengshui.monthly_time import JIE
from fatebridge.utils.errors import FengshuiCalculationError
from fatebridge.utils.json_digest import digest
from fatebridge.validation.claims import _same_value


def audit_monthly_reference(reference: dict[str, Any]) -> dict[str, Any]:
    groups = reference["printed_center_columns"]
    if (
        len(groups) != 3
        or sorted(b for g in groups for b in g["branches"])
        != sorted("子丑寅卯辰巳午未申酉戌亥")
        or any(len(g["centers"]) != 12 for g in groups)
        or any(
            type(n) is not int or n not in range(1, 10)
            for g in groups
            for n in g["centers"]
        )
        or len(reference["printed_term_rows"]) != 12
    ):
        raise ValueError("月紫白夹具须保留十二支、三组与36个原始星数")
    differences = []
    checked = 0
    for year in range(2020, 2032):
        branch = "子丑寅卯辰巳午未申酉戌亥"[(year - 4) % 12]
        column = next(g for g in groups if branch in g["branches"])
        for month, expected in enumerate(column["centers"], 1):
            actual = monthly_stars(
                MonthlyRequest(effective_solar_year=year, solar_month_number=month)
            )["center_star_number"]
            checked += 1
            if not _same_value(actual, expected):
                differences.append(
                    {
                        "year_branch": branch,
                        "month": month,
                        "expected": expected,
                        "actual": actual,
                    }
                )
    label_differences = [
        {
            "solar_month_number": index,
            "printed_terms": terms,
            "selected_start_term": JIE[index - 1],
            "resolution": "independent_author_and_official_astronomical_order_not_rewriting_print",
        }
        for index, terms in enumerate(reference["printed_term_rows"], 1)
        if terms[0] != JIE[index - 1]
    ]
    return {
        "source_cell_count": 36,
        "branch_month_checks": checked,
        "numeric_differences": differences,
        "numeric_scoped_acceptance_passed": not differences,
        "printed_calendar_label_differences": label_differences,
        "printed_calendar_labels_all_conform": not label_differences,
        "whole_book_conformity_established": False,
        "independent_human_expert_review": False,
        "real_world_prediction": "not_tested",
    }


def verify_monthly_reading(
    payload: dict[str, Any], *, trusted_run_metadata: dict[str, Any]
) -> dict[str, Any]:
    """Verify complete delivered text against independently retained receipt."""
    errors = []
    metadata = payload.get("run_metadata") or {}
    expected_digest = trusted_run_metadata.get("business_output_sha256")
    if (
        not isinstance(metadata, dict)
        or not isinstance(trusted_run_metadata.get("run_id"), str)
        or not trusted_run_metadata.get("run_id")
        or not isinstance(expected_digest, str)
        or re.fullmatch(r"[a-f0-9]{64}", expected_digest) is None
        or not _same_value(metadata, trusted_run_metadata)
    ):
        errors.append("trusted_original_receipt_mismatch")
    try:
        if (
            digest({k: v for k, v in payload.items() if k != "run_metadata"})
            != expected_digest
        ):
            errors.append("incomplete_changed_or_projected_business_payload")
    except (TypeError, ValueError):
        errors.append("non_json_business_payload")
    if not isinstance(metadata, dict) or metadata.get("tool_name") not in {
        "fengshui_monthly_stars",
        "fengshui_assess",
    }:
        errors.append("unsupported_original_tool")
    statement_count = 0
    complete = False
    numeric_palaces = 0
    try:
        layer = payload["layers"]["monthly_stars"]
        try:
            numeric_palaces = validate_monthly_layer(layer)["numeric_palaces"]
        except FengshuiCalculationError:
            errors.append("monthly_numeric_context_inconsistent")
        if not _same_value(layer["ruleset"], monthly_provenance()):
            errors.append("unsupported_monthly_profile")
        complete = layer["status"] == "complete"
        if layer["status"] not in {"complete", "partial"}:
            errors.append("unsupported_monthly_status")
        if complete:
            palaces = layer["palaces"]
            if (
                set(palaces) != {"C", "N", "NE", "E", "SE", "S", "SW", "W", "NW"}
                or any(
                    type(p["monthly_star_number"]) is not int for p in palaces.values()
                )
                or sorted(p["monthly_star_number"] for p in palaces.values())
                != list(range(1, 10))
            ):
                errors.append("incomplete_monthly_position_coverage")
        elif layer["palaces"] or not layer["missing_inputs"]:
            errors.append("inconsistent_partial_monthly_context")
        expected = monthly_position_reading(layer)
        if not _same_value(layer["position_reading"], expected):
            errors.append("fixed_text_context_or_coverage_mismatch")
        statement_count = len(expected["statements"])
    except (KeyError, TypeError, ValueError, AttributeError):
        errors.append("unsupported_or_incomplete_monthly_context")
    return {
        "method_id": "trusted_run_monthly_position_reading_v1",
        "status": "rejected" if errors else "verified_served_fixed_monthly_reading",
        "errors": errors,
        "checked_statement_count": statement_count,
        "monthly_position_coverage_verified": complete and not errors,
        "derived_monthly_numeric_consistency_verified": numeric_palaces == 9
        and not errors,
        "calendar_accuracy_verified": False,
        "free_model_prose_verified": False,
        "whole_book_conformity_established": False,
        "real_world_prediction_established": False,
        "authority_certified": False,
        "scope": "只核验本版本固定位置释义与完整可信原run的一致性；历法实现精度须另读独立对照，不以本项未认证否定其他层的有效证据。",
    }

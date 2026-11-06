"""Verify served fixed text and all quotations against a separately trusted run.

The caller must obtain the trusted identifiers independently of the submitted
payload. This is not a signature or a certificate of physical/predictive truth.
"""

from typing import Any

from fatebridge.core.fengshui.host_guest import validate as validate_host_guest
from fatebridge.core.fengshui.mutual_geometry import validate_author_geometries
from fatebridge.core.fengshui.reading import build_natal_reading
from fatebridge.core.fengshui.structure_integrity import validate_natal_structure
from fatebridge.core.public_output import same_public_value as _same_value
from fatebridge.utils.errors import FengshuiCalculationError
from fatebridge.utils.json_values import same_value


def verify_fengshui_reading(
    payload: dict[str, Any],
    *,
    trusted_payload: dict[str, Any],
) -> dict[str, Any]:
    errors = []
    metadata = payload.get("run_metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    trusted_run_id = (trusted_payload.get("run_metadata") or {}).get("run_id")
    if (
        not isinstance(trusted_run_id, str)
        or not trusted_run_id
        or metadata.get("run_id") != trusted_run_id
        or not same_value(metadata, trusted_payload.get("run_metadata"))
    ):
        errors.append({"code": "trusted_original_receipt_mismatch"})
    if not same_value(payload, trusted_payload):
        errors.append({"code": "incomplete_changed_or_projected_business_payload"})
    if metadata.get("tool_name") not in {"fengshui_assess", "fengshui_xuankong_natal"}:
        errors.append({"code": "unsupported_original_tool"})
    actual = payload.get("calculation_reading")
    version = actual.get("version") if isinstance(actual, dict) else None
    geometry_counts = {
        "checked": 0,
        "diagram_derived": 0,
        "five_table_only": 0,
        "unknown": 0,
    }
    host_guest_counts = dict(
        relations=0, source_matches=0, source_differences=0, source_ambiguous=0
    )
    try:
        natal = payload.get("layers", {}).get("xuankong_natal", {})
        if natal.get("interpretation") is not None:
            host_guest_counts = validate_host_guest(natal["interpretation"], natal)
    except (FengshuiCalculationError, KeyError, AttributeError, TypeError):
        errors.append({"code": "host_guest_inconsistent"})
    try:
        natal = payload.get("layers", {}).get("xuankong_natal", {})
        interpretation = natal.get("interpretation")
        if interpretation is not None:
            geometry_counts = validate_author_geometries(
                interpretation,
                natal,
                current=interpretation["current_period_context"]["number"],
            )
    except FengshuiCalculationError as error:
        errors.append(
            {
                "code": (
                    "author_timeliness_inconsistent"
                    if error.reason == "natal_author_timeliness_inconsistent"
                    else "author_mutual_geometry_inconsistent"
                )
            }
        )
    except (KeyError, AttributeError, TypeError):
        errors.append({"code": "author_mutual_geometry_inconsistent"})
    if version == "1.2.0":
        try:
            for chart in (
                payload.get("layers", {})
                .get("xuankong_natal", {})
                .get("candidates", [])
            ):
                validate_natal_structure(chart)
        except (FengshuiCalculationError, AttributeError, TypeError):
            errors.append({"code": "numeric_structure_inconsistent"})
    if version != "1.2.0":
        errors.append({"code": "unsupported_reading_version"})
    expected = build_natal_reading(payload)
    if expected["status"] != "rendered" or not expected["statements"]:
        errors.append({"code": "unsupported_reading_context"})
    if not _same_value(actual, expected):
        errors.append({"code": "fixed_text_context_or_coverage_mismatch"})
    numeric_charts = (
        sum(s["kind"] == "natal_distribution" for s in expected.get("statements", []))
        if version == "1.2.0" and not errors
        else 0
    )
    opposite_charts = (
        sum(
            s["kind"] == "opposite_star_summary" for s in expected.get("statements", [])
        )
        if version == "1.2.0" and not errors
        else 0
    )
    return {
        "method_id": "trusted_run_fengshui_fixed_reading_v1",
        "status": "rejected" if errors else "verified_served_fixed_reading",
        "errors": errors,
        "checked_statement_count": len(expected.get("statements", [])),
        "checked_reading_version": version,
        "numeric_structure_coverage_verified": numeric_charts > 0,
        "numeric_structure_chart_count": numeric_charts,
        "opposite_palace_coverage_verified": opposite_charts > 0,
        "opposite_palace_chart_count": opposite_charts,
        "derived_numeric_consistency_verified": numeric_charts > 0,
        "host_guest_relation_count": (
            host_guest_counts["relations"] if not errors else 0
        ),
        "host_guest_coverage_verified": (
            version == "1.2.0"
            and not errors
            and host_guest_counts["relations"] > 0
            and sum(
                s["kind"] == "host_guest_relation"
                for s in expected.get("statements", [])
            )
            == host_guest_counts["relations"]
        ),
        "host_guest_literal_source_matches": (
            host_guest_counts["source_matches"] if not errors else 0
        ),
        "host_guest_literal_source_differences": (
            host_guest_counts["source_differences"] if not errors else 0
        ),
        "host_guest_ambiguous_source_roles": (
            host_guest_counts["source_ambiguous"] if not errors else 0
        ),
        "author_geometry_record_count": geometry_counts["checked"] if not errors else 0,
        "author_geometry_coverage_verified": (
            geometry_counts["diagram_derived"] > 0
            and version == "1.2.0"
            and sum(
                s["kind"] == "mutual_use_geometry"
                for s in expected.get("statements", [])
            )
            == geometry_counts["checked"]
            and not errors
        ),
        "author_geometry_derived_record_count": (
            geometry_counts["diagram_derived"] if not errors else 0
        ),
        "author_geometry_five_table_only_count": (
            geometry_counts["five_table_only"] if not errors else 0
        ),
        "author_geometry_unknown_count": (
            geometry_counts["unknown"] if not errors else 0
        ),
        "free_model_prose_verified": False,
        "whole_book_conformity_established": False,
        "real_world_prediction_established": False,
        "authority_certified": False,
        "scope": "只核验本版本固定释义及完整上下文与另行可信保存原结果的一致性；不认证自行提交的原结果、任意自由文本、输入真实性、原典全本或现实效力。",
    }

"""Read recorded specialty house roles without inventing missing provenance.

This checks the current numeric house-code policy and structured declarations.
It does not check arbitrary prose, unrecorded native calls or original texts.
"""

from __future__ import annotations

from typing import Any, Mapping

from fatebridge.utils.house_systems import house_system_fields, normalize_house_system


def audit_specialty_house_roles(
    payload: Mapping[str, Any],
    *,
    requested_hsys: int | None = None,
    declared_base_house_system: str | None = None,
) -> dict[str, Any]:
    """Keep missing evidence separate from an observed contradictory claim."""
    if requested_hsys is not None and (
        type(requested_hsys) is not int or requested_hsys not in range(9)
    ):
        raise ValueError("requested_hsys requires an explicit integer0..8")
    base = payload.get("base_chart", payload)
    profile = base.get("chart_profile", {})
    midpoint = payload.get("midpoint_analysis", {})
    sensitivity = midpoint.get("time_sensitivity", payload.get("time_sensitivity", {}))
    issues, missing = [], []
    key = profile.get("house_system")
    observed = {
        "key": key,
        "numeric_code": profile.get("house_system_code"),
        "label_zh": profile.get("house_system_label_zh"),
        "swiss_house_code": None,
    }
    if not isinstance(key, str) or not key.strip():
        missing.append("base_house_system")
    else:
        try:
            canonical = house_system_fields(key)
        except ValueError:
            issues.append("unrecognized_recorded_base_house_system")
        else:
            observed["swiss_house_code"] = canonical["house_system"]
            if observed["numeric_code"] != canonical["house_system_code"]:
                issues.append("recorded_numeric_code_differs_from_current_policy")
            if observed["label_zh"] != canonical["house_system_label_zh"]:
                issues.append("recorded_label_differs_from_current_canonical_label")
            if requested_hsys is not None:
                if normalize_house_system(requested_hsys) != canonical["house_system"]:
                    issues.append("requested_hsys_differs_from_recorded_base")
            if declared_base_house_system is not None:
                if (
                    normalize_house_system(declared_base_house_system)
                    != canonical["house_system"]
                ):
                    issues.append(
                        "declared_base_house_system_differs_from_recorded_base"
                    )

    reference = midpoint.get("profile", {}).get("reference_angle_model")
    if midpoint and reference is None:
        missing.append("native_reference_angle_model")
    sample_models = []
    for index, sample in enumerate(sensitivity.get("samples", [])):
        model = sample.get("reference_angle_model")
        sample_models.append(
            {"offset_seconds": sample.get("offset_seconds"), "model": model}
        )
        if model is None:
            missing.append(f"sample{index}_reference_angle_model")
    for model in [reference, *[row["model"] for row in sample_models]]:
        if model is not None and (
            model.get("role") != "reference_angles_only"
            or model.get("cusp_output_used") is not False
        ):
            issues.append("reference_angle_role_or_unused_cusp_declaration_invalid")
    meridian = midpoint.get("meridian_houses", {}).get("profile", {}).get("house_code")
    partition = payload.get("sector_profile", {}).get("ruleset_id")
    if not midpoint and "sector_profile" not in payload:
        missing.append("specialty_geometry_layer")
    if midpoint and meridian is None:
        missing.append("meridian_cusp_house_code")
    if "sector_profile" in payload and partition is None:
        missing.append("custom_partition_ruleset")
    if any(
        model is not None and not model.get("house_code")
        for model in [reference, *[row["model"] for row in sample_models]]
    ):
        missing.append("reference_angle_model_house_code")
    return {
        "policy_id": "fatebridge_specialty_house_roles_v1",
        "status": (
            "mismatch"
            if issues
            else "partial" if missing else "consistent_recorded_roles"
        ),
        "base_house_system": observed,
        "native_reference_angle_model": reference,
        "sample_reference_angle_models": sample_models,
        "meridian_cusp_house_code": meridian,
        "custom_partition_ruleset": partition,
        "issues": issues,
        "missing_evidence": missing,
        "scope": "Current house-code policy and recorded structured roles only; no arbitrary-prose, unrecorded-call, full-original or predictive validation",
        "all_four_perfect": False,
    }

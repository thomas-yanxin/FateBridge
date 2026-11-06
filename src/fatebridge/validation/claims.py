"""Verify structured quotations against the complete original calculation.

This checks typed quotations, not free-text semantics. A separately trusted
original additionally enables exact comparison of the complete payload.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from fatebridge.utils.json_values import same_value as _same_value


class CalculationClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1)
    value: JsonValue
    run_id: str = Field(min_length=1)


def verify_calculation_claims(
    payload: dict[str, Any],
    claims: list[CalculationClaim],
    *,
    trusted_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Check typed quotations; optionally compare the separately retained original."""
    metadata = payload.get("run_metadata", {})
    body = {k: v for k, v in payload.items() if k != "run_metadata"}
    errors: list[dict[str, Any]] = []
    if trusted_payload is not None and not _same_value(payload, trusted_payload):
        errors.append({"code": "incomplete_or_changed_business_payload"})
    if not metadata.get("run_id"):
        errors.append({"code": "missing_original_run_id"})
    for index, claim in enumerate(claims):
        error = None
        if claim.run_id != metadata.get("run_id"):
            error = "different_calculation_receipt"
        else:
            actual: Any = body
            try:
                for key in claim.path.split("."):
                    if isinstance(actual, list) and key.isdecimal():
                        actual = actual[int(key)]
                    elif isinstance(actual, dict) and key:
                        actual = actual[key]
                    else:
                        raise KeyError(key)
                if not _same_value(actual, claim.value):
                    error = "value_or_type_mismatch"
            except (KeyError, IndexError):
                error = "unsupported_fact_path"
        if error:
            errors.append({"claim_index": index, "path": claim.path, "code": error})
    return {
        "method_id": "same_run_calculation_claims_v2",
        "status": "rejected" if errors or not claims else "verified_structured_facts",
        "checked_claim_count": len(claims),
        "errors": errors,
        "original_payload_compared": trusted_payload is not None,
        "scope": "只核验所供结果中具名run的结构化字段引用；完整原结果身份仅在调用方另行提供可信原结果时逐值比较。不能认证自行提交的结果、自由文本语义、原典成立、外部真实性或现实预测。",
    }

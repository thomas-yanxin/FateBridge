"""Verify structured quotations against the complete original calculation.

This is a fact-checking primitive for hosts, not a semantic free-text grader.
Projection, a different run or changed business data must never pass silently.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from fatebridge.utils.json_digest import digest


class CalculationClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1)
    value: JsonValue
    run_id: str = Field(min_length=1)
    business_output_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


def _same_value(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            _same_value(left[k], right[k]) for k in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _same_value(a, b) for a, b in zip(left, right)
        )
    return bool(left == right)


def verify_calculation_claims(
    payload: dict[str, Any], claims: list[CalculationClaim]
) -> dict[str, Any]:
    """Require original business bytes/values and exact run-scoped field values."""
    metadata = payload.get("run_metadata", {})
    body = {k: v for k, v in payload.items() if k != "run_metadata"}
    expected = metadata.get("business_output_sha256")
    errors: list[dict[str, Any]] = []
    if not isinstance(expected, str) or expected != digest(body):
        errors.append({"code": "incomplete_or_changed_business_payload"})
    if not metadata.get("run_id"):
        errors.append({"code": "missing_original_run_id"})
    for index, claim in enumerate(claims):
        error = None
        if (
            claim.run_id != metadata.get("run_id")
            or claim.business_output_sha256 != expected
        ):
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
        "method_id": "same_run_calculation_claims_v1",
        "status": "rejected" if errors or not claims else "verified_structured_facts",
        "checked_claim_count": len(claims),
        "errors": errors,
        "scope": "只核验同run完整结果中的结构化字段引用；不证明自由文本语义忠实、原典成立、外部真实性或现实预测有效。哈希须与可信原始回执核对，不能把自造回执当认证。",
    }

"""Verify structured quotations against the complete original calculation.

This checks typed quotations, not free-text semantics. A separately trusted
original additionally enables exact comparison of the complete payload.
"""

from typing import Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, JsonValue
from typing_extensions import NotRequired

from fatebridge.utils.json_values import same_value


class CalculationClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1)
    value: JsonValue
    run_id: str = Field(min_length=1)


class ClaimError(TypedDict):
    code: Literal[
        "incomplete_or_changed_business_payload",
        "missing_original_run_id",
        "different_calculation_receipt",
        "unsupported_fact_path",
        "value_or_type_mismatch",
    ]
    claim_index: NotRequired[int]
    path: NotRequired[str]


class ClaimVerification(TypedDict):
    method_id: Literal["same_run_calculation_claims_v2"]
    status: Literal["rejected", "verified_structured_facts"]
    checked_claim_count: int
    errors: list[ClaimError]
    original_payload_compared: bool
    scope: str


def verify_calculation_claims(
    payload: dict[str, JsonValue],
    claims: list[CalculationClaim],
    *,
    trusted_payload: dict[str, JsonValue] | None = None,
) -> ClaimVerification:
    """Check typed quotations; optionally compare the separately retained original."""
    metadata = payload.get("run_metadata")
    run_id = metadata.get("run_id") if isinstance(metadata, dict) else None
    body: dict[str, JsonValue] = {
        field: value for field, value in payload.items() if field != "run_metadata"
    }
    errors: list[ClaimError] = []
    if trusted_payload is not None and not same_value(payload, trusted_payload):
        errors.append({"code": "incomplete_or_changed_business_payload"})
    else:
        pass
    if not run_id:
        errors.append({"code": "missing_original_run_id"})
    else:
        pass
    for index, claim in enumerate(claims):
        error: (
            Literal[
                "different_calculation_receipt",
                "unsupported_fact_path",
                "value_or_type_mismatch",
            ]
            | None
        ) = None
        if claim.run_id != run_id:
            error = "different_calculation_receipt"
        else:
            actual: JsonValue = body
            try:
                for key in claim.path.split("."):
                    if isinstance(actual, list) and key.isdecimal():
                        actual = actual[int(key)]
                    elif isinstance(actual, dict) and key:
                        actual = actual[key]
                    else:
                        raise KeyError(key)
                if not same_value(actual, claim.value):
                    error = "value_or_type_mismatch"
                else:
                    pass
            except (KeyError, IndexError):
                error = "unsupported_fact_path"
        if error:
            errors.append({"claim_index": index, "path": claim.path, "code": error})
        else:
            pass
    return {
        "method_id": "same_run_calculation_claims_v2",
        "status": "rejected" if errors or not claims else "verified_structured_facts",
        "checked_claim_count": len(claims),
        "errors": errors,
        "original_payload_compared": trusted_payload is not None,
        "scope": "只核验所供结果中具名run的结构化字段引用；完整原结果身份仅在调用方另行提供可信原结果时逐值比较。不能认证自行提交的结果、自由文本语义、原典成立、外部真实性或现实预测。",
    }

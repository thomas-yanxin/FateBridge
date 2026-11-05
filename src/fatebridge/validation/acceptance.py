"""Evaluate a frozen population without accepting a successful subset."""

from collections import Counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from fatebridge.utils.json_digest import digest


class GateProtocol(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    gate_id: str
    method_id: str
    axis: Literal[
        "numerical",
        "source_conformity",
        "interpretation_fidelity",
        "real_world_validity",
    ]
    reference_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    case_ids: tuple[str, ...] = Field(min_length=1)
    comparison: Literal["absolute_error_le", "literal_match"]
    tolerance: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    unit: str
    scope: str

    @model_validator(mode="after")
    def fixed_population(self) -> "GateProtocol":
        if len(set(self.case_ids)) != len(self.case_ids):
            raise ValueError("验收总体存在重复ID")
        if (self.comparison == "absolute_error_le") != (self.tolerance is not None):
            raise ValueError("数值验收须声明固定容差，字面验收不补数值容差")
        return self


class GateObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    case_id: str
    reference_sha256: str
    error: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    literal_match: bool | None = None
    unavailable_reason: str | None = None


def evaluate_gate(
    protocol: GateProtocol, observations: tuple[GateObservation, ...]
) -> dict[str, object]:
    found = Counter(row.case_id for row in observations)
    expected = set(protocol.case_ids)
    duplicates = sorted(key for key, count in found.items() if count > 1)
    unexpected = sorted(set(found) - expected)
    missing = sorted(expected - set(found))
    wrong_reference = sorted(
        row.case_id
        for row in observations
        if row.reference_sha256 != protocol.reference_sha256
    )
    failed, unresolved = [], []
    for row in observations:
        if (
            row.case_id not in expected
            or row.reference_sha256 != protocol.reference_sha256
        ):
            continue
        value = (
            row.error
            if protocol.comparison == "absolute_error_le"
            else row.literal_match
        )
        if row.unavailable_reason is not None or value is None:
            unresolved.append(row.case_id)
        elif protocol.comparison == "absolute_error_le":
            assert row.error is not None and protocol.tolerance is not None
            if row.error > protocol.tolerance:
                failed.append(row.case_id)
        elif row.literal_match is False:
            failed.append(row.case_id)
    complete = not (duplicates or unexpected or missing or wrong_reference)
    return {
        "gate_id": protocol.gate_id,
        "method_id": protocol.method_id,
        "axis": protocol.axis,
        "protocol_sha256": digest(protocol.model_dump(mode="json")),
        "reference_sha256": protocol.reference_sha256,
        "denominator": len(expected),
        "observations": len(observations),
        "status": (
            "failed"
            if failed or not complete
            else "unresolved" if unresolved else "passed"
        ),
        "population_complete": complete,
        "failures": sorted(failed),
        "unresolved": sorted(unresolved),
        "missing": missing,
        "duplicates": duplicates,
        "unexpected": unexpected,
        "wrong_reference": wrong_reference,
        "scope": protocol.scope,
    }

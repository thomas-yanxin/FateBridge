"""Jyotish research commitments bound to actual calculation/source materials.

The older commit/reveal primitives remain shared with other research domains.
This stricter entry point checks supplied bytes, not their truth, model execution,
consent, external timestamps or the human separation of forecasting/adjudication.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from pydantic import AwareDatetime, Field, model_validator

from fatebridge.validation import jyotish_study as workflow
from fatebridge.validation.predictions import Forecast, Outcome, StudyPlan, digest

REQUIRED_ARTIFACTS = frozenset(
    {"calendar_rules", "classical_sources", "interpretation_policy", "forecast_policy"}
)
MATERIAL_POLICY = "actual_bytes_sha256_v1"


def _artifact_schema(schema: dict[str, Any]) -> None:
    schema["required"] = sorted(REQUIRED_ARTIFACTS)


class JyotishStudyPlan(StudyPlan):
    interpretation_policy_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    baseline_frozen_at: AwareDatetime
    training_subject_ids: list[str]


class JyotishProtocol(workflow.BlindProtocol):
    plan: JyotishStudyPlan
    artifact_sha256: dict[str, str] = Field(
        min_length=4,
        json_schema_extra=_artifact_schema,
    )

    @model_validator(mode="after")
    def material_bindings(self) -> JyotishProtocol:
        if self.plan.training_subject_ids is None or set(
            self.plan.training_subject_ids
        ) != set(self.training_subject_ids):
            raise ValueError("内外两处训练主体声明须明确且一致，未知不能当作独立留出")
        if len(self.plan.training_subject_ids) != len(self.training_subject_ids):
            raise ValueError("训练主体声明不能重复")
        if not REQUIRED_ARTIFACTS <= set(self.artifact_sha256):
            raise ValueError(
                "须冻结calendar_rules/classical_sources/interpretation_policy/forecast_policy四类实际材料"
            )
        if (
            self.plan.interpretation_policy_sha256 is None
            or self.plan.interpretation_policy_sha256
            != self.artifact_sha256["interpretation_policy"]
        ):
            raise ValueError(
                "解释政策须绑定实际interpretation_policy文件，不能缺失或仅写另一个指纹"
            )
        if self.plan.baseline_frozen_at is None:
            raise ValueError("必须明确事前基线冻结时刻")
        if self.plan.protocol_context_sha256 not in (
            None,
            protocol_context_digest(self),
        ):
            raise ValueError("印占完整协议上下文指纹与材料、裁定或分析指导不一致")
        return self


def protocol_context_digest(protocol: JyotishProtocol) -> str:
    """Commit all wrapper details before the original records bind the plan.

    The containing plan is omitted to avoid a recursive digest. Its ordinary
    canonical hash binds its own fields and this context. Never fill a missing
    context when loading a historical registration, forecast or outcome.
    """
    details = protocol.model_dump(mode="json")
    details.pop("plan")
    return digest(
        {
            "format": "jyotish_protocol_context_v1",
            "blind_protocol_details": details,
        }
    )


def _read_packet(
    packet: dict[str, Any], fields: set[str], format_id: str, hash_key: str
) -> dict[str, Any]:
    body = {k: v for k, v in packet.items() if k != hash_key}
    if (
        set(body) != fields
        or body["format"] != format_id
        or digest(body) != packet.get(hash_key)
    ):
        raise ValueError(
            "印占材料绑定封存已改变或格式不受支持；旧版基础承诺不能冒充严格验收"
        )
    return body


def _verify_files(
    files: dict[str, bytes], expected: dict[str, str], label: str
) -> None:
    if set(files) != set(expected) or any(
        hashlib.sha256(files[case_id]).hexdigest() != value
        for case_id, value in expected.items()
    ):
        raise ValueError(f"须提供与逐例指纹一致的{label}实际文件；不能缺失、增添或替换")


def register(
    protocol: JyotishProtocol,
    model_bytes: bytes,
    *,
    at: datetime,
    artifacts: dict[str, bytes],
) -> dict[str, Any]:
    # Revalidate mutable/model_copy inputs at this public boundary as well.
    protocol = JyotishProtocol.model_validate(protocol.model_dump(mode="python"))
    inner = workflow.register(protocol, model_bytes, at=at, artifacts=artifacts)
    body = {
        "format": "jyotish_material_registration_v1",
        "material_policy": MATERIAL_POLICY,
        "commitment": inner,
    }
    return {**body, "registration_sha256": digest(body)}


def read_registration(registration: dict[str, Any]) -> JyotishProtocol:
    body = _read_packet(
        registration,
        {"format", "material_policy", "commitment"},
        "jyotish_material_registration_v1",
        "registration_sha256",
    )
    if body["material_policy"] != MATERIAL_POLICY:
        raise ValueError("印占材料核验口径不受支持")
    inner = workflow.read_registration(body["commitment"])
    return JyotishProtocol.model_validate(inner.model_dump(mode="python"))


def seal_forecasts(
    registration: dict[str, Any],
    forecasts: list[Forecast],
    *,
    at: datetime,
    evidence: dict[str, bytes],
) -> dict[str, Any]:
    read_registration(registration)
    # JSON serialization would turn an illegally assigned True into 1.0 before
    # validation. Preserve Python types so strict probability checks can reject it.
    forecasts = [
        Forecast.model_validate(f.model_dump(mode="python")) for f in forecasts
    ]
    inner = workflow.seal_forecasts(registration["commitment"], forecasts, at=at)
    _verify_files(
        evidence,
        {f.case_id: f.evidence_sha256 for f in forecasts},
        "计算／解释证据（弃权也须保留原因）",
    )
    body = {
        "format": "jyotish_material_forecasts_v1",
        "registration_sha256": registration["registration_sha256"],
        "commitment": inner,
    }
    return {**body, "forecast_commitment_sha256": digest(body)}


def blind_outcome_sheet(registration: dict[str, Any]) -> dict[str, Any]:
    protocol = read_registration(registration)
    plan = protocol.plan
    return {
        "format": "jyotish_blind_outcome_sheet_v1",
        "study_plan_sha256": digest(plan.model_dump(mode="json")),
        "registration_sha256": registration["registration_sha256"],
        "study_id": plan.study_id,
        "target_definition": plan.target_definition,
        "window_start": plan.window_start.isoformat(),
        "window_end": plan.window_end.isoformat(),
        "case_ids": [m.case_id for m in plan.cohort],
        "adjudication": protocol.outcome_adjudication,
        "scope": "仅供独立结局裁定；不导出结构化出生字段、计算证据或概率。文件不能认证人员盲法，标识符和说明文本本身仍须审查是否泄漏预测。",
    }


def reveal_and_evaluate(
    registration: dict[str, Any],
    sealed: dict[str, Any],
    outcomes: list[Outcome],
    *,
    at: datetime,
    outcome_sources: dict[str, bytes],
) -> dict[str, Any]:
    protocol = read_registration(registration)
    body = _read_packet(
        sealed,
        {"format", "registration_sha256", "commitment"},
        "jyotish_material_forecasts_v1",
        "forecast_commitment_sha256",
    )
    if body["registration_sha256"] != registration["registration_sha256"]:
        raise ValueError("预测不属于这份印占材料绑定注册")
    outcomes = [Outcome.model_validate(o.model_dump(mode="python")) for o in outcomes]
    result = workflow.reveal_and_evaluate(
        registration["commitment"], body["commitment"], outcomes, at=at
    )
    _verify_files(
        outcome_sources,
        {o.case_id: o.source_sha256 for o in outcomes},
        "结局来源",
    )
    if protocol.plan.protocol_context_sha256 is None:
        # Retain all original packets, numerical scores and failed rows. Only
        # the domain's protocol claims need this additional original binding.
        result["protocol_blockers"].append(
            "missing_jyotish_protocol_context_commitment"
        )
        result["protocol_status"] = "incomplete"
        result["preregistered_performance_gate_met"] = False
        result["statistical_evidence_gate_met"] = False
    result.update(
        registration_sha256=registration["registration_sha256"],
        forecast_commitment_sha256=sealed["forecast_commitment_sha256"],
        protocol_context_binding={
            "format": "jyotish_protocol_context_v1",
            "expected_context_sha256": protocol_context_digest(protocol),
            "committed_context_sha256": protocol.plan.protocol_context_sha256,
            "status": "bound" if protocol.plan.protocol_context_sha256 else "missing",
            "original_record_binding_required": True,
            "timestamps_and_provenance_authenticated": False,
            "scope": "裁定、纳排、概率映射、分析指导及全部具名材料须先绑定计划，再由原始预测与结局记录绑定计划；旧缺项保留诊断但不补签、不授予协议验收。",
        },
        material_binding={
            "policy": MATERIAL_POLICY,
            "forecast_evidence_files_checked_at_seal": len(
                body["commitment"]["forecasts"]
            ),
            "outcome_source_files_checked_at_evaluation": len(outcomes),
            "scope": "核对实际文件字节与承诺的对应；不认证内容真实、来源独立、模型实际执行、文件语义或人员盲法。未随访行仍留在原队列。",
        },
    )
    return result

"""Pair-aware prospective validation using the shared commit/reveal machinery.

One person's appearance in several pairs is not several independent samples.
No forecast probability is produced from a mansion, relationship label or score.
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime
from typing import Any

from pydantic import Field, model_validator

from fatebridge.validation import jyotish_study as workflow
from fatebridge.validation.predictions import Forecast, Outcome, Record, digest

REQUIRED_ARTIFACTS = {
    "calendar_rules",
    "classical_sources",
    "interpretation_policy",
    "forecast_policy",
}
GAIN_METHOD = "two_sided_hoeffding_fixed_sample_independent_pairs_range_minus1_plus1"


class PairMembers(Record):
    case_id: str = Field(min_length=1)
    person1_subject_id: str = Field(min_length=1)
    person2_subject_id: str = Field(min_length=1)


class SukuyoProtocol(Record):
    blind_protocol: workflow.BlindProtocol
    pairs: list[PairMembers] = Field(min_length=1)
    relationship_context: str = Field(
        min_length=1,
        description="One registered relationship context, not mixed romantic/business/family outcomes",
    )
    hypothesis: str = Field(
        min_length=1,
        description="A testable prospective hypothesis; traditional favorable labels are not calibrated probabilities",
    )

    @model_validator(mode="after")
    def independent_pairs(self) -> "SukuyoProtocol":
        plan = self.blind_protocol.plan
        if plan.planned_evaluations != 1:
            raise ValueError("宿曜配对方案固定一次到期评价；多次查看须另设序贯设计")
        cases = {m.case_id for m in plan.cohort}
        if (
            len({p.case_id for p in self.pairs}) != len(self.pairs)
            or {p.case_id for p in self.pairs} != cases
        ):
            raise ValueError("配对表必须恰好覆盖注册队列，不能重复或加入未注册case_id")
        people = [
            person
            for pair in self.pairs
            for person in (pair.person1_subject_id, pair.person2_subject_id)
        ]
        if len(set(people)) != len(people):
            raise ValueError(
                "同一人不能重复充当独立配对样本；需另设聚类设计，不能重复计数"
            )
        if set(people) & set(self.blind_protocol.training_subject_ids):
            raise ValueError("配对成员与训练主体重叠，不能计作独立盲测")
        if plan.training_subject_ids is None or set(plan.training_subject_ids) != set(
            self.blind_protocol.training_subject_ids
        ):
            raise ValueError("必须一致声明训练主体；未知训练重叠不能当独立验证")
        if not REQUIRED_ARTIFACTS <= set(self.blind_protocol.artifact_sha256):
            raise ValueError(
                "须冻结calendar_rules/classical_sources/interpretation_policy/forecast_policy四类实际文件"
            )
        if (
            plan.interpretation_policy_sha256 is not None
            and plan.interpretation_policy_sha256
            != self.blind_protocol.artifact_sha256["interpretation_policy"]
        ):
            raise ValueError(
                "解释政策指纹必须对应已提交的实际interpretation_policy文件"
            )
        if plan.protocol_context_sha256 not in (None, protocol_context_digest(self)):
            raise ValueError("宿曜完整协议上下文指纹与配对、来源或分析指导不一致")
        return self


def protocol_context_digest(protocol: SukuyoProtocol) -> str:
    """Bind every wrapper detail without hashing the containing plan recursively.

    This value must be included in the plan before registration and before the
    original forecast/outcome records commit that plan. Never fill it on load.
    List order is retained: reordering a committed protocol is a new context.
    """
    blind = protocol.blind_protocol.model_dump(mode="json")
    blind.pop("plan")
    return digest(
        {
            "format": "sukuyo_protocol_context_v1",
            "pairs": [pair.model_dump(mode="json") for pair in protocol.pairs],
            "relationship_context": protocol.relationship_context,
            "hypothesis": protocol.hypothesis,
            "blind_protocol_details": blind,
        }
    )


def register(
    protocol: SukuyoProtocol,
    model_bytes: bytes,
    *,
    at: datetime,
    artifacts: dict[str, bytes],
) -> dict[str, Any]:
    protocol = SukuyoProtocol.model_validate(protocol.model_dump(mode="python"))
    inner = workflow.register(
        protocol.blind_protocol, model_bytes, at=at, artifacts=artifacts
    )
    body = {
        "format": "sukuyo_pair_registration_v1",
        "analysis_method": GAIN_METHOD,
        "protocol": protocol.model_dump(mode="json"),
        "commitment": inner,
    }
    return {**body, "registration_sha256": digest(body)}


def read_registration(registration: dict[str, Any]) -> SukuyoProtocol:
    body = {k: v for k, v in registration.items() if k != "registration_sha256"}
    if (
        set(body) != {"format", "analysis_method", "protocol", "commitment"}
        or body["format"] != "sukuyo_pair_registration_v1"
        or body["analysis_method"] != GAIN_METHOD
        or digest(body) != registration.get("registration_sha256")
    ):
        raise ValueError("宿曜注册文件已改变或格式无效")
    protocol = SukuyoProtocol.model_validate(body["protocol"])
    inner = workflow.read_registration(body["commitment"])
    if inner.model_dump(mode="json") != protocol.blind_protocol.model_dump(mode="json"):
        raise ValueError("外层配对方案与封存方案不一致")
    return protocol


def seal_forecasts(
    registration: dict[str, Any],
    forecasts: list[Forecast],
    *,
    at: datetime,
    evidence: dict[str, bytes],
) -> dict[str, Any]:
    read_registration(registration)
    inner = workflow.seal_forecasts(registration["commitment"], forecasts, at=at)
    if set(evidence) != {f.case_id for f in forecasts} or any(
        hashlib.sha256(evidence[f.case_id]).hexdigest() != f.evidence_sha256
        for f in forecasts
    ):
        raise ValueError(
            "须提供与每个case证据指纹一致的实际计算/解释材料，弃权也须保留原因"
        )
    body = {
        "format": "sukuyo_pair_forecasts_v1",
        "registration_sha256": registration["registration_sha256"],
        "commitment": inner,
    }
    return {**body, "forecast_commitment_sha256": digest(body)}


def blind_outcome_sheet(registration: dict[str, Any]) -> dict[str, Any]:
    protocol = read_registration(registration)
    plan = protocol.blind_protocol.plan
    return {
        "format": "sukuyo_blind_outcome_sheet_v1",
        "study_plan_sha256": digest(plan.model_dump(mode="json")),
        "protocol_context_sha256": plan.protocol_context_sha256,
        "study_id": plan.study_id,
        "target_definition": plan.target_definition,
        "window_start": plan.window_start.isoformat(),
        "window_end": plan.window_end.isoformat(),
        "case_ids": [m.case_id for m in plan.cohort],
        "adjudication": protocol.blind_protocol.outcome_adjudication,
        "scope": "供结局裁定使用；不含出生日期、宿名、关系标签、概率或封存预测；文件本身不能认证人员盲法。",
    }


def evaluate(
    registration: dict[str, Any],
    sealed: dict[str, Any],
    outcomes: list[Outcome],
    *,
    at: datetime,
    outcome_sources: dict[str, bytes],
) -> dict[str, Any]:
    protocol = read_registration(registration)
    body = {k: v for k, v in sealed.items() if k != "forecast_commitment_sha256"}
    if (
        set(body) != {"format", "registration_sha256", "commitment"}
        or body["format"] != "sukuyo_pair_forecasts_v1"
        or digest(body) != sealed.get("forecast_commitment_sha256")
    ):
        raise ValueError("宿曜预测封存文件已改变或格式无效")
    if body["registration_sha256"] != registration["registration_sha256"]:
        raise ValueError("预测和配对注册方案不一致")
    result = workflow.reveal_and_evaluate(
        registration["commitment"], body["commitment"], outcomes, at=at
    )
    if set(outcome_sources) != {o.case_id for o in outcomes} or any(
        hashlib.sha256(outcome_sources[o.case_id]).hexdigest() != o.source_sha256
        for o in outcomes
    ):
        raise ValueError("须提供与每条结局指纹一致的实际来源记录；指纹不认证记录真实性")
    # A predeclared, conservative bound on paired Brier gain. Each variable
    # (1-required_skill)*baseline_loss - model_loss lies in [-1, 1].
    # Hoeffding's fixed-sample bound is meaningful only for independent pairs;
    # it is not a claim that software can authenticate recruitment or blinding.
    forecasts = {
        f["case_id"]: Forecast.model_validate(f)
        for f in body["commitment"]["forecasts"]
    }
    observed = {o.case_id: o for o in outcomes}
    plan = protocol.blind_protocol.plan
    if plan.protocol_context_sha256 is None:
        result["protocol_blockers"].append("missing_sukuyo_protocol_context_commitment")
        result["protocol_status"] = "incomplete"
        result["preregistered_performance_gate_met"] = False
        result["statistical_evidence_gate_met"] = False
    gains = []
    for row in result["rows"]:
        if row["status"] != "evaluable":
            continue
        forecast = forecasts[row["case_id"]]
        if forecast.probability is None:
            continue
        outcome = int(observed[row["case_id"]].occurred)
        # The shared evaluator binds the frozen reference to this case. It may
        # be a per-case forecast, in which case the constant field is None.
        baseline = row["baseline_probability"]
        assert baseline is not None  # exactly one validated baseline mode
        baseline_loss = (baseline - outcome) ** 2
        gains.append(
            (1 - plan.minimum_brier_skill) * baseline_loss
            - (forecast.probability - outcome) ** 2
        )
    interval = None
    if gains and result["coverage"] == 1.0:
        mean_gain = sum(gains) / len(gains)
        radius = math.sqrt(2 * math.log(2 / (1 - plan.confidence_level)) / len(gains))
        interval = [max(-1.0, mean_gain - radius), min(1.0, mean_gain + radius)]
    result.update(
        registration_sha256=registration["registration_sha256"],
        forecast_commitment_sha256=sealed["forecast_commitment_sha256"],
        pair_count=len(protocol.pairs),
        independent_participant_count=2 * len(protocol.pairs),
        relationship_context=protocol.relationship_context,
        domain="sukuyo",
        authority_certified=False,
        protocol_context_binding={
            "format": "sukuyo_protocol_context_v1",
            "expected_context_sha256": protocol_context_digest(protocol),
            "committed_context_sha256": plan.protocol_context_sha256,
            "status": "bound" if plan.protocol_context_sha256 else "missing",
            "original_record_binding_required": True,
            "timestamps_and_provenance_authenticated": False,
            "scope": "配对、具名材料、假设及全部盲法／分析指导须先绑定计划，再由原始预测与结局记录绑定该计划；旧缺项保留诊断但不补签、不授予验收。",
        },
        human_blinding_and_consent="requires_independent_verification",
        paired_brier_gain_interval=interval,
        paired_gain_interval_method=GAIN_METHOD,
        confidence_bound_gate_met=bool(
            result["preregistered_performance_gate_met"]
            and interval
            and interval[0] > 0
        ),
    )
    return result

"""Prospective binary-outcome evaluation with a frozen cohort and baseline.

No astrological score is converted to a probability here. Forecasts must be
issued externally under the registered model before the outcome window opens.
Timestamps and source hashes are checked for consistency, not authenticated.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from statistics import NormalDist
from sys import float_info
from typing import Any, Literal, Optional

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    StrictBool,
    StrictFloat,
    StrictInt,
    model_serializer,
    model_validator,
)

from fatebridge.utils.civil_clock import utc_instant

Hash = str


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class CohortMember(Record):
    case_id: str = Field(min_length=1)
    subject_id: str = Field(
        min_length=1,
        description="Pseudonymous identifier; one independent subject per row",
    )


class BaselineForecast(Record):
    """A per-case reference probability frozen before registration."""

    case_id: str = Field(min_length=1)
    probability: StrictFloat = Field(ge=0, le=1)
    issued_at: AwareDatetime
    target_definition: str = Field(min_length=1)
    window_start: AwareDatetime
    window_end: AwareDatetime
    source_sha256: Hash = Field(pattern=r"^[a-f0-9]{64}$")
    source_reference: str = Field(min_length=1, pattern=r"\S")


class StudyPlan(Record):
    study_id: str = Field(min_length=1)
    data_kind: Literal["synthetic", "real_world_submission"]
    preregistered_at: AwareDatetime
    registration_reference: Optional[str] = Field(
        default=None, min_length=1, pattern=r"\S"
    )
    window_start: AwareDatetime
    window_end: AwareDatetime
    target_definition: str = Field(min_length=1)
    model_sha256: Hash = Field(pattern=r"^[a-f0-9]{64}$")
    interpretation_policy_sha256: Optional[Hash] = Field(
        default=None, pattern=r"^[a-f0-9]{64}$"
    )
    protocol_context_sha256: Optional[Hash] = Field(
        default=None,
        pattern=r"^[a-f0-9]{64}$",
        description="Domain-validated commitment to protocol details outside this plan; Sukuyo binds pairs, named artifacts, hypothesis and blinding/analysis instructions",
    )
    baseline_frozen_at: Optional[AwareDatetime] = None
    baseline_probability: Optional[StrictFloat] = Field(default=None, ge=0, le=1)
    baseline_forecasts: Optional[list[BaselineForecast]] = None
    decision_threshold: StrictFloat = Field(default=0.5, gt=0, lt=1)
    confidence_level: StrictFloat = Field(default=0.95, gt=0, lt=1)
    minimum_evaluable: StrictInt = Field(default=100, ge=1)
    minimum_brier_skill: StrictFloat = Field(default=0.0, ge=0, lt=1)
    planned_evaluations: StrictInt = Field(
        default=1,
        ge=1,
        le=1_000_000,
        description="Number of predeclared statistical looks; external records must verify adherence",
    )
    training_subject_ids: Optional[list[str]] = Field(
        default=None,
        description="Declared pseudonymous training subjects; absent means overlap is unknown",
    )
    cohort: list[CohortMember] = Field(min_length=1)

    @model_serializer(mode="wrap")
    def preserve_legacy_plan_shape(
        self, handler: SerializerFunctionWrapHandler
    ) -> dict[str, Any]:
        payload: dict[str, Any] = handler(self)
        # Adding an optional domain commitment must not change the canonical
        # digest of already-issued v4 records whose plans have no such field.
        # Supplied commitments are retained in Python and JSON serializations.
        if self.protocol_context_sha256 is None:
            payload.pop("protocol_context_sha256", None)
        return payload

    @model_validator(mode="after")
    def ordered_and_unique(self) -> StudyPlan:
        if (self.baseline_probability is None) == (self.baseline_forecasts is None):
            raise ValueError("必须且只能选择常数基线或逐例冻结基线，不能缺省或同时给出")
        if (
            not utc_instant(self.preregistered_at)
            < utc_instant(self.window_start)
            < utc_instant(self.window_end)
        ):
            raise ValueError("预注册必须早于目标窗口，窗口起点必须早于终点")
        if self.baseline_frozen_at is not None and utc_instant(
            self.baseline_frozen_at
        ) > utc_instant(self.preregistered_at):
            raise ValueError("基线必须在预注册时或之前固定，不能事后选择有利基线")
        if len({m.case_id for m in self.cohort}) != len(self.cohort):
            raise ValueError("预注册队列不能重复case_id")
        if len({m.subject_id for m in self.cohort}) != len(self.cohort):
            raise ValueError("同一主体不能重复计作独立样本；重复观察需另设聚类统计方案")
        if self.training_subject_ids is not None and {
            m.subject_id for m in self.cohort
        }.intersection(self.training_subject_ids):
            raise ValueError("评估队列主体与声明的训练主体重叠，不能作为独立留出样本")
        if self.baseline_forecasts is not None:
            if self.baseline_frozen_at is None:
                raise ValueError("逐例基线须明确统一冻结时刻")
            ids = [b.case_id for b in self.baseline_forecasts]
            if len(ids) != len(set(ids)) or set(ids) != {
                m.case_id for m in self.cohort
            }:
                raise ValueError(
                    "逐例基线须完整且唯一覆盖注册队列，不能遗漏、增删或重复案例"
                )
            if any(
                utc_instant(b.issued_at) > utc_instant(self.baseline_frozen_at)
                for b in self.baseline_forecasts
            ):
                raise ValueError(
                    "逐例基线必须在统一冻结时刻之前或当时发布，不能用事后信息"
                )
            if any(
                b.target_definition != self.target_definition
                or utc_instant(b.window_start) != utc_instant(self.window_start)
                or utc_instant(b.window_end) != utc_instant(self.window_end)
                for b in self.baseline_forecasts
            ):
                raise ValueError(
                    "逐例基线必须预测同一事件定义和同一完整结果窗口，不能换目标比较"
                )
        return self


class Forecast(Record):
    case_id: str = Field(min_length=1)
    study_plan_sha256: Optional[Hash] = Field(
        default=None,
        pattern=r"^[a-f0-9]{64}$",
        description="Canonical validated StudyPlan digest committed when issuing the forecast; missing legacy bindings cannot pass protocol gates",
    )
    issued_at: AwareDatetime
    model_sha256: Hash = Field(pattern=r"^[a-f0-9]{64}$")
    interpretation_policy_sha256: Optional[Hash] = Field(
        default=None, pattern=r"^[a-f0-9]{64}$"
    )
    evidence_sha256: Hash = Field(
        pattern=r"^[a-f0-9]{64}$",
        description="Digest of the original calculation and fixed interpretation policy",
    )
    probability: Optional[StrictFloat] = Field(
        ge=0,
        le=1,
        description="Null records an explicit abstention; never infer from a BaZi score",
    )


class Outcome(Record):
    case_id: str = Field(min_length=1)
    study_plan_sha256: Optional[Hash] = Field(
        default=None,
        pattern=r"^[a-f0-9]{64}$",
        description="Canonical validated StudyPlan digest identifying the endpoint and adjudication window; never infer retrospectively",
    )
    occurred: StrictBool
    event_at: Optional[AwareDatetime] = None
    recorded_at: AwareDatetime
    source_sha256: Hash = Field(pattern=r"^[a-f0-9]{64}$")
    source_reference: str = Field(min_length=1)


def _brier_skill(
    eligible: list[tuple[float, int, float]],
    model_loss: Optional[float],
    baseline_loss: Optional[float],
) -> tuple[Optional[float], str]:
    """Keep loss ratios identifiable when the squared losses underflow.

    Common scaling cancels in the ratio. It changes neither forecasts nor the
    registered reference. Unrepresentably bad skill is explicit, never clipped
    to zero or emitted as non-standard JSON Infinity.
    """
    if not eligible:
        return None, "not_evaluable"
    baseline_errors = [abs(b - y) for _, y, b in eligible]
    if not any(baseline_errors):
        return None, "undefined_zero_baseline_loss"
    model_errors = [abs(p - y) for p, y, _ in eligible]
    assert model_loss is not None and baseline_loss is not None
    if baseline_loss >= float_info.min and (
        model_loss >= float_info.min or not any(model_errors)
    ):
        ratio = model_loss / baseline_loss
        status = "defined"
    else:
        scale = max(max(model_errors), max(baseline_errors))
        normalized_baseline = math.fsum((e / scale) ** 2 for e in baseline_errors)
        if normalized_baseline == 0:
            return None, "negative_overflow"
        ratio = math.fsum((e / scale) ** 2 for e in model_errors) / normalized_baseline
        status = "defined_with_scaled_losses"
    if not math.isfinite(ratio):
        return None, "negative_overflow"
    return 1 - ratio, status


def wilson_interval(
    successes: int, total: int, confidence: float
) -> Optional[list[float]]:
    """NIST Wilson score interval for independent Bernoulli observations."""
    if total == 0:
        return None
    # The upper quantile can round to 1.0 for a valid confidence close to 1.
    # Symmetry keeps the representable lower-tail probability nonzero.
    z = -NormalDist().inv_cdf((1 - confidence) / 2)
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    radius = (
        z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    )
    return [max(0.0, center - radius), min(1.0, center + radius)]


def evaluate_study(
    plan: StudyPlan,
    forecasts: list[Forecast],
    outcomes: list[Outcome],
    *,
    as_of: datetime,
) -> dict[str, Any]:
    """Score matured, recorded outcomes without dropping missing cohort rows.

    Missing/abstained/pending rows remain in the coverage ledger. Full coverage
    and the registered sample/skill criteria are required for the limited gate.
    Software cannot prove consent, independent adjudication or a timestamp's
    authenticity, so no result grants a real-world efficacy certificate.
    """
    if as_of.utcoffset() is None:
        raise ValueError("as_of必须带时区")
    # Models are mutable, and model_copy/model_construct do not validate their
    # updates. Rebuild all records before trusting binary-loss bounds or IDs.
    # Python mode preserves illegal booleans that JSON mode can coerce to1.0.
    plan = StudyPlan.model_validate(plan.model_dump(mode="python"))
    forecasts = [
        Forecast.model_validate(forecast.model_dump(mode="python"))
        for forecast in forecasts
    ]
    outcomes = [
        Outcome.model_validate(outcome.model_dump(mode="python"))
        for outcome in outcomes
    ]
    plan_sha256 = digest(plan.model_dump(mode="json"))
    members = {m.case_id: m for m in plan.cohort}
    baseline_records = {b.case_id: b for b in plan.baseline_forecasts or []}
    baseline_probabilities = (
        {case_id: b.probability for case_id, b in baseline_records.items()}
        if plan.baseline_forecasts is not None
        else {case_id: plan.baseline_probability for case_id in members}
    )
    predicted: dict[str, Forecast] = {}
    observed: dict[str, Outcome] = {}
    for forecast in forecasts:
        if forecast.study_plan_sha256 not in (None, plan_sha256):
            raise ValueError("预测记录绑定的完整研究方案指纹不一致")
        if forecast.case_id not in members or forecast.case_id in predicted:
            raise ValueError("预测包含未注册或重复case_id")
        if forecast.model_sha256 != plan.model_sha256:
            raise ValueError("预测模型指纹与预注册模型不一致")
        if forecast.interpretation_policy_sha256 != plan.interpretation_policy_sha256:
            raise ValueError("预测解释政策指纹与预注册政策不一致")
        if (
            not utc_instant(plan.preregistered_at)
            <= utc_instant(forecast.issued_at)
            < utc_instant(plan.window_start)
        ):
            raise ValueError("预测必须在预注册后、目标窗口开始前发布")
        if utc_instant(forecast.issued_at) > utc_instant(as_of):
            raise ValueError("不能评估as_of之后才发布的预测")
        predicted[forecast.case_id] = forecast
    for outcome in outcomes:
        if outcome.study_plan_sha256 not in (None, plan_sha256):
            raise ValueError("结果记录绑定的完整研究方案指纹不一致")
        if outcome.case_id not in members or outcome.case_id in observed:
            raise ValueError("结果包含未注册或重复case_id")
        if utc_instant(outcome.recorded_at) < utc_instant(plan.window_end):
            raise ValueError(
                "结果必须在完整目标窗口结束后记录，不能把未结束的阴性样本当未发生"
            )
        if outcome.occurred:
            if outcome.event_at is None or not utc_instant(
                plan.window_start
            ) <= utc_instant(outcome.event_at) < utc_instant(plan.window_end):
                raise ValueError("阳性结果必须有目标窗口内的事件时刻")
        elif outcome.event_at is not None:
            raise ValueError("阴性结果不能同时给出事件发生时刻")
        observed[outcome.case_id] = outcome
    eligible: list[tuple[float, int, float]] = []
    rows = []
    mature = utc_instant(as_of) >= utc_instant(plan.window_end)
    for member in plan.cohort:
        submitted = predicted.get(member.case_id)
        recorded = observed.get(member.case_id)
        if submitted is None:
            status = "missing_forecast"
        elif not mature:
            status = "window_pending"
        elif recorded is None or utc_instant(recorded.recorded_at) > utc_instant(as_of):
            status = "outcome_pending"
        elif submitted.probability is None:
            status = "abstained"
        else:
            status = "evaluable"
            baseline = baseline_probabilities[member.case_id]
            assert baseline is not None  # validated exactly-one baseline mode
            eligible.append((submitted.probability, int(recorded.occurred), baseline))
        rows.append(
            {
                "case_id": member.case_id,
                "status": status,
                "forecast_plan_binding": (
                    "missing_record"
                    if submitted is None
                    else "unbound" if submitted.study_plan_sha256 is None else "bound"
                ),
                "outcome_plan_binding": (
                    "missing_record"
                    if recorded is None
                    else "unbound" if recorded.study_plan_sha256 is None else "bound"
                ),
                "baseline_probability": baseline_probabilities[member.case_id],
                "baseline_record_sha256": (
                    digest(baseline_records[member.case_id].model_dump(mode="json"))
                    if baseline_records
                    else None
                ),
            }
        )
    n = len(eligible)
    correct = sum((p >= plan.decision_threshold) == bool(y) for p, y, _ in eligible)
    baseline_correct = sum(
        (b >= plan.decision_threshold) == bool(y) for _, y, b in eligible
    )
    brier = math.fsum((p - y) ** 2 for p, y, _ in eligible) / n if n else None
    baseline_brier = math.fsum((b - y) ** 2 for _, y, b in eligible) / n if n else None
    skill, skill_status = _brier_skill(eligible, brier, baseline_brier)
    numeric_gate = (
        n == len(members)
        and n >= plan.minimum_evaluable
        and skill is not None
        and skill > plan.minimum_brier_skill
    )
    blockers = []
    if plan.registration_reference is None:
        blockers.append("missing_external_registration_reference")
    if plan.interpretation_policy_sha256 is None:
        blockers.append("missing_interpretation_policy_commitment")
    if plan.baseline_frozen_at is None:
        blockers.append("missing_baseline_freeze_time")
    if plan.training_subject_ids is None:
        blockers.append("missing_training_subject_declaration")
    if any(f.study_plan_sha256 is None for f in forecasts):
        blockers.append("missing_forecast_plan_commitment")
    if any(o.study_plan_sha256 is None for o in outcomes):
        blockers.append("missing_outcome_plan_commitment")
    gate = numeric_gate and not blockers
    # Fixed paired losses, not a confidence interval for an unpaired accuracy.
    # For each registered subject Z=(1-s)*baseline_loss-model_loss has range
    # [-1, 1-s], where s is the registered minimum Brier skill. Hoeffding's
    # one-sided bound and a predeclared Bonferroni allocation control all looks.
    # The fixed reference may differ by case: independence and boundedness,
    # rather than identical reference probabilities, are the assumptions.
    alpha = (1 - plan.confidence_level) / plan.planned_evaluations
    mean_improvement = None
    mean_excess = None
    if baseline_brier is not None and brier is not None:
        mean_improvement = baseline_brier - brier
        mean_excess = (1 - plan.minimum_brier_skill) * baseline_brier - brier
    lower_excess = (
        mean_excess
        - (2 - plan.minimum_brier_skill) * math.sqrt(math.log(1 / alpha) / (2 * n))
        if mean_excess is not None
        else None
    )
    statistical_gate = gate and lower_excess is not None and lower_excess > 0
    calibration = []
    for index in range(5):
        members_in_bin = [(p, y) for p, y, _ in eligible if min(int(p * 5), 4) == index]
        bin_size = len(members_in_bin)
        calibration.append(
            {
                "lower": index / 5,
                "upper": (index + 1) / 5,
                "upper_inclusive": index == 4,
                "count": bin_size,
                "mean_probability": (
                    math.fsum(p for p, _ in members_in_bin) / bin_size
                    if bin_size
                    else None
                ),
                "observed_rate": (
                    math.fsum(y for _, y in members_in_bin) / bin_size
                    if bin_size
                    else None
                ),
            }
        )
    return {
        "method_id": "preregistered_binary_evaluation_v4",
        "study_id": plan.study_id,
        "as_of": as_of.astimezone(timezone.utc).isoformat(),
        "plan_sha256": plan_sha256,
        "record_plan_binding": {
            "expected_study_plan_sha256": plan_sha256,
            "forecast_bound_count": sum(
                f.study_plan_sha256 is not None for f in forecasts
            ),
            "forecast_unbound_count": sum(
                f.study_plan_sha256 is None for f in forecasts
            ),
            "outcome_bound_count": sum(
                o.study_plan_sha256 is not None for o in outcomes
            ),
            "outcome_unbound_count": sum(o.study_plan_sha256 is None for o in outcomes),
            "registered_cohort_fully_bound": (
                len(forecasts) == len(outcomes) == len(members)
                and all(f.study_plan_sha256 is not None for f in forecasts)
                and all(o.study_plan_sha256 is not None for o in outcomes)
            ),
            "timestamps_and_provenance_authenticated": False,
            "scope": "仅核对提交记录绑定同一完整注册方案；缺少绑定保留诊断但阻断协议门槛，不能事后补指纹冒充原始承诺。",
        },
        "forecast_records_sha256": digest(
            [f.model_dump(mode="json") for f in forecasts]
        ),
        "outcome_records_sha256": digest([o.model_dump(mode="json") for o in outcomes]),
        "data_kind": plan.data_kind,
        "registered_count": len(members),
        "evaluable_count": n,
        "coverage": n / len(members),
        "training_overlap_check": (
            "not_declared"
            if plan.training_subject_ids is None
            else "declared_disjoint_not_externally_verified"
        ),
        "baseline_comparison": {
            "mode": "frozen_per_case" if baseline_records else "frozen_constant",
            "coverage": "complete_registered_cohort",
            "alignment": "matched_by_case_id_on_the_same_evaluable_subjects",
            "per_case_record_count": len(baseline_records),
            "baseline_frozen_at": (
                plan.baseline_frozen_at.isoformat() if plan.baseline_frozen_at else None
            ),
            "source_provenance_authenticated": False,
            "reference_strength_certified": False,
            "scope": "仅与这份事前冻结参考比较；常数基线不等于现实信息模型，逐例来源声明也不自动证明参考强度或真实性",
        },
        "rows": rows,
        "metrics": {
            "accuracy": correct / n if n else None,
            "accuracy_interval": wilson_interval(correct, n, plan.confidence_level),
            "interval_method": "Wilson_score_independent_Bernoulli",
            "confidence_level": plan.confidence_level,
            "baseline_accuracy": baseline_correct / n if n else None,
            "brier_score": brier,
            "baseline_brier_score": baseline_brier,
            "brier_skill_score": skill,
            "brier_skill_score_status": skill_status,
            "brier_score_status": (
                "not_evaluable"
                if not n
                else (
                    "positive_loss_underflow"
                    if brier == 0 and any(p != y for p, y, _ in eligible)
                    else "finite"
                )
            ),
            "baseline_brier_score_status": (
                "not_evaluable"
                if not n
                else (
                    "positive_loss_underflow"
                    if baseline_brier == 0 and any(b != y for _, y, b in eligible)
                    else "finite"
                )
            ),
            "calibration": calibration,
        },
        "preregistered_performance_gate_met": gate,
        "registered_numeric_gate_met": numeric_gate,
        "protocol_status": (
            "incomplete" if blockers else "declared_complete_not_externally_verified"
        ),
        "protocol_blockers": blockers,
        "statistical_evidence_gate_met": statistical_gate,
        "statistical_evidence": {
            "method_id": "paired_brier_hoeffding_bonferroni_v1",
            "familywise_confidence_level": plan.confidence_level,
            "planned_evaluations": plan.planned_evaluations,
            "per_evaluation_alpha": alpha,
            "mean_paired_brier_improvement": mean_improvement,
            "registered_minimum_brier_skill": plan.minimum_brier_skill,
            "mean_excess_over_registered_threshold": mean_excess,
            "lower_bound_excess_over_registered_threshold": lower_excess,
            "sources": [
                "https://doi.org/10.1080/01621459.1963.10500830",
                "https://www.itl.nist.gov/div898/handbook/prc/section4/prc463.htm",
            ],
            "scope": "假设主体独立、模型与逐例或常数基线事前固定、事先登记观察次数；保守单侧界，不要求每例基线概率相同，仍需完整覆盖和最低样本量。numeric门槛仅检查数值，performance还检查协议声明，两者均不能替代此界。记录真实性、参考强度、主体独立性与是否执行预注册须外部核验。",
        },
        "real_world_efficacy": (
            "not_tested"
            if n == 0
            else (
                "not_established_by_synthetic_data"
                if plan.data_kind == "synthetic"
                else "submitted_metrics_require_external_verification"
            )
        ),
        "authority_certified": False,
        "universal_perfect_prediction_established": False,
        "limitations": [
            "方案指纹绑定事件、窗口、队列、基线和统计政策，但不能证明指纹事前发布；旧记录不自动补绑定。",
            "仅核对记录内部一致性；时间戳、来源哈希、盲法及未用于调参的独立性须外部核验。",
            "准确率及Wilson区间只对可评估样本有效，假设样本独立；不可忽略覆盖率、弃权及未随访记录。",
            "全对样本也不能证明总体准确率为100%；最低样本量与Brier门槛是注册方案条件，不是权威认证标准。",
            "不把命理规则分数转换为现实概率，不验证命理原因与现实事件的因果关系。",
        ],
    }

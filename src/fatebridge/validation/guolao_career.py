"""Paired, fixed-window career evaluation; never generates event forecasts.

The augmented system includes explicit abstentions via the frozen reality
baseline. Missing records are different: they remain in the cohort ledger and
in sharp binary-outcome bounds. This module cannot authenticate a registration,
consent, timestamp, source, blinding declaration or an independent sample.
"""

from __future__ import annotations

import math
import random
from bisect import bisect_right
from datetime import datetime, timezone
from pathlib import Path
from statistics import NormalDist
from typing import Annotated, Any, Literal

from pydantic import (
    AwareDatetime,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    field_validator,
    model_validator,
)

from fatebridge.validation.predictions import (
    CohortMember,
    Outcome,
    Record,
    digest,
    wilson_interval,
)

Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Reference = Annotated[str, Field(min_length=1, pattern=r"\S")]
METHOD = "guolao_career_paired_brier_v1"
RESAMPLES = 10_000
SEED = 20261022
CONFIDENCE = 0.95


def analysis_code_fingerprint() -> str:
    """Commit these two implementation files; not an external time attestation."""
    import hashlib

    here = Path(__file__).resolve().parent
    return digest(
        {
            name: hashlib.sha256((here / name).read_bytes()).hexdigest()
            for name in ("guolao_career.py", "predictions.py")
        }
    )


class CareerStudyPlan(Record):
    study_id: Reference
    data_kind: Literal["synthetic", "real_world_submission"]
    target_definition: Literal["formal_role_change_or_promotion_in_fixed_window"]
    preregistered_at: AwareDatetime
    registration_reference: Reference
    window_start: AwareDatetime
    window_end: AwareDatetime
    models_frozen_at: AwareDatetime
    model_sha256: Sha256
    baseline_model_sha256: Sha256
    interpretation_policy_sha256: Sha256
    analysis_code_sha256: Sha256
    cohort_sha256: Sha256
    training_subject_ids: list[str]
    power_analysis_reference: Reference
    power_analysis_sha256: Sha256
    minimum_evaluable: StrictInt = Field(ge=2)
    minimum_brier_improvement: StrictFloat = Field(ge=0, lt=1)
    decision_threshold: StrictFloat = Field(default=0.5, gt=0, lt=1)
    planned_evaluations: Literal[1] = 1
    cohort: list[CohortMember] = Field(min_length=1)

    @field_validator(
        "preregistered_at", "window_start", "window_end", "models_frozen_at"
    )
    @classmethod
    def physical_instants(cls, value: datetime) -> datetime:
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def frozen_and_unique(self) -> CareerStudyPlan:
        if (
            not self.models_frozen_at
            <= self.preregistered_at
            < self.window_start
            < self.window_end
        ):
            raise ValueError("模型须在登记前冻结，登记须早于目标窗口，窗口前含后不含")
        if len({m.case_id for m in self.cohort}) != len(self.cohort):
            raise ValueError("队列不能重复case_id")
        if len({m.subject_id for m in self.cohort}) != len(self.cohort):
            raise ValueError("每行须为独立主体；重复主体需要另设聚类方案")
        if any(not m.case_id.strip() or not m.subject_id.strip() for m in self.cohort):
            raise ValueError("主体和案例编号不能为空白")
        if {m.subject_id for m in self.cohort}.intersection(self.training_subject_ids):
            raise ValueError("评估队列与声明的训练主体重叠")
        if (
            digest([m.model_dump(mode="json") for m in self.cohort])
            != self.cohort_sha256
        ):
            raise ValueError("队列及其顺序与冻结指纹不符")
        return self


class PairedCareerForecast(Record):
    case_id: Reference
    issued_at: AwareDatetime
    information_cutoff_at: AwareDatetime
    model_sha256: Sha256
    baseline_model_sha256: Sha256
    interpretation_policy_sha256: Sha256
    evidence_sha256: Sha256
    baseline_reality_input_sha256: Sha256
    augmented_reality_input_sha256: Sha256
    independent_timestamp_reference: Reference
    baseline_probability: StrictFloat = Field(ge=0, le=1)
    probability: StrictFloat | None = Field(ge=0, le=1)
    abstention_reason: Reference | None = None

    @field_validator("issued_at", "information_cutoff_at")
    @classmethod
    def physical_instants(cls, value: datetime) -> datetime:
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def paired_inputs_and_abstention(self) -> PairedCareerForecast:
        if self.baseline_reality_input_sha256 != self.augmented_reality_input_sha256:
            raise ValueError("两模型须声明使用相同现实信息输入，不能换比较对象")
        if self.information_cutoff_at > self.issued_at:
            raise ValueError("信息截止点不能晚于预测发布时间")
        if (self.probability is None) != (self.abstention_reason is not None):
            raise ValueError("空概率须明确弃权原因；非空预测不能同时标弃权")
        return self


class CareerOutcome(Outcome):
    subtype: Literal["employer_change", "formal_role_change", "promotion"] | None = None
    window_complete_through: AwareDatetime
    blinded_to_forecasts: StrictBool
    adjudication_reference: Reference

    @field_validator("event_at", "recorded_at", "window_complete_through")
    @classmethod
    def physical_instants(cls, value: datetime | None) -> datetime | None:
        return value.astimezone(timezone.utc) if value is not None else None

    @model_validator(mode="after")
    def endpoint_labels(self) -> CareerOutcome:
        if self.occurred != (self.subtype is not None):
            raise ValueError("阳性须有正式任职事件子类型；阴性不能同时有事件子类型")
        if self.window_complete_through > self.recorded_at:
            raise ValueError("不能声称已随访到结果记录之后")
        return self


def _quantile(ordered: list[float], q: float) -> float:
    position = (len(ordered) - 1) * q
    low = math.floor(position)
    high = math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def _paired_bootstrap(differences: list[float]) -> dict[str, Any]:
    if not differences:
        return {"interval": None, "status": "no_observed_pairs"}
    generator = random.Random(SEED)
    n = len(differences)
    means = sorted(
        math.fsum(generator.choices(differences, k=n)) / n for _ in range(RESAMPLES)
    )
    result: dict[str, Any] = {
        "interval": None,
        "method": "paired_subject_BCa_midrank_bias_jackknife_mean_linear_quantiles",
        "resamples": RESAMPLES,
        "seed": SEED,
        "confidence_level": CONFIDENCE,
        "scope": "以观察到的主体对为单位重抽；失访时仅为完整案例条件区间。小样本、退化样本和非随机队列不保证名义覆盖率。",
    }
    mean = math.fsum(differences) / n
    centered = [d - mean for d in differences]
    squares = math.fsum(d * d for d in centered)
    if not squares:
        return {**result, "status": "degenerate_observed_losses_BCa_undefined"}
    acceleration = math.fsum(d * d * d for d in centered) / (6 * squares**1.5)
    rank = (sum(m < mean for m in means) + sum(m <= mean for m in means)) / (
        2 * RESAMPLES
    )
    if not 0 < rank < 1:
        return {**result, "status": "bootstrap_bias_quantile_not_finite"}
    normal = NormalDist()
    bias = normal.inv_cdf(rank)
    adjusted = []
    for q in (0.025, 0.975):
        term = bias + normal.inv_cdf(q)
        denominator = 1 - acceleration * term
        if denominator <= 0:
            return {**result, "status": "BCa_adjustment_singular"}
        adjusted.append(normal.cdf(bias + term / denominator))
    if adjusted[0] > adjusted[1]:
        return {**result, "status": "BCa_quantiles_not_ordered"}
    return {
        **result,
        "status": "computed",
        "interval": [_quantile(means, q) for q in adjusted],
        "bias_correction": bias,
        "jackknife_acceleration": acceleration,
        "adjusted_quantiles": adjusted,
    }


def _sigmoid(value: float) -> float:
    if value >= 0:
        return 1 / (1 + math.exp(-value))
    exponent = math.exp(value)
    return exponent / (1 + exponent)


def _calibration_fit(pairs: list[tuple[float, int]]) -> dict[str, Any]:
    """Unpenalized logit recalibration MLE, with explicit undefined cases.

    Newton/IRLS with line search; no clipping endpoint forecasts or replacing
    separated/rank-deficient models by an apparently successful finite fit.
    """
    result: dict[str, Any] = {
        "intercept": None,
        "slope": None,
        "intervals": None,
        "method": "unpenalized_logistic_MLE_logit_probability_Wald95",
    }
    if not pairs:
        return {**result, "status": "no_observed_pairs"}
    if any(not 0 < p < 1 for p, _ in pairs):
        return {**result, "status": "undefined_endpoint_probabilities_no_clipping"}
    if len({y for _, y in pairs}) == 1:
        return {**result, "status": "single_outcome_class_no_finite_MLE"}
    raw = [(math.log(p) - math.log1p(-p), y) for p, y in pairs]
    if len({x for x, _ in raw}) == 1:
        return {**result, "status": "rank_deficient_constant_probability"}
    negative, positive = ([x for x, y in raw if y == k] for k in (0, 1))
    if max(negative) <= min(positive) or max(positive) <= min(negative):
        return {**result, "status": "complete_or_quasi_separation_no_finite_MLE"}
    center = math.fsum(x for x, _ in raw) / len(raw)
    data = [(x - center, y) for x, y in raw]
    rate = math.fsum(y for _, y in data) / len(data)
    a, b = math.log(rate) - math.log1p(-rate), 0.0

    def likelihood(intercept: float, slope: float) -> float:
        return math.fsum(
            y * (eta := intercept + slope * x)
            - max(eta, 0)
            - math.log1p(math.exp(-abs(eta)))
            for x, y in data
        )

    for iteration in range(100):
        fitted = [(x, y, _sigmoid(a + b * x)) for x, y in data]
        h00 = math.fsum(p * (1 - p) for _, _, p in fitted)
        h01 = math.fsum(x * p * (1 - p) for x, _, p in fitted)
        h11 = math.fsum(x * x * p * (1 - p) for x, _, p in fitted)
        determinant = h00 * h11 - h01 * h01
        if determinant <= 0 or not math.isfinite(determinant):
            return {**result, "status": "numerically_singular_information"}
        g0 = math.fsum(y - p for _, y, p in fitted)
        g1 = math.fsum(x * (y - p) for x, y, p in fitted)
        if max(abs(g0), abs(g1)) < 1e-10 * len(data):
            variance_a = (h11 + 2 * center * h01 + center * center * h00) / determinant
            variance_b = h00 / determinant
            if variance_a < 0 or variance_b < 0:
                return {**result, "status": "invalid_information_variance"}
            intercept = a - b * center
            z = NormalDist().inv_cdf(0.975)
            return {
                **result,
                "status": "finite_MLE",
                "intercept": intercept,
                "slope": b,
                "intervals": {
                    "intercept": [
                        intercept - z * math.sqrt(variance_a),
                        intercept + z * math.sqrt(variance_a),
                    ],
                    "slope": [
                        b - z * math.sqrt(variance_b),
                        b + z * math.sqrt(variance_b),
                    ],
                },
                "iterations": iteration,
                "scope": "完整案例的非惩罚logit校准；区间为渐近Wald区间，不是有限样本或选择机制保证。",
            }
        da, db = (h11 * g0 - h01 * g1) / determinant, (
            h00 * g1 - h01 * g0
        ) / determinant
        old_likelihood = likelihood(a, b)
        step = 1.0
        for _ in range(60):
            candidate_a, candidate_b = a + step * da, b + step * db
            if (
                math.isfinite(candidate_a)
                and math.isfinite(candidate_b)
                and likelihood(candidate_a, candidate_b) >= old_likelihood
            ):
                a, b = candidate_a, candidate_b
                break
            step /= 2
        else:
            return {**result, "status": "line_search_failed"}
    return {**result, "status": "iteration_limit_not_converged"}


def _metrics(pairs: list[tuple[float, int]], threshold: float) -> dict[str, Any]:
    n = len(pairs)
    positives = sum(y for _, y in pairs)
    true_positive = sum(p >= threshold and y == 1 for p, y in pairs)
    true_negative = sum(p < threshold and y == 0 for p, y in pairs)
    calibration = []
    edges = [i / 10 for i in range(1, 10)]
    for index in range(10):
        selected = [(p, y) for p, y in pairs if bisect_right(edges, p) == index]
        count = len(selected)
        calibration.append(
            {
                "lower": index / 10,
                "upper": (index + 1) / 10,
                "upper_inclusive": index == 9,
                "count": count,
                "mean_probability": (
                    math.fsum(p for p, _ in selected) / count if count else None
                ),
                "observed_rate": (
                    math.fsum(y for _, y in selected) / count if count else None
                ),
                "observed_rate_interval": wilson_interval(
                    sum(y for _, y in selected), count, CONFIDENCE
                ),
            }
        )
    return {
        "count": n,
        "brier_score": math.fsum((p - y) ** 2 for p, y in pairs) / n if n else None,
        "accuracy": (true_positive + true_negative) / n if n else None,
        "accuracy_interval": wilson_interval(
            true_positive + true_negative, n, CONFIDENCE
        ),
        "sensitivity": true_positive / positives if positives else None,
        "specificity": true_negative / (n - positives) if n > positives else None,
        "calibration_bins": calibration,
        "calibration_recalibration": _calibration_fit(pairs),
    }


def _brier_difference(augmented: float, baseline: float, outcome: int) -> float:
    """Keep small paired differences near either probability endpoint.

    a-b retains differences near zero; summing residuals avoids cancelling
    a+b-2 near one. This adds no information beyond the supplied doubles.
    """
    return (augmented - baseline) * ((augmented - outcome) + (baseline - outcome))


def evaluate_career_study(
    plan: CareerStudyPlan,
    forecasts: list[PairedCareerForecast],
    outcomes: list[CareerOutcome],
    *,
    as_of: datetime,
) -> dict[str, Any]:
    """Predeclared paired comparison, full ledger and sharp missingness bounds."""
    plan = CareerStudyPlan.model_validate(plan.model_dump())
    forecasts = [PairedCareerForecast.model_validate(f.model_dump()) for f in forecasts]
    outcomes = [CareerOutcome.model_validate(o.model_dump()) for o in outcomes]
    if as_of.utcoffset() is None:
        raise ValueError("as_of须有时区")
    as_of = as_of.astimezone(timezone.utc)
    if as_of < plan.preregistered_at:
        raise ValueError("不能在登记发生之前声称评估已登记研究")
    code_fingerprint = analysis_code_fingerprint()
    if plan.analysis_code_sha256 != code_fingerprint:
        raise ValueError("分析代码指纹与登记方案不符；不可事后更换评分方法")
    members = {m.case_id for m in plan.cohort}
    predicted: dict[str, PairedCareerForecast] = {}
    observed: dict[str, CareerOutcome] = {}
    for f in forecasts:
        if f.case_id not in members or f.case_id in predicted:
            raise ValueError("预测含未登记或重复案例")
        if (
            f.model_sha256,
            f.baseline_model_sha256,
            f.interpretation_policy_sha256,
        ) != (
            plan.model_sha256,
            plan.baseline_model_sha256,
            plan.interpretation_policy_sha256,
        ):
            raise ValueError("预测模型、基准或文案政策与登记指纹不符")
        if (
            not plan.preregistered_at <= f.issued_at < plan.window_start
            or f.issued_at > as_of
        ):
            raise ValueError("预测须在登记后、窗口开始前发布，且不能晚于as_of")
        predicted[f.case_id] = f
    for o in outcomes:
        if o.case_id not in members or o.case_id in observed:
            raise ValueError("结果含未登记或重复案例")
        if o.recorded_at < plan.window_end:
            raise ValueError("最终结果须在完整窗口结束后记录")
        if o.occurred:
            if (
                o.event_at is None
                or not plan.window_start <= o.event_at < plan.window_end
            ):
                raise ValueError("阳性须有窗口内的任职事件时刻")
            if o.window_complete_through < o.event_at:
                raise ValueError("随访截止点不能早于已确认的任职事件")
        elif o.event_at is not None:
            raise ValueError("阴性不能同时填写事件时刻")
        elif o.window_complete_through < plan.window_end:
            raise ValueError("阴性必须完整随访到窗口结束；失访不能当作未发生")
        observed[o.case_id] = o
    mature = as_of >= plan.window_end
    rows = []
    paired = []
    baseline_pairs = []
    augmented_pairs = []
    lower_terms = []
    upper_terms = []
    blockers = []
    for member in plan.cohort:
        submitted, recorded = predicted.get(member.case_id), observed.get(
            member.case_id
        )
        status = (
            "missing_forecast"
            if submitted is None
            else (
                "window_pending"
                if not mature
                else (
                    "outcome_pending"
                    if recorded is None or recorded.recorded_at > as_of
                    else "observed"
                )
            )
        )
        row: dict[str, Any] = {
            "case_id": member.case_id,
            "status": status,
            "abstained": submitted is not None and submitted.probability is None,
        }
        if submitted is None:
            lower_terms.append(-1.0)
            upper_terms.append(1.0)
        else:
            base = submitted.baseline_probability
            augmented = base if submitted.probability is None else submitted.probability
            row.update(
                {
                    "baseline_probability": base,
                    "effective_augmented_probability": augmented,
                    "abstention_reason": submitted.abstention_reason,
                }
            )
            if status == "observed":
                assert recorded is not None
                y = int(recorded.occurred)
                difference = _brier_difference(augmented, base, y)
                paired.append(difference)
                baseline_pairs.append((base, y))
                augmented_pairs.append((augmented, y))
                lower_terms.append(difference)
                upper_terms.append(difference)
                row["paired_brier_difference"] = difference
                if not recorded.blinded_to_forecasts:
                    blockers.append("declared_unblinded_outcome:" + member.case_id)
            else:
                possible = [_brier_difference(augmented, base, y) for y in (0, 1)]
                lower_terms.append(min(possible))
                upper_terms.append(max(possible))
        rows.append(row)
    n, total = len(paired), len(plan.cohort)
    baseline_metrics = _metrics(baseline_pairs, plan.decision_threshold)
    augmented_metrics = _metrics(augmented_pairs, plan.decision_threshold)
    bootstrap = _paired_bootstrap(paired)
    mean_difference = math.fsum(paired) / n if n else None
    interval = bootstrap["interval"]
    complete = mature and n == total
    gate = (
        complete
        and not blockers
        and n >= plan.minimum_evaluable
        and interval is not None
        and interval[1] < -plan.minimum_brier_improvement
    )
    baseline_brier, augmented_brier = (
        baseline_metrics["brier_score"],
        augmented_metrics["brier_score"],
    )
    if analysis_code_fingerprint() != code_fingerprint:
        raise ValueError("分析源码在执行期间发生变化；须冻结实现后重新分析")
    return {
        "method_id": METHOD,
        "study_id": plan.study_id,
        "data_kind": plan.data_kind,
        "as_of": as_of.astimezone(timezone.utc).isoformat(),
        "plan_sha256": digest(plan.model_dump(mode="json")),
        "analysis_code_sha256": code_fingerprint,
        "forecast_records_sha256": digest(
            [f.model_dump(mode="json") for f in forecasts]
        ),
        "outcome_records_sha256": digest([o.model_dump(mode="json") for o in outcomes]),
        "registered_count": total,
        "forecast_record_count": len(predicted),
        "observed_pair_count": n,
        "nonabstaining_forecast_count": sum(
            f.probability is not None for f in predicted.values()
        ),
        "explicit_abstention_count": sum(
            f.probability is None for f in predicted.values()
        ),
        "missing_forecast_count": total - len(predicted),
        "outcome_pair_coverage": n / total,
        "forecast_record_coverage": len(predicted) / total,
        "nonabstaining_forecast_coverage": sum(
            f.probability is not None for f in predicted.values()
        )
        / total,
        "rows": rows,
        "primary": {
            "direction": "augmented_minus_reality_baseline_negative_favors_augmented",
            "status": (
                "complete_fixed_cohort"
                if complete
                else "incomplete_complete_case_metrics_only"
            ),
            "mean_paired_brier_difference": mean_difference,
            "uncertainty": bootstrap,
            "full_cohort_identification_bounds": [
                math.fsum(lower_terms) / total,
                math.fsum(upper_terms) / total,
            ],
            "bounds_scope": "固定队列未知标签取0/1的逐人最坏/最好界；缺预测记录取[-1,1]，不是置信区间或MAR假设。",
            "minimum_brier_improvement": plan.minimum_brier_improvement,
            "prespecified_sample_comparison_passed": gate,
        },
        "baseline": baseline_metrics,
        "augmented_with_baseline_for_abstentions": augmented_metrics,
        "brier_skill_vs_paired_baseline": (
            1 - augmented_brier / baseline_brier if baseline_brier else None
        ),
        "protocol_blockers": blockers,
        "real_world_efficacy": (
            "not_tested"
            if not n
            else (
                "not_established_by_synthetic_data"
                if plan.data_kind == "synthetic"
                else "submitted_metrics_require_external_verification"
            )
        ),
        "authority_certified": False,
        "universal_perfect_prediction_established": False,
        "method_sources": [
            "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html",
            "https://stat.ethz.ch/R-manual/R-devel/library/stats/html/glm.html",
            "https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm",
        ],
        "limitations": [
            "外部登记、时间戳、授权、盲法、同一现实信息和训练独立性这里只核对声明及指纹，不认证真实性。",
            "弃权回填冻结现实基准进入主要比较；缺记录和失访保留全队列，不当阴性。",
            "BCa bootstrap按独立主体抽样，区间为渐近近似；退化时保留未定义，不以零宽区间冒充证据。小样本/选择偏差不获覆盖率保证，缺失时仅是完整案例条件分析。",
            "校准logit MLE不裁剪0/1预测、不伪造分离或常数模型的斜率；可估计时Wald区间同样为渐近结果。",
            "软件不能核实只查看一次；模型、分析或目标变更须另行登记，不能反复调到测试通过。",
        ],
    }

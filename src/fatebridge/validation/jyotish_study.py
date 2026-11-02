"""Commit-before-reveal workflow around the shared prospective evaluator.

Hashes detect changes relative to a retained commitment. Local files and clock
readings alone do not prove preregistration or human blinding: publish the
commitments to an independent timestamped registry before outcomes exist.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from pydantic import Field, model_validator

from fatebridge.validation.predictions import (
    Forecast,
    Outcome,
    Record,
    StudyPlan,
    digest,
    evaluate_study,
)


class BlindProtocol(Record):
    plan: StudyPlan
    training_subject_ids: list[str]
    baseline_derivation: str = Field(min_length=1)
    outcome_adjudication: str = Field(min_length=1)
    recruitment_and_exclusions: str = Field(min_length=1)
    probability_mapping: str = Field(
        min_length=1,
        description="A frozen forecasting policy, not a traditional rule score relabeled as probability",
    )
    sample_size_justification: str = Field(min_length=1)
    analysis_plan: str = Field(
        min_length=1,
        description="One primary Brier endpoint; frozen uncertainty analysis and missing-data policy; secondary analyses labeled exploratory",
    )
    artifact_sha256: dict[str, str] = Field(min_length=1)

    @model_validator(mode="after")
    def separation(self) -> BlindProtocol:
        if {m.subject_id for m in self.plan.cohort} & set(self.training_subject_ids):
            raise ValueError("训练主体与盲测主体重叠；不能将调参案例计作独立盲测")
        if len(self.training_subject_ids) != len(set(self.training_subject_ids)):
            raise ValueError("训练主体记录重复")
        for name, value in self.artifact_sha256.items():
            if (
                not name
                or len(value) != 64
                or any(c not in "0123456789abcdef" for c in value)
            ):
                raise ValueError("规则、来源与解释策略必须使用具名SHA-256指纹")
        return self


def _clock(at: datetime) -> datetime:
    if at.utcoffset() is None:
        raise ValueError("工作流时刻必须带时区")
    return at.astimezone(timezone.utc)


def register(
    protocol: BlindProtocol,
    model_bytes: bytes,
    *,
    at: datetime,
    artifacts: dict[str, bytes],
) -> dict[str, Any]:
    now = _clock(at)
    if not protocol.plan.preregistered_at <= now < protocol.plan.window_start:
        raise ValueError("必须在注册时刻之后、目标窗口开始之前冻结方案")
    if hashlib.sha256(model_bytes).hexdigest() != protocol.plan.model_sha256:
        raise ValueError("实际模型文件与注册指纹不一致")
    if set(artifacts) != set(protocol.artifact_sha256) or any(
        hashlib.sha256(content).hexdigest() != protocol.artifact_sha256[name]
        for name, content in artifacts.items()
    ):
        raise ValueError("必须提供与全部注册指纹一致的实际规则、来源及解释策略文件")
    body = {
        "format": "jyotish_blind_registration_v1",
        "registered_at": now.isoformat(),
        "protocol": protocol.model_dump(mode="json"),
    }
    return {**body, "registration_sha256": digest(body)}


def read_registration(registration: dict[str, Any]) -> BlindProtocol:
    body = {k: v for k, v in registration.items() if k != "registration_sha256"}
    if (
        set(body) != {"format", "registered_at", "protocol"}
        or body["format"] != "jyotish_blind_registration_v1"
        or digest(body) != registration.get("registration_sha256")
    ):
        raise ValueError("注册文件已改变或格式不受支持")
    protocol = BlindProtocol.model_validate(body["protocol"])
    registered = datetime.fromisoformat(body["registered_at"])
    if (
        not protocol.plan.preregistered_at
        <= _clock(registered)
        < protocol.plan.window_start
    ):
        raise ValueError("注册时间无效")
    return protocol


def seal_forecasts(
    registration: dict[str, Any], forecasts: list[Forecast], *, at: datetime
) -> dict[str, Any]:
    protocol = read_registration(registration)
    now = _clock(at)
    if (
        not datetime.fromisoformat(registration["registered_at"])
        <= now
        < protocol.plan.window_start
    ):
        raise ValueError("预测封存必须在注册后、目标窗口之前")
    if {f.case_id for f in forecasts} != {m.case_id for m in protocol.plan.cohort}:
        raise ValueError("必须覆盖完整注册队列；无法预测也须显式记录弃权")
    # Shared evaluator checks duplicate rows, model IDs and issuance windows.
    evaluate_study(protocol.plan, forecasts, [], as_of=now)
    if any(
        f.issued_at < datetime.fromisoformat(registration["registered_at"])
        for f in forecasts
    ):
        raise ValueError("预测早于实际注册封存时刻")
    serialized = []
    for forecast in forecasts:
        payload = forecast.model_dump(mode="json")
        # Retain the exact v1 packet shape for legacy omitted bindings. An
        # explicit null stays explicit; a supplied commitment is never removed.
        if (
            forecast.study_plan_sha256 is None
            and "study_plan_sha256" not in forecast.model_fields_set
        ):
            payload.pop("study_plan_sha256")
        serialized.append(payload)
    body = {
        "format": "jyotish_blind_forecasts_v1",
        "registration_sha256": registration["registration_sha256"],
        "sealed_at": now.isoformat(),
        "forecasts": serialized,
    }
    return {**body, "forecast_commitment_sha256": digest(body)}


def reveal_and_evaluate(
    registration: dict[str, Any],
    sealed: dict[str, Any],
    outcomes: list[Outcome],
    *,
    at: datetime,
) -> dict[str, Any]:
    protocol = read_registration(registration)
    now = _clock(at)
    body = {k: v for k, v in sealed.items() if k != "forecast_commitment_sha256"}
    if (
        set(body) != {"format", "registration_sha256", "sealed_at", "forecasts"}
        or body["format"] != "jyotish_blind_forecasts_v1"
        or digest(body) != sealed.get("forecast_commitment_sha256")
    ):
        raise ValueError("预测封存文件已改变或格式不受支持")
    if sealed["registration_sha256"] != registration["registration_sha256"]:
        raise ValueError("预测不属于这份注册方案")
    forecasts = [Forecast.model_validate(f) for f in body["forecasts"]]
    # Revalidate all timing/cohort conditions even when loading files directly.
    rebuilt = seal_forecasts(
        registration, forecasts, at=datetime.fromisoformat(sealed["sealed_at"])
    )
    if rebuilt != sealed:
        raise ValueError("预测封存内容不一致")
    if now < protocol.plan.window_end:
        raise ValueError("目标窗口尚未结束；不能提前揭盲或择机停止")
    report = evaluate_study(protocol.plan, forecasts, outcomes, as_of=now)
    report.update(
        {
            "registration_sha256": registration["registration_sha256"],
            "forecast_commitment_sha256": sealed["forecast_commitment_sha256"],
            "external_timestamp_and_blinding": "requires_independent_verification",
            "protocol_scope": "one frozen binary endpoint; no universal or causal validity claim",
        }
    )
    return report

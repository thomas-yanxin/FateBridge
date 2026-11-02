"""Bind a prospective dice study to complete, frozen forecast rules and rolls.

This checks consistency and replay, not the authenticity of a physical roll,
independent timestamps, consent, blinding or predictive validity. The caller
supplies all probabilities; no symbolic dignity is converted to a probability.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from itertools import product
from pathlib import Path
from typing import Any, Optional

from pydantic import AwareDatetime, Field, StrictFloat, field_validator, model_validator

from fatebridge.core import astrodice, astrology_tables, ptolemy
from fatebridge.validation.predictions import (
    Forecast,
    Outcome,
    Record,
    StudyPlan,
    digest,
    evaluate_study,
)


def engine_fingerprint() -> str:
    """Bind the symbol implementation, tables and shared triangle rules."""
    sources = {}
    for module in (astrodice, astrology_tables, ptolemy):
        path = module.__file__
        if path is None:
            raise ValueError("无法取得实际符号规则源码，不能建立研究引擎指纹")
        sources[module.__name__] = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return digest(sources)


class DiceRoll(Record):
    planet: str
    sign: str
    house: int = Field(strict=True, ge=0, le=11)

    @field_validator("planet")
    @classmethod
    def actual_planet(cls, value: str) -> str:
        return astrodice.normalize_planet(value)

    @field_validator("sign")
    @classmethod
    def actual_sign(cls, value: str) -> str:
        return astrodice.normalize_sign(value)

    @property
    def cell(self) -> str:
        return f"{self.planet}|{self.sign}|{self.house}"


class DiceObservation(Record):
    case_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    recorded_at: AwareDatetime
    roll: DiceRoll
    physical_record_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    physical_record_reference: str = Field(min_length=1)


class FrozenDicePolicy(Record):
    """A complete caller-supplied table, including explicit abstention cells."""

    policy_id: str = Field(min_length=1)
    method_id: str
    symbolic_engine_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    target_definition: str = Field(min_length=1)
    probabilities: dict[str, Optional[StrictFloat]] = Field(
        min_length=1728, max_length=1728
    )

    @model_validator(mode="after")
    def complete_canonical_table(self) -> FrozenDicePolicy:
        cells = {
            f"{planet}|{sign}|{house}"
            for planet, sign, house in product(
                astrodice.PLANETS, astrology_tables.SIGNS, range(12)
            )
        }
        if set(self.probabilities) != cells:
            raise ValueError(
                "策略必须完整列出1728个规范骰面组合，包括明确弃权；不能依靠默认值或结果后补规则"
            )
        if any(p is not None and not 0 <= p <= 1 for p in self.probabilities.values()):
            raise ValueError("研究概率须在0..1内；不能把传统分数当作概率")
        return self


def policy_fingerprint(policy: FrozenDicePolicy) -> str:
    """Canonical semantic JSON hash, independent of file whitespace/key order."""
    return digest(policy.model_dump(mode="json"))


def _registered_observations(
    plan: StudyPlan, policy: FrozenDicePolicy, observations: list[DiceObservation]
) -> dict[str, DiceObservation]:
    if (
        policy.method_id != astrodice.METHOD_ID
        or policy.symbolic_engine_sha256 != engine_fingerprint()
    ):
        raise ValueError(
            "冻结的符号引擎与当前代码不一致；需使用注册时的实际引擎重放，不可事后换版"
        )
    if plan.model_sha256 != policy_fingerprint(policy):
        raise ValueError("策略与预注册模型指纹不一致")
    if plan.target_definition != policy.target_definition:
        raise ValueError("策略目标与预注册事件定义不一致")
    if plan.training_subject_ids is None:
        raise ValueError("须声明训练主体；无训练主体也须明确传空列表")
    by_case = {record.case_id: record for record in observations}
    if len(by_case) != len(observations) or set(by_case) != {
        m.case_id for m in plan.cohort
    }:
        raise ValueError("骰面记录必须完整覆盖预注册队列，不能重复、漏报或增加案例")
    for member in plan.cohort:
        record = by_case[member.case_id]
        if record.subject_id != member.subject_id:
            raise ValueError("骰面记录主体与注册队列不一致")
        if not plan.preregistered_at <= record.recorded_at < plan.window_start:
            raise ValueError("骰面记录必须在预注册后且目标窗口开始前固定")
    return by_case


def evidence_fingerprint(observation: DiceObservation, policy: FrozenDicePolicy) -> str:
    roll = observation.roll
    return digest(
        {
            "observation": observation.model_dump(mode="json"),
            "policy_sha256": policy_fingerprint(policy),
            "symbolic_result": astrodice.build_symbolic_evidence(
                roll.planet, roll.sign, roll.house
            ),
        }
    )


def make_forecasts(
    plan: StudyPlan,
    policy: FrozenDicePolicy,
    observations: list[DiceObservation],
    *,
    at: datetime,
) -> list[Forecast]:
    records = _registered_observations(plan, policy, observations)
    if at.utcoffset() is None or not plan.preregistered_at <= at < plan.window_start:
        raise ValueError("预测发布时刻必须带时区，并位于预注册后、目标窗口前")
    forecasts = []
    plan_hash = digest(plan.model_dump(mode="json"))
    for member in plan.cohort:
        record = records[member.case_id]
        if record.recorded_at > at:
            raise ValueError("不能用发布时刻之后才记录的骰面生成预测")
        forecasts.append(
            Forecast(
                case_id=member.case_id,
                study_plan_sha256=plan_hash,
                issued_at=at,
                model_sha256=plan.model_sha256,
                evidence_sha256=evidence_fingerprint(record, policy),
                probability=policy.probabilities[record.roll.cell],
            )
        )
    return forecasts


def audit_study(
    plan: StudyPlan,
    policy: FrozenDicePolicy,
    observations: list[DiceObservation],
    forecasts: list[Forecast],
    outcomes: list[Outcome],
    *,
    as_of: datetime,
) -> dict[str, Any]:
    records = _registered_observations(plan, policy, observations)
    if len({f.case_id for f in forecasts}) != len(forecasts) or {
        f.case_id for f in forecasts
    } != set(records):
        raise ValueError("预测须覆盖完整队列；无法预测须明确记录弃权，不能删去案例")
    for forecast in forecasts:
        record = records[forecast.case_id]
        if record.recorded_at > forecast.issued_at:
            raise ValueError("骰面证据晚于预测发布时刻")
        if forecast.evidence_sha256 != evidence_fingerprint(record, policy):
            raise ValueError("预测未绑定实际骰面、符号计算及冻结策略")
        if forecast.probability != policy.probabilities[record.roll.cell]:
            raise ValueError("提交概率与冻结策略不一致；不得按结果更改预测或弃权")
    report = evaluate_study(plan, forecasts, outcomes, as_of=as_of)
    report.update(
        {
            "dice_evidence_binding": "all_registered_rolls_and_policy_outputs_recomputed",
            "dice_policy_sha256": policy_fingerprint(policy),
            "symbolic_engine_sha256": policy.symbolic_engine_sha256,
            "dice_method_id": policy.method_id,
            "physical_roll_and_timestamp_authenticity": "requires_independent_verification",
        }
    )
    return report

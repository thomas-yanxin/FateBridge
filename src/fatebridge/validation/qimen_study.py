"""Replay prospective Qimen forecasts from a frozen, outcome-blind policy.

This is a research protocol, not a validated predictor. Probabilities are
caller-declared hypotheses, never conversions of traditional scores. Local
hashes check consistency; they cannot authenticate registration, timestamps,
questions, independence, blinding, consent or outcomes.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import os
import platform
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import (
    AwareDatetime,
    Field,
    StrictBool,
    StrictFloat,
    StrictStr,
    model_validator,
)

from fatebridge.core import ephemeris_runtime
from fatebridge.services.metaphysics import calculate_qimen_analysis
from fatebridge.utils.civil_clock import format_utc_offset, utc_instant
from fatebridge.utils.timezones import parse_timezone_name
from fatebridge.validation.predictions import (
    Forecast,
    Outcome,
    Record,
    StudyPlan,
    digest,
    evaluate_study,
)

Pattern = Literal[
    "door_pressure",
    "six_instrument_punishment",
    "wonder_tomb",
    "stem_pair",
    "heaven_dun",
    "earth_dun",
    "human_dun",
    "spirit_dun",
    "true_deception",
    "heavy_deception",
    "rest_deception",
    "heaven_jia",
    "earth_jia",
    "spirit_jia",
    "ghost_jia",
    "human_jia",
    "wonders_de_shi",
    "jade_maiden_gate",
    "flying_bird_enters_cave",
    "dragon_returns_head",
    "hidden_palace",
    "flying_palace",
    "hidden_day_stem",
    "flying_day_stem",
    "hour_stem_block",
    "year_stem_block",
    "lunar_month_start_block",
]
Feature = Literal[
    "stars_fuyin",
    "stars_fanyin",
    "doors_fuyin",
    "doors_fanyin",
    "five_not_meet",
    "hour_branch_tomb",
    "door",
    "star",
    "god",
    "star_season_state",
    "door_pressure",
    "hour_void_scope",
    "pattern_present",
    "pattern_conditions_observed",
]
OUTER = set("坎坤震巽乾兑艮离")
STRUCTURE = {
    "hour_branch_tomb",
    "stars_fuyin",
    "stars_fanyin",
    "doors_fuyin",
    "doors_fanyin",
    "five_not_meet",
}
PALACE = {
    "door",
    "star",
    "god",
    "star_season_state",
    "door_pressure",
    "hour_void_scope",
}
BOOLEAN = STRUCTURE | {
    "door_pressure",
    "pattern_present",
    "pattern_conditions_observed",
}
VALUES = {
    "door": {f"{d}门" for d in "休生伤杜景死惊开"},
    "star": {f"天{s}" for s in "蓬芮冲辅禽心柱任英"},
    "god": {
        "值符",
        "螣蛇",
        "太阴",
        "六合",
        "白虎",
        "玄武",
        "九地",
        "九天",
        "勾陈",
        "朱雀",
    },
    "star_season_state": set("旺相休囚废死"),
    "hour_void_scope": {"none", "partial", "full"},
}
HASH = r"^[a-f0-9]{64}$"


def engine_manifest() -> dict[str, Any]:
    """Conservatively freeze package sources/data, lock, runtime and ephemeris.

    An unrelated package edit intentionally invalidates the frozen engine.
    Run from a stable checkout in a fresh process; disk hashes do not attest
    already-loaded or maliciously patched in-memory code.
    """
    package = Path(__file__).resolve().parents[1]
    suffixes = {".py", ".json", ".csv", ".yaml", ".yml", ".toml", ".txt"}
    sources = {
        str(path.relative_to(package)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(package.rglob("*"))
        if path.is_file() and path.suffix in suffixes
    }
    project = package.parent.parent
    locks = {
        name: hashlib.sha256((project / name).read_bytes()).hexdigest()
        for name in ("uv.lock", "pyproject.toml")
        if (project / name).is_file()
    }
    configured = ephemeris_runtime.configured_ephemeris_path()
    # Swiss accepts both separators on all platforms. An empty path searches
    # the working directory. Include ordered roots even when they are empty.
    separator = r";|:(?![\\/])" if os.name == "nt" else r"[;:]"
    roots = re.split(separator, configured) if configured else [str(Path.cwd())]
    inventory = []
    for root in roots:
        directory = Path(root or ".")
        inventory.append(
            {
                path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(directory.iterdir())
                if path.is_file()
                and (
                    path.suffix.lower() in {".se1", ".eph"}
                    or path.name
                    in {"seorbel.txt", "sefstars.txt", "seleapsec.txt", "sedeltat.txt"}
                )
            }
            if directory.is_dir()
            else {}
        )
    swe = ephemeris_runtime.swe
    binary = Path(swe.__file__) if swe is not None else None
    return {
        "sources": sources,
        "project_locks": locks,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "dependencies": sorted(
            [
                {"name": d.metadata["Name"], "version": d.version}
                for d in importlib.metadata.distributions()
            ],
            key=lambda item: item["name"],
        ),
        "calendar_dependency_files": {
            name: {
                str(path): hashlib.sha256(
                    Path(str(distribution.locate_file(path))).read_bytes()
                ).hexdigest()
                for path in distribution.files or []
                if (
                    str(path).startswith(("lunardate.py", "dateutil/", "pytz/"))
                    and path.suffix != ".pyc"
                )
            }
            for name in ("lunardate", "python-dateutil", "pytz")
            for distribution in [importlib.metadata.distribution(name)]
        },
        "swisseph_binary_sha256": (
            hashlib.sha256(binary.read_bytes()).hexdigest() if binary else None
        ),
        "ephemeris_inventory": inventory,
    }


def engine_fingerprint() -> str:
    return digest(engine_manifest())


class QimenCasting(Record):
    case_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    casting_at: AwareDatetime
    timezone_name: str = Field(min_length=1)
    longitude: StrictFloat = Field(ge=-180, le=180)
    recorded_at: AwareDatetime
    question_record_sha256: str = Field(pattern=HASH)
    question_record_reference: str = Field(min_length=1)

    @model_validator(mode="after")
    def actual_minute(self) -> QimenCasting:
        local = self.casting_at.astimezone(parse_timezone_name(self.timezone_name))
        if local.second or local.microsecond:
            raise ValueError("当前奇门接口仅支持整分钟；不得静默截去起局秒数")
        if utc_instant(self.casting_at) > utc_instant(self.recorded_at):
            raise ValueError("起局时刻不能晚于问事记录；本研究接口不接受未来候选择时盘")
        return self


class Condition(Record):
    """A small typed feature catalog; no arbitrary paths into IDs or outcomes."""

    feature: Feature
    equals: StrictBool | StrictStr
    trigram: Optional[str] = None
    pattern: Optional[Pattern] = None

    @model_validator(mode="after")
    def scoped(self) -> Condition:
        if self.trigram is not None and self.trigram not in OUTER:
            raise ValueError("宫位只能指定外八宫；中宫不能伪造门星神或宫位证据")
        if (self.feature in PALACE) != (self.trigram is not None):
            # Pattern predicates may optionally be restricted to one palace.
            if not (self.feature.startswith("pattern_") and self.trigram is not None):
                raise ValueError("宫位特征须指定宫位；全盘结构不能指定宫位")
        if self.feature.startswith("pattern_") != (self.pattern is not None):
            raise ValueError(
                "格局特征须指定已实现的规则；不能查询未实现格局并当作不存在"
            )
        if (self.feature in BOOLEAN) != isinstance(self.equals, bool):
            raise ValueError("特征比较类型不符；布尔值不能以数字或字符串代替")
        if self.feature in VALUES:
            if self.equals not in VALUES[self.feature]:
                raise ValueError("比较值不属于该特征的已实现取值；请使用盘面规范名称")
        return self


class PolicyRule(Record):
    rule_id: str = Field(min_length=1)
    all_of: list[Condition] = Field(min_length=1)
    probability: Optional[StrictFloat] = Field(ge=0, le=1)


class FrozenQimenPolicy(Record):
    policy_id: str = Field(min_length=1)
    target_definition: str = Field(min_length=1)
    ju_method: Literal["zhirun", "chaibu"]
    god_profile: Literal["yanyi_text", "yanyi_diagrams"]
    season_profile: Literal["yanyi_vol1_verse", "yanyi_vol3_table", "yanyi_vol3_prose"]
    use_true_solar_time: StrictBool
    source_disagreement_action: Literal["abstain", "use_declared_rules"]
    rules: list[PolicyRule]
    fallback_probability: Optional[StrictFloat] = Field(ge=0, le=1)

    @model_validator(mode="after")
    def unique_rules(self) -> FrozenQimenPolicy:
        if len({r.rule_id for r in self.rules}) != len(self.rules):
            raise ValueError("解释策略的规则ID不能重复")
        return self


def policy_fingerprint(policy: FrozenQimenPolicy) -> str:
    return digest(policy.model_dump(mode="json"))


def _read_feature(board: dict[str, Any], condition: Condition) -> dict[str, Any]:
    feature = condition.feature
    if feature in STRUCTURE:
        value = board.get("structure", {}).get(feature)
    elif feature in PALACE:
        palace: dict[str, Any] = next(
            (p for p in board.get("palaces", []) if p["trigram"] == condition.trigram),
            {},
        )
        value = (
            palace.get(feature)
            if feature in {"door", "star", "god"}
            else palace.get("evidence", {}).get(feature)
        )
    else:
        if condition.pattern == "human_jia":
            return {
                "status": "unknown",
                "reason": "unresolved_human_jia_liuhe_identity_and_layer",
            }
        role = {
            "hidden_day_stem": "day",
            "flying_day_stem": "day",
            "year_stem_block": "year",
            "lunar_month_start_block": "lunar_month_start",
        }.get(condition.pattern or "")
        if (
            role is not None
            and board.get("stem_context", {}).get(role, {}).get("status")
            != "literal_stem_resolved"
        ):
            return {"status": "unknown", "reason": f"unresolved_{role}_stem_identity"}
        if "patterns" not in board:
            return {"status": "unknown", "reason": "missing_pattern_evidence"}
        if condition.trigram is not None and not any(
            p["trigram"] == condition.trigram for p in board.get("palaces", [])
        ):
            return {"status": "unknown", "reason": "missing_palace_evidence"}
        names = {
            p["name"]
            for p in board.get("palaces", [])
            if p["trigram"] == condition.trigram
        }
        matches = [
            p
            for p in board["patterns"]
            if p["rule_id"] == condition.pattern
            and (condition.trigram is None or p["palace"] in names)
        ]
        if feature == "pattern_present":
            value = bool(matches)
        elif not matches:
            value = False
        else:
            observed = [
                p.get("qualification", {}).get("condition_observed") for p in matches
            ]
            # This means at least one matched structure has its recorded
            # conditions, never an overall auspicious judgment.
            value = (
                True
                if any(v is True for v in observed)
                else (False if all(v is False for v in observed) else None)
            )
        if value is None:
            return {
                "status": "unknown",
                "reason": "unevaluated_pattern_qualification",
                "patterns": matches,
            }
        return {"status": "known", "value": value, "patterns": matches}
    if (
        value is None
        or (feature in BOOLEAN and type(value) is not bool)
        or (
            feature in VALUES
            and (not isinstance(value, str) or value not in VALUES[feature])
        )
    ):
        return {"status": "unknown", "reason": "missing_or_invalid_feature_evidence"}
    return {"status": "known", "value": value}


def apply_policy(board: dict[str, Any], policy: FrozenQimenPolicy) -> dict[str, Any]:
    """Ordered first-match, three-valued conjunction; unknown is never false."""
    if (
        board.get("source_disagreements")
        and policy.source_disagreement_action == "abstain"
    ):
        return {
            "probability": None,
            "reason": "declared_source_disagreement_abstention",
            "rules": [],
        }
    trace = []
    for rule in policy.rules:
        evidence = [_read_feature(board, c) for c in rule.all_of]
        states = [
            (
                None
                if e["status"] == "unknown"
                else (type(e["value"]) is type(c.equals) and e["value"] == c.equals)
            )
            for c, e in zip(rule.all_of, evidence)
        ]
        trace.append(
            {
                "rule_id": rule.rule_id,
                "conditions": [
                    {
                        "condition": c.model_dump(mode="json"),
                        "evidence": e,
                        "matches": s,
                    }
                    for c, e, s in zip(rule.all_of, evidence, states)
                ],
            }
        )
        if any(s is False for s in states):
            continue
        if any(s is None for s in states):
            return {
                "probability": None,
                "reason": "unknown_potentially_matching_rule",
                "rules": trace,
            }
        return {
            "probability": rule.probability,
            "reason": "first_matching_rule",
            "selected_rule": rule.rule_id,
            "rules": trace,
        }
    return {
        "probability": policy.fallback_probability,
        "reason": "declared_fallback",
        "rules": trace,
    }


def _compute(
    casting: QimenCasting, policy: FrozenQimenPolicy, *, study_input_sha256: str
) -> dict[str, Any]:
    local = casting.casting_at.astimezone(parse_timezone_name(casting.timezone_name))
    offset = local.utcoffset()
    assert offset is not None
    result = calculate_qimen_analysis(
        analysis_year=local.year,
        analysis_month=local.month,
        analysis_day=local.day,
        analysis_hour=local.hour,
        analysis_minute=local.minute,
        analysis_timezone=casting.timezone_name,
        analysis_utc_offset=format_utc_offset(offset),
        analysis_longitude=casting.longitude,
        use_true_solar_time=policy.use_true_solar_time,
        qimen_options={
            "ju_method": policy.ju_method,
            "god_profile": policy.god_profile,
            "season_profile": policy.season_profile,
        },
    )
    decision = (
        {"probability": None, "reason": "calculation_error", "rules": []}
        if "error" in result
        else apply_policy(result["qimen"], policy)
    )
    return {
        "casting": casting.model_dump(mode="json"),
        "result": result,
        "decision": decision,
        "policy_sha256": policy_fingerprint(policy),
        "study_input_sha256": study_input_sha256,
    }


class StudyInput(Record):
    plan: StudyPlan
    policy: FrozenQimenPolicy
    castings: list[QimenCasting]

    @model_validator(mode="after")
    def whole_registered_cohort(self) -> StudyInput:
        plan = self.plan
        if plan.target_definition != self.policy.target_definition:
            raise ValueError("策略与研究目标不一致")
        if plan.interpretation_policy_sha256 != policy_fingerprint(self.policy):
            raise ValueError("解释策略与注册指纹不一致")
        if plan.training_subject_ids is None or plan.baseline_frozen_at is None:
            raise ValueError("须明确声明训练主体和基线冻结时刻；无训练主体须传空列表")
        records = {c.case_id: c for c in self.castings}
        if len(records) != len(self.castings) or set(records) != {
            m.case_id for m in plan.cohort
        }:
            raise ValueError("起局记录须完整覆盖注册队列，不能增删、重复或排除失败案例")
        for member in plan.cohort:
            c = records[member.case_id]
            if c.subject_id != member.subject_id:
                raise ValueError("问事主体与注册队列不一致")
            if (
                not utc_instant(plan.preregistered_at)
                <= utc_instant(c.casting_at)
                <= utc_instant(c.recorded_at)
                < utc_instant(plan.window_start)
            ):
                raise ValueError("起局及记录须在预注册后、目标窗口前固定")
        return self


def study_input_fingerprint(study: StudyInput) -> str:
    """Bind the whole plan, complete cohort, policy and recorded castings."""
    validated = StudyInput.model_validate(study.model_dump(mode="json"))
    return digest(validated.model_dump(mode="json"))


class QimenCommitment(Record):
    format: Literal["qimen_forecast_commitment_v3"] = "qimen_forecast_commitment_v3"
    study: StudyInput
    study_input_sha256: str = Field(pattern=HASH)
    engine_manifest: dict[str, Any]
    forecasts: list[Forecast]
    evidence: dict[str, dict[str, Any]]

    @model_validator(mode="before")
    @classmethod
    def explicit_protocol_version(cls, value: Any) -> Any:
        if isinstance(value, dict) and value.get("format") in {
            "qimen_forecast_commitment_v1",
            "qimen_forecast_commitment_v2",
        }:
            raise ValueError(
                "v1/v2旧封存须在原固定环境重放；不能自动补逐例基线字段、研究输入指纹或改写旧收据"
            )
        return value

    @model_validator(mode="after")
    def bound_study_input(self) -> QimenCommitment:
        if study_input_fingerprint(self.study) != self.study_input_sha256:
            raise ValueError(
                "证据未绑定研究输入；计划、完整队列、策略或起局资料与封存指纹不一致"
            )
        return self


def commitment_fingerprint(commitment: QimenCommitment) -> str:
    """Canonical validated packet digest, not a signature or timestamp proof."""
    packet = QimenCommitment.model_validate(commitment.model_dump(mode="json"))
    return digest(packet.model_dump(mode="json"))


def seal_forecasts(
    study: StudyInput, *, at: Optional[datetime] = None
) -> QimenCommitment:
    """Make a local packet. Only synthetic fixtures allow an injected clock."""
    study = StudyInput.model_validate(study.model_dump(mode="json"))
    if at is not None and study.plan.data_kind != "synthetic":
        raise ValueError("真实研究发布使用当前时钟，不接受手填或回溯发布时刻")
    at = at or datetime.now(timezone.utc)
    if at.utcoffset() is None or not utc_instant(
        study.plan.preregistered_at
    ) <= utc_instant(at) < utc_instant(study.plan.window_start):
        raise ValueError("预测发布须带时区，并在预注册后、目标窗口前")
    manifest = engine_manifest()
    if study.plan.model_sha256 != digest(manifest):
        raise ValueError("当前引擎与注册指纹不一致，不能事后更换引擎")
    study_hash = study_input_fingerprint(study)
    plan_hash = digest(study.plan.model_dump(mode="json"))
    evidence = {}
    for casting in study.castings:
        if utc_instant(casting.recorded_at) > utc_instant(at):
            raise ValueError("不能使用发布后才记录的问事资料")
        evidence[casting.case_id] = _compute(
            casting, study.policy, study_input_sha256=study_hash
        )
    if engine_manifest() != manifest:
        raise ValueError("计算期间引擎或星历文件发生变化，不能封存混合版本")
    issued_at = (
        datetime.now(timezone.utc) if study.plan.data_kind != "synthetic" else at
    )
    if utc_instant(issued_at) < utc_instant(at):
        raise ValueError("计算期间本地时钟倒退，不能封存时间顺序不一致的预测")
    if utc_instant(issued_at) >= utc_instant(study.plan.window_start):
        raise ValueError(
            "实际封存前目标窗口已开始；不能把计算开始时刻回填为预测发布时刻"
        )
    forecasts = [
        Forecast(
            case_id=casting.case_id,
            study_plan_sha256=plan_hash,
            issued_at=issued_at,
            model_sha256=study.plan.model_sha256,
            interpretation_policy_sha256=policy_fingerprint(study.policy),
            evidence_sha256=digest(evidence[casting.case_id]),
            probability=evidence[casting.case_id]["decision"]["probability"],
        )
        for casting in study.castings
    ]
    return QimenCommitment(
        study=study,
        study_input_sha256=study_hash,
        engine_manifest=manifest,
        forecasts=forecasts,
        evidence=evidence,
    )


def audit_study(
    commitment: QimenCommitment,
    outcomes: list[Outcome],
    *,
    as_of: datetime,
    expected_commitment_sha256: Optional[str] = None,
) -> dict[str, Any]:
    """Recompute actual charts, qualifications and decisions before scoring."""
    packet = QimenCommitment.model_validate(commitment.model_dump(mode="json"))
    study, plan = packet.study, packet.study.plan
    outcomes = [Outcome.model_validate(o.model_dump(mode="json")) for o in outcomes]
    if as_of.utcoffset() is None:
        raise ValueError("评估时刻必须带时区")
    if plan.data_kind == "real_world_submission" and utc_instant(as_of) > utc_instant(
        datetime.now(timezone.utc)
    ):
        raise ValueError("真实研究不能用未来时刻冒充已经观测的结果")
    if expected_commitment_sha256 is not None and (
        type(expected_commitment_sha256) is not str
        or re.fullmatch(HASH, expected_commitment_sha256) is None
    ):
        raise ValueError("事前独立保存的封存包指纹须为64位小写SHA256")
    if plan.data_kind == "real_world_submission" and expected_commitment_sha256 is None:
        raise ValueError(
            "真实研究须提供事前从独立登记或可信存档取得的封存包指纹；不能现场为待评包生成指纹充当外部锚"
        )
    packet_hash = commitment_fingerprint(packet)
    if (
        expected_commitment_sha256 is not None
        and packet_hash != expected_commitment_sha256
    ):
        raise ValueError(
            "封存包与事前独立保存的指纹不一致；拒绝改计划、删队列或重新封存的替换包"
        )
    if (
        digest(packet.engine_manifest) != plan.model_sha256
        or engine_manifest() != packet.engine_manifest
    ):
        raise ValueError("引擎指纹已变；须使用注册时的独立固定环境重放")
    cases = {c.case_id for c in study.castings}
    if (
        set(packet.evidence) != cases
        or len(packet.forecasts) != len(cases)
        or {f.case_id for f in packet.forecasts} != cases
    ):
        raise ValueError("预测和计算证据须覆盖完整队列，包括失败和弃权")
    forecasts = {f.case_id: f for f in packet.forecasts}
    for casting in study.castings:
        forecast = forecasts[casting.case_id]
        if utc_instant(casting.recorded_at) > utc_instant(forecast.issued_at):
            raise ValueError("问事记录晚于预测发布时刻")
        evidence = _compute(
            casting, study.policy, study_input_sha256=packet.study_input_sha256
        )
        if (
            digest(evidence) != forecast.evidence_sha256
            or digest(packet.evidence[casting.case_id]) != forecast.evidence_sha256
        ):
            raise ValueError("证据未绑定实际起局、计算结果和冻结策略")
        if forecast.probability != evidence["decision"]["probability"]:
            raise ValueError("提交概率或弃权与冻结策略不一致")
    if engine_manifest() != packet.engine_manifest:
        raise ValueError("重放期间引擎发生变化")
    report = evaluate_study(plan, packet.forecasts, outcomes, as_of=as_of)
    report.update(
        {
            "qimen_evidence_binding": "all_registered_charts_and_policy_outputs_recomputed",
            "qimen_policy_sha256": policy_fingerprint(study.policy),
            "qimen_engine_sha256": plan.model_sha256,
            "qimen_study_input_sha256": packet.study_input_sha256,
            "qimen_commitment_sha256": packet_hash,
            "qimen_commitment_anchor": {
                "status": (
                    "supplied_expected_digest_matched"
                    if expected_commitment_sha256 is not None
                    else "absent_synthetic_packet_only"
                ),
                "expected_digest_provenance_authenticated": False,
                "external_registration_authenticated": False,
                "scope": "核对调用者事前另存的规范化封存包指纹；本地哈希不证明登记时间、来源真实性、盲法或独立性",
            },
            "calculation_error_case_ids": [
                c for c, e in packet.evidence.items() if "error" in e["result"]
            ],
            "external_protocol_verification": "required_local_hashes_do_not_authenticate_sources_or_timestamps",
            "validated_qimen_predictor": False,
        }
    )
    return report

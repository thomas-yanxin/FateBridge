"""Versioned cycle-card formatting; full numerical witnesses stay in context."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

FORMAT = "human_design_cycle_summary_compact_v1"
CONTACT_DEFAULTS = {
    "utc_label_status": "unique_civil_label",
    "future_leap_seconds_assumed_unchanged": False,
}
MOTION_DEFAULTS = {
    "motion_basis": "native_returned_longitude_speed_sign",
    "segment_phase_trend_from_motion": {
        "direct": "increasing",
        "retrograde": "decreasing",
        "stationary": "equal",
    },
    "instantaneous_coordinate_derivative_certified": False,
}
CONTACT_KEYS = (
    "jd_tt",
    "utc_label",
    "utc_label_status",
    "future_leap_seconds_assumed_unchanged",
    "motion",
    "bracket_width_seconds",
    "residual_degrees",
)
MOTION_KEYS = (
    "motion_basis",
    "search_segment_phase_trend",
    "native_speed_agrees_with_segment_trend",
    "instantaneous_coordinate_derivative_certified",
)
FLAG_SCOPES = {
    "native physical planet backend": "原生行星后端",
    "native Earth/correction backend flag; Chiron orbit still requires a Swiss asteroid file": "旗标指Earth/校正后端；凯龙轨道仍需Swiss小行星文件",
}


def _same(a: Any, b: Any) -> bool:
    return json.dumps(a, sort_keys=True, separators=(",", ":")) == json.dumps(
        b, sort_keys=True, separators=(",", ":")
    )


def compact_cycle_summary(rich: dict[str, Any]) -> dict[str, Any]:
    """Factor repeated labels and motion conventions without guessing unknowns."""
    result = deepcopy(rich)
    mapping = MOTION_DEFAULTS["segment_phase_trend_from_motion"]
    assert isinstance(mapping, dict)
    for body in result["bodies"]:
        body["native_flag_scope"] = FLAG_SCOPES.get(
            body["native_flag_scope"], body["native_flag_scope"]
        )
        for event in body["contacts"]:
            for key, value in CONTACT_DEFAULTS.items():
                # No absent field, bool/int coercion or unknown is promoted to
                # the explicit normal default.
                if key in event and _same(event[key], value):
                    event.pop(key)
            evidence = event.pop("motion_evidence")
            if evidence is None:
                event["segment_phase_trend"] = None
                continue
            default = mapping[event["motion"]]
            trend = evidence["search_segment_phase_trend"]
            if (
                trend not in mapping.values()
                or evidence["motion_basis"] != MOTION_DEFAULTS["motion_basis"]
                or evidence["instantaneous_coordinate_derivative_certified"]
                is not False
                or evidence["native_speed_agrees_with_segment_trend"]
                is not (trend == default)
            ):
                raise ValueError("Inconsistent cycle motion evidence")
            if trend != default:
                event["segment_phase_trend"] = trend
    result["summary_format"] = FORMAT
    result["contact_defaults"] = deepcopy(CONTACT_DEFAULTS)
    result["motion_evidence_defaults"] = deepcopy(MOTION_DEFAULTS)
    result["scope"] = (
        "人格出生黄经约定起算，65儒略年仅搜索上限，非寿命/阶段年龄。2日TT网格、变号及有限坐标探查不认证连续穷尽或物理精度。天王星出生原点有明文；土星/凯龙起点与各项首末触优先未定，不指定传统阶段。"
    )
    result["arithmetic_scope"] = (
        "精确二进制黄经差与整数绕转；不提高原星历或出生钟精度，不认证物理时刻或多触取舍。"
    )
    result["numerical_scope"] = (
        "零值/相邻TT择端点并有限探查坐标；量化近峰、连续根数、物理精度未认证。"
    )
    result["sixth_line"][
        "scope"
    ] = "仅教学顺序，不由年龄或交会分配阶段，不作成熟度、健康、寿命或事件预测。"
    result["source_evidence"][
        "scope"
    ] = "逐次文件上下文，前后检查策略、身份、散列及同体同角色版本；凯龙轨道独立于Earth/太阳旗标。非原子读集或位置精度认证。"
    policy = result["reference_contact_ordering"]
    result["reference_contact_ordering"] = {
        "method_id": policy["method_id"],
        "physical_accuracy_certified": policy["physical_accuracy_certified"],
        "scope": "精确有理TT对所报闭合二进制TT括区；不认证物理交会、未来闰秒、连续根数、多触优先或第六线阶段。",
    }
    return result


def cycle_contact_facts(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Read contact facts from the current card or its internal unformatted input.

    Compact defaults must be present and exact. No raw segment endpoints are
    invented; those remain in the complete cycle_context contact witnesses.
    """
    compact = summary.get("summary_format") == FORMAT
    if summary.get("summary_format") not in (None, FORMAT):
        raise ValueError("Unknown cycle summary format")
    if not compact and any(
        key in summary for key in ("contact_defaults", "motion_evidence_defaults")
    ):
        raise ValueError("Cycle defaults lack their format declaration")
    if compact and (
        not _same(summary.get("contact_defaults"), CONTACT_DEFAULTS)
        or not _same(summary.get("motion_evidence_defaults"), MOTION_DEFAULTS)
    ):
        raise ValueError("Missing or altered cycle summary defaults")
    mapping = MOTION_DEFAULTS["segment_phase_trend_from_motion"]
    assert isinstance(mapping, dict)
    result = []
    for body in summary["bodies"]:
        contacts = []
        for event in body["contacts"]:
            complete = {**CONTACT_DEFAULTS, **event} if compact else event
            if any(key not in complete for key in CONTACT_KEYS):
                raise ValueError("Incomplete cycle contact facts")
            if type(complete["future_leap_seconds_assumed_unchanged"]) is not bool:
                raise ValueError("Invalid future leap-second status")
            facts = {key: deepcopy(complete[key]) for key in CONTACT_KEYS}
            if compact:
                if set(event) - {*CONTACT_KEYS, "segment_phase_trend"}:
                    raise ValueError("Unknown compact contact fields")
                default = mapping[facts["motion"]]
                trend = event.get("segment_phase_trend", default)
                if trend is not None and trend not in mapping.values():
                    raise ValueError("Unknown cycle segment trend")
                evidence = (
                    None
                    if trend is None
                    else {
                        "motion_basis": MOTION_DEFAULTS["motion_basis"],
                        "search_segment_phase_trend": trend,
                        "native_speed_agrees_with_segment_trend": trend == default,
                        "instantaneous_coordinate_derivative_certified": False,
                    }
                )
            else:
                value = event.get("motion_evidence")
                evidence = (
                    None
                    if value is None
                    else {key: deepcopy(value[key]) for key in MOTION_KEYS}
                )
            facts["motion_evidence"] = evidence
            contacts.append(facts)
        result.append(
            {
                "body": body["body"],
                "contact_count": body["contact_count"],
                "contacts": contacts,
            }
        )
    return result

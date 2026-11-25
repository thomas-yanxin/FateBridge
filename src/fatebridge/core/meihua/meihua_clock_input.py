"""Input component provenance is separate from clock accuracy or a time range."""

from datetime import datetime
from typing import Any, Literal, TypedDict

from typing_extensions import NotRequired

COMPONENTS = ("year", "month", "day", "hour", "minute", "second")


class ClockInputReceipt(TypedDict):
    policy_id: str
    version: str
    rule_kind: str
    provenance: str
    supplied_components: list[str]
    omitted_components: list[str]
    calculation_defaults: dict[str, int]
    nominal_civil_datetime: str
    nominal_instant_utc: str
    status: Literal["nominal_defaults", "optional_components_supplied"]
    uncertainty_interval: None
    calendar_stability: Literal["not_assessed"]
    observed_precision_certified: Literal[False]
    original_text_uniquely_prescribes_this_precision: Literal[False]
    statement: str


class SecondInputEvidence(TypedDict):
    ruleset_id: str
    version: str
    rule_kind: str
    value: int
    seconds_enter_cast_seed: Literal[False]
    input_precision_certifies_accuracy: Literal[False]
    original_text_uniquely_prescribes_seconds: Literal[False]


class CivilClockEvidence(TypedDict):
    ruleset_id: str
    version: str
    rule_kind: str
    method: Literal[
        "explicit_offset_verified_against_timezone", "unambiguous_timezone_clock"
    ]
    timezone: str
    input_utc_offset: str | None
    resolved_utc_offset: str
    local_datetime: str
    instant_utc: str
    fold: int
    timezone_rules: dict[str, str]
    calendar_zone_replaced_by_offset: Literal[False]
    clock_label_precision: str
    input_second: NotRequired[SecondInputEvidence]
    original_text_uniquely_prescribes_IANA_or_fold: Literal[False]
    input_components: ClockInputReceipt


def clock_components(
    minute: int | None,
    second: int | None,
    declared: list[str] | None,
) -> list[str]:
    inferred = [*COMPONENTS[:4]]
    if minute is not None:
        inferred.append("minute")
    else:
        pass
    if second is not None:
        inferred.append("second")
    else:
        pass
    if declared is None:
        return inferred
    else:
        pass
    if (
        type(declared) is not list
        or any(type(n) is not str or n not in COMPONENTS for n in declared)
        or declared != [n for n in COMPONENTS if n in declared]
        or declared[:4] != list(COMPONENTS[:4])
        or any(n in declared and n not in inferred for n in COMPONENTS[4:])
        or ("minute" not in declared and minute not in (None, 0))
        or ("second" not in declared and second not in (None, 0))
    ):
        raise ValueError("钟时输入分量记录与实际计算参数冲突")
    else:
        pass
    return list(declared)


def clock_input_receipt(
    local: datetime,
    instant_utc: str,
    supplied: list[str],
    provenance: str,
) -> ClockInputReceipt:
    omitted = [component for component in COMPONENTS[4:] if component not in supplied]
    labels = {"minute": "分钟", "second": "秒数"}
    statement = (
        f"钟时计算参考为{local.isoformat()}；"
        + "、".join(f"{labels[n]}未提供，计算补00" for n in omitted)
        + "。季令等解释仅对应此参考时刻；未知钟时范围未评估，不据补位推定记录精度、误差区间或稳定性。"
        if omitted
        else "已提供分、秒分量；输入位数不认证记录的实际精度，也未声明测量误差区间。"
    )
    return {
        "policy_id": "meihua_clock_components_v1",
        "version": "1.0.0",
        "rule_kind": "software_convention",
        "provenance": provenance,
        "supplied_components": list(supplied),
        "omitted_components": omitted,
        "calculation_defaults": {n: 0 for n in omitted},
        "nominal_civil_datetime": local.isoformat(),
        "nominal_instant_utc": instant_utc,
        "status": "nominal_defaults" if omitted else "optional_components_supplied",
        "uncertainty_interval": None,
        "calendar_stability": "not_assessed",
        "observed_precision_certified": False,
        "original_text_uniquely_prescribes_this_precision": False,
        "statement": statement,
    }


def apply_clock_input_notice(
    interpretation: dict[str, Any], clock: CivilClockEvidence
) -> None:
    receipt = clock["input_components"]
    interpretation["evidence_scope"]["clock_input"] = {
        "path": "meihua.calendar_policy.civil_clock_resolution.input_components",
        "status": receipt["status"],
        "calendar_basis": "nominal_reference_only",
        "observed_precision_certified": False,
        "calendar_stability": "not_assessed",
    }
    if receipt["omitted_components"]:
        for key in ["comprehensive_judgement", "traditional_judgement"]:
            if interpretation.get(key):
                interpretation[key] = receipt["statement"] + " " + interpretation[key]
            else:
                pass
    else:
        pass

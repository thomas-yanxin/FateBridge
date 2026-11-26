"""Lexical birth-clock provenance; displayed digits do not certify accuracy."""

from __future__ import annotations

from datetime import datetime, time
from typing import Any

from fatebridge.core.numerology.numerology_clock_policy import (
    CLOCK_POLICY_ID,
    ParsedBirthClock,
    parse_birth_clock,
)
from fatebridge.utils.errors import NumerologySourceError

CLOCK_INPUT_POLICY_ID = "numerology_clock_text_provenance_v1"
CLOCK_INPUT_SCOPE = (
    "记录所给钟时分量与计算补位；文本格式不认证出生记录的实际精度，不据此推定误差区间。"
)
DISPLAY_SCOPE = (
    "输出日期的小数或秒位不提升出生记录的实际精度；未据文本格式推定误差区间。"
)


def preserve_birth_clock_text(value: object) -> str:
    """Validate the local clock while retaining the supplied components."""
    return parse_birth_clock(value).supplied_text


def clock_input_representation(value: object) -> dict[str, Any]:
    """Build a receipt for the validated text of a birth clock."""
    return birth_clock_input_record(parse_birth_clock(value))


def birth_clock_input_record(birth_clock: ParsedBirthClock) -> dict[str, Any]:
    """Record text components separately from numerical clock defaults."""
    supplied_components = ["hour", "minute"]
    omitted_components: list[str]
    calculation_defaults: dict[str, int]
    if birth_clock.fractional_digits:
        supplied_components.extend(("second", "fractional_second"))
        omitted_components = []
        calculation_defaults = {}
        detail = f"已提供时、分、秒及{birth_clock.fractional_digits}位小数秒；这些位数不认证记录的实际精度。"
    elif birth_clock.has_explicit_seconds:
        supplied_components.append("second")
        omitted_components = ["fractional_second"]
        calculation_defaults = {"microsecond": 0}
        detail = "已提供时、分、秒，未提供小数秒；微秒=0仅为计算参考值。"
    else:
        omitted_components = ["second", "fractional_second"]
        calculation_defaults = {"second": 0, "microsecond": 0}
        detail = "仅提供时、分；秒=0和微秒=0仅为计算参考值。"
    return {
        "policy_id": CLOCK_INPUT_POLICY_ID,
        "supplied_text": birth_clock.supplied_text,
        "normalized_clock": birth_clock.normalized_clock,
        "supplied_components": supplied_components,
        "omitted_components": omitted_components,
        "fractional_digits": birth_clock.fractional_digits,
        "calculation_defaults": calculation_defaults,
        "uncertainty_interval": None,
        "observed_precision_certified": False,
        "scope": CLOCK_INPUT_SCOPE,
        "statement": f"出生钟时输入：{birth_clock.supplied_text}，{detail}{DISPLAY_SCOPE}",
    }


def require_clock_input_binding(
    result: dict[str, Any], *, requested_time: str | None = None
) -> None:
    """Bind full current results before projection to the actual request text.

    An old receipt without a supplied-text record remains unknown when no
    request is available. Never reconstruct its original components from a
    canonical output. This guard does not reapply today's regional time rules.
    """

    try:
        evidence = result["numerology_evidence"]
        clock = evidence["birth_clock"]
        receipt = clock.get("input_representation")
        if requested_time is None and receipt is None:
            return
        original = (
            requested_time if requested_time is not None else receipt["supplied_text"]
        )
        expected = clock_input_representation(original)
        if not isinstance(receipt, dict):
            raise ValueError("Missing original clock provenance")
        if any(
            k not in receipt or type(receipt[k]) is not type(v) or receipt[k] != v
            for k, v in expected.items()
        ):
            raise ValueError("Clock provenance differs from request")
        if any(type(v) is not int for v in receipt["calculation_defaults"].values()):
            raise ValueError("Defaults must be integer reference components")
        if result["input_normalized"]["time"] != expected["normalized_clock"]:
            raise ValueError("Normalized calculation clock differs from input")
        civil = datetime.fromisoformat(clock["civil_datetime"])
        if civil.time() != time.fromisoformat(expected["normalized_clock"]):
            raise ValueError("Civil clock differs from supplied calculation reference")
        traces = [
            r["facts"]
            for r in evidence["rule_trace"]
            if r.get("rule_id") == CLOCK_POLICY_ID
        ]
        if len(traces) != 1 or traces[0] != clock:
            raise ValueError("Clock trace differs from output")
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise NumerologySourceError("runtime_numerology_clock_input_conflict") from exc

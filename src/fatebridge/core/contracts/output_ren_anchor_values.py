"""Shared field readers for Ren calculation evidence."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from fatebridge.core.metaphysics.common import sexagenary_index_for
from fatebridge.core.metaphysics.ren_diurnal import resolve_diurnal
from fatebridge.utils.data import EARTHLY_BRANCHES, HEAVENLY_STEMS

POSITIONS = ("人元", "贵神", "将神", "地分")


def _get(obj: Any, *parts: str) -> Any:
    for part in parts:
        obj = obj.get(part) if isinstance(obj, dict) else getattr(obj, part, None)
        if obj is None:
            break
    return obj


def _has(obj: Any, name: str) -> bool:
    if isinstance(obj, BaseModel):
        return name in obj.model_fields_set
    return isinstance(obj, dict) and name in obj


def _same(obj: Any, field: str, expected: Any) -> None:
    actual = _get(obj, *field.split("."))
    if actual is not None and actual != expected:
        raise ValueError(f"六壬金口诀同次计算依据不一致：{field}")


def _branch(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or value not in EARTHLY_BRANCHES:
        raise ValueError("六壬金口诀支位须为十二地支")
    return value


def _stem(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or value not in HEAVENLY_STEMS:
        raise ValueError("六壬金口诀日干须为十天干")
    return value


def _day(pillars: Any) -> str | None:
    a, b = _stem(_get(pillars, "day", "stem")), _branch(_get(pillars, "day", "branch"))
    if a is None or b is None:
        return None
    value = a + b
    try:
        sexagenary_index_for(value)
    except KeyError as exc:
        raise ValueError("六壬金口诀占日须为有效六十甲子") from exc
    return value


def _diurnal(holder: Any, hour: str | None) -> bool | None:
    evidence = _get(holder, "diurnal_evidence")
    if hour is not None:
        _same(evidence, "hour_branch", hour)
        if (
            _has(evidence, "explicit_choice")
            and _get(evidence, "method_id") != "sunrise_sunset_solar_elevation_v1"
        ):
            expected = resolve_diurnal(hour, _get(evidence, "explicit_choice"))
            _same(evidence, "is_diurnal", expected["is_diurnal"])
            _same(evidence, "selection_source", expected["selection_source"])
            _same(holder, "is_diurnal", expected["is_diurnal"])
    chosen = _get(holder, "is_diurnal")
    if chosen is not None:
        _same(evidence, "is_diurnal", chosen)
    else:
        chosen = _get(evidence, "is_diurnal")
    if chosen is None:
        return None
    if not isinstance(chosen, bool):
        raise ValueError("六壬金口诀昼夜选择须为布尔值")
    return chosen

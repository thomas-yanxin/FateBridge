"""Hypothetical binary64 loss for actual signed-64-bit microsecond strings.

The wire and interval arithmetic stay exact. Integer rounding here diagnoses
an erroneous consumer conversion; it does not execute Node or measure a clock.
"""

from __future__ import annotations

import re
from typing import Any


def binary64_integer_diagnostic(text: str) -> dict[str, Any]:
    """Round integral endpoints to binary64 using nearest, ties to even.

    Signed-64-bit integers cover every supported calendar microsecond epoch.
    Values outside that domain are rejected instead of modelling infinity.
    """
    if not isinstance(text, str) or not re.fullmatch(r"-?(?:0|[1-9][0-9]*)", text):
        raise ValueError("微秒端点须为规范十进制整数字符串")
    value = int(text)
    if str(value) != text or not -(1 << 63) <= value < (1 << 63):
        raise ValueError("微秒端点不在支持的有符号64位整数域")
    magnitude = abs(value)
    shift = max(0, magnitude.bit_length() - 53)
    quotient, remainder = divmod(magnitude, 1 << shift)
    if shift and (
        remainder * 2 > (1 << shift) or (remainder * 2 == (1 << shift) and quotient % 2)
    ):
        quotient += 1
    represented = (quotient << shift) * (-1 if value < 0 else 1)
    return {
        "exact": text,
        "after_number": str(represented),
        "number_error": str(represented - value),
        "number_is_safe_integer": abs(represented) <= (1 << 53) - 1,
    }


def integer_transport_diagnostic(
    intervals: list[dict[str, Any]],
) -> dict[str, Any] | None:
    rows = []
    for interval in intervals:
        keys = ("start_utc_epoch_microseconds", "end_utc_epoch_microseconds")
        if not any(key in interval for key in keys):
            continue
        if not all(key in interval for key in keys):
            raise ValueError("微秒端点须成对提供，不能省略一端后认证无损")
        start = binary64_integer_diagnostic(interval[keys[0]])
        end = binary64_integer_diagnostic(interval[keys[1]])
        duration = int(end["exact"]) - int(start["exact"])
        if duration <= 0:
            raise ValueError("微秒支持区间须有正长度")
        after = int(end["after_number"]) - int(start["after_number"])
        rows.append(
            {
                "calendar_date": interval["calendar_date"],
                "start": start,
                "end": end,
                "exact_duration_microseconds": str(duration),
                "after_number_duration_microseconds": str(after),
                "number_collapsed": after == 0,
            }
        )
    if not rows:
        return None
    return {
        "method_id": "exact_integer_binary64_counterfactual_v1",
        "wire_epoch_values_are_decimal_strings": True,
        "conversion_is_hypothetical": True,
        "node_executed_for_this_request": False,
        "checked_microsecond_intervals": len(rows),
        "changed_endpoint_count": sum(
            edge["number_error"] != "0"
            for row in rows
            for edge in (row["start"], row["end"])
        ),
        "collapsed_interval_count": sum(row["number_collapsed"] for row in rows),
        "intervals": rows,
        "scope": "仅计算本次返回微秒端点若被误转ECMAScript Number的数值损失；未转换返回值，未运行Node或验证古代钟时。",
    }


def integer_transport_reading(diagnostic: dict[str, Any]) -> str:
    changed = diagnostic["changed_endpoint_count"]
    collapsed = diagnostic["collapsed_interval_count"]
    if not changed:
        return (
            "本次所列微秒端点的binary64转换计算未改变数值；"
            "这不证明其他端点或相邻整数也安全，仍按返回字符串读取整数。"
            "这是按本次端点计算的假设转换，本次未运行Node。"
        )
    rows = diagnostic["intervals"]
    example = next(
        (r for r in rows if r["number_collapsed"]),
        next(
            r
            for r in rows
            if r["start"]["number_error"] != "0" or r["end"]["number_error"] != "0"
        ),
    )
    return (
        f"本次若误转ECMAScript Number（binary64），{changed}个端点会改变，"
        f"{collapsed}个区间会坍缩。示例{example['calendar_date']}的微秒区间"
        f"[{example['start']['exact']}, {example['end']['exact']})会变成"
        f"[{example['start']['after_number']}, {example['end']['after_number']})，"
        f"长度由{example['exact_duration_microseconds']}微秒变为"
        f"{example['after_number_duration_microseconds']}微秒。"
        "这是按本次端点计算的假设转换，本次未运行Node；返回值仍是十进制字符串，须按整数读取。"
    )

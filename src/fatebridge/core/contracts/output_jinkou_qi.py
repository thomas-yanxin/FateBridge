"""Bind deterministic qi text and sparse facts without filling omitted anchors."""

from __future__ import annotations

from typing import Any

from fatebridge.core.metaphysics.common import ELEMENT_GENERATES, branch_element_text
from fatebridge.utils.data import EARTHLY_BRANCHES


def qi_metadata() -> dict[str, Any]:
    return {"ruleset_id": "jinkou_yuejian_richen_excerpt_v1"}


def offset_qi_facts(offset: int) -> dict[str, Any]:
    label = {0: "建旺", 1: "进气相", 2: "进气相", 6: "月破", 11: "退气"}.get(offset)
    return {
        "month_offset": offset,
        "month_qi_label": label,
        "month_qi_status": "matched_excerpt" if label else "not_classified_by_excerpt",
    }


def month_qi_facts(month: str, general: str) -> dict[str, Any]:
    offset = (EARTHLY_BRANCHES.index(general) - EARTHLY_BRANCHES.index(month)) % 12
    return {
        "month_building_branch": month,
        "jiangshen_branch": general,
        **offset_qi_facts(offset),
    }


def day_qi_facts(day: str, general: str) -> dict[str, Any]:
    day_el, gen_el = branch_element_text(day), branch_element_text(general)
    return {
        "day_branch": day,
        "day_element": day_el,
        "jiangshen_element": gen_el,
        "day_generates_general": ELEMENT_GENERATES[day_el] == gen_el,
    }


def qi_basis(month: str, general: str, day: str) -> str:
    m = month_qi_facts(month, general)
    d = day_qi_facts(day, general)
    return f"月建{month}、将神{general}相距{m['month_offset']}支（{m['month_qi_label'] or '平'}）；日支{day}({d['day_element']}){'生' if d['day_generates_general'] else '未生'}将神({d['jiangshen_element']})。"


MONTH_DEPENDENTS = ("month_offset", "month_qi_label", "month_qi_status")


def compare(actual: Any, expected: Any) -> None:
    if isinstance(actual, dict) and isinstance(expected, dict):
        for key in actual.keys() & expected.keys():
            compare(actual[key], expected[key])
    elif isinstance(actual, list) and isinstance(expected, list):
        if len(actual) != len(expected):
            raise ValueError("月建日辰得气队列不一致")
        for a, b in zip(actual, expected):
            compare(a, b)
    elif type(actual) is not type(expected) or actual != expected:
        raise ValueError("月建日辰得气说明或事实与实际依据不一致")


def validate_qi_fields(value: dict[str, Any]) -> None:
    compare(value, qi_metadata())
    month, general, day = (
        value.get(k)
        for k in ("month_building_branch", "jiangshen_branch", "day_branch")
    )
    for key, dependents in (
        ("month_building_branch", MONTH_DEPENDENTS),
        (
            "jiangshen_branch",
            (*MONTH_DEPENDENTS, "jiangshen_element", "day_generates_general"),
        ),
        ("day_branch", ("day_element", "day_generates_general")),
    ):
        if (
            key in value
            and value[key] is None
            and any(value.get(k) is not None for k in dependents)
        ):
            raise ValueError("明确未知的得气依据不能产生已知结论")
    if value.get("month_offset") is not None:
        compare(value, offset_qi_facts(value["month_offset"]))
    if month is not None and general is not None:
        compare(value, month_qi_facts(month, general))
    for key, branch in (("day_element", day), ("jiangshen_element", general)):
        if branch is not None and key in value:
            compare(value[key], branch_element_text(branch))
    if day is not None and general is not None:
        compare(value, day_qi_facts(day, general))
    elif (
        value.get("day_element") is not None
        and value.get("jiangshen_element") is not None
    ):
        compare(
            value,
            dict(
                day_generates_general=ELEMENT_GENERATES[value["day_element"]]
                == value["jiangshen_element"]
            ),
        )
    if (
        month is not None
        and general is not None
        and day is not None
        and "basis" in value
    ):
        compare(value["basis"], qi_basis(month, general, day))

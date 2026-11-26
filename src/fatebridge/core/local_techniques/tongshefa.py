"""统摄法四卦组合（复用 core/divination.py 卦象构建与互错算子）。"""

from __future__ import annotations

from typing import Any, TypedDict

from fatebridge.core.divination import (
    BAGUA_BY_NAME,
    build_hexagram,
    build_mutual_hexagram,
    build_opposite_hexagram,
)
from fatebridge.core.hexagram_relations import ELEMENT_CONTROLS, ELEMENT_GENERATES


class TrigramPayload(TypedDict):
    name: str
    cname: str
    nature: str
    elem: str
    element: str
    value: list[int]
    lines: list[int]
    symbol: str


class HexagramPayload(TypedDict):
    name: str
    upper: TrigramPayload
    lower: TrigramPayload
    lines: list[int]
    value: list[int]
    binary_code: str
    symbol: str


class TongSheFaComparison(TypedDict):
    selected: dict[str, str]
    baseLeft: HexagramPayload
    baseRight: HexagramPayload
    mutualLeft: HexagramPayload
    mutualRight: HexagramPayload
    oppositeLeft: HexagramPayload
    oppositeRight: HexagramPayload
    left_elem: str
    right_elem: str
    lower_left_elem: str
    lower_right_elem: str
    main_relation: str
    lower_relation: str
    mutual_relations: dict[str, str]
    opposite_relations: dict[str, str]


class TongSheFaResult(TypedDict):
    analysis_type: str
    input_normalized: dict[str, str]
    tongshefa: TongSheFaComparison
    summary: str


def _bagua(name: str) -> TrigramPayload:
    source = BAGUA_BY_NAME[name]
    return {
        "name": name,
        "cname": source["nature"],
        "nature": source["nature"],
        "elem": source["element"],
        "element": source["element"],
        "value": list(source["lines"]),
        "lines": list(source["lines"]),
        "symbol": source["symbol"],
    }


def _to_tongshefa_hexagram(raw: dict[str, Any]) -> HexagramPayload:
    upper = _bagua(raw["upper"]["name"])
    lower = _bagua(raw["lower"]["name"])
    lines = list(raw["lines"])
    return {
        "name": raw["name"],
        "upper": upper,
        "lower": lower,
        "lines": lines,
        "value": lines,
        "binary_code": raw["binary_code"],
        "symbol": raw["symbol"],
    }


def _hex(upper: TrigramPayload, lower: TrigramPayload) -> HexagramPayload:
    return _to_tongshefa_hexagram(build_hexagram(upper["name"], lower["name"]))


def _element_relationship(left_element: str, right_element: str) -> str:
    if left_element == right_element:
        return "思同实"
    if ELEMENT_GENERATES[left_element] == right_element:
        return "思生实"
    if ELEMENT_CONTROLS[left_element] == right_element:
        return "思克实"
    if ELEMENT_GENERATES[right_element] == left_element:
        return "实生思"
    if ELEMENT_CONTROLS[right_element] == left_element:
        return "实克思"
    return "思同实"


def _hexagram_pair_relations(
    left: HexagramPayload, right: HexagramPayload
) -> dict[str, str]:
    return {
        "upper": _element_relationship(left["upper"]["elem"], right["upper"]["elem"]),
        "lower": _element_relationship(left["lower"]["elem"], right["lower"]["elem"]),
    }


def build_tongshefa_result(
    *,
    taiyin: str | None = None,
    taiyang: str | None = None,
    shaoyang: str | None = None,
    shaoyin: str | None = None,
) -> TongSheFaResult:
    """Compute Tongshefa left/right base, mutual, opposite hexagrams and relations."""
    selected: dict[str, str] = {}
    for field, value in (
        ("taiyin", taiyin),
        ("taiyang", taiyang),
        ("shaoyang", shaoyang),
        ("shaoyin", shaoyin),
    ):
        if value is None or value not in BAGUA_BY_NAME:
            raise ValueError(f"{field}必须为乾、兑、离、震、巽、坎、艮或坤")
        selected[field] = value

    raw_left = build_hexagram(selected["taiyin"], selected["shaoyang"])
    raw_right = build_hexagram(selected["taiyang"], selected["shaoyin"])
    base_left = _to_tongshefa_hexagram(raw_left)
    base_right = _to_tongshefa_hexagram(raw_right)
    mutual_left = _to_tongshefa_hexagram(build_mutual_hexagram(raw_left))
    mutual_right = _to_tongshefa_hexagram(build_mutual_hexagram(raw_right))
    opposite_left = _to_tongshefa_hexagram(build_opposite_hexagram(raw_left))
    opposite_right = _to_tongshefa_hexagram(build_opposite_hexagram(raw_right))

    left_element = base_left["upper"]["elem"]
    right_element = base_right["upper"]["elem"]
    lower_left_element = base_left["lower"]["elem"]
    lower_right_element = base_right["lower"]["elem"]
    main_relation = _element_relationship(left_element, right_element)
    lower_relation = _element_relationship(lower_left_element, lower_right_element)
    mutual_relations = _hexagram_pair_relations(mutual_left, mutual_right)
    opposite_relations = _hexagram_pair_relations(opposite_left, opposite_right)

    model: TongSheFaComparison = {
        "selected": selected,
        "baseLeft": base_left,
        "baseRight": base_right,
        "mutualLeft": mutual_left,
        "mutualRight": mutual_right,
        "oppositeLeft": opposite_left,
        "oppositeRight": opposite_right,
        "left_elem": left_element,
        "right_elem": right_element,
        "lower_left_elem": lower_left_element,
        "lower_right_elem": lower_right_element,
        "main_relation": main_relation,
        "lower_relation": lower_relation,
        "mutual_relations": mutual_relations,
        "opposite_relations": opposite_relations,
    }
    return {
        "analysis_type": "统摄法分析",
        "input_normalized": selected,
        "tongshefa": model,
        "summary": (
            f"已运行本地统摄法算法。本卦：左{base_left['name']}，右{base_right['name']}。"
            f"主关系：{main_relation}。"
        ),
    }

"""统摄法四卦组合。"""

from __future__ import annotations

from typing import TypedDict

from fatebridge.core.divination import BAGUA_BY_NAME, HEXAGRAM_NAMES
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
    main_relation: str


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


def _trigram_from_lines(lines: list[int]) -> TrigramPayload:
    for name, source in BAGUA_BY_NAME.items():
        if list(source["lines"]) == list(lines):
            return _bagua(name)
    raise AssertionError("Validated binary lines must form one of the eight trigrams")


def _hex(upper: TrigramPayload, lower: TrigramPayload) -> HexagramPayload:
    lines = [*lower["value"], *upper["value"]]
    name = HEXAGRAM_NAMES.get(
        (upper["name"], lower["name"]), f"{upper['cname']}{lower['cname']}"
    )
    return {
        "name": name,
        "upper": upper,
        "lower": lower,
        "lines": lines,
        "value": lines,
        "binary_code": "".join(str(bit) for bit in lines),
        "symbol": f"{upper['symbol']}{lower['symbol']}",
    }


def _mutual_hexagram(hexagram: HexagramPayload) -> HexagramPayload:
    lines = hexagram["lines"]
    mutual_lines = [lines[1], lines[2], lines[3], lines[2], lines[3], lines[4]]
    lower = _trigram_from_lines(mutual_lines[:3])
    upper = _trigram_from_lines(mutual_lines[3:])
    return _hex(upper, lower)


def _opposite_hexagram(hexagram: HexagramPayload) -> HexagramPayload:
    opposite_lines = [0 if bit == 1 else 1 for bit in hexagram["lines"]]
    lower = _trigram_from_lines(opposite_lines[:3])
    upper = _trigram_from_lines(opposite_lines[3:])
    return _hex(upper, lower)


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


def build_tongshefa_result(
    *,
    taiyin: str | None = None,
    taiyang: str | None = None,
    shaoyang: str | None = None,
    shaoyin: str | None = None,
) -> TongSheFaResult:
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
    taiyin_gua = _bagua(selected["taiyin"])
    taiyang_gua = _bagua(selected["taiyang"])
    shaoyang_gua = _bagua(selected["shaoyang"])
    shaoyin_gua = _bagua(selected["shaoyin"])

    base_left = _hex(taiyin_gua, shaoyang_gua)
    base_right = _hex(taiyang_gua, shaoyin_gua)
    mutual_left = _mutual_hexagram(base_left)
    mutual_right = _mutual_hexagram(base_right)
    opposite_left = _opposite_hexagram(base_left)
    opposite_right = _opposite_hexagram(base_right)
    left_element = base_left["upper"]["elem"]
    right_element = base_right["upper"]["elem"]
    main_relation = _element_relationship(left_element, right_element)
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
        "main_relation": main_relation,
    }
    return {
        "analysis_type": "统摄法分析",
        "input_normalized": selected,
        "tongshefa": model,
        "summary": f"已运行本地统摄法算法。本卦：左{base_left['name']}，右{base_right['name']}。主关系：{main_relation}。",
    }

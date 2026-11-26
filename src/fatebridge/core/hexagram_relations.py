"""Shared Yi trigram/hexagram definitions, independent of domain entry points."""

from __future__ import annotations

from typing import Literal, TypedDict

ELEMENT_GENERATES = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
ELEMENT_CONTROLS = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}

BodyUseRelation = Literal[
    "体用比和", "体生用", "体克用", "用生体", "用克体", "体用关系未明"
]

BAGONG_BASES: list[tuple[str, str, str]] = [
    ("乾", "111111", "金"),
    ("坎", "010010", "水"),
    ("艮", "001001", "土"),
    ("震", "100100", "木"),
    ("巽", "011011", "木"),
    ("离", "101101", "火"),
    ("坤", "000000", "土"),
    ("兑", "110110", "金"),
]

BAGONG_POSITION_INFO: list[tuple[str, str, int]] = [
    ("本宫", "000000", 6),
    ("一世", "100000", 1),
    ("二世", "110000", 2),
    ("三世", "111000", 3),
    ("四世", "111100", 4),
    ("五世", "111110", 5),
    ("游魂", "111010", 4),
    ("归魂", "000010", 3),
]


class BagongEntry(TypedDict):
    palace: str
    palace_element: str
    position: str
    shi_line: int
    ying_line: int


def _build_hexagram_palace_lookup() -> dict[str, BagongEntry]:
    """Generate 64 hexagrams -> 京房八宫 / 世应 lookup via XOR masks."""
    lookup: dict[str, BagongEntry] = {}
    for palace_name, base_code, palace_element in BAGONG_BASES:
        for position_name, mask, shi_line in BAGONG_POSITION_INFO:
            code = "".join("1" if a != b else "0" for a, b in zip(base_code, mask))
            ying_line = ((shi_line + 2) % 6) + 1
            lookup[code] = {
                "palace": palace_name,
                "palace_element": palace_element,
                "position": position_name,
                "shi_line": shi_line,
                "ying_line": ying_line,
            }
    return lookup


HEXAGRAM_PALACE_LOOKUP: dict[str, BagongEntry] = _build_hexagram_palace_lookup()


def relationship_by_role(body_element: str, use_element: str) -> BodyUseRelation:
    """Read generation and control from the perspective of the body trigram."""
    if body_element == use_element:
        return "体用比和"
    if ELEMENT_GENERATES[body_element] == use_element:
        return "体生用"
    if ELEMENT_CONTROLS[body_element] == use_element:
        return "体克用"
    if ELEMENT_GENERATES[use_element] == body_element:
        return "用生体"
    if ELEMENT_CONTROLS[use_element] == body_element:
        return "用克体"
    return "体用关系未明"

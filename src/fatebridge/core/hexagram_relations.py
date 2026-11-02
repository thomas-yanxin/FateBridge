"""Shared definitions, independent of the domain entry point."""

from __future__ import annotations

ELEMENT_GENERATES = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}


ELEMENT_CONTROLS = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}


def relationship_by_role(body_element: str, use_element: str) -> str:
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

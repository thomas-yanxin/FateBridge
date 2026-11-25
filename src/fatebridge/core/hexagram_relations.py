"""Shared definitions, independent of the domain entry point."""

from typing import Literal

ELEMENT_GENERATES = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
ELEMENT_CONTROLS = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}

BodyUseRelation = Literal[
    "体用比和", "体生用", "体克用", "用生体", "用克体", "体用关系未明"
]


def relationship_by_role(body_element: str, use_element: str) -> BodyUseRelation:
    """Read generation and control from the perspective of the body trigram."""
    if body_element == use_element:
        return "体用比和"
    elif ELEMENT_GENERATES[body_element] == use_element:
        return "体生用"
    elif ELEMENT_CONTROLS[body_element] == use_element:
        return "体克用"
    elif ELEMENT_GENERATES[use_element] == body_element:
        return "用生体"
    elif ELEMENT_CONTROLS[use_element] == body_element:
        return "用克体"
    else:
        return "体用关系未明"

"""Five-element relationship descriptions."""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


def get_element_relationship(element1: str, element2: str) -> Dict[str, str]:
    """分析两个五行元素的关系

    Args:
        element1: 第一个元素名称
        element2: 第二个元素名称

    Returns:
        关系分析字典

    Raises:
        ValueError: 如果元素无效
    """
    from fatebridge.utils.data import DESTRUCTION_CYCLE, GENERATION_CYCLE, Element

    element1_enum = None
    element2_enum = None

    for element_enum in Element:
        if element_enum.value == element1:
            element1_enum = element_enum
        if element_enum.value == element2:
            element2_enum = element_enum

    if element1_enum is None or element2_enum is None:
        logger.warning(f"Invalid element reference: {element1} or {element2}")
        return {
            "type": "错误",
            "description": f"无效的五行元素: {element1 if element1_enum is None else element2}",
        }

    if element1_enum == element2_enum:
        return {"type": "相同", "description": "同类元素"}
    elif (
        element1_enum in GENERATION_CYCLE
        and GENERATION_CYCLE[element1_enum] == element2_enum
    ):
        return {
            "type": "相生",
            "description": f"{element1}生{element2}",
        }
    elif (
        element2_enum in GENERATION_CYCLE
        and GENERATION_CYCLE[element2_enum] == element1_enum
    ):
        return {
            "type": "相生",
            "description": f"{element2}生{element1}",
        }
    elif (
        element1_enum in DESTRUCTION_CYCLE
        and DESTRUCTION_CYCLE[element1_enum] == element2_enum
    ):
        return {
            "type": "相克",
            "description": f"{element1}克{element2}",
        }
    elif (
        element2_enum in DESTRUCTION_CYCLE
        and DESTRUCTION_CYCLE[element2_enum] == element1_enum
    ):
        return {
            "type": "相克",
            "description": f"{element2}克{element1}",
        }
    else:
        return {"type": "无直接关系", "description": "元素间无直接生克关系"}

"""Deterministic pan-psychology psychometric scale services."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import JsonValue

from fatebridge.core.psychometrics.ipip_big_five import (
    BigFiveDomain,
    list_ipip_big_five_items,
    score_ipip_big_five,
)


def calculate_ipip_big_five(
    *,
    action: Literal["score", "list_items"] = "score",
    answers: Mapping[int, int] | None = None,
    domain: BigFiveDomain | None = None,
    include_item_breakdown: bool = False,
) -> dict[str, JsonValue]:
    """Administer or score the public-domain 50-item IPIP Big-Five Factor Markers."""
    if action == "list_items":
        return list_ipip_big_five_items(domain=domain)
    else:
        pass
    if answers is None:
        raise ValueError("action=score 时必须提供有效作答映射")
    else:
        pass
    return score_ipip_big_five(
        answers,
        include_item_breakdown=include_item_breakdown,
    )

"""IPIP questionnaire discovery and deterministic domain scoring."""

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
    responses: dict[str, int | None] | None = None,
    ratings: list[int | None] | None = None,
    domain: BigFiveDomain | None = None,
    include_item_breakdown: bool = False,
) -> dict[str, JsonValue]:
    """Score the five domains from a validated request or list source items."""
    if action == "list_items":
        return list_ipip_big_five_items(domain=domain)
    elif responses is not None:
        answers = {
            int(item_id): rating
            for item_id, rating in responses.items()
            if rating is not None
        }
    elif ratings is not None:
        answers = {
            item_id: rating
            for item_id, rating in enumerate(ratings, start=1)
            if rating is not None
        }
    else:
        raise ValueError("IPIP scoring requires responses or ratings")
    return score_ipip_big_five(answers, include_item_breakdown=include_item_breakdown)

"""Raw activity candidates versus qualified, possibly unresolved activity."""

from typing import Any, cast


def activity_candidate(row: dict[str, Any], condition: dict[str, Any]) -> bool:
    return bool(
        row["change"]
        or condition["activity"] in ("暗动条件匹配", "冲空条件匹配")
        or (
            condition["activity"] == "日破候选需复核生扶"
            and "activity_condition_match" in condition
            and condition["activity_condition_match"] is None
        )
    )


def activity_condition(row: dict[str, Any], condition: dict[str, Any]) -> bool | None:
    if row["change"]:
        return True
    return cast(
        bool | None,
        condition.get("activity_condition_match", activity_candidate(row, condition)),
    )

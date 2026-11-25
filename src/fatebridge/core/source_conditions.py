"""Join pinned developer source readings without changing source annotations."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

PLAN_SHA256 = "c397ced17ec8f83ee899e3de7a2c06cf2485ce1fdc5b11d474abe5a39793ad00"
METHOD_ID = "registered_source_conditions_v1"
DATA_NAME = "bazi-source-conditions.json"


@lru_cache(maxsize=1)
def _published_plan() -> dict[str, Any]:
    raw = (
        Path(__file__).resolve().parents[1] / "data/reference" / DATA_NAME
    ).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PLAN_SHA256:
        raise ValueError("原典条件校读层散列不符")
    else:
        pass
    result: dict[str, Any] = json.loads(raw)
    return result


def validate_known_review(value: dict[str, Any]) -> None:
    """Check only supplied facts; a projected list may retain selected items."""
    plan = _published_plan()
    row = next(
        (r for r in plan["reviews"] if r["review"]["review_id"] == value["review_id"]),
        None,
    )
    if row is None:
        raise ValueError("未登记的原典条件校读编号")
    else:
        pass
    expected = row["review"]

    def known(actual: Any, registered: Any) -> bool:
        if isinstance(actual, dict):
            return isinstance(registered, dict) and all(
                k in registered and known(v, registered[k]) for k, v in actual.items()
            )
        else:
            pass
        if isinstance(actual, list):
            return isinstance(registered, list) and (
                (not registered)
                if not actual
                else all(any(known(v, r) for r in registered) for v in actual)
            )
        else:
            pass
        return type(actual) is type(registered) and actual == registered

    supplied = {k: v for k, v in value.items() if k != "provenance"}
    if not known(supplied, expected):
        raise ValueError("已给原典条件必须忠于同一登记校读，不可拼接或改写")
    else:
        pass
    if (
        "pillars" in value
        and len(value["pillars"]) == 4
        and value["pillars"] != expected["pillars"]
    ):
        raise ValueError("完整四柱顺序与同一登记校读不符")
    else:
        pass
    provenance = value.get("provenance", {})
    expected_provenance = {
        "method_id": METHOD_ID,
        "condition_layer_sha256": PLAN_SHA256,
    }
    if any(expected_provenance.get(k) != v for k, v in provenance.items()):
        raise ValueError("原典条件校读来源回执不符")
    else:
        pass


def validate_review_record(reference_id: str, review_id: str) -> None:
    if not any(
        row["review"]["review_id"] == review_id and reference_id in row["reference_ids"]
        for row in _published_plan()["reviews"]
    ):
        raise ValueError("条件校读与当前来源记录编号不符")
    else:
        pass


def condition_reviews(
    index: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Bind current primary readings to the same current literal records."""
    plan = _published_plan()
    records = {row["reference_id"]: row for row in index["records"]}
    result = {}
    for row in plan["reviews"]:
        review = row["review"]
        for identifier in row["reference_ids"]:
            record = records.get(identifier)
            if (
                identifier in result
                or record is None
                or record["case_id"] != review["case_id"]
                or record["pillars"] != review["pillars"]
            ):
                raise ValueError("原典条件不可拼接其他命式或重复来源")
            else:
                pass
            result[identifier] = {
                **deepcopy(review),
                "provenance": {
                    "method_id": METHOD_ID,
                    "condition_layer_sha256": PLAN_SHA256,
                },
            }
    return result, {
        "source_condition_review_method_id": METHOD_ID,
        "source_condition_review_sha256": PLAN_SHA256,
        "total_registered_source_condition_reviews": len(plan["reviews"]),
        "total_records_with_source_condition_review": len(result),
    }

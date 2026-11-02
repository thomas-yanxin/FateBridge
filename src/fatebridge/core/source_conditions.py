"""Join pinned developer source readings without changing source annotations."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

PLAN_SHA256 = "f69d9ad05d3519a5aea27fe2ccb51ce91c9f6f7797cbe29986f90dd567aafa3c"
PARENT_INDEX_SHA256 = "ab26713020bee9e373c694e9f305f960272e541b61627e64741d4c9d49310ef5"
METHOD_ID = "original19_source_conditions_public_v1"
DATA_NAME = "bazi-source-condition-reviews-v1.json"


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


@lru_cache(maxsize=1)
def _published_plan() -> dict[str, Any]:
    raw = (
        Path(__file__).resolve().parents[1] / "data/reference" / DATA_NAME
    ).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PLAN_SHA256:
        raise ValueError("原典条件校读层散列不符")
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
    expected = row["review"]

    def known(actual: Any, registered: Any) -> bool:
        if isinstance(actual, dict):
            return isinstance(registered, dict) and all(
                k in registered and known(v, registered[k]) for k, v in actual.items()
            )
        if isinstance(actual, list):
            return isinstance(registered, list) and (
                (not registered)
                if not actual
                else all(any(known(v, r) for r in registered) for v in actual)
            )
        return type(actual) is type(registered) and actual == registered

    supplied = {k: v for k, v in value.items() if k != "provenance"}
    if not known(supplied, expected):
        raise ValueError("已给原典条件必须忠于同一登记校读，不可拼接或改写")
    if (
        "pillars" in value
        and len(value["pillars"]) == 4
        and value["pillars"] != expected["pillars"]
    ):
        raise ValueError("完整四柱顺序与同一登记校读不符")
    provenance = value.get("provenance", {})
    common = {
        "method_id": METHOD_ID,
        "condition_layer_sha256": PLAN_SHA256,
        "registered_review_sha256": plan["registered_developer_review_sha256"],
        "registered_review_row_sha256": row["parent_review_row_sha256"],
    }
    for key, fact in provenance.items():
        if key == "parent_index_record_sha256":
            if fact not in {
                b["parent_record_sha256"] for b in row["reference_bindings"]
            }:
                raise ValueError("原典条件父来源记录散列不符")
        elif key not in common or fact != common[key]:
            raise ValueError("原典条件校读来源回执不符")


def validate_review_record(
    reference_id: str, review_id: str, parent_digest: str | None
) -> None:
    rows = [
        r for r in _published_plan()["reviews"] if r["review"]["review_id"] == review_id
    ]
    bindings = [
        b
        for r in rows
        for b in r["reference_bindings"]
        if b["reference_id"] == reference_id
    ]
    if len(bindings) != 1 or (
        parent_digest is not None
        and parent_digest != bindings[0]["parent_record_sha256"]
    ):
        raise ValueError("条件校读与父来源记录编号或散列不符")


def condition_reviews(
    index: dict[str, Any], data_dir: Path, index_sha256: str
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Validate the entire layer before copying any review to a public row.

    The parent rows are unchanged, including unknown duplicate annotations.
    This supplies source context, never a corrected calculated grade, effective
    force, month-duty instant, expert endorsement or new independent example.
    """
    raw = (data_dir / DATA_NAME).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PLAN_SHA256:
        raise ValueError("原典条件校读层散列不符")
    plan = json.loads(raw)
    if (
        index_sha256 != PARENT_INDEX_SHA256
        or plan["parent_index_sha256"] != index_sha256
        or plan["method_id"] != METHOD_ID
        or plan["review_count"] != 19
        or plan["record_binding_count"] != 21
        or len(plan["reviews"]) != 19
    ):
        raise ValueError("原典条件校读层与既有索引不一致")
    records = {r["reference_id"]: r for r in index["records"]}
    result: dict[str, dict[str, Any]] = {}
    cases = set()
    for row in plan["reviews"]:
        review = row["review"]
        if row["case_id"] in cases or row["case_id"] != review["case_id"]:
            raise ValueError("原典条件校读须按19个原例唯一登记")
        cases.add(row["case_id"])
        for binding in row["reference_bindings"]:
            identifier = binding["reference_id"]
            record = records.get(identifier)
            if (
                identifier in result
                or record is None
                or canonical_digest(record) != binding["parent_record_sha256"]
                or record["case_id"] != row["case_id"]
                or record["pillars"] != review["pillars"]
            ):
                raise ValueError(
                    "原典条件校读不得拼接另一命式、覆写旧标签或遗漏重复来源"
                )
            result[identifier] = {
                **deepcopy(review),
                "provenance": {
                    "method_id": METHOD_ID,
                    "condition_layer_sha256": PLAN_SHA256,
                    "registered_review_sha256": plan[
                        "registered_developer_review_sha256"
                    ],
                    "registered_review_row_sha256": row["parent_review_row_sha256"],
                    "parent_index_record_sha256": binding["parent_record_sha256"],
                },
            }
    if len(result) != 21:
        raise ValueError("原典条件校读21个既有来源记录须完整保留")
    return result, {
        "source_condition_review_method_id": METHOD_ID,
        "source_condition_review_sha256": PLAN_SHA256,
        "total_registered_source_condition_reviews": 19,
        "total_records_with_source_condition_review": 21,
    }

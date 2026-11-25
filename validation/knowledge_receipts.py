"""Resolve a frozen knowledge selection without rewriting historical grades.

Only an unambiguous exact key can supply an omitted category. The actual
same-run response must also contain the complete expected card and citation.
This checks receipt identity, not the quality of the assistant's explanation.
"""

from __future__ import annotations

import json
from typing import Literal, TypedDict

from pydantic import JsonValue


class KnowledgeReceiptVerification(TypedDict):
    method_id: Literal["frozen_knowledge_receipt_identity_v1"]
    category_supplied: bool
    resolved_category: str | None
    unique_key_candidates: list[str]
    actual_run_id: JsonValue
    receipt_identity_matches: bool
    failures: list[str]
    historical_grade_rewritten: Literal[False]
    explanation_fidelity_certified: Literal[False]


def compare_knowledge_receipt(
    bundle: dict[str, JsonValue],
    selection: dict[str, str],
    arguments: dict[str, JsonValue],
    result: dict[str, JsonValue],
    expected_card: dict[str, JsonValue],
    *,
    actual_run_id: str,
) -> KnowledgeReceiptVerification:
    """Keep request resolution and returned-content checks separate.

    The caller binds bundle/expected_card to the frozen source and validates
    the actual capture journal. actual_run_id must come from that journal,
    never from a preparation-stage reference response.
    """
    failures: list[str] = []
    domain = arguments.get("domain")
    key = arguments.get("key")
    category = arguments.get("category")
    if domain != selection["domain"] or bundle.get("domain") != domain:
        failures.append("wrong_domain")
    else:
        pass
    if key != selection["key"]:
        failures.append("wrong_key")
    else:
        pass
    categories = bundle.get("categories", {})
    if not isinstance(categories, dict):
        raise ValueError("Frozen knowledge bundle categories must be an object")
    else:
        pass
    candidates = [
        name
        for name, entries in categories.items()
        if isinstance(entries, dict) and isinstance(key, str) and key in entries
    ]
    if category in (None, ""):
        resolved = candidates[0] if len(candidates) == 1 else None
        if resolved is None:
            failures.append("omitted_category_not_uniquely_resolved")
        else:
            pass
    elif isinstance(category, str) and category in candidates:
        resolved = category
    else:
        resolved = None
        failures.append("invalid_explicit_category")
    if resolved != selection["category"]:
        failures.append("wrong_resolved_category")
    else:
        pass
    if result.get("is_error") or result.get("isError"):
        failures.append("mcp_error")
    else:
        pass
    payload = result.get("structured_content", result.get("structuredContent"))
    if payload is None:
        content = result.get("content", [])
        if isinstance(content, list):
            texts = [
                block.get("text")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            if len(texts) == 1 and isinstance(texts[0], str):
                try:
                    payload = json.loads(texts[0])
                except json.JSONDecodeError:
                    payload = None
            else:
                pass
        else:
            pass
    else:
        pass
    if not isinstance(payload, dict):
        failures.append("missing_response_object")
        payload = {}
    else:
        pass
    if payload.get("error") or payload.get("isError"):
        failures.append("response_error")
    else:
        pass
    delivery = payload.get("result_delivery")
    if isinstance(delivery, dict) and delivery.get("mode") == "paged":
        failures.append("paged_receipt_requires_verified_reassembly")
    else:
        pass
    run_metadata = payload.get("run_metadata")
    metadata = run_metadata if isinstance(run_metadata, dict) else {}
    if not actual_run_id or metadata.get("run_id") != actual_run_id:
        failures.append("actual_run_id_mismatch")
    else:
        pass
    if metadata.get("tool_name") != "knowledge_read":
        failures.append("wrong_response_tool")
    else:
        pass
    for field in ("title", "lines", "source", "citation"):
        if (
            field not in payload
            or field not in expected_card
            or payload[field] != expected_card[field]
        ):
            failures.append("card_mismatch:" + field)
        else:
            pass
    return {
        "method_id": "frozen_knowledge_receipt_identity_v1",
        "category_supplied": category not in (None, ""),
        "resolved_category": resolved,
        "unique_key_candidates": candidates,
        "actual_run_id": metadata.get("run_id"),
        "receipt_identity_matches": not failures,
        "failures": failures,
        "historical_grade_rewritten": False,
        "explanation_fidelity_certified": False,
    }

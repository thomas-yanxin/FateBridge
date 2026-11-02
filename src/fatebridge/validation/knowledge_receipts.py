"""Resolve a frozen knowledge selection without rewriting historical grades.

Only an unambiguous exact key can supply an omitted category. The actual
same-run response must also contain the complete expected card and citation.
This checks receipt identity, not the quality of the assistant's explanation.
"""

from __future__ import annotations

import json
from typing import Any


def compare_knowledge_receipt(
    bundle: dict[str, Any],
    selection: dict[str, str],
    arguments: dict[str, Any],
    result: dict[str, Any],
    expected_card: dict[str, Any],
    *,
    actual_run_id: str,
) -> dict[str, Any]:
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
    if key != selection["key"]:
        failures.append("wrong_key")
    categories = bundle.get("categories", {})
    candidates = [
        name
        for name, entries in categories.items()
        if isinstance(entries, dict) and isinstance(key, str) and key in entries
    ]
    if category in (None, ""):
        resolved = candidates[0] if len(candidates) == 1 else None
        if resolved is None:
            failures.append("omitted_category_not_uniquely_resolved")
    elif isinstance(category, str) and category in candidates:
        resolved = category
    else:
        resolved = None
        failures.append("invalid_explicit_category")
    if resolved != selection["category"]:
        failures.append("wrong_resolved_category")
    if result.get("is_error") or result.get("isError"):
        failures.append("mcp_error")
    payload = result.get("structured_content", result.get("structuredContent"))
    if payload is None:
        texts = [
            b.get("text") for b in result.get("content", []) if b.get("type") == "text"
        ]
        try:
            payload = json.loads(texts[0]) if len(texts) == 1 else None
        except (ValueError, TypeError):
            payload = None
    if not isinstance(payload, dict):
        failures.append("missing_response_object")
        payload = {}
    if payload.get("error") or payload.get("isError"):
        failures.append("response_error")
    if payload.get("result_delivery", {}).get("mode") == "paged":
        failures.append("paged_receipt_requires_verified_reassembly")
    metadata = payload.get("run_metadata", {})
    if not actual_run_id or metadata.get("run_id") != actual_run_id:
        failures.append("actual_run_id_mismatch")
    if metadata.get("tool_name") != "knowledge_read":
        failures.append("wrong_response_tool")
    for field in ("title", "lines", "source", "citation"):
        if (
            field not in payload
            or field not in expected_card
            or payload[field] != expected_card[field]
        ):
            failures.append("card_mismatch:" + field)
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

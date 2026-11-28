"""Output hygiene contracts: snake_case top-level keys, zero audit bloat."""

from __future__ import annotations

import json
import re
from typing import Any

from fatebridge.core.response_models import output_model_for
from fatebridge.services.knowledge import calculate_knowledge_registry
from fatebridge.services.tool_catalog import CATALOG

SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*$")

REMOVED_BLOAT_KEYS = frozenset(
    {
        "rule_trace",
        "rulesets",
        "conventions",
        "calendar_conventions",
        "source_citations",
        "source_catalog",
        "count_trace",
        "evidence_scope",
        "classical_text_evidence",
        "interpretation_contract",
        "trace",
    }
)


def _walk_schema_keys(
    schema: dict[str, Any],
    defs: dict[str, Any],
    path: str = "",
    seen: frozenset[str] = frozenset(),
) -> list[str]:
    hits: list[str] = []
    if "$ref" in schema:
        ref = schema["$ref"].split("/")[-1]
        if ref in seen:
            return hits
        return _walk_schema_keys(defs.get(ref, {}), defs, path, seen | {ref})
    for key, prop in schema.get("properties", {}).items():
        next_path = f"{path}.{key}" if path else key
        if key in REMOVED_BLOAT_KEYS:
            hits.append(next_path)
        if isinstance(prop, dict):
            hits.extend(_walk_schema_keys(prop, defs, next_path, seen))
    for sub_key in ("items", "additionalProperties"):
        sub = schema.get(sub_key)
        if isinstance(sub, dict):
            hits.extend(_walk_schema_keys(sub, defs, path, seen))
    for comb in ("anyOf", "oneOf", "allOf"):
        for opt in schema.get(comb, ()):
            if isinstance(opt, dict):
                hits.extend(_walk_schema_keys(opt, defs, path, seen))
    return hits


def test_output_models_top_level_keys_are_snake_case() -> None:
    """Every top-level key in every tool's output_model must be snake_case."""
    bad: dict[str, list[str]] = {}
    for spec in CATALOG:
        model = output_model_for(spec.name)
        invalid = [k for k in model.model_fields if not SNAKE_CASE_RE.match(k)]
        if invalid:
            bad[spec.name] = invalid
    assert not bad, f"Non-snake_case top-level output_model keys: {bad}"


def test_all_output_models_exclude_removed_keys() -> None:
    """No removed bloat key appears in any tool output_model."""
    violations: dict[str, list[str]] = {}
    for spec in CATALOG:
        model = output_model_for(spec.name)
        schema = model.model_json_schema()
        hits = sorted(set(_walk_schema_keys(schema, schema.get("$defs", {}))))
        if spec.name == "lunar_calendar_time" and "birth" in model.model_fields:
            hits.append("birth")
        if spec.name == "liuyao":
            ev_schema = model.model_fields["liuyao_evidence"].annotation
            if (
                hasattr(ev_schema, "model_fields")
                and "sources" in ev_schema.model_fields
            ):
                hits.append("liuyao_evidence.sources")
        if hits:
            violations[spec.name] = hits
    assert (
        not violations
    ), f"Forbidden keys remain in output_model schemas: {violations}"


def test_knowledge_catalog_payload_is_concise() -> None:
    """knowledge_catalog canonical response stays concise under 8 KiB."""
    payload = calculate_knowledge_registry()
    size = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    assert size < 8192, f"knowledge_catalog payload too large: {size} bytes"

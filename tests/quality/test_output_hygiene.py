"""Output hygiene contracts: snake_case top-level keys, zero audit bloat, unified naming."""

from __future__ import annotations

import json
import re
from typing import Any

from fatebridge.application.examples import example_input
from fatebridge.application.execution import execute_with_receipt
from fatebridge.application.response_delivery import deliver_response
from fatebridge.core.execution_context import ExecutionOptions
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

RENAMED_INCONSISTENT_KEYS = frozenset(
    {
        "personal_info",
        "birth_pillars",
        "dayun_analysis",
        "dayun_info",
        "liunian_analysis",
        "liunian_info",
        "liuyue_analysis",
        "liuyue_info",
        "liuri_analysis",
        "liuri_info",
        "liushi_analysis",
        "liushi_info",
        "combination_effects",
        "liureng",
        "liureng_gods",
        "india",
        "diceChart",
        "dayGanZi",
        "dayInt",
        "monthGanZi",
        "monthInt",
        "timeGanZi",
        "yearGanZi",
        "yearJieqi",
        "distributions",
        "keypoints",
        "yearsystem129",
        "persian_directed",
        "vedic_progression",
        "jaynes_declination",
        "extrareturns",
        "lunation_phase",
        "triplicity_rulers",
        "mundane",
        "horary",
        "input_normalized",
        "input_context",
        "query_context",
        "analysis_reference",
    }
)

FORBIDDEN_NON_FENGSHUI_KEYS = REMOVED_BLOAT_KEYS | RENAMED_INCONSISTENT_KEYS


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
        if key in FORBIDDEN_NON_FENGSHUI_KEYS:
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


def _walk_runtime_keys(value: Any, path: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            next_path = f"{path}.{key}" if path else str(key)
            if key in FORBIDDEN_NON_FENGSHUI_KEYS:
                hits.append(next_path)
            hits.extend(_walk_runtime_keys(item, next_path))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            hits.extend(_walk_runtime_keys(item, f"{path}[{idx}]"))
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
    """No removed bloat or inconsistent key appears in any tool output_model."""
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


def test_all_runtime_audit_responses_exclude_removed_keys() -> None:
    """Every tool's audit runtime response excludes removed bloat/renamed keys."""
    options = ExecutionOptions(detail="audit", as_of="2026-10-12T12:00:00+08:00")
    violations: dict[str, list[str]] = {}
    for spec in CATALOG:
        payload = example_input(spec)
        if payload is None and spec.name == "fengshui_monthly_stars":
            payload = {"effective_solar_year": 2026, "solar_month_number": 1}
        request = spec.request_model.model_validate(payload)
        raw = execute_with_receipt(spec, request, options=options)
        delivered = deliver_response(raw, spec=spec, detail="audit")
        hits = sorted(set(_walk_runtime_keys(delivered)))
        if spec.name == "lunar_calendar_time" and "birth" in delivered:
            hits.append("birth")
        if spec.name == "liuyao":
            ev = delivered.get("liuyao_evidence")
            if isinstance(ev, dict) and "sources" in ev:
                hits.append("liuyao_evidence.sources")
        if hits:
            violations[spec.name] = hits
    assert not violations, f"Forbidden keys emitted at runtime: {violations}"


def test_knowledge_catalog_audit_payload_is_concise() -> None:
    """knowledge_catalog audit response stays under 5 KiB."""
    payload = calculate_knowledge_registry()
    size = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    assert size < 5120, f"knowledge_catalog audit payload too large: {size} bytes"

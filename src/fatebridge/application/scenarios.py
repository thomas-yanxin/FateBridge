"""Packaged scenario definitions joined to live ToolSpecs on each discovery."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from fatebridge.application.description import spec_is_cli_safe, summarize_spec
from fatebridge.application.tool_spec import ToolSpec
from fatebridge.utils.errors import ParameterError


@lru_cache(maxsize=1)
def definitions() -> Dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "data/agent_scenarios.json"
    return json.loads(path.read_text())  # type: ignore[no-any-return]


def scenario_keys(specs: List[ToolSpec], scenario: str) -> Set[str]:
    records = {record["id"]: record for record in definitions()["scenarios"]}
    names = [part.strip() for part in scenario.split(",")]
    if any(name not in records for name in names):
        raise ParameterError(
            "场景名称无效",
            [
                {
                    "path": "scenario",
                    "code": "unknown_scenario",
                    "constraints": {"allowed": sorted(records)},
                }
            ],
        )
    requested = {key for name in names for key in records[name]["engine_tools"]}
    by_key = {spec.key: spec for spec in specs}
    missing = requested - set(by_key)
    if missing:
        raise RuntimeError("Packaged scenario references an unknown catalog key")
    # Nested REST and flat MCP/CLI siblings declare the same operation label.
    labels = {by_key[key].operation_label_zh for key in requested}
    return {
        spec.key
        for spec in specs
        if spec.key in requested or spec.operation_label_zh in labels
    }


def discover_scenarios(
    specs: List[ToolSpec],
    *,
    scenario: Optional[str] = None,
    surface: Optional[str] = None,
    detail: str = "full",
    allowed_names: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    if detail not in {"summary", "full"}:
        raise ParameterError(
            "场景详情模式无效", [{"path": "detail", "code": "invalid_detail"}]
        )
    if surface not in {None, "rest", "mcp", "cli"}:
        raise ParameterError(
            "工具接口无效", [{"path": "surface", "code": "invalid_surface"}]
        )
    if scenario is not None:
        scenario_keys(specs, scenario)
    requested = (
        {part.strip() for part in scenario.split(",")} if scenario is not None else None
    )
    bundle = definitions()
    records = []
    for definition in bundle["scenarios"]:
        if requested is not None and definition["id"] not in requested:
            continue
        keys = scenario_keys(specs, definition["id"])
        candidates = [spec for spec in specs if spec.key in keys]
        exposed = [
            spec
            for spec in candidates
            if (
                (surface != "rest" or spec.rest_path)
                and (surface != "mcp" or spec.mcp_name)
                and (surface != "cli" or spec_is_cli_safe(spec))
                and (allowed_names is None or spec.tool_name in allowed_names)
            )
        ]
        visible_labels = {spec.operation_label_zh for spec in exposed}
        missing = [
            spec.key
            for spec in candidates
            if spec.operation_label_zh not in visible_labels
        ]
        if not exposed and allowed_names is not None and requested is None:
            continue
        record = {
            key: definition[key]
            for key in ("id", "name", "version", "summary", "triggers", "boundary")
        }
        record["consultation"] = definition["consultation"]
        record["tool_count"] = len(exposed)
        record["availability"] = {"complete": not missing, "missing_tool_keys": missing}
        if detail == "full":
            record.update(
                {
                    key: definition[key]
                    for key in ("required_inputs", "output", "source")
                }
            )
            record["required_inputs_scope"] = (
                "skill-level guidance; per-tool required parameters remain authoritative"
            )
            record["tools"] = [
                {
                    **summarize_spec(spec),
                    "key": spec.key,
                    "cli_name": spec.tool_name if spec_is_cli_safe(spec) else None,
                    "required_parameters": [
                        name
                        for name, field in spec.request_model.model_fields.items()
                        if field.is_required()
                    ],
                }
                for spec in exposed
            ]
            # Keep routing IDs joined to available transport siblings; do not
            # suggest an unavailable MCP name or silently change evidence roles.
            by_key = {spec.key: spec for spec in candidates}
            record["routing"] = []
            for row in definition["routing"]:
                evidence = []
                for group in row["evidence"]:
                    alternatives: List[str] = []
                    for key in group["alternatives"]:
                        if key not in by_key:
                            raise RuntimeError(
                                "Scenario route is outside its declared tools"
                            )
                        label = by_key[key].operation_label_zh
                        alternatives.extend(
                            spec.key
                            for spec in exposed
                            if spec.operation_label_zh == label
                        )
                    evidence.append(
                        {
                            **group,
                            "alternatives": list(dict.fromkeys(alternatives)),
                            "available": bool(alternatives),
                        }
                    )
                record["routing"].append(
                    {"intent": row["intent"], "evidence": evidence}
                )
        records.append(record)
    return {
        "schema_version": bundle["schema_version"],
        "consultation_policy": bundle["consultation_policy"],
        "detail": detail,
        "matched_count": len(records),
        "scenarios": records,
    }

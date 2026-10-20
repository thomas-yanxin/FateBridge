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
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def dependency_closure(
    records: Dict[str, Any], known_keys: Set[str]
) -> Dict[str, Set[str]]:
    """Validate and resolve explicit dependencies, including inactive branches.

    Conditions govern when an agent uses a capability, not its publication.
    Keep direct tools separate so an available helper is never a tool quota.
    """
    resolved: Dict[str, Set[str]] = {}
    visiting: Set[str] = set()

    def visit(name: str) -> Set[str]:
        if name in visiting:
            raise ValueError(f"Cyclic scenario dependency: {name}")
        if name not in records:
            raise ValueError(f"Unknown scenario dependency: {name}")
        if name in resolved:
            return resolved[name]
        visiting.add(name)
        record = records[name]
        keys = set(record["engine_tools"])
        for dependency in record.get("dependencies", []):
            if dependency.get("kind") not in {
                "shared_support",
                "conditional_service",
                "composite_topic",
            } or not dependency.get("condition"):
                raise ValueError(f"Invalid scenario dependency: {name}")
            if bool(dependency.get("scenario")) == bool(dependency.get("tools")):
                raise ValueError(f"Dependency needs one scenario or tools: {name}")
            if dependency.get("scenario"):
                keys.update(visit(dependency["scenario"]))
            else:
                keys.update(dependency["tools"])
        if keys - known_keys:
            raise ValueError(
                f"Unknown catalog keys in scenario {name}: {sorted(keys - known_keys)}"
            )
        visiting.remove(name)
        resolved[name] = keys
        return keys

    for name in records:
        visit(name)
    return resolved


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
    by_key = {spec.key: spec for spec in specs}
    closure = dependency_closure(records, set(by_key))
    requested = {key for name in names for key in closure[name]}
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
    by_id = {definition["id"]: definition for definition in bundle["scenarios"]}
    by_catalog_key = {spec.key: spec for spec in specs}
    closure = dependency_closure(by_id, set(by_catalog_key))

    def join_routing(
        rows: List[Dict[str, Any]],
        candidates: List[ToolSpec],
        exposed: List[ToolSpec],
    ) -> List[Dict[str, Any]]:
        by_key = {spec.key: spec for spec in candidates}
        joined = []
        for row in rows:
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
                        spec.key for spec in exposed if spec.operation_label_zh == label
                    )
                evidence.append(
                    {
                        **group,
                        "alternatives": list(dict.fromkeys(alternatives)),
                        "available": bool(alternatives),
                    }
                )
            joined.append({"intent": row["intent"], "evidence": evidence})
        return joined

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
        record["direct_engine_tools"] = definition["engine_tools"]
        record["resolved_engine_tools"] = sorted(closure[definition["id"]])
        record["tool_count"] = len(exposed)
        record["availability"] = {"complete": not missing, "missing_tool_keys": missing}
        record["dependencies"] = []
        for dependency in definition.get("dependencies", []):
            dependency_keys = (
                closure[dependency["scenario"]]
                if dependency.get("scenario")
                else set(dependency["tools"])
            )
            dependency_labels = {
                by_catalog_key[key].operation_label_zh for key in dependency_keys
            }
            dependency_tools = [
                spec for spec in exposed if spec.operation_label_zh in dependency_labels
            ]
            missing_dependency = sorted(
                key
                for key in dependency_keys
                if by_catalog_key[key].operation_label_zh not in visible_labels
            )
            branch = {
                **dependency,
                "resolved_engine_tools": sorted(dependency_keys),
                "available_tool_keys": [spec.key for spec in dependency_tools],
                "availability": {
                    "complete": not missing_dependency,
                    "missing_tool_keys": missing_dependency,
                },
            }
            if detail == "full" and dependency.get("scenario"):
                # All descendant routes retain their originating topic and
                # dependency conditions; publication is not a recommendation.
                visited: Set[str] = set()
                branch["routing"] = []

                def append_routes(name: str, conditions: List[str]) -> None:
                    if name in visited:
                        return
                    visited.add(name)
                    target = by_id[name]
                    branch["routing"].append(
                        {
                            "scenario": name,
                            "conditions": conditions,
                            "routes": join_routing(
                                target["routing"], candidates, exposed
                            ),
                        }
                    )
                    for child in target.get("dependencies", []):
                        if child.get("scenario"):
                            append_routes(
                                child["scenario"], [*conditions, child["condition"]]
                            )

                append_routes(dependency["scenario"], [dependency["condition"]])
            record["dependencies"].append(branch)
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
            record["routing"] = join_routing(definition["routing"], candidates, exposed)
        records.append(record)
    return {
        "schema_version": bundle["schema_version"],
        "consultation_policy": bundle["consultation_policy"],
        "detail": detail,
        "matched_count": len(records),
        "scenarios": records,
    }

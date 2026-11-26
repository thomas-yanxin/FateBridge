"""Assemble residential results and their source and snapshot receipts."""

from typing import Any

from pydantic import JsonValue

from fatebridge.core.fengshui.directions import rule_data
from fatebridge.core.fengshui.geomagnetic import geomagnetic_provenance
from fatebridge.core.fengshui.natal_interpretation import interpretation_provenance
from fatebridge.core.fengshui.reading import build_natal_reading
from fatebridge.core.fengshui.snapshot import sections
from fatebridge.services.snapshot_builders import (
    build_snapshot_export,
    render_snapshot_lines,
)


def _collect_sources(result: dict[str, Any]) -> None:
    """Register bibliographic facts once and keep citation scope at its use."""
    catalog: dict[str, dict[str, JsonValue]] = {}
    bibliography_fields = (
        "title",
        "url",
        "kind",
        "author",
        "author_identity_url",
        "edition",
        "isbn",
    )
    citation_fields = (
        "source_version",
        "published",
        "retrieved_at",
        "locator",
        "pages",
        "scope",
        "evidence_excerpt",
        "boundary",
        "source_disagreements",
        "verification_note",
        "retrieval_status_2026_10_22",
        "retrieval_error",
    )
    registered_sources = {
        record["ruleset_id"]: record.get("sources") for record in result["rulesets"]
    }

    def visit(value: JsonValue, *, registry_record: bool = False) -> JsonValue:
        if isinstance(value, list):
            return [visit(row) for row in value]
        if not isinstance(value, dict):
            return value
        shaped = {name: visit(child) for name, child in value.items()}
        if "ruleset_id" in value and "sources" in value:
            sources = value["sources"]
            ruleset_id = value["ruleset_id"]
            assert isinstance(sources, list) and isinstance(ruleset_id, str)
            shaped.pop("sources")
            if not registry_record and sources == registered_sources.get(ruleset_id):
                return shaped
            citations: dict[str, JsonValue] = {}
            for source in sources:
                assert isinstance(source, dict)
                source_id = source["source_id"]
                assert isinstance(source_id, str)
                catalog.setdefault(source_id, {}).update(
                    {key: source[key] for key in bibliography_fields if key in source}
                )
                citations[source_id] = {
                    key: source[key] for key in citation_fields if key in source
                }
            if citations:
                shaped["source_citations"] = citations
        return shaped

    result["rulesets"] = [
        visit(record, registry_record=True) for record in result["rulesets"]
    ]
    for name, value in result.items():
        if name != "rulesets":
            result[name] = visit(value)
    result["source_catalog"] = catalog


def compose_fengshui_result(
    layers: dict[str, Any],
    conflicts: list[dict[str, Any]],
    layout: dict[str, Any] | None = None,
    scene_scope: dict[str, Any] | None = None,
    method_selection: dict[str, Any] | None = None,
    method_reference: dict[str, Any] | None = None,
    include_calculation_reading: bool = False,
) -> dict[str, Any]:
    missing = [m for layer in layers.values() for m in layer["missing_inputs"]]
    status = "partial" if missing else "complete"
    summary = "；".join(f"{name}: {layer['status']}" for name, layer in layers.items())
    natal_selected = "xuankong_natal" in layers
    result: dict[str, Any] = {
        "analysis_type": "家居风水分层计算" if natal_selected else "家居风水基础计算",
        "engine": (
            "fatebridge-fengshui-natal-v1"
            if natal_selected
            else "fatebridge-fengshui-foundation-v1"
        ),
        "status": status,
        "layers": layers,
        "rulesets": [layer["ruleset"] for layer in layers.values()],
        "coverage": {
            "implemented_layers": list(layers),
            "missing_inputs": missing,
            "unavailable_layers": [
                n
                for n in rule_data("unavailable_layers")
                if n not in {"xuankong_natal", "monthly_stars"}
            ],
            "not_requested_layers": [
                n
                for n in (
                    "bazhai",
                    "jinsuo",
                    "annual_stars",
                    "monthly_stars",
                    "xuankong_natal",
                )
                if n not in layers
            ],
        },
        "conflicts": conflicts,
        "rule_trace": [
            {
                "method": name,
                "ruleset_id": layer["ruleset"]["ruleset_id"],
                "version": layer["ruleset"]["version"],
                "source_ids": layer["ruleset"]["source_ids"],
                "scope": layer["ruleset"]["scope"],
            }
            for name, layer in layers.items()
        ],
        "summary": summary,
    }
    if layout is not None:
        result["layout_analysis"] = layout
        measured = layout.get("workstation_layout_analysis")
        if measured is not None:
            result["coverage"]["unavailable_layers"] = [
                name
                for name in result["coverage"]["unavailable_layers"]
                if name != "automatic_floorplan_geometry"
            ] + ["automatic_image_floorplan_extraction"]
            result["coverage"]["measured_workstation"] = {
                "status": measured["status"],
                "scope": measured["scope"],
                "candidate_only": measured["geometry"]["candidate_only"],
                "search_enumeration_complete": measured.get("search", {}).get(
                    "enumeration_complete"
                ),
            }
        # Top-level status retains the raw-chart contract. Requested layout
        # readiness is separate and must survive a coverage-only projection.
        result["coverage"].update(
            analysis_progress=layout["analysis_progress"],
            layout_status=layout["status"],
            layout_missing_inputs=layout["missing_inputs"],
            requested_analysis_status=(
                "partial"
                if status == "partial" or layout["status"] == "partial"
                else "complete"
            ),
        )
        result["summary"] = (
            f"{summary}；layout: {layout['status']}"
            if layers
            else f"layout: {layout['status']}"
        )
        extra_rules = layout["supplemental_rulesets"]
        if extra_rules:
            result["rulesets"].extend(extra_rules)
            result["coverage"]["supplemental_rulesets"] = [
                r["ruleset_id"] for r in extra_rules
            ]
            result["rule_trace"].extend(
                {
                    "method": r["method"],
                    "ruleset_id": r["ruleset_id"],
                    "version": r["version"],
                    "source_ids": r["source_ids"],
                    "scope": r["scope"],
                }
                for r in extra_rules
            )
        if not layers:
            result["status"] = layout["status"]
            result["summary"] = f"layout: {layout['status']}"
            result["coverage"]["missing_inputs"] = layout["missing_inputs"]
        for branch in (
            "interior_analysis",
            "material_analysis",
            "workstation_analysis",
            "workstation_layout_analysis",
        ):
            result["rule_trace"].extend(layout.get(branch, {}).get("rule_trace", []))
    source_comparison = layers.get("xuankong_natal", {}).get("source_comparison")
    if source_comparison is not None:
        record = source_comparison["ruleset"]
        result["rulesets"].append(record)
        result["coverage"]["natal_source_comparison"] = source_comparison["summary"]
        result["rule_trace"].append(
            {
                key: record[key]
                for key in ("method", "ruleset_id", "version", "source_ids", "scope")
            }
        )
    interpretation = layers.get("xuankong_natal", {}).get("interpretation")
    if interpretation is not None:
        provenance_record = interpretation_provenance()
        result["rulesets"].append(provenance_record)
        if interpretation.get("timeliness_ruleset") is not None:
            record = interpretation["timeliness_ruleset"]
            result["rulesets"].append(record)
            result["rule_trace"].append(
                {
                    key: record[key]
                    for key in (
                        "method",
                        "ruleset_id",
                        "version",
                        "source_ids",
                        "scope",
                    )
                }
            )
        if interpretation.get("host_guest_analysis") is not None:
            host_guest = interpretation["host_guest_analysis"]
            result["rulesets"].append(host_guest["ruleset"])
            result["coverage"]["natal_host_guest"] = {
                "status": host_guest["status"],
                "candidate_count": len(host_guest["candidates"]),
                "relation_count": 8 * len(host_guest["candidates"]),
                "scope": host_guest["scope"],
            }
        if interpretation.get("fixed_lingzheng_analysis") is not None:
            record = interpretation["fixed_lingzheng_analysis"]["ruleset"]
            result["rulesets"].append(record)
            result["rule_trace"].extend(
                interpretation["fixed_lingzheng_analysis"]["rule_trace"]
            )
        result["rule_trace"].append(
            {
                key: provenance_record[key]
                for key in ("method", "ruleset_id", "version", "source_ids", "scope")
            }
        )
        result["coverage"].update(
            natal_interpretation_status=interpretation["status"],
            natal_interpretation_missing_inputs=interpretation["missing_inputs"],
            requested_analysis_status=(
                "partial"
                if interpretation["status"] == "partial"
                or result["coverage"].get("requested_analysis_status", status)
                == "partial"
                else "complete"
            ),
        )
    city_gate = layers.get("xuankong_natal", {}).get("city_gate_analysis")
    if city_gate is not None:
        result["summary"] += f"；city_gate: {city_gate['status']}（独立参考运）"
        record = city_gate["ruleset"]
        result["rulesets"].append(record)
        result["rule_trace"].append(
            {
                key: record[key]
                for key in ("method", "ruleset_id", "version", "source_ids", "scope")
            }
        )
        result["coverage"].update(
            city_gate_status=city_gate["status"],
            city_gate_calculation_status=city_gate["calculation_status"],
            city_gate_missing_inputs=city_gate["missing_inputs"],
            requested_analysis_status=(
                "partial"
                if city_gate["status"] == "partial"
                or result["coverage"].get("requested_analysis_status", status)
                == "partial"
                else "complete"
            ),
        )
    geomagnetic = layers.get("directions", {}).get("geomagnetic_reference")
    if geomagnetic is not None:
        record = geomagnetic_provenance()
        result["rulesets"].append(record)
        result["rule_trace"].append(
            {
                key: record[key]
                for key in ("method", "ruleset_id", "version", "source_ids", "scope")
            }
        )
    if scene_scope is not None:
        result["coverage"]["scene_scope"] = scene_scope
    if method_selection is not None and method_reference is not None:
        result["method_policy"] = method_selection
        result["method_details"] = method_reference
        result["coverage"]["method_priority_review"] = {
            key: method_selection[key]
            for key in (
                "priority_review_status",
                "priority_missing_methods",
                "priority_missing_inputs",
            )
        }
        reference = method_reference["ruleset"]
        result["rulesets"].append(reference)
        result["rule_trace"].append(
            {
                key: reference[key]
                for key in ("method", "ruleset_id", "version", "source_ids", "scope")
            }
        )
    context = (layout or {}).get("environmental_context")
    if context is not None:
        result["coverage"].update(
            environmental_context_status=context["status"],
            environmental_context_missing_inputs=context["missing_inputs"],
        )
    _collect_sources(result)
    snapshot_sections = sections(result)
    result["snapshot_text"] = render_snapshot_lines(snapshot_sections)
    result["snapshot_export"] = build_snapshot_export(
        technique="fengshui",
        snapshot_text=result["snapshot_text"],
        selected_sections=[title for title, _ in snapshot_sections],
    )
    if include_calculation_reading:
        result["calculation_reading"] = build_natal_reading(result)
    return result

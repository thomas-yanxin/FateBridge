"""Compose measured evidence, coverage and optional search in the domain layer."""

from pydantic import BaseModel, JsonValue, TypeAdapter

from .models import AssessRequest
from .spatial_layout import geometry_output, measured_assessment
from .spatial_outputs import EvaluatedGeometry, MeasuredLayoutOutput
from .spatial_search import search_measured_layouts
from .spatial_sources import RegisteredRuleset, research_coverage, spatial_limitations
from .surface import summarize_analysis_progress


class ProgressFacts(BaseModel):
    rule_coverage_counts: dict[str, int]
    action_counts: dict[str, int]
    pending_confirmations: list[dict[str, JsonValue]]
    rule_coverage_status: str
    optional_action_count: int


class LayoutMergeFacts(BaseModel):
    supplemental_rulesets: list[RegisteredRuleset]
    missing_inputs: list[str]
    analysis_progress: ProgressFacts
    unsupported_queries: list[str]


def merge_measured_layout(
    original: AssessRequest,
    prepared: AssessRequest,
    geometry: EvaluatedGeometry,
    layers: dict[str, JsonValue],
    layout: dict[str, JsonValue],
) -> dict[str, JsonValue]:
    current = LayoutMergeFacts.model_validate(layout)
    measured = measured_assessment(prepared, geometry, layers, layout)
    search = (
        search_measured_layouts(original, layers)
        if original.workstation_layout and original.workstation_layout.search
        else None
    )
    coverage = research_coverage()
    branch = MeasuredLayoutOutput(
        status="partial" if measured.missing_inputs else "complete",
        geometry=geometry_output(measured),
        missing_inputs=measured.missing_inputs,
        readings=[r.model_dump(mode="json") for r in measured.readings],
        rule_comparisons=[c.model_dump(mode="json") for c in measured.comparisons],
        search=search,
        limitations=spatial_limitations(),
        scope="measured_scene_and_explicit_author_rules_finite_search_not_whole_property_certification",
        research_completion_status=(
            "complete"
            if all(row.status == "implemented" for row in coverage)
            else "incomplete"
        ),
        research_coverage=coverage,
        rule_trace=TypeAdapter(list[dict[str, JsonValue]]).validate_python(
            [
                dict(
                    rule_id=c.rule_id,
                    source_ids=c.source_ids,
                    object_id=c.object_id,
                    instance_id=c.instance_id,
                    status=c.status,
                )
                for c in measured.comparisons
            ]
            + [
                dict(
                    rule_id=r.rule_id,
                    source_ids=r.source_ids,
                    object_id=r.desk_id,
                    direction=r.direction,
                    candidate_id=r.chart_candidate_id,
                )
                for r in measured.readings
            ]
        ),
    )
    result = dict(layout)
    result["workstation_layout_analysis"] = branch.model_dump(
        mode="json", exclude={"search"} if search is None else set()
    )
    registered = {record.ruleset_id: record for record in current.supplemental_rulesets}
    registered.update({record.ruleset_id: record for record in measured.rulesets})
    result["supplemental_rulesets"] = [
        record.model_dump(mode="json") for record in registered.values()
    ]
    missing = list(dict.fromkeys([*current.missing_inputs, *measured.missing_inputs]))
    missing_json: list[JsonValue] = list(missing)
    result["missing_inputs"] = missing_json
    if missing:
        result["status"] = "partial"
    previous = current.analysis_progress
    counts = dict(previous.rule_coverage_counts)
    counts["supported"] += 0 if geometry.candidate_only else len(geometry.checks)
    counts["unknown"] += len(measured.missing_inputs)
    actions = [
        dict(
            status={
                "ready": "ready",
                "conditional": "conditional_option",
                "candidate": "candidate_only",
                "blocked": "blocked",
            }[key],
            optional=False,
        )
        for key, count in previous.action_counts.items()
        for _ in range(count)
    ]
    receipts = (search.receipts or []) if search else []
    pending = list(previous.pending_confirmations)
    for path in measured.missing_inputs:
        pending.append(
            dict(
                path=path,
                reason="confirm_measured_rule_fact_if_relevant",
                required_for="assessment",
            )
        )
    for path in dict.fromkeys(
        path for row in receipts for path in row.pending_confirmations
    ):
        pending.append(
            dict(
                path=path,
                reason="confirm_generated_action_condition",
                required_for="optional_action",
            )
        )
    progress = summarize_analysis_progress(
        missing,
        counts,
        [*actions, *(dict(status=row.status, optional=True) for row in receipts)],
        pending,
        count_unit="surface_items_and_layout_checks",
        limited=previous.rule_coverage_status == "limited",
        conditional_basis_count=len(geometry.checks) if geometry.candidate_only else 0,
    )
    progress["optional_action_count"] += previous.optional_action_count
    result["analysis_progress"] = progress
    unsupported = [
        q
        for q in current.unsupported_queries
        if q
        not in {
            "automatic_candidate_relocation_feasibility",
            "automatic_floorplan_geometry_and_external_landform_analysis",
        }
    ]
    result["unsupported_queries"] = [
        *unsupported,
        "automatic_image_floorplan_extraction",
        "unmeasured_external_landform_analysis",
    ]
    return result

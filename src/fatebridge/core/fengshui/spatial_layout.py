"""Adapter between measured scenes and the existing shared domain algorithms."""

import hashlib
import json
from dataclasses import dataclass

from pydantic import BaseModel, JsonValue, TypeAdapter

from .bazhai import bazhai
from .context_inputs import EnvironmentalContext, EnvironmentalObject
from .jinsuo import jinsuo
from .layout import analyze_layout
from .models import AssessRequest, EnvironmentFeature, JinsuoRequest, Placement
from .spatial_desktop import desktop_rule_comparisons
from .spatial_inputs import SpatialScene
from .spatial_outputs import EvaluatedGeometry, GeometryOutput
from .spatial_reasoning import (
    ComputedSpatialFacts,
    RuleComparison,
    TimedWorkstationReading,
    conditioned_readings,
)
from .spatial_scene import evaluate_geometry
from .spatial_sources import RegisteredRuleset, spatial_ruleset
from .timeliness import timeliness_provenance
from .workstation_inputs import EntryBarrier, ObservedCondition, WorkstationReview


class FormCheckEvidence(BaseModel):
    criterion: str
    observed: bool | str | float | None
    expected: bool | str
    finding: str
    candidate_only: bool
    rule_id: str
    source_ids: list[str]


class FormEvidence(BaseModel):
    object_id: str
    checks: list[FormCheckEvidence]


class FormEvidenceCollection(BaseModel):
    findings: list[FormEvidence] = []


class PlacementEvidence(BaseModel):
    object_id: str
    method: str
    subject_id: str | None = None
    aspect: str | None = None
    matches_convention: bool | None = None
    candidate_only: bool = False
    rule_id: str
    source_ids: list[str]


class LayoutEvidence(BaseModel):
    form_analysis: FormEvidenceCollection
    placement_findings: list[PlacementEvidence]
    supplemental_rulesets: list[RegisteredRuleset]
    environment_adjustments: list["SandWaterEvidence"] = []
    workstation_analysis: "BarrierReviewEvidence | None" = None


class BarrierFindingEvidence(BaseModel):
    desk_id: str | None = None
    rule_id: str
    source_ids: list[str]
    status: str
    relation_id: str | None = None
    entry_line_through_user: ObservedCondition | None = None
    barrier_between_entry_and_user: ObservedCondition | None = None


class BarrierReviewEvidence(BaseModel):
    findings: list[BarrierFindingEvidence]


class SandWaterEvidence(BaseModel):
    object_id: str
    rule_id: str
    source_ids: list[str]
    finding: str
    classification: str
    preferred_classification: str


@dataclass
class SceneAssessment:
    request: AssessRequest
    geometry: EvaluatedGeometry
    comparisons: list[RuleComparison]
    readings: list[TimedWorkstationReading]
    missing_inputs: list[str]
    rulesets: list[RegisteredRuleset]
    legacy_layout: dict[str, JsonValue]


def prepare_spatial_request(
    req: AssessRequest, scene: SpatialScene
) -> tuple[AssessRequest, EvaluatedGeometry]:
    geometry = evaluate_geometry(scene)
    owned = {seat.desk_id for seat in scene.seats}
    # Start with the original public request for every candidate. Never compile
    # from another candidate's already-derived placements or observations.
    placements = [p for p in req.placements if p.object_id not in owned]
    forms = [f for f in req.form_observations if f.object_id not in owned]
    for seat in geometry.seats:
        if seat.form is not None and (
            not geometry.candidate_only or scene.observation_basis == "image_observed"
        ):
            forms.append(seat.form)
        location = (
            seat.location_directions[0]
            if seat.chart_binding_status == "confirmed" and not geometry.candidate_only
            else None
        )
        facing = (
            seat.facing_directions[0]
            if len(seat.facing_directions) == 1 and not geometry.candidate_only
            else None
        )
        if location is not None or facing is not None:
            placements.append(
                Placement(
                    object_id=seat.desk_id,
                    purpose="desk",
                    subject_ids=seat.subject_ids,
                    location_direction=location,
                    facing_direction=facing,
                    facing_role="desk_facing" if facing is not None else None,
                )
            )
    spatial = req.workstation_layout
    context = req.environmental_context
    barriers = [body for body in scene.bodies if body.kind in {"plant", "screen"}]
    if barriers and scene.coordinate_uncertainty_m == 0:
        objects = list(context.objects) if context else []
        review = context.workstation_review if context else None
        relationships = list(review.entry_barriers) if review else []
        existing_ids = {obj.object_id for obj in objects}
        openings = {opening.object_id: opening for opening in scene.openings}
        for seat_input, seat in zip(scene.seats, geometry.seats):
            if seat_input.entrance_id is None or seat.form is None:
                continue
            entry = openings[seat_input.entrance_id]
            for object_id, kind, purpose in (
                (entry.object_id, "opening", "door"),
                (seat.desk_id, "furniture", "desk"),
            ):
                if object_id not in existing_ids:
                    objects.append(
                        EnvironmentalObject.model_validate(
                            dict(
                                object_id=object_id,
                                kind=kind,
                                purpose=purpose,
                                label=object_id,
                                evidence=scene.evidence,
                            )
                        )
                    )
                    existing_ids.add(object_id)
            for barrier in barriers:
                if barrier.object_id not in existing_ids:
                    objects.append(
                        EnvironmentalObject(
                            object_id=barrier.object_id,
                            kind="furniture",
                            label=barrier.object_id,
                            evidence=scene.evidence,
                        )
                    )
                    existing_ids.add(barrier.object_id)
                facts = {
                    key: ObservedCondition(
                        value=value,
                        observation_basis=scene.observation_basis,
                        evidence=f"workstation_layout_v1:{scene.frame_id}; supplied geometry",
                    )
                    for key, value in dict(
                        entry_line_through_user=seat.form.entrance_direct_line,
                        barrier_between_entry_and_user=barrier.object_id
                        in seat.barriers_between,
                        entrance_view_maintained=seat.form.entrance_visible,
                        circulation_clear=(
                            all(
                                c.passed is True
                                for c in geometry.checks
                                if c.check_id == "keep_clear"
                                and barrier.object_id in c.object_ids
                            )
                            if scene.inventory_confirmed
                            else None
                        ),
                        operating_space_clear=(
                            all(
                                c.passed is True
                                for c in geometry.checks
                                if c.check_id == "operating_zone_clear"
                                and barrier.object_id in c.object_ids
                            )
                            if scene.inventory_confirmed
                            else None
                        ),
                        physically_feasible=(
                            geometry.physically_feasible
                            if scene.inventory_confirmed
                            else None
                        ),
                    ).items()
                }
                relationships.append(
                    EntryBarrier(
                        ruleset_id="afsi_entry_barrier_v1",
                        relation_id="spatial:"
                        + hashlib.sha256(
                            json.dumps(
                                [seat.desk_id, barrier.object_id], ensure_ascii=False
                            ).encode()
                        ).hexdigest(),
                        entrance_id=entry.object_id,
                        desk_id=seat.desk_id,
                        barrier_id=barrier.object_id,
                        barrier_kind="plant" if barrier.kind == "plant" else "screen",
                        operation="retain",
                        observation_basis=scene.observation_basis,
                        evidence=scene.evidence,
                        **facts,
                    )
                )
        if relationships:
            new_review = (
                review.model_copy(update=dict(entry_barriers=relationships))
                if review
                else WorkstationReview(entry_barriers=relationships)
            )
            context = (
                context.model_copy(
                    update=dict(objects=objects, workstation_review=new_review)
                )
                if context
                else EnvironmentalContext(
                    objects=objects, workstation_review=new_review
                )
            )
    body_ids = {body.object_id for body in scene.bodies}
    features = [
        feature for feature in req.features if feature.object_id not in body_ids
    ]
    seats = {seat.desk_id: seat for seat in geometry.seats}
    for body in scene.bodies:
        observation = body.sand_water
        directions = (
            seats[body.object_id].location_directions
            if body.object_id in seats
            else geometry.body_sectors[body.object_id]
        )
        if (
            observation
            and observation.observation_basis != "image_observed"
            and scene.compass
            and scene.compass.chart_binding_confirmed
            and not geometry.candidate_only
            and len(directions) == 1
        ):
            features.append(
                EnvironmentFeature(
                    object_id=body.object_id,
                    direction=directions[0],
                    classification=observation.classification,
                    classification_basis=observation.observation_basis,
                    evidence=observation.evidence,
                )
            )
    return (
        req.model_copy(
            update=dict(
                placements=placements,
                form_observations=forms,
                features=features,
                environmental_context=context,
                scene=req.scene or "workstation",
                methods=req.selected_methods,
                workstation_layout=(
                    spatial.model_copy(update=dict(scene=scene)) if spatial else None
                ),
            )
        ),
        geometry,
    )


def measured_assessment(
    req: AssessRequest,
    geometry: EvaluatedGeometry,
    layers: dict[str, JsonValue],
    layout: dict[str, JsonValue],
) -> SceneAssessment:
    facts = ComputedSpatialFacts.model_validate(layers)
    legacy = LayoutEvidence.model_validate(layout)
    spatial = req.workstation_layout
    if spatial is None:
        raise ValueError("measured_assessment requires a measured scene")
    comparisons, desktop_rulesets = desktop_rule_comparisons(spatial.scene, geometry)
    for finding in legacy.form_analysis.findings:
        for check in finding.checks:
            comparisons.append(
                RuleComparison(
                    object_id=finding.object_id,
                    rule_id=check.rule_id,
                    source_ids=check.source_ids,
                    reference_frame="seated_indoor_form",
                    candidate_only=check.candidate_only,
                    matches=(
                        None
                        if check.finding == "undetermined"
                        else check.finding == "matches_rule"
                    ),
                    status=check.finding,
                    observed=(
                        str(check.observed) if check.observed is not None else None
                    ),
                    expected=str(check.expected),
                )
            )
    for placement_finding in legacy.placement_findings:
        if placement_finding.method == "bazhai":
            comparisons.append(
                RuleComparison(
                    object_id=placement_finding.object_id,
                    rule_id=placement_finding.rule_id,
                    instance_id=json.dumps(
                        [placement_finding.subject_id, placement_finding.aspect]
                    ),
                    source_ids=placement_finding.source_ids,
                    reference_frame="bazhai_separate_person_or_house",
                    matches=placement_finding.matches_convention,
                    candidate_only=placement_finding.candidate_only,
                    status="reference_only_no_combined_direction_verdict",
                )
            )
    readings, missing = conditioned_readings(req, geometry, facts)
    for reading in readings:
        if reading.selected_role is None or reading.evaluation_period_number is None:
            continue
        comparisons.append(
            RuleComparison(
                object_id=reading.desk_id,
                rule_id="workstation_conditioned_v1.current_role_period_match",
                source_ids=reading.source_ids,
                instance_id=reading.chart_candidate_id,
                reference_frame="explicit_work_role_period_condition_not_fortune_score",
                matches=reading.current_role_condition,
                candidate_only=reading.candidate_only,
                status="period_condition_only_not_auspiciousness",
                observed=str(reading.facing_star_number),
                expected=str(reading.evaluation_period_number),
                conditions=[
                    "只比较向星与明确评价运是否相同",
                    "非当令不等于不利；不产生全局吉凶",
                ],
            )
        )
    for feature in legacy.environment_adjustments:
        comparisons.append(
            RuleComparison(
                object_id=feature.object_id,
                rule_id=feature.rule_id,
                source_ids=feature.source_ids,
                reference_frame="confirmed_jinsuo_eight_palaces",
                matches=(
                    None
                    if feature.finding == "undetermined"
                    else feature.finding == "matches_preference"
                ),
                candidate_only=geometry.candidate_only,
                status=feature.finding,
                observed=feature.classification,
                expected=feature.preferred_classification,
            )
        )
    if legacy.workstation_analysis:
        for relation in legacy.workstation_analysis.findings:
            if (
                relation.desk_id is None
                or relation.entry_line_through_user is None
                or relation.barrier_between_entry_and_user is None
            ):
                continue
            line, between = (
                relation.entry_line_through_user,
                relation.barrier_between_entry_and_user,
            )
            match = True if line.value is False else between.value
            comparisons.append(
                RuleComparison(
                    object_id=relation.desk_id,
                    rule_id=relation.rule_id,
                    source_ids=relation.source_ids,
                    reference_frame="actual_entry_user_barrier_relationship",
                    matches=match,
                    candidate_only=relation.status == "candidate_only",
                    status=relation.status,
                    observed=f"entry_line={line.value};barrier_between={between.value}",
                    expected="barrier_between_when_actual_entry_line_crosses_user",
                    instance_id=relation.relation_id,
                )
            )
    rulesets = [
        spatial_ruleset("workstation_layout_v1"),
        *legacy.supplemental_rulesets,
        *desktop_rulesets,
    ]
    if facts.xuankong_natal is not None:
        rulesets.append(spatial_ruleset("workstation_conditioned_v1"))
    if any("wofs_desktop_compass_v1" in d.ruleset_ids for d in spatial.scene.desktops):
        rulesets.append(spatial_ruleset("wofs_desktop_compass_v1"))
    if spatial.timeliness_ruleset_id:
        rulesets.append(RegisteredRuleset.model_validate(timeliness_provenance()))
    if geometry.candidate_only:
        missing.append("workstation_layout.scene.confirmed_measurements")
    for geometry_check in geometry.checks:
        if geometry_check.passed is None:
            missing.append(
                f"workstation_layout.geometry.{geometry_check.check_id}:{','.join(geometry_check.object_ids)}"
            )
    # A source's uncovered object is not a missing fact. Do not ask for
    # orientation/material simply to invent an unregistered placement rule.
    for comparison in comparisons:
        if comparison.status != "not_covered" and (
            comparison.matches is None
            or comparison.candidate_only
            or comparison.status == "needs_confirmation"
        ):
            missing.append(
                f"workstation_layout.rules.{comparison.object_id}.{comparison.rule_id}"
            )
    return SceneAssessment(
        request=req,
        geometry=geometry,
        comparisons=comparisons,
        readings=readings,
        missing_inputs=list(dict.fromkeys(missing)),
        rulesets=list({r.ruleset_id: r for r in rulesets}.values()),
        legacy_layout=layout,
    )


def evaluate_measured_candidate(
    original: AssessRequest, scene: SpatialScene, layers: dict[str, JsonValue]
) -> SceneAssessment:
    req, geometry = prepare_spatial_request(original, scene)
    candidate_layers = dict(layers)
    if "bazhai" in candidate_layers:
        # Recalculate placement-dependent findings, preserving chart provenance.
        prior = candidate_layers["bazhai"]
        if not isinstance(prior, dict):
            raise ValueError("computed bazhai layer must be an object")
        candidate_layers["bazhai"] = TypeAdapter(dict[str, JsonValue]).validate_python(
            {**bazhai(req), "ruleset": prior["ruleset"]}
        )
    if "jinsuo" in candidate_layers:
        prior = candidate_layers["jinsuo"]
        if not isinstance(prior, dict):
            raise ValueError("computed jinsuo layer must be an object")
        candidate_layers["jinsuo"] = TypeAdapter(dict[str, JsonValue]).validate_python(
            {
                **jinsuo(
                    JinsuoRequest(
                        features=req.features, ruleset_id=req.jinsuo_ruleset_id
                    )
                ),
                "ruleset": prior["ruleset"],
            }
        )
    layout = TypeAdapter(dict[str, JsonValue]).validate_python(
        analyze_layout(req, candidate_layers)
    )
    return measured_assessment(req, geometry, candidate_layers, layout)


def geometry_output(assessment: SceneAssessment) -> GeometryOutput:
    spatial = assessment.request.workstation_layout
    if spatial is None:
        raise ValueError("geometry_output requires a measured scene")
    scene = spatial.scene
    return GeometryOutput(
        frame_id=scene.frame_id,
        observation_basis=scene.observation_basis,
        coordinate_uncertainty_m=scene.coordinate_uncertainty_m,
        candidate_only=assessment.geometry.candidate_only,
        physically_feasible=assessment.geometry.physically_feasible,
        seats=assessment.geometry.seats,
        checks=assessment.geometry.checks,
        desktop_placements=assessment.geometry.desktop_placements,
        body_sectors=assessment.geometry.body_sectors,
        screen_visibility=assessment.geometry.screen_visibility,
    )

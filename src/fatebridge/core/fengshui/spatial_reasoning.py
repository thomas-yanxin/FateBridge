"""Conditional workstation readings over computed facts, never rebuilt charts."""

from pydantic import BaseModel, JsonValue, TypeAdapter

from .directions import rule_data
from .models import AssessRequest
from .natal_interpretation import _ordered_relationship
from .spatial_inputs import CompassDirection
from .spatial_outputs import EvaluatedGeometry
from .timeliness import classify_timeliness


class StarFacts(BaseModel):
    mountain_star_number: int
    facing_star_number: int
    period_star_number: int


class ComputedNatal(BaseModel):
    candidate_id: str
    period_number: int
    palaces: dict[str, StarFacts]
    structure: dict[str, JsonValue] = {}


class HostGuestAxis(BaseModel):
    direction: str
    relations: list[dict[str, JsonValue]]


class HostGuestCandidate(BaseModel):
    candidate_id: str
    axes: dict[str, HostGuestAxis]


class HostGuestFacts(BaseModel):
    candidates: list[HostGuestCandidate]


class NatalInterpretationFacts(BaseModel):
    host_guest_analysis: HostGuestFacts | None = None


class NatalFacts(BaseModel):
    candidates: list[ComputedNatal] = []
    interpretation: NatalInterpretationFacts | None = None


class TimeStarFacts(BaseModel):
    annual_star_number: int | None = None
    monthly_star_number: int | None = None


class TimeLayerFacts(BaseModel):
    palaces: dict[str, TimeStarFacts] = {}
    time_context: dict[str, JsonValue] = {}


class ComputedSpatialFacts(BaseModel):
    xuankong_natal: NatalFacts | None = None
    annual_stars: TimeLayerFacts | None = None
    monthly_stars: TimeLayerFacts | None = None


class ElementStar(BaseModel):
    element: str


class RuleComparison(BaseModel):
    object_id: str
    rule_id: str
    source_ids: list[str]
    reference_frame: str
    matches: bool | None
    candidate_only: bool
    status: str
    observed: str | None = None
    expected: str | None = None
    conditions: list[str] = []
    application_conditions_met: bool | None = None
    instance_id: str | None = None


class TimedWorkstationReading(BaseModel):
    desk_id: str
    direction: CompassDirection
    chart_candidate_id: str
    candidate_only: bool
    historical_period_number: int
    evaluation_period_number: int | None
    activity: str
    selected_role: str | None
    mountain_star_number: int
    facing_star_number: int
    mountain_element: str
    facing_element: str
    ordered_element_relationship: str
    basic_timeliness: dict[str, JsonValue] | None
    current_role_condition: bool | None
    external_water_condition: str
    external_water_evidence: str | None
    host_guest_scope: str
    host_guest_reference: dict[str, JsonValue] | None
    time_layer_references: dict[str, int]
    time_layer_contexts: dict[str, dict[str, JsonValue]]
    indoor_conditions: dict[str, bool | None]
    chart_structure_reference: dict[str, JsonValue]
    source_ids: list[str]
    rule_id: str = "workstation_conditioned_v1.context"
    conclusion: str
    scope: str = (
        "source_scoped_conditions_not_81_pair_fortune_or_water_object_prescription"
    )


def conditioned_readings(
    req: AssessRequest, geometry: EvaluatedGeometry, facts: ComputedSpatialFacts
) -> tuple[list[TimedWorkstationReading], list[str]]:
    spatial = req.workstation_layout
    if spatial is None:
        return [], []
    natal = facts.xuankong_natal
    if natal is None:
        return [], []
    interpretation = req.xuankong.interpretation if req.xuankong else None
    period = spatial.evaluation_period
    if period is None and interpretation:
        period = interpretation.current_period_number
    author_timeliness = spatial.timeliness_ruleset_id is not None or bool(
        interpretation and interpretation.timeliness_ruleset_id
    )
    elements = TypeAdapter(dict[int, ElementStar]).validate_python(
        rule_data("annual_stars")
    )
    readings: list[TimedWorkstationReading] = []
    missing = []
    for seat, observation in zip(spatial.scene.seats, geometry.seats):
        if observation.chart_binding_status in {"not_bound", "at_sector_origin"}:
            missing.append(
                f"workstation_layout.scene.{seat.desk_id}.confirmed_chart_binding"
            )
            continue
        if not natal.candidates:
            missing.append("workstation_layout.computed_xuankong_natal")
        for direction in observation.location_directions:
            for chart in natal.candidates:
                palace = chart.palaces[direction]
                mountain, facing = (
                    palace.mountain_star_number,
                    palace.facing_star_number,
                )
                role = "facing" if seat.activity in {"work", "study"} else None
                timely = (
                    facing == period
                    if role is not None and period is not None
                    else None
                )
                external = (
                    next(
                        (
                            o
                            for o in interpretation.external_forms
                            if o.direction == direction
                        ),
                        None,
                    )
                    if interpretation
                    else None
                )
                water = "not_assessed_no_external_observation"
                if external:
                    water = (
                        "candidate_only"
                        if external.observation_basis == "image_observed"
                        else (
                            "unknown"
                            if external.water_present is None
                            else "present" if external.water_present else "absent"
                        )
                    )
                time_layers = {}
                time_contexts = {}
                for name, layer in (
                    ("annual_stars", facts.annual_stars),
                    ("monthly_stars", facts.monthly_stars),
                ):
                    if layer and direction in layer.palaces:
                        star = layer.palaces[direction]
                        number = (
                            star.annual_star_number
                            if name == "annual_stars"
                            else star.monthly_star_number
                        )
                        if number is not None:
                            time_layers[name] = number
                            time_contexts[name] = layer.time_context
                host_scope = "not_selected"
                host_reference = None
                if interpretation and interpretation.host_guest_ruleset_id:
                    # The registered Shen host/guest implementation covers axes,
                    # not an arbitrary workstation palace. Do not extrapolate.
                    host_scope = "outside_selected_source_axis_scope"
                    host_guest = (
                        natal.interpretation.host_guest_analysis
                        if natal.interpretation
                        else None
                    )
                    if host_guest:
                        for source_candidate in host_guest.candidates:
                            if source_candidate.candidate_id != chart.candidate_id:
                                continue
                            for axis in source_candidate.axes.values():
                                if axis.direction == direction:
                                    host_scope = "existing_axis_operations_only_not_workstation_fortune"
                                    host_reference = TypeAdapter(
                                        dict[str, JsonValue]
                                    ).validate_python(axis.model_dump(mode="json"))
                candidate = (
                    geometry.candidate_only
                    or observation.chart_binding_status != "confirmed"
                    or len(natal.candidates) > 1
                )
                if role is None:
                    conclusion = "本版本工作/学习用途条件不覆盖该活动；保留实际活动，不借用床门规则。"
                elif period is None:
                    conclusion = (
                        "工作/学习按该作者取向星角色；评价运未知，不能判断当令。"
                    )
                elif timely:
                    conclusion = "工作/学习用途所取向星与明确评价运相同；形势、外局及材料条件分别核对。"
                else:
                    conclusion = "工作/学习用途所取向星与明确评价运不同；此事实不能直接判为不利。"
                readings.append(
                    TimedWorkstationReading(
                        desk_id=seat.desk_id,
                        direction=direction,
                        chart_candidate_id=chart.candidate_id,
                        candidate_only=candidate,
                        historical_period_number=chart.period_number,
                        evaluation_period_number=period,
                        activity=seat.activity,
                        selected_role=role,
                        mountain_star_number=mountain,
                        facing_star_number=facing,
                        mountain_element=elements[mountain].element,
                        facing_element=elements[facing].element,
                        ordered_element_relationship=_ordered_relationship(
                            elements[mountain].element, elements[facing].element
                        ),
                        basic_timeliness=(
                            TypeAdapter(dict[str, JsonValue]).validate_python(
                                classify_timeliness(facing, period)
                            )
                            if author_timeliness
                            else None
                        ),
                        current_role_condition=timely,
                        external_water_condition=water,
                        external_water_evidence=external.evidence if external else None,
                        host_guest_scope=host_scope,
                        host_guest_reference=host_reference,
                        time_layer_references=time_layers,
                        time_layer_contexts=time_contexts,
                        indoor_conditions=dict(
                            entrance_visible=(
                                observation.form.entrance_visible
                                if observation.form
                                else None
                            ),
                            entrance_direct_line=(
                                observation.form.entrance_direct_line
                                if observation.form
                                else None
                            ),
                            solid_backing=(
                                observation.form.solid_backing
                                if observation.form
                                else None
                            ),
                        ),
                        chart_structure_reference=chart.structure,
                        source_ids=["K0", "K2"],
                        conclusion=conclusion,
                    )
                )
        if len(observation.location_directions) > 1:
            missing.append(
                f"workstation_layout.scene.{seat.desk_id}.unambiguous_sector"
            )
    if author_timeliness and period is None:
        missing.append("workstation_layout.evaluation_period")
    return readings, list(dict.fromkeys(missing))

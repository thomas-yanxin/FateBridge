"""Projectable Human Design calculation contracts (pure structured facts)."""

from pydantic import JsonValue

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_projection import ProjectedOutput
from fatebridge.core.receipt_models import RunMetadata


class Activation(PartialOutput):
    body: str | None = None
    longitude: float | None = None
    longitude_speed: float | None = None
    ephemeris_model: str | None = None
    return_flags: int | None = None
    native_return_flag_model: str | None = None
    derived_from: str | None = None
    derivation_source_longitude: float | None = None
    gate: int | None = None
    center: str | None = None
    line: int | None = None
    color: int | None = None
    tone: int | None = None
    base: int | None = None
    tone_orientation: str | None = None
    gate_start_longitude: float | None = None
    line_boundary_distance_degrees: float | None = None
    base_boundary_distance_arcseconds: float | None = None


class Activations(PartialOutput):
    personality: list[Activation] | None = None
    design: list[Activation] | None = None


class HDChannel(PartialOutput):
    id: str | None = None
    gates: list[int] | None = None
    centers: list[str] | None = None
    circuit: str | None = None
    personality_complete: bool | None = None
    design_complete: bool | None = None
    mixed_only: bool | None = None


class HDCenter(PartialOutput):
    status: str | None = None
    activated_gates: list[int] | None = None


class HDDefinition(PartialOutput):
    kind: str | None = None
    components: list[list[str]] | None = None
    single_gate_bridges: list[int] | None = None


class HDCircuitEntry(PartialOutput):
    id: str | None = None
    group: str | None = None
    channel_ids: list[str] | None = None
    channel_count: int | None = None


class HDCircuitry(PartialOutput):
    defined_channel_count: int | None = None
    circuits: list[HDCircuitEntry] | None = None
    group_channel_counts: dict[str, int] | None = None
    integration: dict[str, JsonValue] | None = None


class BodyGraph(PartialOutput):
    type: str | None = None
    subtype: str | None = None
    authority: str | None = None
    strategy: str | None = None
    motor_to_throat: bool | None = None
    definition: HDDefinition | None = None
    centers: dict[str, HDCenter] | None = None
    channels: list[HDChannel] | None = None
    circuitry: HDCircuitry | None = None
    activated_gates: list[int] | None = None
    hanging_gates: list[int] | None = None
    gate_sources: dict[str, list[str]] | None = None


class DesignSolver(PartialOutput):
    target_solar_arc_degrees: float | None = None
    residual_degrees: float | None = None
    bracket_width_seconds: float | None = None
    days_before_birth: float | None = None
    iterations: int | None = None
    method: str | None = None
    civil_elapsed_days: float | None = None
    birth_jd_tt: float | None = None
    design_jd_tt: float | None = None
    utc_is_leap_second: bool | None = None
    utc_label_status: str | None = None


class HDTimeScale(PartialOutput):
    jd_tt: float | None = None
    jd_ut1: float | None = None
    method: str | None = None
    future_leap_seconds_assumed_unchanged: bool | None = None
    utc_is_leap_second: bool | None = None
    utc_label_status: str | None = None


class HDTimeScales(PartialOutput):
    personality: HDTimeScale | None = None
    design: HDTimeScale | None = None


class IncarnationCross(PartialOutput):
    gates: list[int] | None = None
    order: list[str] | None = None
    angle: str | None = None
    name: str | None = None
    short_name: str | None = None
    name_status: str | None = None
    source_pdf_page_one_based: int | None = None


class HDLineFixing(PartialOutput):
    side: str | None = None
    body: str | None = None
    gate: int | None = None
    line: int | None = None
    calculation_path: str | None = None
    gate_name: str | None = None
    exaltation_planet: str | None = None
    detriment_planet: str | None = None
    polarity_kind: str | None = None
    status: str | None = None
    fixing_state: str | None = None
    recipient_kind: str | None = None
    fixing_planets: dict[str, JsonValue] | None = None


class HDDepthEvidence(PartialOutput):
    line_fixings: list[HDLineFixing] | None = None
    fixing_summary: dict[str, JsonValue] | None = None
    channel_identifiers: list[dict[str, JsonValue]] | None = None


class HDVariables(PartialOutput):
    status: str | None = None
    code: str | None = None
    arrows: list[dict[str, JsonValue]] | None = None
    notation_order: list[str] | None = None
    phs_determination: dict[str, JsonValue] | None = None
    environment: dict[str, JsonValue] | None = None
    motivation: dict[str, JsonValue] | None = None
    view: dict[str, JsonValue] | None = None
    cognition: dict[str, JsonValue] | None = None
    sense: dict[str, JsonValue] | None = None
    personality_colors: dict[str, JsonValue] | None = None


class HumanDesignOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    engine: str | None = None
    method_id: str | None = None
    name: str | None = None
    birth_utc: str | None = None
    birth_clock_evidence: dict[str, JsonValue] | None = None
    design_utc: str | None = None
    design_solver: DesignSolver | None = None
    time_scales: HDTimeScales | None = None
    calculation_policy: dict[str, JsonValue] | None = None
    activations: Activations | None = None
    variables: HDVariables | None = None
    bodygraph: BodyGraph | None = None
    definition_bridging: dict[str, JsonValue] | None = None
    profile: str | None = None
    incarnation_cross: IncarnationCross | None = None
    depth_evidence: HDDepthEvidence | None = None
    line_fixings: list[HDLineFixing] | None = None
    cycle_context: dict[str, JsonValue] | None = None
    cycle_summary: dict[str, JsonValue] | None = None
    time_sensitivity: dict[str, JsonValue] | None = None
    transit_overlay: dict[str, JsonValue] | None = None
    composite: dict[str, JsonValue] | None = None
    summary: str | None = None

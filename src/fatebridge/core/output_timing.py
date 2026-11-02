"""Projectable structural evidence for the shared BaZi timing engine."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import Field, model_validator

from fatebridge.core.output_base import PartialOutput
from fatebridge.core.output_hidden_carriers import (
    HiddenCarrierRelations,
    TemporalHiddenCarrier,
)
from fatebridge.core.output_timing_carriers import TimingCarrier, TimingCarrierSummary


class AnalysisReference(PartialOutput):
    method_id: Optional[Literal["bazi_analysis_instant_v1"]] = None
    basis: Optional[
        Literal[
            "implicit_execution_clock",
            "explicit_components",
            "legacy_partial_components",
            "explicit_age_reference",
        ]
    ] = None
    analysis_datetime: Optional[str] = None
    utc_datetime: Optional[str] = None
    timezone: Optional[str] = None
    fold: Optional[int] = Field(default=None, ge=0, le=1)
    precision: Optional[Literal["execution_clock", "minute"]] = None
    provided_fields: Optional[List[str]] = None
    defaulted_from_clock: Optional[List[str]] = None
    fixed_defaults: Optional[Dict[str, int]] = None
    scope: Optional[str] = None


class TimingNode(PartialOutput):
    id: Optional[str] = None
    scope: Optional[str] = None
    layer: Optional[str] = None
    stem: Optional[str] = None
    branch: Optional[str] = None
    pillar: Optional[str] = None


class TimingRelation(PartialOutput):
    id: Optional[str] = None
    rule_id: Optional[str] = None
    participants: Optional[List[str]] = None
    scope: Optional[str] = None
    status: Optional[str] = None
    transformation: Optional[str] = None
    complete: Optional[bool] = None
    source: Optional[str] = None
    target: Optional[str] = None
    group: Optional[str] = None
    bureau: Optional[str] = None
    traditional_label: Optional[str] = None
    definition: Optional[str] = None


class TimingInteractions(PartialOutput):
    method_id: Optional[str] = None
    assessment_status: Optional[str] = None
    nodes: Optional[List[TimingNode]] = None
    ten_god_context: Optional[List[Dict[str, Any]]] = None
    pillar_carriers: Optional[List[TimingCarrier]] = None
    pillar_carrier_summary: Optional[List[TimingCarrierSummary]] = None
    pillar_carrier_scope: Optional[str] = None
    pillar_carrier_source: Optional[Dict[str, str]] = None
    hidden_target_reference: Optional[HiddenCarrierRelations] = None
    hidden_target_carriers: Optional[List[TemporalHiddenCarrier]] = None
    relations: Optional[List[TimingRelation]] = None
    rulesets: Optional[List[Dict[str, str]]] = None
    rule_trace: Optional[List[str]] = None
    coverage: Optional[Dict[str, List[str]]] = None
    interpretation_scope: Optional[str] = None

    @model_validator(mode="after")
    def same_receipt_summary(self) -> "TimingInteractions":
        if self.pillar_carriers is not None and self.pillar_carrier_summary is not None:
            detailed = {
                r.node_id: r for r in self.pillar_carriers if r.node_id is not None
            }
            for row in self.pillar_carrier_summary:
                if row.node_id not in detailed:
                    continue
                raw = detailed[row.node_id]
                for key in (
                    "pillar",
                    "principal_relation",
                    "own_hidden_root_present",
                    "branch_covered_if_desired",
                    "stem_pressure_if_desired",
                    "effective_force_status",
                ):
                    shown, actual = getattr(row, key), getattr(raw, key)
                    if shown is not None and actual is not None and shown != actual:
                        raise ValueError("承载摘要必须忠于同次明细")
                if (
                    row.external_natal_root_count is not None
                    and raw.external_natal_roots is not None
                    and row.external_natal_root_count != len(raw.external_natal_roots)
                ):
                    raise ValueError("外援根摘要数量必须忠于同次原局根明细")
        return self


class PillarsCandidate(PartialOutput):
    pillars: Optional[Dict[str, str]] = None
    first_sample_at: Optional[str] = None
    last_sample_at: Optional[str] = None
    sample_count: Optional[int] = Field(
        default=None, description="原分钟网格命中数；0不排除事件探针候选，不是概率"
    )
    event_probe_count: Optional[int] = Field(
        default=None, description="独立计数的派生事件探针，不是观测频率或概率"
    )
    first_event_probe_at: Optional[str] = None
    last_event_probe_at: Optional[str] = None
    evidence_sources: Optional[
        List[Literal["minute_grid", "event_probe", "dayun_event_probe"]]
    ] = None


class BirthTimeEvent(PartialOutput):
    kind: Optional[
        Literal[
            "jie",
            "civil_clock",
            "solar_clock",
            "dayun_nominal_month_carry",
            "dayun_civil_clock",
            "dayun_future_civil_gap_end",
            "dayun_future_civil_fold_end",
            "dayun_analysis_moment",
            "dayun_decade_leap_clip",
        ]
    ] = None
    name: Optional[str] = None
    lower_utc: Optional[str] = None
    upper_utc: Optional[str] = None
    at_utc: Optional[str] = None
    bracket_width_seconds: Optional[float] = Field(
        default=None, description="计算括区间宽度，不是物理精度或出生记录误差界"
    )
    source: Optional[Dict[str, str]] = None


class BirthTimeEventProbe(PartialOutput):
    instant_utc: Optional[str] = None
    civil_datetime: Optional[str] = None
    corrected_clock_datetime: Optional[str] = None
    pillars: Optional[Dict[str, str]] = None


class BirthTimeEventRegion(PartialOutput):
    start_utc: Optional[str] = None
    end_utc: Optional[str] = None
    end_inclusive: Optional[bool] = None
    probe_index: Optional[int] = Field(
        default=None, description="区间代表探针在probes中的下标；不认证区间内完整稳定性"
    )


class BirthTimeEventOrder(PartialOutput):
    event_indices: Optional[List[int]] = None
    lower_utc: Optional[str] = None
    upper_utc: Optional[str] = None
    reason: Optional[str] = None


class BirthTimeEventAnalysis(PartialOutput):
    method_id: Optional[Literal["natal_event_boundary_probes_v1"]] = None
    status: Optional[Literal["partial_unresolved_event_order", "calculated_probes"]] = (
        None
    )
    clock_mode: Optional[str] = None
    range_basis: Optional[str] = None
    raw_clock_scan_step_seconds: Optional[int] = None
    apparent_root_bracket_max_seconds: Optional[float] = None
    monotonic_at_minute_anchors: Optional[bool] = None
    coverage_scope: Optional[str] = None
    events: Optional[List[BirthTimeEvent]] = None
    regions: Optional[List[BirthTimeEventRegion]] = None
    probes: Optional[List[BirthTimeEventProbe]] = None
    probe_count: Optional[int] = None
    endpoint_probe_indices: Optional[List[int]] = None
    unresolved_event_orders: Optional[List[BirthTimeEventOrder]] = None
    unresolved_layers: Optional[List[str]] = None
    continuous_completeness_certified: Optional[Literal[False]] = None
    physical_precision_certified: Optional[Literal[False]] = None
    interpretation_scope: Optional[str] = None


class DayunCandidate(PartialOutput):
    direction: Optional[str] = None
    status: Optional[str] = None
    period: Optional[int] = None
    pillar: Optional[str] = None


class DayunFutureClockScan(PartialOutput):
    status: Optional[
        Literal[
            "not_applicable_explicit_age",
            "fixed_offset",
            "unavailable_clock_window",
            "calculated",
        ]
    ] = None
    timezone: Optional[str] = None
    analysis_utc_day: Optional[str] = None
    scan_start_utc: Optional[str] = None
    scan_end_utc: Optional[str] = None
    forward_gap_count: Optional[int] = None
    backward_fold_count: Optional[int] = None
    scan_step_seconds: Optional[int] = None
    continuous_completeness_certified: Optional[Literal[False]] = None
    physical_precision_certified: Optional[Literal[False]] = None


class DayunBoundaryClockWindow(PartialOutput):
    lower_utc: Optional[str] = None
    upper_utc: Optional[str] = None
    decade_boundary_index: Optional[int] = None
    projected_wall_start: Optional[str] = None
    projected_wall_end: Optional[str] = None
    scan_start_utc: Optional[str] = None
    scan_end_utc: Optional[str] = None
    forward_gap_count: Optional[int] = None


class DayunBoundaryClockScan(PartialOutput):
    status: Optional[Literal["fixed_offset", "calculated"]] = None
    timezone: Optional[str] = None
    scan_basis: Optional[str] = None
    boundary_count: Optional[int] = None
    scan_step_seconds: Optional[int] = None
    windows: Optional[List[DayunBoundaryClockWindow]] = None
    continuous_completeness_certified: Optional[Literal[False]] = None
    physical_precision_certified: Optional[Literal[False]] = None


class DayunBirthEventAnalysis(PartialOutput):
    method_id: Optional[
        Literal[
            "dayun_nominal_month_carry_probes_v1",
            "dayun_calendar_and_future_gap_probes_v2",
            "dayun_analysis_clipping_and_civil_probes_v3",
            "dayun_all_boundary_gap_and_analysis_probes_v4",
        ]
    ] = None
    status: Optional[Literal["calculated_probes", "partial_unresolved_cells"]] = None
    range_basis: Optional[str] = None
    clock_basis: Optional[str] = None
    nominal_month_carry_seconds: Optional[int] = None
    guard_probe_offsets_microseconds: Optional[List[int]] = None
    events: Optional[List[BirthTimeEvent]] = None
    probes: Optional[List[BirthTimeEventProbe]] = None
    probe_count: Optional[int] = None
    future_clock_scan: Optional[DayunFutureClockScan] = None
    boundary_clock_scan: Optional[DayunBoundaryClockScan] = None
    unresolved_cells: Optional[List[BirthTimeEventOrder]] = None
    unresolved_layers: Optional[List[str]] = None
    continuous_completeness_certified: Optional[Literal[False]] = None
    physical_precision_certified: Optional[Literal[False]] = None
    interpretation_scope: Optional[str] = None


class DayunBoundaryRange(PartialOutput):
    direction: Optional[str] = None
    period: Optional[int] = None
    pillar: Optional[str] = None
    earliest_start_at: Optional[str] = None
    latest_start_at: Optional[str] = None
    earliest_end_at: Optional[str] = None
    latest_end_at: Optional[str] = None


class BirthTimeSensitivity(PartialOutput):
    method_id: Optional[str] = None
    status: Optional[str] = None
    status_scope: Optional[str] = None
    dayun_assessment_status: Optional[str] = None
    unavailable_fields: Optional[List[str]] = None
    boundary_ranges_vary: Optional[bool] = None
    uncertainty_minutes: Optional[int] = None
    sample_count: Optional[int] = Field(
        default=None, description="仅原分钟网格数量，不含额外事件探针，不是概率分母"
    )
    event_probe_count: Optional[int] = Field(
        default=None,
        description="事件探针数量，可能与分钟网格重叠；合并数量见total_assessed_instants",
    )
    natal_event_probe_count: Optional[int] = None
    dayun_event_probe_count: Optional[int] = None
    additional_event_probe_count: Optional[int] = None
    total_assessed_instants: Optional[int] = None
    birth_at_range: Optional[Dict[str, str]] = None
    sampling_policy: Optional[str] = None
    boundary_range_scope: Optional[str] = None
    event_analysis: Optional[BirthTimeEventAnalysis] = None
    dayun_event_analysis: Optional[DayunBirthEventAnalysis] = None
    pillars_candidates: Optional[List[PillarsCandidate]] = None
    current_dayun_candidates: Optional[List[DayunCandidate]] = None
    dayun_boundary_ranges: Optional[List[DayunBoundaryRange]] = None
    affected_fields: Optional[List[str]] = None
    interpretation_scope: Optional[str] = None

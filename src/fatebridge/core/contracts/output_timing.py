"""Projectable structural evidence for the shared BaZi timing engine."""

from typing import Literal

from pydantic import Field, JsonValue, ValidationInfo, model_validator

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput
from fatebridge.core.contracts.output_civil_time import CivilPointEvidence
from fatebridge.core.contracts.output_classical_roots import ClassicalRoot
from fatebridge.core.contracts.output_hidden_carriers import (
    HiddenCarrierRelations,
    TemporalHiddenCarrier,
)
from fatebridge.core.contracts.output_timing_carriers import (
    TimingCarrier,
    TimingCarrierSummary,
)
from fatebridge.core.contracts.output_timing_strength import TimingStrengthProjection
from fatebridge.core.timing_roots import BRANCH_RELATION_KINDS
from fatebridge.utils.civil_time import ZonedCalendar, nominal_calendar_bracket


class AnalysisReference(PartialOutput):
    method_id: Literal["bazi_analysis_instant_v1"] | None = None
    basis: (
        Literal[
            "implicit_execution_clock",
            "explicit_components",
            "declared_partial_components",
            "explicit_age_reference",
        ]
        | None
    ) = None
    analysis_datetime: str | None = None
    utc_datetime: str | None = None
    timezone: str | None = None
    fold: int | None = Field(default=None, ge=0, le=1)
    precision: Literal["execution_clock", "minute"] | None = None
    provided_fields: list[str] | None = None
    defaulted_from_clock: list[str] | None = None
    fixed_defaults: dict[str, int] | None = None
    scope: str | None = None


class TimingNode(PartialOutput):
    id: str | None = None
    scope: str | None = None
    layer: str | None = None
    stem: str | None = None
    branch: str | None = None
    pillar: str | None = None


class TimingRelation(PartialOutput):
    id: str | None = None
    rule_id: str | None = None
    participants: list[str] | None = None
    scope: str | None = None
    status: str | None = None
    transformation: str | None = None
    complete: bool | None = None
    source: str | None = None
    target: str | None = None
    group: str | None = None
    bureau: str | None = None
    traditional_label: str | None = None
    definition: str | None = None


class TimingRootObservation(PartialOutput):
    stem_node_id: str | None = None
    branch_node_id: str | None = None
    classification: ClassicalRoot | None = None
    branch_relation_ids: list[str] | None = None


class TimingRootContext(PartialOutput):
    method_id: Literal["natal_timing_root_support_v1"] | None = None
    month_command_node_id: Literal["natal.month"] | None = None
    day_master_roots: list[TimingRootObservation] | None = None
    timing_stem_natal_roots: list[TimingRootObservation] | None = None
    effective_force_status: Literal["not_adjudicated"] | None = None
    source: dict[str, JsonValue] | None = None
    scope: str | None = None


class TimingInteractions(PartialOutput):
    method_id: str | None = None
    assessment_status: str | None = None
    nodes: list[TimingNode] | None = None
    ten_god_context: list[dict[str, OpenJsonValue]] | None = None
    pillar_carriers: list[TimingCarrier] | None = None
    pillar_carrier_summary: list[TimingCarrierSummary] | None = None
    pillar_carrier_scope: str | None = None
    pillar_carrier_source: dict[str, str] | None = None
    hidden_target_reference: HiddenCarrierRelations | None = None
    hidden_target_carriers: list[TemporalHiddenCarrier] | None = None
    relations: list[TimingRelation] | None = None
    root_context: TimingRootContext | None = None
    strength_projection: TimingStrengthProjection | None = None
    rulesets: list[dict[str, str]] | None = None
    rule_trace: list[str] | None = None
    coverage: dict[str, list[str]] | None = None
    interpretation_scope: str | None = None

    @model_validator(mode="after")
    def same_receipt_summary(self) -> "TimingInteractions":
        if self.pillar_carriers is not None and self.pillar_carrier_summary is not None:
            detailed = {
                r.node_id: r for r in self.pillar_carriers if r.node_id is not None
            }
            for row in self.pillar_carrier_summary:
                if row.node_id not in detailed:
                    continue
                else:
                    pass
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
                    else:
                        pass
                if (
                    row.external_natal_root_count is not None
                    and raw.external_natal_roots is not None
                    and row.external_natal_root_count != len(raw.external_natal_roots)
                ):
                    raise ValueError("外援根摘要数量必须忠于同次原局根明细")
                else:
                    pass
        else:
            pass
        if self.root_context is not None:
            roots = (self.root_context.day_master_roots or []) + (
                self.root_context.timing_stem_natal_roots or []
            )
            nodes = {n.id: n for n in self.nodes or [] if n.id is not None}
            relations = {r.id: r for r in self.relations or [] if r.id is not None}
            for root in roots:
                for node_id, component in (
                    (root.stem_node_id, "stem"),
                    (root.branch_node_id, "branch"),
                ):
                    if node_id is None or self.nodes is None:
                        continue
                    else:
                        pass
                    if node_id not in nodes:
                        if all(n.id is not None for n in self.nodes):
                            raise ValueError("时运根气必须引用同次实际节点")
                        else:
                            pass
                        continue
                    else:
                        pass
                    if root.classification is not None:
                        shown = getattr(root.classification, component)
                        actual = getattr(nodes[node_id], component)
                        if shown is not None and actual is not None and shown != actual:
                            raise ValueError("时运根类必须匹配所引用节点的干支")
                        else:
                            pass
                    else:
                        pass
                for relation_id in root.branch_relation_ids or []:
                    if self.relations is None:
                        continue
                    else:
                        pass
                    relation = relations.get(relation_id)
                    if relation is None:
                        if all(r.id is not None for r in self.relations):
                            raise ValueError("根位触点必须引用同次地支关系")
                        else:
                            pass
                        continue
                    else:
                        pass
                    if (
                        relation.rule_id is not None
                        and relation.rule_id not in BRANCH_RELATION_KINDS
                    ):
                        raise ValueError("根位触点必须引用同次地支关系")
                    else:
                        pass
                    if (
                        root.branch_node_id is not None
                        and relation.participants is not None
                        and root.branch_node_id not in relation.participants
                    ):
                        raise ValueError("根位触点必须实际包含该地支节点")
                    else:
                        pass
        else:
            pass
        return self


class PillarsCandidate(PartialOutput):
    pillars: dict[str, str] | None = None
    first_sample_at: str | None = None
    last_sample_at: str | None = None
    sample_count: int | None = Field(
        default=None, description="原分钟网格命中数；0不排除事件探针候选，不是概率"
    )
    event_probe_count: int | None = Field(
        default=None, description="独立计数的派生事件探针，不是观测频率或概率"
    )
    first_event_probe_at: str | None = None
    last_event_probe_at: str | None = None
    evidence_sources: (
        list[Literal["minute_grid", "event_probe", "dayun_event_probe"]] | None
    ) = None


class BirthTimeEvent(PartialOutput):
    kind: (
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
        | None
    ) = None
    name: str | None = None
    lower_utc: str | None = None
    upper_utc: str | None = None
    at_utc: str | None = None
    bracket_width_seconds: float | None = Field(
        default=None, description="计算括区间宽度，不是物理精度或出生记录误差界"
    )
    civil_point: CivilPointEvidence | None = None
    reference_point: CivilPointEvidence | None = None
    bracket_basis: Literal["nominal_gregorian_microsecond_enclosure_v1"] | None = Field(
        default=None,
        description="仅包住所声明名义民用坐标；不认证实际日历墙钟跃变或连续完备性",
    )
    source: dict[str, str] | None = None

    @model_validator(mode="after")
    def preserve_nominal_point_bracket(self, info: ValidationInfo) -> "BirthTimeEvent":
        if self.bracket_basis != "nominal_gregorian_microsecond_enclosure_v1":
            return self
        else:
            pass
        if info.context and info.context.get("full_result"):
            if (
                self.civil_point is None
                or self.lower_utc is None
                or self.upper_utc is None
            ):
                raise ValueError("完整名义事件括区间须保留主点及两端标签")
            else:
                pass
            if (
                self.kind == "dayun_nominal_month_carry"
                and self.reference_point is None
            ):
                raise ValueError("完整名义月进位须保留同次实际参考节令主点")
            else:
                pass
        else:
            pass
        day = self.civil_point.known_day() if self.civil_point is not None else None
        if day is None:
            return self
        else:
            pass
        expected_lower, expected_upper = nominal_calendar_bracket(day)
        if self.lower_utc is not None:
            lower = ZonedCalendar.from_isoformat(self.lower_utc).utc
            if lower != expected_lower:
                raise ValueError("名义事件下端须为保留坐标的微秒格点下包")
            else:
                pass
        else:
            pass
        if self.upper_utc is not None:
            upper = ZonedCalendar.from_isoformat(self.upper_utc).utc
            if upper != expected_upper:
                raise ValueError("名义事件上端须为保留坐标的微秒格点上包")
            else:
                pass
        else:
            pass
        if self.at_utc is not None:
            if ZonedCalendar.from_isoformat(self.at_utc).utc != expected_upper:
                raise ValueError("名义事件代表标签须为括区间上端，不冒充未舍入主点")
            else:
                pass
        else:
            pass
        if self.bracket_width_seconds is not None:
            width = float(
                (expected_upper.julian_day_exact() - expected_lower.julian_day_exact())
                * 86400
            )
            if self.bracket_width_seconds != width:
                raise ValueError("名义事件括区间宽度须与所声明坐标外包一致")
            else:
                pass
        else:
            pass
        return self


class BirthTimeEventProbe(PartialOutput):
    instant_utc: str | None = None
    civil_datetime: str | None = None
    corrected_clock_datetime: str | None = None
    pillars: dict[str, str] | None = None


class BirthTimeEventRegion(PartialOutput):
    start_utc: str | None = None
    end_utc: str | None = None
    end_inclusive: bool | None = None
    probe_index: int | None = Field(
        default=None, description="区间代表探针在probes中的下标；不认证区间内完整稳定性"
    )


class BirthTimeEventOrder(PartialOutput):
    event_indices: list[int] | None = None
    lower_utc: str | None = None
    upper_utc: str | None = None
    reason: str | None = None


class BirthTimeEventAnalysis(PartialOutput):
    method_id: Literal["natal_event_boundary_probes_v1"] | None = None
    status: Literal["partial_unresolved_event_order", "calculated_probes"] | None = None
    clock_mode: str | None = None
    range_basis: str | None = None
    raw_clock_scan_step_seconds: int | None = None
    apparent_root_bracket_max_seconds: float | None = None
    monotonic_at_minute_anchors: bool | None = None
    coverage_scope: str | None = None
    events: list[BirthTimeEvent] | None = None
    regions: list[BirthTimeEventRegion] | None = None
    probes: list[BirthTimeEventProbe] | None = None
    probe_count: int | None = None
    endpoint_probe_indices: list[int] | None = None
    unresolved_event_orders: list[BirthTimeEventOrder] | None = None
    unresolved_layers: list[str] | None = None
    continuous_completeness_certified: Literal[False] | None = None
    physical_precision_certified: Literal[False] | None = None
    interpretation_scope: str | None = None


class DayunCandidate(PartialOutput):
    direction: str | None = None
    status: str | None = None
    period: int | None = None
    pillar: str | None = None


class DayunFutureClockScan(PartialOutput):
    status: (
        Literal[
            "not_applicable_explicit_age",
            "fixed_offset",
            "unavailable_clock_window",
            "calculated",
        ]
        | None
    ) = None
    timezone: str | None = None
    analysis_utc_day: str | None = None
    scan_start_utc: str | None = None
    scan_end_utc: str | None = None
    forward_gap_count: int | None = None
    backward_fold_count: int | None = None
    scan_step_seconds: int | None = None
    continuous_completeness_certified: Literal[False] | None = None
    physical_precision_certified: Literal[False] | None = None


class DayunBoundaryClockWindow(PartialOutput):
    lower_utc: str | None = None
    upper_utc: str | None = None
    decade_boundary_index: int | None = None
    projected_wall_start: str | None = None
    projected_wall_end: str | None = None
    scan_start_utc: str | None = None
    scan_end_utc: str | None = None
    forward_gap_count: int | None = None


class DayunBoundaryClockScan(PartialOutput):
    status: Literal["fixed_offset", "calculated"] | None = None
    timezone: str | None = None
    scan_basis: str | None = None
    boundary_count: int | None = None
    scan_step_seconds: int | None = None
    windows: list[DayunBoundaryClockWindow] | None = None
    continuous_completeness_certified: Literal[False] | None = None
    physical_precision_certified: Literal[False] | None = None


class DayunBirthEventAnalysis(PartialOutput):
    method_id: (
        Literal[
            "dayun_nominal_month_carry_probes_v1",
            "dayun_calendar_and_future_gap_probes_v2",
            "dayun_analysis_clipping_and_civil_probes_v3",
            "dayun_all_boundary_gap_and_analysis_probes_v4",
        ]
        | None
    ) = None
    status: Literal["calculated_probes", "partial_unresolved_cells"] | None = None
    range_basis: str | None = None
    clock_basis: str | None = None
    nominal_month_carry_seconds: int | None = None
    guard_probe_offsets_microseconds: list[int] | None = None
    events: list[BirthTimeEvent] | None = None
    probes: list[BirthTimeEventProbe] | None = None
    probe_count: int | None = None
    future_clock_scan: DayunFutureClockScan | None = None
    boundary_clock_scan: DayunBoundaryClockScan | None = None
    unresolved_cells: list[BirthTimeEventOrder] | None = None
    unresolved_layers: list[str] | None = None
    continuous_completeness_certified: Literal[False] | None = None
    physical_precision_certified: Literal[False] | None = None
    interpretation_scope: str | None = None


class DayunBoundaryRange(PartialOutput):
    direction: str | None = None
    period: int | None = None
    pillar: str | None = None
    earliest_start_at: str | None = None
    latest_start_at: str | None = None
    earliest_end_at: str | None = None
    latest_end_at: str | None = None


class BirthTimeSensitivity(PartialOutput):
    method_id: str | None = None
    status: str | None = None
    status_scope: str | None = None
    dayun_assessment_status: str | None = None
    unavailable_fields: list[str] | None = None
    boundary_ranges_vary: bool | None = None
    uncertainty_minutes: int | None = None
    sample_count: int | None = Field(
        default=None, description="仅原分钟网格数量，不含额外事件探针，不是概率分母"
    )
    event_probe_count: int | None = Field(
        default=None,
        description="事件探针数量，可能与分钟网格重叠；合并数量见total_assessed_instants",
    )
    natal_event_probe_count: int | None = None
    dayun_event_probe_count: int | None = None
    additional_event_probe_count: int | None = None
    total_assessed_instants: int | None = None
    birth_at_range: dict[str, str] | None = None
    sampling_policy: str | None = None
    boundary_range_scope: str | None = None
    event_analysis: BirthTimeEventAnalysis | None = None
    dayun_event_analysis: DayunBirthEventAnalysis | None = None
    pillars_candidates: list[PillarsCandidate] | None = None
    current_dayun_candidates: list[DayunCandidate] | None = None
    dayun_boundary_ranges: list[DayunBoundaryRange] | None = None
    affected_fields: list[str] | None = None
    interpretation_scope: str | None = None

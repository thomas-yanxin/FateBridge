"""Output contracts and full-anchor validators for BaZi, compatibility, and timing."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, JsonValue, ValidationInfo, model_validator

from fatebridge.core.contracts.base import (
    FULL_FACT,
    OpenJsonValue,
    PartialOutput,
    ProjectedOutput,
)
from fatebridge.core.contracts.common import (
    AnalysisContext,
    CalendarContext,
    CivilPointEvidence,
    FourPillars,
    LunarCalendar,
    PersonInfo,
    SolarTerm,
)
from fatebridge.core.receipt_models import Object, RunMetadata
from fatebridge.utils.civil_time import ZonedCalendar, nominal_calendar_bracket

TOPICS = (
    "career",
    "wealth",
    "health",
    "children",
    "education",
    "personality",
    "relatives",
    "marriage",
    "romance",
)
BAZI_ANCHOR_TOOLS = frozenset(
    ("bazi_overview", "bazi_birth_chart", *("bazi_" + t for t in TOPICS))
)
POSITIONS = ("year", "month", "day", "hour")
Grade = Literal["强", "中和", "弱"]
Role = Literal["person1", "person2"]


class RelationEvidence(PartialOutput):
    kind: str | None = None
    level: Literal["stem", "branch", "pillar"] | None = None
    positions: list[str] | None = None
    characters: list[str] | None = None
    distance: int | None = Field(default=None, ge=1, le=3)
    effect_status: Literal["relation_only"] | None = None
    candidate_element: str | None = None
    detail: str | None = None
    group: str | None = None
    complete: bool | None = None


class GroupEvidence(PartialOutput):
    kind: Literal["三合", "三会", "三刑", "半合", "拱合", "拱会"] | None = None
    positions: list[str] | None = None
    branches: list[str] | None = None
    bureau: str | None = None
    arched: str | None = None
    effect_status: Literal["relation_only"] | None = None


class DominantStructure(PartialOutput):
    key: str | None = None
    label: str | None = None
    category: str | None = None
    selection_rule: str | None = None
    month_stem: str | None = None
    month_ten_god: str | None = None
    formation_status: str | None = None
    obstructions: list[str] | None = None
    rescues: list[str] | None = None
    useful_elements: list[str] | None = None
    avoid_elements: list[str] | None = None
    reason: str | None = None


class ClassicalForceSummary(PartialOutput):
    status: str | None = None
    body_strength: Grade | None = None
    ordinary_fuyi_applicable: bool | None = None
    dominant_pattern: str | None = None
    formation_status: str | None = None


class SeasonalClimateInfo(PartialOutput):
    available: bool | None = None
    primary: str | None = None
    secondary: list[str] | None = None
    elements: list[str] | None = None
    primary_present: bool | None = None
    observations: list[dict[str, OpenJsonValue]] | None = None


class EvidenceStructureProfile(PartialOutput):
    assessment_status: (
        Literal["adjudicated", "conditional", "partial", "not_adjudicated"] | None
    ) = None
    dominant_structure: DominantStructure | None = None
    recognized_structures: list[dict[str, OpenJsonValue]] | None = None
    useful_elements: list[str] | None = None
    avoid_elements: list[str] | None = None
    neutral_elements: list[str] | None = None
    useful_ten_gods: list[str] | None = None
    seasonal_climate: SeasonalClimateInfo | None = None
    classical_adjudication: ClassicalForceSummary | None = None
    harmony_patterns: dict[str, OpenJsonValue] | None = None
    clash_patterns: dict[str, OpenJsonValue] | None = None


class DayMaster(PartialOutput):
    stem: str | None = None
    element: str | None = None
    polarity: str | None = None
    strength: str | None = None
    support_share: float | None = None
    life_stages: dict[str, str] | None = None
    changsheng_school: str | None = None
    classical_adjudication: Annotated[ClassicalForceSummary | None, FULL_FACT] = None
    engineering_index: dict[str, OpenJsonValue] | None = None


class BaziBirth(PartialOutput):
    engine: str | None = None
    time_algorithm: str | None = None
    analysis_date: str | None = None
    person_info: PersonInfo | None = None
    four_pillars: FourPillars | None = None
    three_origins: dict[str, OpenJsonValue] | None = None
    taixi: dict[str, OpenJsonValue] | None = None
    day_master: DayMaster | None = None
    element_distribution: Object | None = None
    element_seasonal_phase: dict[str, str] | None = None
    favorable_elements: list[JsonValue] | None = None
    favorable_elements_status: Annotated[str | None, FULL_FACT] = None
    avoid_elements: list[str] | None = None
    structure_profile: EvidenceStructureProfile | None = None
    intra_month_duty: dict[str, OpenJsonValue] | None = None
    ten_gods: Object | None = None
    patterns: Object | None = None
    kongwang: dict[str, OpenJsonValue] | None = None
    shensha: list[dict[str, OpenJsonValue]] | None = None
    shensha_triggered: list[dict[str, OpenJsonValue]] | None = None
    three_origins_shensha: list[dict[str, OpenJsonValue]] | None = None
    calendar_context: CalendarContext | None = None
    analysis_calendar_context: CalendarContext | None = None
    timing_overview: dict[str, OpenJsonValue] | None = None
    coverage: dict[str, OpenJsonValue] | None = None


class TimingOverrides(PartialOutput):
    dayun_pillar: bool | None = None
    liunian_pillar: bool | None = None


class DimensionTimingContext(PartialOutput):
    analysis_date: str | None = None
    analysis_datetime: str | None = None
    timezone: str | None = None
    input_granularity: Literal["date"] | None = None
    anchor_policy: Literal["local_midnight"] | None = None
    year_boundary_policy: Literal["lichun_exact_moment"] | None = None
    boundary_status: Literal["year_boundary_day", "not_year_boundary_day"] | None = None
    boundaries_on_date: list[SolarTerm] | None = None
    dayun_pillar: str | None = None
    liunian_pillar: str | None = None
    source: str | None = None
    dayun_status: str | None = None
    message: str | None = None
    dayun_age: float | None = None
    dayun_selection_basis: str | None = None
    dayun_start_at: str | None = None
    dayun_end_at: str | None = None
    child_limit: dict[str, OpenJsonValue] | None = None
    xiaoyun_pillar: str | None = None
    xiaoyun: dict[str, OpenJsonValue] | None = None
    overridden: TimingOverrides | None = None


class TopicMarker(PartialOutput):
    name: str | None = None
    anchor: str | None = None
    target_branch: str | None = None
    direction: str | None = None
    natal_positions: list[str] | None = None
    timing_layers: list[str] | None = None


class TopicFacts(PartialOutput):
    topic: str | None = None
    four_pillars: FourPillars | None = None
    day_master: dict[str, OpenJsonValue] | None = None
    favorable_elements: list[str] | None = None
    avoid_elements: list[str] | None = None
    dominant_structure: str | None = None
    structure_detail: DominantStructure | None = None
    seasonal_climate: dict[str, OpenJsonValue] | None = None
    element_distribution: dict[str, float] | None = None
    element_seasonal_phase: dict[str, str] | None = None
    natal_stars: list[dict[str, OpenJsonValue]] | None = None
    markers: list[TopicMarker] | None = None
    palace_relations: dict[str, list[dict[str, OpenJsonValue]]] | None = None
    natal_groups: list[dict[str, OpenJsonValue]] | None = None
    timing_layers: list[dict[str, OpenJsonValue]] | None = None


class DimensionOutput(PartialOutput):
    model_config = ConfigDict(extra="forbid")

    calendar_context: CalendarContext | None = None
    timing_context: DimensionTimingContext | None = None
    topic_facts: TopicFacts | None = None


class PairDayMaster(PartialOutput):
    stem: str | None = None
    element: str | None = None
    polarity: str | None = None
    strength: str | None = None
    support_share: float | None = None
    life_stages: dict[str, str] | None = None
    changsheng_school: str | None = None
    classical_adjudication: ClassicalForceSummary | None = None
    engineering_index: dict[str, OpenJsonValue] | None = None


class PairPreference(PartialOutput):
    assessment_status: str | None = None
    dominant_structure: str | None = None
    useful_elements: list[str] | None = None
    avoid_elements: list[str] | None = None
    neutral_elements: list[str] | None = None


class PairNatalContext(PartialOutput):
    four_pillars: FourPillars | None = None
    calendar_context: CalendarContext | None = None
    element_distribution: dict[str, float] | None = None
    day_master: PairDayMaster | None = None
    preference_assessment: PairPreference | None = None


class CrossChartGroup(PartialOutput):
    kind: Literal["三合", "三会", "三刑", "半合", "拱合", "拱会"] | None = None
    positions: list[str] | None = None
    branches: list[str] | None = None
    bureau: str | None = None
    arched: str | None = None
    effect_status: Literal["relation_only"] | None = None
    source_scope: Literal["cross_person", "person1", "person2"] | None = None
    natal_matches: list[Role] | None = None


class CrossChartPunishment(PartialOutput):
    source: str | None = None
    target: str | None = None
    branches: list[str] | None = None


class CrossChartRelations(PartialOutput):
    pairs: list[RelationEvidence] | None = None
    groups: list[CrossChartGroup] | None = None
    directional_punishments: list[CrossChartPunishment] | None = None


class CrossChartStar(PartialOutput):
    pillar: str | None = None
    stem: str | None = None
    location: Literal["天干", "地支藏干"] | None = None
    ten_god: str | None = None


class DirectionalTenGods(PartialOutput):
    source: Role | None = None
    target: Role | None = None
    target_day_stem: str | None = None
    stars: list[CrossChartStar] | None = None


class SourceAnnotationComparison(PartialOutput):
    status: str | None = None
    computed_strength: Grade | None = None
    literal_match_count: int | None = None
    known_annotation_count: int | None = None
    unknown_or_unannotated_count: int | None = None
    agreeing_known_count: int | None = None
    differing_known_count: int | None = None
    retained_expected_strengths: list[Grade] | None = None
    records: list[dict[str, OpenJsonValue]] | None = None
    reference_index: dict[str, OpenJsonValue] | None = None
    calculation_overridden: Literal[False] | None = None


class SourceCurrentCalculation(PartialOutput):
    strength_level: Grade | None = None
    day_master: dict[str, OpenJsonValue] | None = None
    favorable_elements: list[str] | None = None
    dominant_structure: dict[str, OpenJsonValue] | None = None


class LiteralSourceInputContext(PartialOutput):
    pillars: list[str] | None = None
    valid_sexagenary_characters: bool | None = None
    input_kind: Literal["literal_four_pillars"] | None = None
    birth_datetime_reconstructed: Literal[False] | None = None


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
    source: str | None = None
    target: str | None = None
    group: str | None = None
    bureau: str | None = None
    detail: str | None = None
    complete: bool | None = None
    traditional_label: str | None = None


class TimingInteractions(PartialOutput):
    nodes: list[TimingNode] | None = None
    ten_god_context: list[dict[str, OpenJsonValue]] | None = None
    relations: list[TimingRelation] | None = None


class PillarsCandidate(PartialOutput):
    pillars: dict[str, str] | None = None
    first_sample_at: str | None = None
    last_sample_at: str | None = None
    sample_count: int | None = None
    event_probe_count: int | None = None
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
    bracket_width_seconds: float | None = None
    civil_point: CivilPointEvidence | None = None
    reference_point: CivilPointEvidence | None = None
    bracket_basis: Literal["nominal_gregorian_microsecond_enclosure_v1"] | None = None
    source: dict[str, str] | None = None

    @model_validator(mode="after")
    def preserve_nominal_point_bracket(self, info: ValidationInfo) -> "BirthTimeEvent":
        if self.bracket_basis != "nominal_gregorian_microsecond_enclosure_v1":
            return self
        if info.context and info.context.get("full_result"):
            if (
                self.civil_point is None
                or self.lower_utc is None
                or self.upper_utc is None
            ):
                raise ValueError("完整名义事件括区间须保留主点及两端标签")
            if (
                self.kind == "dayun_nominal_month_carry"
                and self.reference_point is None
            ):
                raise ValueError("完整名义月进位须保留同次实际参考节令主点")
        day = self.civil_point.known_day() if self.civil_point is not None else None
        if day is None:
            return self
        expected_lower, expected_upper = nominal_calendar_bracket(day)
        if self.lower_utc is not None:
            lower = ZonedCalendar.from_isoformat(self.lower_utc).utc
            if lower != expected_lower:
                raise ValueError("名义事件下端须为保留坐标的微秒格点下包")
        if self.upper_utc is not None:
            upper = ZonedCalendar.from_isoformat(self.upper_utc).utc
            if upper != expected_upper:
                raise ValueError("名义事件上端须为保留坐标的微秒格点上包")
        if self.at_utc is not None:
            if ZonedCalendar.from_isoformat(self.at_utc).utc != expected_upper:
                raise ValueError("名义事件代表标签须为括区间上端，不冒充未舍入主点")
        if self.bracket_width_seconds is not None:
            width = float(
                (expected_upper.julian_day_exact() - expected_lower.julian_day_exact())
                * 86400
            )
            if self.bracket_width_seconds != width:
                raise ValueError("名义事件括区间宽度须与所声明坐标外包一致")
        return self


class BirthTimeSensitivity(PartialOutput):
    method_id: str | None = None
    status: str | None = None
    status_scope: str | None = None
    dayun_assessment_status: str | None = None
    unavailable_fields: list[str] | None = None
    boundary_ranges_vary: bool | None = None
    uncertainty_minutes: int | None = None
    sample_count: int | None = None
    event_probe_count: int | None = None
    natal_event_probe_count: int | None = None
    dayun_event_probe_count: int | None = None
    additional_event_probe_count: int | None = None
    total_assessed_instants: int | None = None
    birth_at_range: dict[str, str] | None = None
    sampling_policy: str | None = None
    boundary_range_scope: str | None = None
    event_analysis: dict[str, OpenJsonValue] | None = None
    dayun_event_analysis: dict[str, OpenJsonValue] | None = None
    pillars_candidates: list[PillarsCandidate] | None = None
    current_dayun_candidates: list[dict[str, OpenJsonValue]] | None = None
    dayun_boundary_ranges: list[dict[str, OpenJsonValue]] | None = None
    affected_fields: list[str] | None = None
    interpretation_scope: str | None = None


def _object(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("完整八字结果缺少计算依据对象")
    return value


def _keys(
    value: object, names: str, *, nullable: set[str] | None = None
) -> Mapping[str, object]:
    obj = _object(value)
    for key in names.split():
        if key not in obj or (obj[key] is None and key not in (nullable or set())):
            raise ValueError("完整八字结果缺少计算依据字段：" + key)
        entry = obj[key]
        if isinstance(entry, str) and not entry.strip():
            raise ValueError("完整八字计算依据不能为空字符串：" + key)
    return obj


def _calendar(value: object) -> None:
    c = _keys(
        value,
        "timezone solar_datetime current_solar_term next_solar_term solar_term_delta bazi_month_boundary lunar_calendar lunar_calendar_support",
        nullable={"lunar_calendar"},
    )
    support = _keys(c["lunar_calendar_support"], "supported supported_range")
    _keys(support["supported_range"], "start end")
    if support["supported"] is True:
        _keys(c["lunar_calendar"], "year month day is_leap_month day_ganzhi")
    elif support["supported"] is False:
        _keys(support, "reason")
        if c["lunar_calendar"] is not None:
            raise ValueError("表外农历不能以完整计算结果交付")
    else:
        raise ValueError("完整八字结果须明示农历支持状态")
    month = _keys(
        c["bazi_month_boundary"],
        "branch month_index comparison_datetime elapsed_basis elapsed_seconds_since_start elapsed_seconds_until_next days_since_start days_until_next start_term next_term",
    )
    for term in (
        c["current_solar_term"],
        c["next_solar_term"],
        month["start_term"],
        month["next_term"],
    ):
        evidence = _keys(term, "name timezone resolution_provider ephemeris_model")
        if evidence.get("datetime_utc") is not None:
            _keys(evidence, "datetime_utc civil_point comparison_policy")
        else:
            _keys(evidence, "datetime datetime_with_offset utc_offset_seconds fold")
    _keys(c["solar_term_delta"], "days_since_current days_until_next description")


def _timing(value: object) -> None:
    t = _keys(
        value,
        "source dayun_pillar liunian_pillar overridden",
        nullable={"dayun_pillar"},
    )
    _keys(t["overridden"], "dayun_pillar liunian_pillar")
    if t["source"] != "explicit_pillar_overrides":
        _keys(
            t,
            "analysis_date analysis_datetime timezone input_granularity anchor_policy year_boundary_policy boundary_status boundaries_on_date",
        )


def require_complete_bazi_anchors(key: str, result: Mapping[str, object]) -> None:
    """Validate required anchors on full successful BaZi results."""
    if key not in BAZI_ANCHOR_TOOLS:
        return
    if key in {"bazi_overview", "bazi_birth_chart"}:
        root: object = result if key == "bazi_overview" else result.get("bazi_birth")
        r = _keys(
            root,
            "person_info four_pillars day_master element_distribution favorable_elements favorable_elements_status ten_gods patterns calendar_context structure_profile intra_month_duty",
        )
        _keys(
            r["person_info"],
            "name gender birth_datetime birth_timezone zi_hour_policy",
        )
        coverage = r.get("coverage")
        three_pillar = (
            isinstance(coverage, Mapping)
            and coverage.get("mode") == "three_pillars_hour_unknown"
        )
        expected_positions = ("year", "month", "day") if three_pillar else POSITIONS
        pillars = _keys(
            r["four_pillars"],
            "year month day hour",
            nullable={"hour"} if three_pillar else None,
        )
        for name in expected_positions:
            _keys(pillars[name], "stem branch")
        if three_pillar and pillars.get("hour") is not None:
            raise ValueError("时辰未知三柱模式不得伪造时柱")
        dm = _keys(
            r["day_master"],
            "stem element polarity strength classical_adjudication",
        )
        _keys(r["ten_gods"], " ".join(expected_positions))
        profile = _keys(
            r["structure_profile"],
            "assessment_status dominant_structure useful_elements avoid_elements seasonal_climate classical_adjudication",
        )
        if dm["classical_adjudication"] != profile["classical_adjudication"]:
            raise ValueError("日主与格局须复用同次力量裁定")
        if key == "bazi_birth_chart":
            _keys(
                r,
                "three_origins taixi kongwang shensha three_origins_shensha timing_overview",
            )
    else:
        topic = key.removeprefix("bazi_")
        r = _keys(
            result.get(topic + "_analysis"),
            "calendar_context timing_context topic_facts",
        )
        _timing(r["timing_context"])
        facts = _keys(
            r["topic_facts"],
            "topic four_pillars day_master favorable_elements dominant_structure natal_stars markers timing_layers",
        )
        if facts["topic"] != topic:
            raise ValueError("完整专题依据须对应实际专题")
    _calendar(r["calendar_context"])


# --- Public Tool Output Models (22 BaZi, Compatibility & Timing tools) ---


class CompareBaziSourcesOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: LiteralSourceInputContext | None = None
    analysis_type: str | None = None
    current_calculation: SourceCurrentCalculation | None = None
    four_pillars: FourPillars | None = None
    source_comparison: SourceAnnotationComparison | None = None


class BaziOverviewOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    avoid_elements: list[JsonValue] | None = None
    calendar_context: CalendarContext | None = None
    coverage: Object | None = None
    day_master: DayMaster | None = None
    element_distribution: Object | None = None
    element_seasonal_phase: Object | None = None
    favorable_elements: list[JsonValue] | None = None
    favorable_elements_status: str | None = None
    four_pillars: FourPillars | None = None
    intra_month_duty: Object | None = None
    patterns: Object | list[JsonValue] | None = None
    person_info: PersonInfo | None = None
    structure_profile: EvidenceStructureProfile | None = None
    ten_gods: Object | None = None


class BaziBirthChartOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_type: str | None = None
    bazi_birth: BaziBirth | None = None
    coverage: Object | None = None


class BaziMarriageOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_type: str | None = None
    marriage_analysis: DimensionOutput | None = None


class BaziCareerOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_type: str | None = None
    career_analysis: DimensionOutput | None = None


class BaziWealthOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_type: str | None = None
    wealth_analysis: DimensionOutput | None = None


class BaziHealthOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_type: str | None = None
    health_analysis: DimensionOutput | None = None


class BaziChildrenOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_type: str | None = None
    children_analysis: DimensionOutput | None = None


class BaziEducationOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_type: str | None = None
    education_analysis: DimensionOutput | None = None


class BaziPersonalityOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_type: str | None = None
    personality_analysis: DimensionOutput | None = None


class BaziRelativesOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_type: str | None = None
    relatives_analysis: DimensionOutput | None = None


class BaziRomanceOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_type: str | None = None
    romance_analysis: DimensionOutput | None = None


class BaziCompatibilityOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    relationship_type: (
        Literal["general", "marriage", "friendship", "business", "family"] | None
    ) = None
    person_info: PersonInfo | None = None
    natal_contexts: dict[Role, PairNatalContext] | None = None
    element_relationship: Object | None = None
    nayin_comparison: dict[str, OpenJsonValue] | None = None
    day_pillar_synergy: dict[str, OpenJsonValue] | None = None
    element_complementarity: dict[str, OpenJsonValue] | None = None
    cross_shensha: dict[str, OpenJsonValue] | None = None
    cross_chart_relations: CrossChartRelations | None = None
    directional_ten_gods: (
        dict[Literal["person1_to_person2", "person2_to_person1"], DirectionalTenGods]
        | None
    ) = None


class BaziTimingOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_calendar: Object | None = None
    analysis_context: AnalysisReference | None = None
    analysis_type: str | None = None
    birth_time_sensitivity: BirthTimeSensitivity | None = None
    calendar_context: CalendarContext | None = None
    combined_effects: Object | None = None
    coverage: Object | None = None
    dayun: Object | list[JsonValue] | None = None
    four_pillars: FourPillars | None = None
    interaction_analysis: TimingInteractions | None = None
    liunian: Object | None = None
    liuri: Object | None = None
    liushi: Object | None = None
    liuyue: Object | None = None
    person_info: PersonInfo | None = None
    summary: Object | list[JsonValue] | str | None = None


class BaziLuckCyclesOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisReference | None = None
    analysis_type: str | None = None
    birth_time_sensitivity: BirthTimeSensitivity | None = None
    calendar_context: CalendarContext | None = None
    dayun: Object | list[JsonValue] | None = None
    dayun_timeline: list[JsonValue] | None = None
    element_effects: Object | None = None
    person_info: PersonInfo | None = None
    summary: Object | list[JsonValue] | str | None = None
    timing_context: Object | None = None


class BaziYearlyTimingOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisReference | None = None
    analysis_type: str | None = None
    calendar_context: CalendarContext | None = None
    element_effects: Object | None = None
    liunian: Object | None = None
    person_info: PersonInfo | None = None
    summary: Object | list[JsonValue] | str | None = None
    yearly_timeline: list[JsonValue] | None = None


class BaziMonthlyTimingOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_calendar: Object | None = None
    analysis_context: AnalysisReference | None = None
    analysis_type: str | None = None
    calendar_context: CalendarContext | None = None
    combined_effects: Object | None = None
    detailed_analysis: Object | None = None
    element_effects: Object | None = None
    liunian: Object | None = None
    liuyue: Object | None = None
    monthly_timeline: list[JsonValue] | None = None
    person_info: PersonInfo | None = None
    summary: Object | list[JsonValue] | str | None = None


class BaziDailyTimingOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_calendar: Object | None = None
    analysis_context: AnalysisReference | None = None
    analysis_type: str | None = None
    calendar_context: CalendarContext | None = None
    daily_timeline: list[JsonValue] | None = None
    detailed_analysis: Object | None = None
    element_effects: Object | None = None
    liuri: Object | None = None
    person_info: PersonInfo | None = None
    summary: Object | list[JsonValue] | str | None = None


class BaziHourlyTimingOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_calendar: Object | None = None
    analysis_context: AnalysisReference | None = None
    analysis_type: str | None = None
    calendar_context: CalendarContext | None = None
    detailed_analysis: Object | None = None
    element_effects: Object | None = None
    liushi: Object | None = None
    person_info: PersonInfo | None = None
    summary: Object | list[JsonValue] | str | None = None


class SolarTermTimelineOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisReference | None = None
    analysis_type: str | None = None
    calendar_context: CalendarContext | None = None
    jieqi_timeline: list[JsonValue] | None = None
    person_info: PersonInfo | None = None
    summary: Object | list[JsonValue] | str | None = None
    target_year_jieqi: list[SolarTerm] | None = None


class SolarTermsForYearOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    jieqi_year: list[SolarTerm] | None = None
    selected_jieqi: list[SolarTerm] | None = None
    summary: Object | list[JsonValue] | str | None = None
    year: int | str | None = None


class LunarCalendarTimeOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    calendar_context: CalendarContext | None = None
    day: str | None = None
    day_ganzhi: str | None = None
    day_int: int | None = None
    four_pillars: FourPillars | None = None
    jiedelta: str | None = None
    jieqi: str | None = None
    leap: bool | None = None
    lunar_calendar: LunarCalendar | None = None
    month: str | None = None
    month_ganzhi: str | None = None
    month_int: int | None = None
    nongli: Object | str | None = None
    person_info: PersonInfo | None = None
    summary: Object | list[JsonValue] | str | None = None
    time_ganzhi: str | None = None
    year_ganzhi: str | None = None
    year_jieqi: str | None = None

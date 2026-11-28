"""Output contracts for Canping, Heluo, and numerology clock/evidence."""

from __future__ import annotations

from datetime import time
from typing import Annotated, Literal

from pydantic import (
    BeforeValidator,
    Field,
    FiniteFloat,
    JsonValue,
    ValidationInfo,
    model_validator,
)

from fatebridge.core.contracts.base import PartialOutput, ProjectedOutput
from fatebridge.core.contracts.common import (
    AnalysisContext,
    CalendarContext,
    CivilPointEvidence,
    CivilPointLabelEvidence,
    FourPillars,
)
from fatebridge.core.heluo.judgment import OPERATORS
from fatebridge.core.heluo.judgment import _jiehou_form as _form
from fatebridge.core.heluo.judgment import _structure_name as _name
from fatebridge.core.heluo.judgment import nominal_hou_day, term_assignment
from fatebridge.core.heluo.texts import _gua_tables, gua_lines, yao_name
from fatebridge.core.heluo.timing import CYCLE as HELUO_CYCLE
from fatebridge.core.numerology.numerology_clock_input import (
    CLOCK_INPUT_SCOPE,
    clock_input_representation,
)
from fatebridge.core.numerology.numerology_inputs import (
    CYCLE,
    GAN,
    LINK_GROUPS,
    LINK_HEADS,
    ZHI,
    normalize_numerology_utc_offset,
    require_birth_clock,
)
from fatebridge.core.numerology.timing import (
    APPLIED,
    LEGACY,
    SUMMARIES,
    clause_role,
    clock_policy_for_rules,
    date_mapping_statement,
    source_readings,
)
from fatebridge.core.receipt_models import Object, RunMetadata
from fatebridge.utils.civil_clock import format_utc_offset
from fatebridge.utils.civil_time import (
    UTCCalendar,
    ZonedCalendar,
    parse_iso_datetime,
    utc_calendar,
)
from fatebridge.utils.timezones import parse_timezone_name


def _exact_bool(value: object) -> bool:
    if type(value) is not bool:
        raise ValueError("布尔事实不能用0/1或字符串替代。")
    return value


def _exact_false(value: object) -> Literal[False]:
    if value is not False:
        raise ValueError("未完成的原典／效验状态不能提升或以0代替false。")
    return value


def _exact_true(value: object) -> Literal[True]:
    if value is not True:
        raise ValueError("布尔事实不能用0/1或字符串替代。")
    return value


def _not_a_boolean_number(value: object) -> object:
    if type(value) is bool:
        raise ValueError("刻数不能用布尔替代。")
    return value


KnownTrue = Annotated[Literal[True], BeforeValidator(_exact_bool)]
KnownFalse = Annotated[Literal[False], BeforeValidator(_exact_bool)]
_KnownTrue = Annotated[Literal[True], BeforeValidator(_exact_true)]
_KnownFalse = Annotated[Literal[False], BeforeValidator(_exact_false)]
_Profile = Literal["bazi_appendix_v1", "bazi_continuous_v1", "legacy_minggong_v1"]
_ClockPolicy = Literal[
    "explicit_fixed_offset_assumption; no_regional_future_rules",
    "pinned_regional_rules; subject_to_future_legislation",
]
NominalModel = Literal["continuous_yao_from_yi_four", "six_days_per_gua_caption_first"]

# note (schema): Keep the Heluo order distinct from the shared five-element order.
HeluoBodyElement = Annotated[Literal["金", "木", "水", "火", "土"], Field()]


class CanpingTextWitness(PartialOutput):
    element: str | None = None
    number: int | None = None
    kind: Literal["male", "female", "luck"] | None = None
    text: str | None = None
    pdf_pages: list[int] | None = None
    body_pdf_page: int | None = None
    source_occurrence_id: str | None = Field(default=None, min_length=1)
    header_pdf_page: int | None = Field(default=None, gt=0)
    number_occurrence_count: int | None = Field(default=None, gt=0)
    number_occurrence_ambiguous: bool | None = None
    reading_uncertainties: list[str] | None = None
    source_corpus_id: str | None = None
    text_status: str | None = None
    relation: (
        Literal[
            "same_text",
            "different_text",
            "selected_reading_uncertain",
            "witness_reading_uncertain",
            "both_readings_uncertain",
        ]
        | None
    ) = None
    replaces_selected_text: Literal[False] | None = None
    inherited_reading_matches: bool | None = None


class CanpingReadingRevision(PartialOutput):
    rereading_id: str | None = None
    previous_collation_version: str | None = None
    previous_text: str | None = None
    previous_cell_status: Literal["source_reading_uncertain"] | None = None
    source_pdf_page: int | None = Field(default=None, gt=0)
    note: str | None = None


class CanpingNumberReadingEvidence(PartialOutput):
    element: str | None = None
    provisional_number: int | None = None
    pdf_page: int | None = Field(default=None, gt=0)
    observed_header: str | None = None
    obstruction_kind: Literal["seal_overprint", "faded_digit"] | None = None
    note: str | None = None
    resolution_status: Literal["unresolved"] | None = None
    witness_id: str | None = None
    body_evidence_basis: (
        Literal["prior_literal_transcription_not_new_body_collation"] | None
    ) = None


class CanpingTextSelection(PartialOutput):
    element: str | None = None
    number: int | None = None
    kind: Literal["male", "female", "luck"] | None = None
    column: str | None = None
    corpus_key: str | None = None
    row_status: str | None = None
    cell_status: str | None = None
    corrected_number: int | None = None
    collation_id: str | None = None
    source_pdf_page: int | None = None
    reading_notes: list[str] | None = None
    reading_uncertainties: list[str] | None = None
    number_reading_uncertainties: list[str] | None = None
    number_attribution_status: Literal["provisional_inherited_key"] | None = None
    reading_revision: CanpingReadingRevision | None = None
    body_reading_status: (
        Literal[
            "source_body_visually_read",
            "source_body_printed_blank",
            "source_body_printed_partial_blank",
            "source_body_reading_uncertain",
        ]
        | None
    ) = None
    number_reading_evidence: CanpingNumberReadingEvidence | None = None
    editorial_unknown_marker: str | None = None
    witnesses: list[CanpingTextWitness] | None = None
    inherited_text: str | None = None
    inherited_number: int | None = None
    unapplied_note: dict[str, JsonValue] | None = None


class CanpingPairResolution(PartialOutput):
    same_number: bool | None = None
    distinct_numbers: int | None = None
    local_text_availability: str | None = None
    source_rule_pdf_page: int | None = None
    independent_evidence_count: int | None = None
    scope: str | None = None


class CanpingInterval(PartialOutput):
    """Half-open interval labels and optional point bounds."""

    start_at: str | None = None
    end_at: str | None = None
    start_point: CivilPointEvidence | None = None
    end_point: CivilPointEvidence | None = None
    comparison_policy: Literal["retained_nominal_civil_point_v1"] | None = None

    @model_validator(mode="after")
    def coherent_interval(self, info: ValidationInfo) -> "CanpingInterval":
        if (
            info.context
            and info.context.get("full_result")
            and self.comparison_policy == "retained_nominal_civil_point_v1"
            and any(
                value is None
                for value in (
                    self.start_at,
                    self.end_at,
                    self.start_point,
                    self.end_point,
                )
            )
        ):
            raise ValueError("精确配运区间缺少完整数值端点或显示标签。")
        for evidence, label in (
            (self.start_point, self.start_at),
            (self.end_point, self.end_at),
        ):
            point = evidence.known_point() if evidence is not None else None
            if point is not None and label is not None:
                if point.as_calendar() != ZonedCalendar.from_isoformat(label).utc:
                    raise ValueError("配运数值端点与显示标签不一致。")
        start = self.start_point.known_day() if self.start_point is not None else None
        end = self.end_point.known_day() if self.end_point is not None else None
        if start is not None and end is not None and start >= end:
            raise ValueError("配运数值区间须为正长度半开区间。")
        return self


class CanpingSolarTermRecord(CivilPointLabelEvidence):
    name: Literal["立春"] | None = None
    resolution_provider: str | None = None
    ephemeris_model: str | None = None
    solar_model_details: dict[str, JsonValue] | None = None


class CanpingSolarBoundary(PartialOutput):
    year: int | None = None
    record: CanpingSolarTermRecord | None = None
    instant_utc: str | None = None
    ephemeris_retflags: list[int] | None = None
    ephemeris_library_version: str | None = None
    selection: (
        Literal["ordinary_public_year_grid", "bounded_derived_lichun_event"] | None
    ) = None

    @model_validator(mode="after")
    def same_instant(self) -> "CanpingSolarBoundary":
        if self.instant_utc is not None:
            at = ZonedCalendar.from_isoformat(self.instant_utc).utc
            civil = self.record.display_with_offset if self.record is not None else None
            if civil is not None and at != ZonedCalendar.from_isoformat(civil).utc:
                raise ValueError("民用立春与UTC边界不一致。")
        return self


class CanpingSolarContext(PartialOutput):
    policy_id: str | None = None
    origin_civil_year: int | None = None
    origin_bazi_year: int | None = None
    birth_instant_utc: str | None = None
    timezone: str | None = None
    horizon_years: int | None = None
    boundary_count: int | None = None
    observed_models: list[str] | None = None
    derived_event_years: list[int] | None = None
    de440_projection_profile_used: bool | None = None
    de440_extended_projection_profile_used: bool | None = None
    registered_public_input_years: list[int] | None = None
    qualified_origin_civil_year_ranges: list[list[int]] | None = None
    public_model_years_extended: Literal[False] | None = None
    not_a_lifespan_estimate: Literal[True] | None = None
    leap_table_expires_at: str | None = None
    scope: str | None = None

    @model_validator(mode="after")
    def complete_horizon(self) -> "CanpingSolarContext":
        if self.horizon_years is not None:
            if not 1 <= self.horizon_years <= 120:
                raise ValueError("年序范围须为1至120。")
            if (
                self.boundary_count is not None
                and self.boundary_count != self.horizon_years + 1
            ):
                raise ValueError("立春边界数量须为年序范围加1。")
        return self


class CanpingVerses(PartialOutput):
    statusShun: str | None = None
    statusNi: str | None = None
    numNi: int | None = None
    numShun: int | None = None
    textNi: str | None = None
    textShun: str | None = None
    selectionShun: CanpingTextSelection | None = None
    selectionNi: CanpingTextSelection | None = None
    pair_resolution: CanpingPairResolution | None = None


class CanpingRow(CanpingInterval):
    year_start_boundary: CanpingSolarBoundary | None = None
    year_end_boundary: CanpingSolarBoundary | None = None
    age: int | None = None
    ageEnd: int | None = None
    ageStart: int | None = None
    branch: str | None = None
    index: int | None = None
    ni: int | None = None
    numNi: int | None = None
    numShun: int | None = None
    shun: int | None = None
    ziRound: int | None = None
    verses: CanpingVerses | None = None
    dayunBranch: str | None = None
    dayunRange: str | None = None
    ganzhi: str | None = None
    taisuiBranch: str | None = None
    year: int | None = None
    at: str | None = None
    start_age: float | None = None
    end_age: float | None = None
    status: str | None = None
    pillar: str | None = None
    dayun_index: int | None = None
    dayun_pillar: str | None = None
    segments: list["CanpingRow"] | None = None

    @model_validator(mode="after")
    def coherent_dated_row(self) -> "CanpingRow":
        if self.status == "not_started" and any(
            value is not None
            for value in (
                self.dayun_index,
                self.dayunBranch,
                self.dayun_pillar,
                self.numNi,
                self.numShun,
                self.verses,
            )
        ):
            raise ValueError("未起运区间不能附活动大运或条文。")
        at = (
            ZonedCalendar.from_isoformat(self.at).utc.julian_day_exact()
            if self.at is not None
            else None
        )
        start = (
            ZonedCalendar.from_isoformat(self.start_at).utc.julian_day_exact()
            if self.start_at is not None
            else None
        )
        end = (
            ZonedCalendar.from_isoformat(self.end_at).utc.julian_day_exact()
            if self.end_at is not None
            else None
        )
        if at is not None and (
            (start is not None and at < start) or (end is not None and at >= end)
        ):
            raise ValueError("查询时刻不在所选半开区间。")
        for boundary, ending in (
            (self.year_start_boundary, False),
            (self.year_end_boundary, True),
        ):
            if boundary is None:
                continue
            if self.year is not None and boundary.year is not None:
                if boundary.year != self.year + int(ending):
                    raise ValueError("所选年与实际立春边界年份不一致。")
        return self


class CanpingScheduleSource(PartialOutput):
    title: str | None = None
    edition: str | None = None


class CanpingReadingContext(PartialOutput):
    profile_id: _Profile | None = None
    future_clock_policy: _ClockPolicy | None = None
    timezone_spec: str | None = None
    date_mapping_statement: str | None = None

    @model_validator(mode="after")
    def coherent_reading_context(self) -> "CanpingReadingContext":
        if self.profile_id is not None:
            if self.date_mapping_statement is not None and (
                self.profile_id == LEGACY
                or (
                    self.future_clock_policy is not None
                    and self.timezone_spec is not None
                )
            ):
                expected = date_mapping_statement(
                    self.profile_id, self.future_clock_policy, self.timezone_spec
                )
                if self.date_mapping_statement != expected:
                    raise ValueError("阅读日期条件与所选方法及钟制不符。")
        return self


class CanpingScheduleClause(PartialOutput):
    id: str | None = None
    source_id: Literal["heluo_najda", "sanming_nlc"] | None = None
    pdf_page: int | None = Field(default=None, ge=1)
    printed_page: str | None = None
    locator: str | None = None
    text: str | None = None
    kind: str | None = None
    role: (
        Literal[
            "applied_rule",
            "supplementary_ziping_background",
            "source_context",
            "comparison_not_applied",
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def coherent_source_excerpt(self) -> "CanpingScheduleClause":
        if self.id is None:
            return self

        entry = next(
            (x for x in source_readings()["clauses"] if x["id"] == self.id), None
        )
        if entry is None:
            raise ValueError("未登记的配运原句。")
        for key in ("source_id", "pdf_page", "printed_page", "locator", "text", "kind"):
            value = getattr(self, key)
            if value is not None and value != entry[key]:
                raise ValueError("配运原句及其出处不能互换或改写。")
        return self


class CanpingScheduleBasis(PartialOutput):
    policy_id: Literal["canping_schedule_source_mapping_v1"] | None = None
    profile_id: _Profile | None = None
    corpus_id: Literal["canping_schedule_clauses_v1"] | None = None
    corpus_version: str | None = None
    review_status: str | None = None
    sources: dict[str, CanpingScheduleSource] | None = None
    clauses: list[CanpingScheduleClause] | None = None
    applied_clause_ids: list[str] | None = None
    bridge_step_years: Literal[10] | None = None
    target_excerpt_ten_year_step_explicitly_collated: _KnownFalse | None = None
    has_actual_date_mapping: bool | None = None
    datetime_mapping_is_original_source_formula: _KnownFalse | None = None
    calendar_mapping: dict[str, str] | None = None
    age_conversion_result: dict[str, JsonValue] | None = None
    actual_start_at: str | None = None
    timezone_spec: str | None = None
    timezone_rules: dict[str, JsonValue] | None = None
    future_clock_policy: (
        Literal[
            "explicit_fixed_offset_assumption; no_regional_future_rules",
            "pinned_regional_rules; subject_to_future_legislation",
        ]
        | None
    ) = None
    reading_context: CanpingReadingContext | None = None
    summary: str | None = None

    @model_validator(mode="after")
    def coherent_selected_policy(self) -> "CanpingScheduleBasis":
        data = source_readings()
        for field, expected in (
            ("corpus_version", data["version"]),
            ("review_status", data["review_status"]),
        ):
            value = getattr(self, field)
            if value is not None and value != expected:
                raise ValueError("配运来源身份与所选版本不一致。")
        if self.summary is not None:
            possible = (
                [SUMMARIES[self.profile_id]]
                if self.profile_id is not None
                else list(SUMMARIES.values())
            )
            if self.summary not in possible:
                raise ValueError("配运摘要与实际方法或已核范围不一致。")
        if self.sources is not None:
            for source_id, source in self.sources.items():
                expected_source = data["sources"].get(source_id)
                if expected_source is None:
                    raise ValueError("未登记的配运书目来源。")
                for key, expected in expected_source.items():
                    if (
                        key in source.model_fields_set
                        and getattr(source, key) != expected
                    ):
                        raise ValueError("配运书名、版本或书影身份不能互换。")
        if self.timezone_rules is not None:
            expected_policy = clock_policy_for_rules(self.timezone_rules)
            if (
                self.future_clock_policy is not None
                and expected_policy is not None
                and self.future_clock_policy != expected_policy
            ):
                raise ValueError("未来钟面政策与本次时区规则不一致。")
        if self.reading_context is not None:
            for field in ("profile_id", "future_clock_policy", "timezone_spec"):
                outer = getattr(self, field)
                inner = getattr(self.reading_context, field)
                if outer is not None and inner is not None and outer != inner:
                    raise ValueError("阅读上下文与同次配运回执不符。")

        if self.profile_id is not None:
            if (
                self.has_actual_date_mapping is not None
                and self.has_actual_date_mapping
                != (self.profile_id != "legacy_minggong_v1")
            ):
                raise ValueError("旧命宫排法没有已核实际日期映射。")
            if (
                self.applied_clause_ids is not None
                and self.applied_clause_ids != APPLIED[self.profile_id]
            ):
                raise ValueError("实际采用的配运规则与所选方法不一致。")
            if self.clauses is not None:
                for c in self.clauses:
                    if c.id is not None and c.role is not None:
                        entry = next(x for x in data["clauses"] if x["id"] == c.id)
                        if c.role != clause_role(self.profile_id, entry):
                            raise ValueError("配运原句的本次角色与实际方法不一致。")
        if self.clauses is not None:
            ids = [c.id for c in self.clauses if c.id is not None]
            if len(ids) != len(set(ids)):
                raise ValueError("配运原句不能重复计数。")
        return self


class CanpingSeries(PartialOutput):
    comparison_policy: Literal["retained_nominal_civil_point_v1"] | None = None
    year_boundaries: list[CanpingSolarBoundary] | None = None
    solar_context: CanpingSolarContext | None = None
    dayun: list[CanpingRow] | None = None
    element: str | None = None
    partName: str | None = None
    qiyunAge: int | None = None
    rows: list[CanpingRow] | None = None
    year_boundary: str | None = None
    birth_pillar_year: int | None = None
    age_policy: str | None = None

    @model_validator(mode="after")
    def coherent_annual_points(self) -> "CanpingSeries":
        previous_year = None
        for row in self.rows or []:
            if row.year is not None and previous_year is not None:
                if row.year != previous_year + 1:
                    raise ValueError("配运年序年份不连续。")
            previous_year = row.year
        context = self.solar_context
        if context is not None:
            if self.rows is not None and context.horizon_years is not None:
                if len(self.rows) != context.horizon_years:
                    raise ValueError("实际年序行数与声明的范围不一致。")
            if (
                self.birth_pillar_year is not None
                and context.origin_bazi_year is not None
            ):
                if self.birth_pillar_year != context.origin_bazi_year:
                    raise ValueError("年序起年与实际出生干支年不一致。")
        if (
            self.rows
            and self.rows[0].year is not None
            and self.birth_pillar_year is not None
        ):
            if self.rows[0].year != self.birth_pillar_year:
                raise ValueError("年序首行不是实际出生干支年。")
        return self


class CanpingTiming(PartialOutput):
    comparison_policy: Literal["retained_nominal_civil_point_v1"] | None = None
    solar_year_context: CanpingSolarContext | None = None
    profile_id: str | None = None
    method_id: str | None = None
    birth_at: str | None = None
    timezone: str | None = None
    start_at: str | None = None
    start_details: Object | None = None
    calendar_offset: Object | None = None
    calendar_policy: str | None = None
    reference_policy: str | None = None
    boundary_policy: str | None = None
    dst_policy: str | None = None
    ruleset_id: str | None = None
    ruleset_version: str | None = None
    source_title: str | None = None
    source_url: str | None = None
    source_pdf_pages: list[int] | None = None
    source_status: str | None = None
    calendar_scope: str | None = None
    heluo_period_distinction: str | None = None
    selected: CanpingRow | None = None
    schedule_basis: CanpingScheduleBasis | None = None
    first_row: CanpingRow | None = None
    first_period: CanpingRow | None = None

    @model_validator(mode="after")
    def coherent_schedule_source_map(self) -> "CanpingTiming":
        basis = self.schedule_basis
        known_profile = self.profile_id or (basis.profile_id if basis else None)
        known_start = self.start_at or (basis.actual_start_at if basis else None)
        if self.first_row is not None:
            if known_profile == "legacy_minggong_v1" or (
                basis is not None and basis.has_actual_date_mapping is False
            ):
                for key in (
                    "start_at",
                    "end_at",
                    "start_age",
                    "end_age",
                    "at",
                    "dayun_index",
                ):
                    if getattr(self.first_row, key) is not None:
                        raise ValueError(
                            "旧法首行仅为年龄标签，不能补实际日期或查询身份。"
                        )
            if self.first_period is not None:

                def agree(a: object, b: object) -> bool:
                    if a is None or b is None:
                        return True
                    if isinstance(a, dict) and isinstance(b, dict):
                        return all(agree(a[k], b[k]) for k in a.keys() & b.keys())
                    if isinstance(a, list) and isinstance(b, list):
                        return len(a) == len(b) and all(
                            agree(x, y) for x, y in zip(a, b)
                        )
                    return bool(a == b)

                if not agree(
                    self.first_row.model_dump(exclude_unset=True),
                    self.first_period.model_dump(exclude_unset=True),
                ):
                    raise ValueError("首行与首运的已返回事实不一致。")
        if basis is not None:
            if (
                self.start_at is not None
                and basis.actual_start_at is not None
                and self.start_at != basis.actual_start_at
            ):
                raise ValueError("配运来源回执与实际起运瞬间不一致。")
            if (
                self.profile_id is not None
                and basis.profile_id is not None
                and self.profile_id != basis.profile_id
            ):
                raise ValueError("配运来源回执与实际方法不一致。")
            if (
                self.calendar_offset is not None
                and basis.age_conversion_result is not None
            ):
                for key in (
                    self.calendar_offset.keys() & basis.age_conversion_result.keys()
                ):
                    actual = self.calendar_offset[key]
                    recorded = basis.age_conversion_result[key]
                    if type(actual) is not type(recorded) or actual != recorded:
                        raise ValueError("配运年龄折算回执与本次实际结果不一致。")
            if basis.calendar_mapping is not None:
                for key in (
                    "calendar_policy",
                    "reference_policy",
                    "boundary_policy",
                    "dst_policy",
                ):
                    actual = getattr(self, key)
                    recorded = basis.calendar_mapping.get(key)
                    if (
                        known_profile != "legacy_minggong_v1"
                        and actual is not None
                        and recorded is not None
                        and actual != recorded
                    ):
                        raise ValueError("配运日期映射回执与本次实际政策不一致。")
        if (
            self.first_period is not None
            and self.first_period.start_at is not None
            and known_start is not None
            and self.first_period.start_at != known_start
        ):
            raise ValueError("首运摘要与实际起运时刻不一致。")
        if self.first_period is not None and (
            known_profile == "legacy_minggong_v1"
            or basis is not None
            and basis.has_actual_date_mapping is False
        ):
            raise ValueError("旧命宫排法不能补成已核日期首运。")
        return self


class JiehouForm(PartialOutput):
    gua: str | None = None
    lines: list[int] | None = Field(default=None, min_length=6, max_length=6)
    position: int | None = Field(default=None, ge=1, le=6)
    yao: str | None = None

    @model_validator(mode="after")
    def coherent_form(self) -> "JiehouForm":
        if self.lines is not None and any(n not in (0, 1) for n in self.lines):
            raise ValueError("节候卦形须为自下而上的六个0／1。")
        lines: list[int] | None = self.lines
        if self.gua is not None:
            pair = _gua_tables()[0].get(self.gua)
            if pair is None:
                raise ValueError("节候卦名无对应卦形。")
            lines = gua_lines(pair["up"], pair["low"])
            if self.lines is not None and self.lines != lines:
                raise ValueError("节候卦名与六爻不一致。")
        if (
            lines is not None
            and self.position is not None
            and self.yao is not None
            and self.yao != yao_name(lines, self.position)
        ):
            raise ValueError("推演用爻名与卦形不一致；原印标签应另存。")
        return self


class JiehouTerm(JiehouForm):
    term: str | None = None
    source_pdf_page: int | None = None

    @model_validator(mode="after")
    def named_assignment(self) -> "JiehouTerm":
        if self.term is not None:
            actual = term_assignment(self.term)
            for key in ("gua", "position", "source_pdf_page"):
                value = getattr(self, key)
                if value is not None and value != actual[key]:
                    raise ValueError("节气名与所选底本节卦不一致。")
        return self


class JiehouLiteral(PartialOutput):
    term: str | None = None
    entry_in_group: int | None = Field(default=None, ge=1, le=3)
    short_name: str | None = None
    gua: str | None = None
    raw_yao: Literal["六四", "初六", "初九"] | None = None
    source_pdf_page: int | None = None
    printed_position: int | None = Field(default=None, ge=1, le=6)
    canonical_yao: str | None = None
    yao_polarity_agrees: bool | None = None

    @model_validator(mode="after")
    def retain_literal_difference(self) -> "JiehouLiteral":
        if self.raw_yao is not None and self.printed_position is not None:
            if self.printed_position != (4 if self.raw_yao == "六四" else 1):
                raise ValueError("原印爻名与所列原印位置不一致。")
        if self.gua is not None and self.printed_position is not None:
            canonical = _form(self.gua, self.printed_position)["yao"]
            if self.canonical_yao is not None and self.canonical_yao != canonical:
                raise ValueError("候卦形的爻名不一致。")
        else:
            canonical = self.canonical_yao
        if (
            self.raw_yao is not None
            and canonical is not None
            and self.yao_polarity_agrees is not None
            and self.yao_polarity_agrees != (self.raw_yao == canonical)
        ):
            raise ValueError("原印与卦形的差异不能被反转。")
        return self


class JiehouNominalDay(JiehouForm):
    model: NominalModel | None = None
    day_offset: int | None = Field(default=None, ge=0, lt=360)
    origin: Literal["printed_winter_solstice_yi_six_four; no_civil_instant"] | None = (
        None
    )
    basis: (
        Literal["sixty_gua_order_and_one_yao_per_nominal_day_reconstruction"] | None
    ) = None
    derived_only: KnownTrue | None = None
    physical_date_applied: KnownFalse | None = None
    extra_ke_applied: KnownFalse | None = None

    @model_validator(mode="after")
    def coherent_nominal_slot(self) -> "JiehouNominalDay":
        if self.day_offset is not None and self.model is not None:
            row = nominal_hou_day(self.day_offset, model=self.model)
            for key in ("gua", "position", "yao", "lines"):
                value = getattr(self, key)
                if value is not None and value != row[key]:
                    raise ValueError("名义日序与六日重建的卦爻不一致。")
        return self


class JiehouPrintedDay(PartialOutput):
    day_label: int | None = None
    gua: str | None = None
    position: int | None = Field(default=None, ge=1, le=6)


class JiehouCaptionComparison(PartialOutput):
    printed: JiehouPrintedDay | None = None
    derived: JiehouNominalDay | None = None
    agrees: bool | None = None

    @model_validator(mode="after")
    def faithful_comparison(self) -> "JiehouCaptionComparison":
        p, d = self.printed, self.derived
        if (
            p is not None
            and d is not None
            and self.agrees is not None
            and all(v is not None for v in (p.gua, p.position, d.gua, d.position))
            and self.agrees != ((p.gua, p.position) == (d.gua, d.position))
        ):
            raise ValueError("原例与六日重建的比较事实不一致。")
        return self


class JiehouTermStartComparison(PartialOutput):
    term: str | None = None
    printed_gua: str | None = None
    printed_yao: str | None = None
    printed_position: int | None = Field(default=None, ge=1, le=6)
    derived: JiehouNominalDay | None = None
    gua_agrees: bool | None = None
    position_agrees: bool | None = None
    interpretation_of_heading_unresolved: KnownTrue | None = None

    @model_validator(mode="after")
    def faithful_position_comparison(self) -> "JiehouTermStartComparison":
        d = self.derived
        if (
            self.printed_gua is not None
            and d is not None
            and d.gua is not None
            and self.gua_agrees is not None
            and self.gua_agrees != (self.printed_gua == d.gua)
        ):
            raise ValueError("表头与十五名义日模型的卦名比较不一致。")
        if (
            self.printed_position is not None
            and d is not None
            and d.position is not None
            and self.position_agrees is not None
            and self.position_agrees != (self.printed_position == d.position)
        ):
            raise ValueError("表头与十五名义日模型的位置比较不一致。")
        return self


class JiehouModelComparison(PartialOutput):
    model: NominalModel | None = None
    status: Literal["conditional_reconstruction; no_preferred_model"] | None = None
    caption_comparison: list[JiehouCaptionComparison] | None = Field(
        default=None, min_length=6, max_length=6
    )
    caption_difference_count: int | None = Field(default=None, ge=0, le=6)
    term_start_position_difference_count: int | None = Field(default=None, ge=0, le=24)
    term_start_gua_difference_count: int | None = Field(default=None, ge=0, le=24)
    selected_term_start_comparison: JiehouTermStartComparison | None = None

    @model_validator(mode="after")
    def count_actual_comparisons(self) -> "JiehouModelComparison":
        start = self.selected_term_start_comparison
        if (
            self.model is not None
            and start is not None
            and start.derived is not None
            and start.derived.model is not None
            and self.model != start.derived.model
        ):
            raise ValueError("交节点比较不能混用不同日序模型。")
        rows = self.caption_comparison
        if rows is not None:
            if self.model is not None and any(
                r.derived is not None
                and r.derived.model is not None
                and r.derived.model != self.model
                for r in rows
            ):
                raise ValueError("示例比较不能混用不同日序模型。")
            if (
                self.caption_difference_count is not None
                and all(r.agrees is not None for r in rows)
                and self.caption_difference_count
                != sum(r.agrees is False for r in rows)
            ):
                raise ValueError("原例差异计数与逐项比较不一致。")
        return self


class JiehouCounts(PartialOutput):
    term_rows: int | None = Field(default=None, ge=24, le=24)
    literal_hou_rows: int | None = Field(default=None, ge=72, le=72)
    distinct_hou_gua: int | None = Field(default=None, ge=60, le=60)
    nominal_gua_days: int | None = Field(default=None, ge=6, le=6)
    nominal_hou_days: int | None = Field(default=None, ge=5, le=5)
    nominal_term_line_days: int | None = Field(default=None, ge=15, le=15)
    nominal_quarter_days: int | None = Field(default=None, ge=90, le=90)
    nominal_year_days: int | None = Field(default=None, ge=360, le=360)


class HeluoJiehouEvidence(PartialOutput):
    ruleset_id: Literal["heluo_wenming_jiehou_v1"] | None = None
    version: str | None = None
    source_title: str | None = None
    source_url: str | None = None
    source_pdf_pages: list[int] | None = None
    review_status: str | None = None
    selection_basis: (
        Literal["already_computed_term_label; modern_calendar_convention"] | None
    ) = None
    upstream_term_label: str | None = None
    anchor_utc: str | None = None
    anchor_precision: Literal["birth_instant", "date_midnight_approximation"] | None = (
        None
    )
    selected_term_gua: JiehouTerm | None = None
    literal_hou_group: list[JiehouLiteral] | None = Field(
        default=None, min_length=3, max_length=3
    )
    selected_hou: None = None
    huagong_assessment: None = None
    counts: JiehouCounts | None = None
    literal_yao_conflicts: list[JiehouLiteral] | None = None
    reconstruction_models: list[JiehouModelComparison] | None = Field(
        default=None, min_length=2, max_length=2
    )
    selected_reconstruction_model: None = None
    printed_total_yao_phrase: str | None = None
    historical_term_instants_established: KnownFalse | None = None
    hou_physical_date_mapping_complete: KnownFalse | None = None
    interpretation_constraints: list[str] | None = None

    @model_validator(mode="after")
    def same_term_context(self) -> "HeluoJiehouEvidence":
        if self.reconstruction_models is not None:
            names = [r.model for r in self.reconstruction_models]
            if all(name is not None for name in names) and names != [
                "continuous_yao_from_yi_four",
                "six_days_per_gua_caption_first",
            ]:
                raise ValueError("须保留两种具名重建，不能重复或删去一种。")
        if self.upstream_term_label is not None:
            actual = term_assignment(self.upstream_term_label)
            term = actual["term"]
            if self.reconstruction_models is not None and any(
                r.selected_term_start_comparison is not None
                and r.selected_term_start_comparison.term is not None
                and r.selected_term_start_comparison.term != term
                for r in self.reconstruction_models
            ):
                raise ValueError("模型交节点比较与本次节气不一致。")
            if self.selected_term_gua is not None:
                for key in ("gua", "position"):
                    value = getattr(self.selected_term_gua, key)
                    if value is not None and value != actual[key]:
                        raise ValueError("本次节气与已知节卦事实不一致。")
            if (
                self.selected_term_gua is not None
                and self.selected_term_gua.term is not None
            ):
                if term != self.selected_term_gua.term:
                    raise ValueError("本次节气标签与所选节卦不一致。")
            if self.literal_hou_group is not None and any(
                row.term is not None and row.term != term
                for row in self.literal_hou_group
            ):
                raise ValueError("原候卦组与本次节气不一致。")
        return self


class HeluoNajiaSource(PartialOutput):
    basis: Literal["hexagram_entry", "pure_trigram_rule"] | None = None
    source_hexagram: str | None = None
    source_pdf_page: int | None = Field(default=None, ge=1)
    source_assignment_index: int | None = Field(default=None, ge=1, le=6)


class HeluoNajiaLine(PartialOutput):
    pos: int | None = Field(default=None, ge=1, le=6)
    trigram: str | None = None
    direct: str | None = None
    borrowed: list[str] | None = None
    source: HeluoNajiaSource | None = None


class HeluoNajiaMatch(PartialOutput):
    pos: int | None = Field(default=None, ge=1, le=6)
    kind: Literal["direct", "borrowed"] | None = None


class HeluoNajiaAssessment(PartialOutput):
    phase: Literal["xian", "hou"] | None = None
    gua: str | None = None
    year_ganzhi: str | None = None
    lines: list[HeluoNajiaLine] | None = None
    matches: list[HeluoNajiaMatch] | None = None
    present: bool | None = None
    source_scope: str | None = None
    source_issues: list[dict[str, JsonValue]] | None = None


class HeluoNumberFact(PartialOutput):
    value: int | None = Field(default=None, gt=0)
    reference: int | None = None
    difference: int | None = None
    comparison: Literal["正数", "不足", "有余"] | None = None
    extreme_band: Literal["至弱", "太过"] | None = None
    extreme_band_status: str | None = None
    weak_range: list[int] | None = None
    high_lower_bound: int | None = None
    high_upper_bound: int | None = None
    source_pdf_pages: list[int] | None = None
    scope: str | None = None


class HeluoNumericalCondition(PartialOutput):
    rule_id: str | None = None
    label: str | None = None
    source_pdf_page: int | None = None
    condition: str | None = None
    matched: bool | None = None


class HeluoSeasonWindow(PartialOutput):
    rule_id: str | None = None
    label: str | None = None
    axis: Literal["tian", "di"] | None = None
    source_pdf_page: int | None = None
    start_term: str | None = None
    end_term: str | None = None
    start_at: str | None = None
    end_at: str | None = None
    start_provider: str | None = None
    end_provider: str | None = None
    start_source: dict[str, JsonValue] | None = None
    end_source: dict[str, JsonValue] | None = None
    active: bool | None = None
    numeric_condition: str | None = None
    numeric_band_match: bool | None = None
    numeric_band_status: str | None = None
    scope: str | None = None


class HeluoSeasonalNumbers(PartialOutput):
    context_timezone: str | None = None
    context_local_year: int | None = None
    ruleset_id: str | None = None
    version: str | None = None
    source_url: str | None = None
    source_pdf_pages: list[int] | None = None
    assessment_status: str | None = None
    numbers: dict[str, HeluoNumberFact] | None = None
    numerical_conditions: list[HeluoNumericalCondition] | None = None
    matched_pattern_ids: list[str] | None = None
    seasonal_status: str | None = None
    birth_instant_utc: str | None = None
    seasonal_windows: list[HeluoSeasonWindow] | None = None
    overlap_policy: str | None = None
    boundary_policy: str | None = None
    complete_assessment: Literal[False] | None = None
    unresolved: list[str] | None = None


class HeluoNatalNajiaClause(PartialOutput):
    rule_id: str | None = None
    source_pdf_page: int | None = Field(default=None, ge=1)
    literal: str | None = None
    month_numbers: list[Annotated[int, Field(ge=1, le=12)]] | None = None
    month_label_match: bool | None = None
    najia: HeluoNajiaAssessment | None = None
    qualifier_status: (
        Literal["current_phase_facts_available", "not_evaluated_missing_najia"] | None
    ) = None
    connector_status: Literal["source_ji_scope_unresolved"] | None = None
    match: None = None
    scope: str | None = None


class HeluoAdditionalMonthWindow(PartialOutput):
    rule_id: str | None = None
    source_pdf_page: int | None = Field(default=None, ge=1)
    literal: str | None = None
    kind: Literal["continuous_range", "discrete_months", "season_set"] | None = None
    meaning: (
        Literal[
            "timely", "untimely", "named_favorable_months", "named_months_with_najia"
        ]
        | None
    ) = None
    month_numbers: list[Annotated[int, Field(ge=1, le=12)]] | None = None
    uncertain_month_numbers: list[Annotated[int, Field(ge=1, le=12)]] | None = None
    month_label_match: bool | None = None
    qualifiers: list[str] | None = None
    natal_najia_clause_id: str | None = None
    qualifier_status: Literal["none", "not_evaluated"] | None = None
    first_month_number: int | None = Field(default=None, ge=1, le=12)
    last_month_number: int | None = Field(default=None, ge=1, le=12)
    first_month_inclusive: bool | None = None
    last_month_inclusive: bool | None = None
    match: bool | None = None
    status: str | None = None


class HeluoMonthSourceReading(PartialOutput):
    section: Literal["hexagram_intro", "volume_one_table"] | None = None
    month_number: int | None = Field(default=None, ge=1, le=12)
    source_pdf_page: int | None = Field(default=None, ge=1)
    literal: str | None = Field(
        default=None,
        description="卷首月号读标，卦名沿用系统规范字形并线性化；不是原页逐字转写。卦条未收逐字引文时为null。",
    )
    month_label_match: bool | None = None
    status: Literal["explicit_month", "month_not_explicit"] | None = None


class HeluoMonthAssignmentConflict(PartialOutput):
    gua: str | None = None
    intro_month: int | None = Field(default=None, ge=1, le=12)
    intro_pdf_page: int | None = Field(default=None, ge=1)
    table_month: int | None = Field(default=None, ge=1, le=12)
    table_pdf_page: int | None = Field(default=None, ge=1)


class HeluoAssignedMonth(PartialOutput):
    phase: Literal["xian", "hou"] | None = None
    gua: str | None = None
    assigned_month_number: int | None = Field(default=None, ge=1, le=12)
    assigned_month_branch: str | None = None
    assigned_month_match: bool | None = None
    selected_month_source: Literal["hexagram_intro", "volume_one_table"] | None = None
    source_readings: list[HeluoMonthSourceReading] | None = None
    source_months_agree: bool | None = None
    source_consensus_match: bool | None = None
    source_status: str | None = None
    source_pdf_page: int | None = Field(default=None, ge=1)
    additional_windows: list[HeluoAdditionalMonthWindow] | None = None
    natal_najia_clause: HeluoNatalNajiaClause | None = None
    opposed_month_conditions: bool | None = None
    conflict_rule_ids: list[str] | None = None


class HeluoMonthAffinity(PartialOutput):
    assignment_method: Literal["intro_preferred_v1", "volume_one_table_v1"] | None = (
        None
    )
    volume_one_explicit_months: int | None = Field(default=None, ge=0, le=64)
    source_assignment_conflicts: list[HeluoMonthAssignmentConflict] | None = None
    source_consensus_match: bool | None = Field(
        default=None,
        description="逐阶段两处来源对本月匹配结论的三值或；不是比较两个完整方法的deTime是否相同。缺号或阶段分歧保留null。",
    )
    ruleset_id: str | None = None
    version: str | None = None
    collation_version: str | None = None
    source_url: str | None = None
    review_status: str | None = None
    reviewed_hexagram_introductions: int | None = Field(default=None, ge=0, le=64)
    explicit_assigned_months: int | None = Field(default=None, ge=0, le=64)
    additional_month_clauses: int | None = Field(default=None, ge=0)
    registered_natal_najia_clauses: int | None = Field(default=None, ge=0, le=64)
    birth_month_branch: str | None = None
    birth_month_number: int | None = Field(default=None, ge=1, le=12)
    month_number_policy: str | None = None
    phases: list[HeluoAssignedMonth] | None = None
    complete_assessment: Literal[False] | None = None
    scope: str | None = None
    unresolved: list[str] | None = None


class HeluoBodyRelation(PartialOutput):
    body_id: str | None = None
    phase: Literal["xian", "hou"] | None = None
    gua: str | None = None
    kind: Literal["lower", "lower_nuclear", "upper_nuclear", "upper"] | None = None
    line_positions: list[Annotated[int, Field(ge=1, le=6)]] | None = None
    trigram: str | None = None
    element: HeluoBodyElement | None = None
    relation: (
        Literal[
            "same_element",
            "body_generates_nayin",
            "nayin_generates_body",
            "body_controls_nayin",
            "nayin_controls_body",
        ]
        | None
    ) = None
    yuanqi_kinds: list[Literal["tian", "di"]] | None = None


class HeluoGeneratingQi(PartialOutput):
    source_pdf_page: int | None = None
    direction: Literal["body_generates_nayin"] | None = None
    body_ids: list[str] | None = None
    relation_present: bool | None = None
    yuanqi_absence_required: Literal[True] | None = None
    condition_match: bool | None = None


class HeluoMutualGeneration(PartialOutput):
    source_pdf_page: int | None = None
    body_generates_nayin_ids: list[str] | None = None
    nayin_generates_body_ids: list[str] | None = None
    relation_present: bool | None = None
    scope: str | None = None


class HeluoBodyEvidence(PartialOutput):
    ruleset_id: str | None = None
    version: str | None = None
    source_url: str | None = None
    source_pdf_pages: list[int] | None = None
    assessment_status: str | None = None
    year_ganzhi: str | None = None
    nayin: str | None = None
    nayin_element: HeluoBodyElement | None = None
    nayin_policy: str | None = None
    body_scope_policy: str | None = None
    bodies: list[HeluoBodyRelation] | None = None
    same_element_body_ids: list[str] | None = None
    yuanqi_absent: bool | None = None
    generating_qi: HeluoGeneratingQi | None = None
    mutual_generation: HeluoMutualGeneration | None = None
    present: None = None
    complete_assessment: Literal[False] | None = None
    review_status: str | None = None
    unresolved: list[str] | None = None


class HeluoQiBody(PartialOutput):
    body_id: str | None = None
    gua: str | None = None
    kind: Literal["lower", "lower_nuclear", "upper_nuclear", "upper"] | None = None
    line_positions: list[Annotated[int, Field(ge=1, le=6)]] | None = None
    trigram: str | None = None


class HeluoQiMatch(PartialOutput):
    trigrams: list[str] | None = None
    direct_body_ids: list[str] | None = None
    nuclear_body_ids: list[str] | None = None
    present: bool | None = None


class HeluoQiMatches(PartialOutput):
    yuan_tian: HeluoQiMatch | None = None
    yuan_di: HeluoQiMatch | None = None
    fan_yuan_tian: HeluoQiMatch | None = None
    fan_yuan_di: HeluoQiMatch | None = None
    huagong: HeluoQiMatch | None = None
    fanhua: HeluoQiMatch | None = None


class HeluoQiPhase(PartialOutput):
    phase: Literal["xian", "hou"] | None = None
    gua: str | None = None
    bodies: list[HeluoQiBody] | None = None
    matches: HeluoQiMatches | None = None


class HeluoQiTransition(PartialOutput):
    kind: (
        Literal[
            "yuan_tian", "yuan_di", "fan_yuan_tian", "fan_yuan_di", "huagong", "fanhua"
        ]
        | None
    ) = None
    xian_present: bool | None = None
    hou_present: bool | None = None
    change: Literal["retained", "lost", "gained", "absent", "not_evaluated"] | None = (
        None
    )


class HeluoYuanqiOppositionCondition(PartialOutput):
    kind: Literal["tian", "di"] | None = None
    yuan_trigram: str | None = None
    fan_trigram: str | None = None
    yuan_body_ids: list[str] | None = None
    fan_body_ids: list[str] | None = None
    yuan_absent: bool | None = None
    fan_present: bool | None = None
    condition_match: bool | None = None
    direct_only_condition_match: bool | None = None
    rescue_match: Literal[None] = None

    @model_validator(mode="after")
    def preserve_known_premises(self) -> "HeluoYuanqiOppositionCondition":
        if self.yuan_body_ids is not None and self.yuan_absent is not None:
            if self.yuan_absent != (not self.yuan_body_ids):
                raise ValueError("元气缺席须与实际卦体位置一致。")
        if self.fan_body_ids is not None and self.fan_present is not None:
            if self.fan_present != bool(self.fan_body_ids):
                raise ValueError("反候选命中须与实际卦体位置一致。")
        if all(
            v is not None
            for v in (self.yuan_absent, self.fan_present, self.condition_match)
        ):
            if self.condition_match != (self.yuan_absent and self.fan_present):
                raise ValueError("无正而有反式不能省略无正前提。")
        return self


class HeluoYuanqiOppositionPhase(PartialOutput):
    phase: Literal["xian", "hou"] | None = None
    gua: str | None = None
    conditions: list[HeluoYuanqiOppositionCondition] | None = None


class HeluoYuanqiOpposition(PartialOutput):
    ruleset_id: str | None = None
    version: str | None = None
    source_title: str | None = None
    source_url: str | None = None
    source_pdf_pages: list[int] | None = None
    review_status: str | None = None
    year_context_literal: str | None = None
    absence_literal: str | None = None
    rescue_literal: str | None = None
    year_ganzhi: str | None = None
    body_scope_policy: str | None = None
    direct_only_policy: str | None = None
    phases: list[HeluoYuanqiOppositionPhase] | None = None
    full_rescue_assessment: Literal[False] | None = None
    unresolved: list[str] | None = None
    scope: str | None = None


class HeluoPhaseQi(PartialOutput):
    ruleset_id: str | None = None
    version: str | None = None
    source_url: str | None = None
    source_pdf_pages: list[int] | None = None
    candidate_basis: str | None = None
    birth_instant_utc: str | None = None
    fanhua_rule_ids: list[str] | None = None
    phases: list[HeluoQiPhase] | None = None
    transitions: list[HeluoQiTransition] | None = None
    yuanqi_opposition: HeluoYuanqiOpposition | None = None
    complete_assessment: Literal[False] | None = None
    scope: str | None = None
    unresolved: list[str] | None = None


class HeluoYuantangPlacement(PartialOutput):
    rule_id: str | None = None
    hour_zhi: str | None = None
    hour_half: Literal["yang", "yin"] | None = None
    hour_index: int | None = Field(default=None, ge=1, le=6)
    matching_positions: list[int] | None = None
    other_positions: list[int] | None = None
    slot_positions: list[int] | None = None
    selected_pos: int | None = Field(default=None, ge=1, le=6)
    pure_direction: Literal["ascending", "descending"] | None = None
    source_pdf_pages: list[int] | None = None


class HeluoHalfYearCounterfactual(PartialOutput):
    yang_ling: bool | None = None
    xian_yuan: int | None = Field(default=None, ge=1, le=6)
    hou_name: str | None = None
    hou_yuan: int | None = Field(default=None, ge=1, le=6)
    hou_lines: list[int] | None = None


class HeluoHalfYearResolution(PartialOutput):
    value: bool | None = None
    basis: str | None = None
    birth_instant_utc: str | None = None
    candidate_values: list[bool] | None = None
    yuantang_depends_on_half_year: bool | None = None
    houtian_depends_on_half_year: bool | None = None
    counterfactuals: list[HeluoHalfYearCounterfactual] | None = None
    result_selection: (
        Literal["resolved_half_year", "invariant_under_both_halves"] | None
    ) = None


class HeluoYuantangDerivation(PartialOutput):
    ruleset_id: str | None = None
    version: str | None = None
    source_url: str | None = None
    source_pdf_pages: list[int] | None = None
    review_status: str | None = None
    gender: Literal["男", "女"] | None = None
    half_year: HeluoHalfYearResolution | None = None
    placement: HeluoYuantangPlacement | None = None
    houtian_transform: dict[str, JsonValue] | None = None
    scope: str | None = None


class HeluoSolarTermRecord(CivilPointLabelEvidence):
    """The source facts consumed here; other receipt fields remain intact."""

    name: str | None = None


class HeluoSolarBoundary(PartialOutput):
    role: Literal["current_term", "preceding_solstice", "next_four_li"] | None = None
    record: HeluoSolarTermRecord | None = None
    instant_utc: str | None = None
    ephemeris_retflags: list[int] | None = None
    ephemeris_library_version: str | None = None

    @model_validator(mode="after")
    def same_instant(self) -> "HeluoSolarBoundary":
        if self.instant_utc is not None:
            at = ZonedCalendar.from_isoformat(self.instant_utc).utc
            civil = self.record.display_with_offset if self.record is not None else None
            if civil is not None and ZonedCalendar.from_isoformat(civil).utc != at:
                raise ValueError("实际交节记录与所列UTC瞬间不是同一时刻。")
        return self


class HeluoSolarContext(PartialOutput):
    policy_id: str | None = None
    comparison_policy: Literal["retained_nominal_civil_point_v1"] | None = None
    context_local_year: int | None = None
    context_timezone: str | None = None
    birth_instant_utc: str | None = None
    dependencies: list[HeluoSolarBoundary] | None = None
    environment_unchanged_at_observation_points: Literal[True] | None = None
    calendar_context_match: Literal[True] | None = None
    scope: str | None = None

    @model_validator(mode="after")
    def local_year_matches_instant(self) -> "HeluoSolarContext":
        if self.birth_instant_utc is not None:
            at = ZonedCalendar.from_isoformat(self.birth_instant_utc)
            if (
                self.context_timezone is not None
                and self.context_local_year is not None
            ):
                if (
                    ZonedCalendar(
                        at.utc, parse_timezone_name(self.context_timezone)
                    ).local_parts[0]
                    != self.context_local_year
                ):
                    raise ValueError(
                        "上下文年份须取已给时区的民用年，不能替换成UTC年。"
                    )
        return self


class HeluoSolarTermEvidence(PartialOutput):
    hg: list[str] | None = None
    fh: list[str] | None = None
    quarter: str | None = None
    tuyong: bool | None = None
    fanhua_rule_ids: list[str] | None = None
    term: str | None = None
    yang_ling: bool | None = None
    anchor_utc: str | None = None
    precision: Literal["birth_instant", "date_midnight_approximation"] | None = None
    tuyong_policy: str | None = None
    tuyong_start_utc: str | None = None
    tuyong_end_utc: str | None = None
    comparison_policy: Literal["retained_nominal_civil_point_v1"] | None = None
    tuyong_start_point: CivilPointEvidence | None = None
    tuyong_end_point: CivilPointEvidence | None = None
    boundary_context: HeluoSolarContext | None = None

    @model_validator(mode="after")
    def known_boundary_facts(self) -> "HeluoSolarTermEvidence":
        context = self.boundary_context
        if context is None:
            return self
        if self.anchor_utc is not None and context.birth_instant_utc is not None:
            if ZonedCalendar.from_isoformat(self.anchor_utc).utc != (
                ZonedCalendar.from_isoformat(context.birth_instant_utc).utc
            ):
                raise ValueError("节气上下文与出生锚点不一致。")
        roles = {r.role: r for r in context.dependencies or [] if r.role is not None}
        if (row := roles.get("current_term")) is not None and row.record is not None:
            if (
                self.term is not None
                and row.record.name is not None
                and row.record.name != self.term
            ):
                raise ValueError("实际交节记录与所列节气不一致。")
        if (
            row := roles.get("preceding_solstice")
        ) is not None and row.record is not None:
            if self.yang_ling is not None and row.record.name in {"冬至", "夏至"}:
                if self.yang_ling != (row.record.name == "冬至"):
                    raise ValueError("阴阳令须与实际最近至点一致。")
        if self.anchor_utc is not None:
            anchor = ZonedCalendar.from_isoformat(
                self.anchor_utc
            ).utc.julian_day_exact()
            for role, row in roles.items():
                point = row.record.civil_point if row.record is not None else None
                day = point.known_day() if point is not None else None
                if day is not None:
                    if (role == "next_four_li" and day <= anchor) or (
                        role != "next_four_li" and day > anchor
                    ):
                        raise ValueError("交节包含端点与下一四立的时序不一致。")
        start = (
            self.tuyong_start_point.known_day()
            if self.tuyong_start_point is not None
            else None
        )
        end = (
            self.tuyong_end_point.known_day()
            if self.tuyong_end_point is not None
            else None
        )
        if start is not None and end is not None:
            if start != end - 18:
                raise ValueError("土用精确起点须为下一四立主点前十八个名义日。")
            if self.tuyong is not None and self.anchor_utc is not None:
                anchor = ZonedCalendar.from_isoformat(
                    self.anchor_utc
                ).utc.julian_day_exact()
                if self.tuyong != (start <= anchor < end):
                    raise ValueError("土用匹配与所列精确民用边界不一致。")
        if (row := roles.get("next_four_li")) is not None:
            point = row.record.civil_point if row.record is not None else None
            source_end = point.known_day() if point is not None else None
            if source_end is not None and end is not None and source_end != end:
                raise ValueError("土用终点与下一四立精确主点不一致。")
            if row.instant_utc is not None:
                end_label = ZonedCalendar.from_isoformat(row.instant_utc).utc
                start_label = UTCCalendar(
                    end_label.ordinal - 18, end_label.microseconds_of_day
                )
                if (
                    self.tuyong_start_utc is not None
                    and ZonedCalendar.from_isoformat(self.tuyong_start_utc).utc
                    != start_label
                ):
                    raise ValueError("土用显示起点须为四立显示标签前十八个名义日。")
                if (
                    self.tuyong_end_utc is not None
                    and ZonedCalendar.from_isoformat(self.tuyong_end_utc).utc
                    != end_label
                ):
                    raise ValueError("土用显示终点须为本次下一四立显示标签。")
        return self


class HeluoRulerMinisterSeat(PartialOutput):
    source_pdf_page: int | None = None
    positions: list[int] | None = None
    match: bool | None = None
    scope: str | None = None


class HeluoZhongzong(PartialOutput):
    source_pdf_page: int | None = None
    yang_count: int | None = Field(default=None, ge=0, le=6)
    yin_count: int | None = Field(default=None, ge=0, le=6)
    # note (schema): Preserve the published order when the opposite literal is cached.
    minority_polarity: Annotated[Literal["yang", "yin"], Field()] | None = None
    minority_pos: int | None = Field(default=None, ge=1, le=6)
    match: bool | None = None


class HeluoSourceYouyuan(PartialOutput):
    rule_id: Literal["wenming_yin_yuantang_yang_corresponding_v1"] | None = None
    source_pdf_page: int | None = None
    selected_pos: int | None = Field(default=None, ge=1, le=6)
    selected_yang: bool | None = None
    corresponding_pos: int | None = Field(default=None, ge=1, le=6)
    corresponding_yang: bool | None = None
    polarity_opposed: bool | None = None
    required_selected_yang: Literal[False] | None = None
    required_corresponding_yang: Literal[True] | None = None
    clause_match: bool | None = None
    scope: (
        Literal[
            "named_primary_yin_line_yang_corresponding_clause_only; not_full_ten_condition_verdict"
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def coherent_correspondence_and_clause(self) -> "HeluoSourceYouyuan":
        if self.selected_pos is not None and self.corresponding_pos is not None:
            expected = (
                self.selected_pos + 3
                if self.selected_pos <= 3
                else self.selected_pos - 3
            )
            if self.corresponding_pos != expected:
                raise ValueError("有援原句须使用同卦实际对应爻位。")
        if self.selected_yang is not None and self.corresponding_yang is not None:
            if self.polarity_opposed is not None and self.polarity_opposed != (
                self.selected_yang != self.corresponding_yang
            ):
                raise ValueError("相应阴阳事实不一致。")
            if self.clause_match is not None and self.clause_match != (
                not self.selected_yang and self.corresponding_yang
            ):
                raise ValueError("有援所选主本原句不能用通用相应或反向相应替代。")
        return self


class HeluoLineConditionRow(PartialOutput):
    phase: Literal["xian", "hou"] | None = None
    gua: str | None = None
    lines: list[Annotated[int, Field(ge=0, le=1)]] | None = None
    pos: int | None = Field(default=None, ge=1, le=6)
    yang: bool | None = None
    position_polarity_match: bool | None = None
    position_preference_order: int | None = Field(default=None, ge=1, le=4)
    ruler_minister_seat: HeluoRulerMinisterSeat | None = None
    zhongzong: HeluoZhongzong | None = None
    source_youyuan: HeluoSourceYouyuan | None = None

    @model_validator(mode="after")
    def coherent_selected_phase_support(self) -> "HeluoLineConditionRow":
        aid = self.source_youyuan
        if aid is None:
            return self
        if (
            self.pos is not None
            and aid.selected_pos is not None
            and self.pos != aid.selected_pos
        ):
            raise ValueError("有援原句的元堂须属于本阶段。")
        if (
            self.yang is not None
            and aid.selected_yang is not None
            and self.yang != aid.selected_yang
        ):
            raise ValueError("有援原句的元堂阴阳须属于本阶段。")
        if self.lines is not None:
            if len(self.lines) != 6:
                raise ValueError("有援原句需要同卦六爻事实。")
            for pos, yang in [
                (aid.selected_pos, aid.selected_yang),
                (aid.corresponding_pos, aid.corresponding_yang),
            ]:
                if (
                    pos is not None
                    and yang is not None
                    and bool(self.lines[pos - 1]) != yang
                ):
                    raise ValueError("有援原句的爻阴阳与本阶段六爻不一致。")
        return self


class HeluoSourceDangwei(PartialOutput):
    source_pdf_page: int | None = None
    literal_condition: str | None = None
    status: Literal["yinyue_definition_pending"] | None = None
    month_polarity: None = None
    match: None = None
    line_index_parity_substituted: Literal[False] | None = None
    solstice_half_year_substituted: Literal[False] | None = None


class HeluoLineConditions(PartialOutput):
    ruleset_id: str | None = None
    version: str | None = None
    source_url: str | None = None
    source_pdf_pages: list[int] | None = None
    review_status: str | None = None
    literal_clauses: dict[str, dict[str, JsonValue]] | None = None
    position_preference_policy: str | None = None
    phases: list[HeluoLineConditionRow] | None = None
    source_dangwei: HeluoSourceDangwei | None = None
    complete_assessment: Literal[False] | None = None
    ten_condition_score: None = None
    scope: str | None = None
    constraints: list[str] | None = None


class HeluoStructureRecord(PartialOutput):
    kind: (
        Literal[
            "lower",
            "upper",
            "lower_reversed",
            "upper_reversed",
            "upper_nuclear",
            "lower_nuclear",
            "third_to_top",
            "reverse_then_third_to_top",
        ]
        | None
    ) = None
    arity: Literal[3, 6] | None = None
    original_positions: list[Annotated[int, Field(ge=1, le=6)]] | None = None
    lines: list[Annotated[int, Field(ge=0, le=1)]] | None = None
    name: str | None = None

    @model_validator(mode="after")
    def coherent_operator(self) -> "HeluoStructureRecord":
        arities = [
            len(value)
            for value in (self.original_positions, self.lines)
            if value is not None
        ]
        if self.arity is not None:
            arities.append(self.arity)
        if self.kind is not None:
            expected = dict(OPERATORS)[self.kind]
            arities.append(len(expected))
            if self.original_positions is not None and self.original_positions != list(
                expected
            ):
                raise ValueError("卦体结构须保留实际取爻次序。")
        if any(arity not in (3, 6) for arity in arities) or len(set(arities)) > 1:
            raise ValueError("卦体结构的种类、爻数、原位与爻形不能混用三爻或六爻。")
        if self.lines is not None and self.name is not None:
            if _name(self.lines) != self.name:
                raise ValueError("卦体结构名称与爻形不一致。")
        return self


class HeluoWholeReversal(PartialOutput):
    original_positions: list[Annotated[int, Field(ge=1, le=6)]] | None = None
    lines: list[Annotated[int, Field(ge=0, le=1)]] | None = None
    name: str | None = None

    @model_validator(mode="after")
    def coherent_reversal(self) -> "HeluoWholeReversal":
        if self.original_positions is not None and self.original_positions != [
            6,
            5,
            4,
            3,
            2,
            1,
        ]:
            raise ValueError("全卦倒序须保留六爻次序。")
        if self.lines is not None:
            if len(self.lines) != 6 or (
                self.name is not None and _name(self.lines) != self.name
            ):
                raise ValueError("全卦倒序名称与六爻不一致。")
        return self


class HeluoStructurePhase(PartialOutput):
    phase: Literal["xian", "hou"] | None = None
    gua: str | None = None
    input_lines: list[Annotated[int, Field(ge=0, le=1)]] | None = None
    records: list[HeluoStructureRecord] | None = None
    record_count: Literal[8] | None = None
    whole_reversal: HeluoWholeReversal | None = None
    literal_case_match: bool | None = None
    literal_names_reproduced: bool | None = None
    source_application: (
        Literal[
            "named_jian_paragraph",
            "permutation_derivation; not_this_hexagrams_literal_source_example",
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def coherent_phase(self) -> "HeluoStructurePhase":
        if self.gua is not None and self.literal_case_match is not None:
            if self.literal_case_match != (self.gua == "風山漸"):
                raise ValueError("不能把其他卦标为所核渐卦原例。")
        if (
            self.literal_case_match is False
            and self.literal_names_reproduced is not None
        ):
            raise ValueError("其他卦的推演不冒充新增原例核对。")
        if self.literal_case_match is not None and self.source_application is not None:
            expected_basis = (
                "named_jian_paragraph"
                if self.literal_case_match
                else "permutation_derivation; not_this_hexagrams_literal_source_example"
            )
            if self.source_application != expected_basis:
                raise ValueError("原例与算子推演的来源标签不一致。")
        if self.records is not None:
            if len(self.records) != 8:
                raise ValueError("所列结构应保留八条记录，包括重复名称。")
            for row, (kind, _) in zip(self.records, OPERATORS):
                if row.kind is not None and row.kind != kind:
                    raise ValueError("结构记录次序不一致。")
            if (
                self.literal_case_match is True
                and self.literal_names_reproduced is not None
                and all(row.name is not None for row in self.records)
                and self.whole_reversal is not None
                and self.whole_reversal.name is not None
            ):
                reproduced = [row.name for row in self.records] == [
                    "艮",
                    "巽",
                    "震",
                    "兌",
                    "離",
                    "坎",
                    "天地否",
                    "地天泰",
                ] and self.whole_reversal.name == "雷澤歸妹"
                if self.literal_names_reproduced != reproduced:
                    raise ValueError("原例复现标记与实际结构名称不一致。")
        if self.input_lines is not None:
            if len(self.input_lines) != 6 or (
                self.gua is not None and _name(self.input_lines) != self.gua
            ):
                raise ValueError("同阶段卦名与输入六爻不一致。")
            for row in self.records or []:
                if row.original_positions is not None and row.lines is not None:
                    if row.lines != [
                        self.input_lines[p - 1] for p in row.original_positions
                    ]:
                        raise ValueError("结构记录不能借用另一阶段爻形或翻转阴阳。")
            if (
                self.whole_reversal is not None
                and self.whole_reversal.lines is not None
            ):
                if self.whole_reversal.lines != self.input_lines[::-1]:
                    raise ValueError("全卦倒序不能变爻。")
        return self


class HeluoFiveMingTerminology(PartialOutput):
    symbol_readings: dict[str, str] | None = None
    source_pdf_pages: list[int] | None = None
    selected_pillar: None = None
    nayin_substituted: Literal[False] | None = None
    scope: (
        Literal["literal_symbol_lists_only; no_global_person_element_selection"] | None
    ) = None


class HeluoBodyStructure(PartialOutput):
    ruleset_id: Literal["heluo_wenming_jian_structure_v1"] | None = None
    version: str | None = None
    source_url: str | None = None
    source_pdf_pages: list[int] | None = None
    calculation_source_pdf_pages: list[int] | None = None
    review_status: str | None = None
    wording_variants: list[dict[str, str]] | None = None
    phases: list[HeluoStructurePhase] | None = None
    five_ming_terminology: HeluoFiveMingTerminology | None = None
    scope: str | None = None
    complete_futi_assessment: Literal[False] | None = None
    complete_assessment: Literal[False] | None = None
    constraints: list[str] | None = None


class HeluoSelectedYuantang(PartialOutput):
    pos: Literal[1, 2, 3, 4, 5, 6] | None = None
    yang: bool | None = None
    position_polarity_match: bool | None = None
    youYing: bool | None = None
    youYing_policy: str | None = None
    heLi: bool | None = None
    heLi_policy: str | None = None


class HeluoJudge(PartialOutput):
    assessment_status: str | None = None
    xie_policy: str | None = None
    deSheng_policy: str | None = None
    deTime_policy: str | None = None
    deTi_policy: str | None = None
    najia: list[HeluoNajiaAssessment] | None = None
    deSheng: bool | None = None
    deTime: bool | None = None
    month_affinity: HeluoMonthAffinity | None = None
    xie: bool | None = None
    yuan: dict[str, JsonValue] | None = None
    fanYuan: dict[str, JsonValue] | None = None
    fanYuan_policy: str | None = None
    huagong: dict[str, JsonValue] | None = None
    fanhua: dict[str, JsonValue] | None = None
    qi_phases: HeluoPhaseQi | None = None
    deTi: HeluoBodyEvidence | None = None
    erShu: dict[str, JsonValue] | None = None
    seasonal_numbers: HeluoSeasonalNumbers | None = None
    yuanTang: HeluoSelectedYuantang | None = None
    line_conditions: HeluoLineConditions | None = None
    body_structure: HeluoBodyStructure | None = None


class HeluoTimingRow(PartialOutput):
    gua: str | None = None
    lines: list[int] | None = None
    pos: int | None = None
    changed_pos: int | None = None
    input_lines: list[int] | None = None
    ordinal_in_period: int | None = None
    age: int | None = None
    year_label: int | None = None
    ganzhi: str | None = None
    phase: str | None = None
    period_index: int | None = None
    period_pos: int | None = None
    period_start_yang: bool | None = None
    month_index: int | None = None
    parent_month_index: int | None = None
    rule_id: str | None = None
    block_index: int | None = None
    day_index: int | None = None


class HeluoTimingYearContext(PartialOutput):
    cycle_year: int | None = None
    birth_ganzhi: str | None = None
    expected_ganzhi: str | None = None
    matches: _KnownTrue | None = None
    basis: (
        Literal["selected_pillar_year_label; not_civil_birth_year_substitution"] | None
    ) = None

    @model_validator(mode="after")
    def consistent_year(self) -> "HeluoTimingYearContext":
        for gz in (self.birth_ganzhi, self.expected_ganzhi):
            if gz is not None and gz not in HELUO_CYCLE:
                raise ValueError("岁运年上下文须用有效六十甲子。")
            if (
                gz is not None
                and self.cycle_year is not None
                and gz != HELUO_CYCLE[(self.cycle_year - 4) % 60]
            ):
                raise ValueError("岁运年标签与年柱不一致。")
        if (
            self.birth_ganzhi is not None
            and self.expected_ganzhi is not None
            and self.birth_ganzhi != self.expected_ganzhi
        ):
            raise ValueError("岁运实际与预期年柱不一致。")
        return self


class HeluoClockRatio(PartialOutput):
    numerator: int | None = None
    denominator: int | None = Field(default=None, gt=0)


class HeluoClockBranch(PartialOutput):
    branch: (
        Literal["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
        | None
    ) = None
    length_ke: Literal[8, 9] | None = None

    @model_validator(mode="after")
    def source_length(self) -> "HeluoClockBranch":
        if (
            self.branch is not None
            and self.length_ke is not None
            and self.length_ke != (9 if self.branch in "寅申巳亥" else 8)
        ):
            raise ValueError("卷一九刻支组不能换成等长或其他支组。")
        return self


class HeluoClockDailyExtra(PartialOutput):
    ke: Annotated[Literal[1], BeforeValidator(_not_a_boolean_number)] | None = None
    fen: Literal[7] | None = None
    fen_per_ke: None = None


class HeluoClockAnnualExtra(PartialOutput):
    nominal_days: Literal[360] | None = None
    printed_days: Literal[365] | None = None
    monthly_extra_shi: Literal[5] | None = None
    months: Literal[12] | None = None
    annual_extra_shi: Literal[60] | None = None


class HeluoClockProjection(PartialOutput):
    extra_ke_per_nominal_day: HeluoClockRatio | None = None
    fen_per_ke_required_for_numeric_closure: HeluoClockRatio | None = None
    derived_only: _KnownTrue | None = None
    source_fen_scale_verified: _KnownFalse | None = None

    @model_validator(mode="after")
    def only_a_conditional_projection(self) -> "HeluoClockProjection":
        for value, n, d in (
            (self.extra_ke_per_nominal_day, 25, 18),
            (self.fen_per_ke_required_for_numeric_closure, 18, 1),
        ):
            if (
                value is not None
                and value.numerator is not None
                and value.denominator is not None
                and (value.numerator, value.denominator) != (n, d)
            ):
                raise ValueError("等时条件推算与所列年余量不一致。")
        return self


class HeluoClockBranchShift(PartialOutput):
    year_blocks: Literal[60] | None = None
    extra_shi: Literal[60] | None = None
    extra_ke: Literal[500] | None = None
    total_source_days: HeluoClockRatio | None = None
    origin_basis: (
        Literal["full_cycles_total_invariant; no_physical_origin_selected"] | None
    ) = None
    branch_start_only: _KnownTrue | None = None
    derived_only: _KnownTrue | None = None
    source_fen_scale_selected: _KnownFalse | None = None
    daily_internal_distribution_resolved: _KnownFalse | None = None

    @model_validator(mode="after")
    def conditional_total(self) -> "HeluoClockBranchShift":
        value = self.total_source_days
        if (
            value is not None
            and value.numerator is not None
            and value.denominator is not None
            and (value.numerator, value.denominator) != (365, 1)
        ):
            raise ValueError("六十支移位的源刻总量与所列大数年不一致。")
        return self


class HeluoSourceClock(PartialOutput):
    ruleset_id: Literal["heluo_wenming_baike_clock_v1"] | None = None
    version: str | None = None
    source_title: str | None = None
    source_url: str | None = None
    source_pdf_pages: list[int] | None = None
    review_status: str | None = None
    scope: str | None = None
    day_ke: Literal[100] | None = None
    base_ke: Literal[96] | None = None
    extra_ke: Literal[4] | None = None
    branch_lengths: list[HeluoClockBranch] | None = None
    extra_branches_in_printed_order: list[str] | None = None
    physical_origin_branch: None = None
    daily_extra_literal: HeluoClockDailyExtra | None = None
    annual_extra_literal: HeluoClockAnnualExtra | None = None
    branch_shift_projection: HeluoClockBranchShift | None = None
    equal_shi_projection: HeluoClockProjection | None = None
    physical_clock_applied: _KnownFalse | None = None
    calendar_mapping_complete: _KnownFalse | None = None
    constraints: list[str] | None = None

    @model_validator(mode="after")
    def source_counts_and_unresolved_origin(self) -> "HeluoSourceClock":
        if (
            self.extra_branches_in_printed_order is not None
            and self.extra_branches_in_printed_order != ["寅", "申", "巳", "亥"]
        ):
            raise ValueError("应保留原印寅申巳亥组及次序。")
        if self.branch_lengths is not None:
            if len(self.branch_lengths) != 12:
                raise ValueError("百刻循环须保留十二支。")
            if all(b.branch is not None for b in self.branch_lengths) and [
                b.branch for b in self.branch_lengths
            ] != list("子丑寅卯辰巳午未申酉戌亥"):
                raise ValueError("展示用循环支序不能混换。")
            if (
                all(b.length_ke is not None for b in self.branch_lengths)
                and sum(
                    b.length_ke for b in self.branch_lengths if b.length_ke is not None
                )
                != 100
            ):
                raise ValueError("十二支原刻总数须为一百。")
        return self


class HeluoTiming(PartialOutput):
    year_context: HeluoTimingYearContext | None = None
    source_clock: HeluoSourceClock | None = None
    ruleset_id: str | None = None
    ruleset_version: str | None = None
    source_title: str | None = None
    source_url: str | None = None
    source_pdf_pages: list[int] | None = None
    scope: str | None = None
    calendar_policy: dict[str, str] | None = None
    annual_rows: list[HeluoTimingRow] | None = None
    selected_annual: HeluoTimingRow | None = None
    monthly_rows: list[HeluoTimingRow] | None = None
    selected_month: HeluoTimingRow | None = None
    daily_template: list[HeluoTimingRow] | None = None
    selected_day: HeluoTimingRow | None = None
    selected_texts: list[dict[str, JsonValue]] | None = None


class HeluoHexagram(PartialOutput):
    lines: list[int] | None = None
    name: str | None = None
    yuan: int | None = None
    low: str | None = None
    up: str | None = None


class HeluoChart(PartialOutput):
    cycleYear: int | None = None
    yuanCycle: str | None = None
    yangLingBasis: str | None = None
    yuantang_derivation: HeluoYuantangDerivation | None = None
    di: int | None = None
    diGua: str | None = None
    diNum: int | None = None
    gender: str | None = None
    hourZhi: str | None = None
    tian: int | None = None
    tianGua: str | None = None
    tianNum: int | None = None
    tianTop: bool | None = None
    yangGan: bool | None = None
    yangLing: bool | None = None
    yangMing: bool | None = None
    hou: HeluoHexagram | None = None
    xian: HeluoHexagram | None = None


class HeluoPeriod(PartialOutput):
    ageEnd: int | None = None
    ageStart: int | None = None
    gua: str | None = None
    lines: list[int] | None = None
    pos: int | None = None
    yang: bool | None = None
    yearStart: int | None = None
    years: int | None = None


class HeluoDayun(PartialOutput):
    all: list[HeluoPeriod] | None = None
    hou: list[HeluoPeriod] | None = None
    xian: list[HeluoPeriod] | None = None
    endAge: int | None = None
    xianEndAge: int | None = None


class NumerologyRuleset(PartialOutput):
    ruleset_id: str | None = None
    version: str | None = None
    source_title: str | None = None
    source_url: str | None = None
    source_status: str | None = None
    authorship_status: str | None = None


class NumerologyValidation(PartialOutput):
    calendar: str | None = None
    classical: str | None = None
    interpretation: str | None = None
    prediction: str | None = None


class NumerologyCalendarPolicy(PartialOutput):
    input_calendar: Literal["proleptic_gregorian"] | None = None
    automatic_reform_cutover: Literal[False] | None = None
    historical_lunar_date_conversion: Literal[False] | None = None
    historical_official_calendar_reconstruction: Literal[False] | None = None


def _uncertified_clock_precision(value: object) -> Literal[False]:
    if value is not False:
        raise ValueError("钟时文本分量不能认证出生记录精度。")
    return value


class NumerologyClockInput(PartialOutput):
    policy_id: Literal["numerology_clock_text_provenance_v1"] | None = None
    supplied_text: str | None = None
    normalized_clock: str | None = None
    supplied_components: (
        list[Literal["hour", "minute", "second", "fractional_second"]] | None
    ) = None
    omitted_components: list[Literal["second", "fractional_second"]] | None = None
    fractional_digits: int | None = Field(default=None, ge=0, le=6)
    calculation_defaults: dict[Literal["second", "microsecond"], int] | None = None
    uncertainty_interval: None = None
    observed_precision_certified: (
        Annotated[Literal[False], BeforeValidator(_uncertified_clock_precision)] | None
    ) = None
    scope: str | None = None
    statement: str | None = None

    @model_validator(mode="after")
    def coherent_supplied_components(self) -> "NumerologyClockInput":
        if self.scope is not None and self.scope != CLOCK_INPUT_SCOPE:
            raise ValueError("出生钟时分量的范围声明不一致。")
        if self.calculation_defaults is not None and any(
            v != 0 for v in self.calculation_defaults.values()
        ):
            raise ValueError("未给钟时分量的计算参考值须为零。")
        for components in (self.supplied_components, self.omitted_components):
            if components is not None and len(components) != len(set(components)):
                raise ValueError("钟时分量不能重复。")
        if self.normalized_clock is not None and (
            require_birth_clock(self.normalized_clock) != self.normalized_clock
        ):
            raise ValueError("计算参考钟面须为归一化格式。")
        if self.supplied_text is not None:
            expected = clock_input_representation(self.supplied_text)
            for k in self.model_fields_set:
                if k in expected and getattr(self, k) != expected[k]:
                    raise ValueError("所给钟时文本与分量回执不一致。")
        if self.supplied_components is not None and self.omitted_components is not None:
            if set(self.supplied_components) & set(self.omitted_components):
                raise ValueError("同一钟时分量不能同时为已给和未给。")
        return self


class NumerologyBirthClock(PartialOutput):
    policy_id: str | None = None
    mode: Literal["civil", "apparent_solar"] | None = None
    calendar_policy: NumerologyCalendarPolicy | None = None
    timezone_policy_id: str | None = None
    timezone_spec: str | None = None
    timezone_default_policy: str | None = None
    timezone_rules: dict[str, JsonValue] | None = None
    civil_utc_offset_seconds: (
        Annotated[int, Field(gt=-86400, lt=86400)]
        | Annotated[FiniteFloat, Field(gt=-86400, lt=86400)]
        | None
    ) = Field(
        default=None,
        description="Actual UTC offset in seconds, retaining fractional seconds at datetime microsecond resolution; integral offsets remain integers.",
    )
    civil_daylight_saving_seconds: int | None = None
    civil_datetime: str | None = None
    birth_instant_utc: str | None = None
    calculation_wall_clock: str | None = None
    longitude: float | None = Field(default=None, ge=-180, le=180)
    longitude_source: Literal["longitude"] | None = None
    longitude_used: bool | None = None
    longitude_selection_policy: str | None = None
    total_correction_minutes: float | None = None
    pillar_clock_policy: str | None = None
    precision_scope: str | None = None
    input_representation: NumerologyClockInput | None = None
    birth_utc_offset_policy_id: (
        Literal["numerology_confirmed_civil_offset_v1"] | None
    ) = None
    requested_utc_offset: str | None = None
    civil_utc_offset: str | None = None
    civil_fold: int | None = Field(default=None, ge=0, le=1)
    civil_time_ambiguous: bool | None = None
    offset_selection_scope: str | None = None

    @model_validator(mode="after")
    def coherent_selected_birth_offset(self) -> "NumerologyBirthClock":
        """Check present receipts, without needing siblings lost in projection."""
        offsets = [
            normalize_numerology_utc_offset(value)
            for value in (self.requested_utc_offset, self.civil_utc_offset)
            if value is not None
        ]
        if len(set(offsets)) > 1:
            raise ValueError("出生偏移回执与已确认偏移不一致。")
        civil = (
            parse_iso_datetime(self.civil_datetime)
            if self.civil_datetime is not None
            else None
        )
        if civil is not None:
            if (
                self.input_representation is not None
                and self.input_representation.normalized_clock is not None
            ):
                if civil.time() != time.fromisoformat(
                    self.input_representation.normalized_clock
                ):
                    raise ValueError("出生民用钟面与所给分量的计算参考值不一致。")
            offset = civil.utcoffset()
            if offset is None:
                raise ValueError("出生民用时刻回执须带实际偏移。")
            if offsets and offsets[0] != format_utc_offset(offset):
                raise ValueError("出生民用时刻与偏移回执不一致。")
            if (
                self.civil_utc_offset_seconds is not None
                and self.civil_utc_offset_seconds != offset.total_seconds()
            ):
                raise ValueError("出生民用时刻与偏移秒数不一致。")
        if self.birth_instant_utc is not None:
            actual = ZonedCalendar.from_isoformat(self.birth_instant_utc)
            if civil is not None and actual.utc != utc_calendar(civil):
                raise ValueError("出生民用时刻与UTC瞬间回执不一致。")
        if self.civil_time_ambiguous is False and self.civil_fold == 1:
            raise ValueError("非重复出生钟时不能标记第二次出现。")
        return self


class HeluoNajiaCollation(PartialOutput):
    ruleset_id: str | None = None
    version: str | None = None
    source_url: str | None = None
    review_status: str | None = None
    pure_trigram_tables: int | None = Field(default=None, ge=0, le=8)
    pure_table_assignment_slots: int | None = Field(default=None, ge=0, le=48)
    pure_table_borrowed_slots: int | None = Field(default=None, ge=0, le=12)
    directly_collated_hexagrams: int | None = Field(default=None, ge=0, le=64)
    other_hexagrams_not_individually_collated: int | None = Field(
        default=None, ge=0, le=64
    )
    direct_assignment_observations: int | None = Field(default=None, ge=0)
    borrowed_assignment_observations: int | None = Field(default=None, ge=0)
    source_pdf_pages: list[int] | None = None
    source_order_issues: list[dict[str, JsonValue]] | None = None
    unquantified_timing_najia_clauses: list[dict[str, JsonValue]] | None = None
    complete_assessment: Literal[False] | None = None
    scope: str | None = None


class NumerologyPillarLink(PartialOutput):
    target: Literal["month", "hour"] | None = None
    basis: Literal["year", "day"] | None = None
    basis_pillar: str | None = None
    basis_stem: str | None = None
    source_stem_group: str | None = None
    head_pillar: str | None = None
    branch_step: int | None = Field(default=None, ge=0, le=11)
    actual_pillar: str | None = None
    expected_pillar: str | None = None
    matches: bool | None = None

    @model_validator(mode="after")
    def coherent_stem_link(self) -> "NumerologyPillarLink":
        for value in (
            self.basis_pillar,
            self.head_pillar,
            self.actual_pillar,
            self.expected_pillar,
        ):
            if value is not None and value not in CYCLE:
                raise ValueError("干支衔接证据须用有效六十甲子。")
        if (
            self.target is not None
            and self.basis is not None
            and self.basis != {"month": "year", "hour": "day"}[self.target]
        ):
            raise ValueError("月干须据年干，时干须据所用日干。")
        if self.basis_stem is not None:
            if self.basis_stem not in GAN or len(self.basis_stem) != 1:
                raise ValueError("所用基准干无效。")
            if (
                self.basis_pillar is not None
                and self.basis_stem != self.basis_pillar[0]
            ):
                raise ValueError("基准干不能替成公历年干或未换日日干。")
            if (
                self.source_stem_group is not None
                and self.basis_stem not in self.source_stem_group
            ):
                raise ValueError("原句干组不含实际基准干。")
            if (
                self.target is not None
                and self.head_pillar is not None
                and self.head_pillar
                != LINK_HEADS[self.target][GAN.index(self.basis_stem)]
            ):
                raise ValueError("实际基准干对应的原句头干不一致。")
            if (
                self.source_stem_group is not None
                and self.source_stem_group != LINK_GROUPS[GAN.index(self.basis_stem)]
            ):
                raise ValueError("原句干组不能任意扩大。")
        if (
            self.target is not None
            and self.head_pillar is not None
            and self.actual_pillar is not None
            and self.branch_step is not None
        ):
            order = "寅卯辰巳午未申酉戌亥子丑" if self.target == "month" else ZHI
            if (
                self.head_pillar[1] != order[0]
                or order.index(self.actual_pillar[1]) != self.branch_step
            ):
                raise ValueError("月、时支序或起头支不一致。")
        if (
            self.head_pillar is not None
            and self.branch_step is not None
            and self.expected_pillar is not None
        ):
            if (
                self.expected_pillar[0]
                != GAN[(GAN.index(self.head_pillar[0]) + self.branch_step) % 10]
            ):
                raise ValueError("顺行干序与原句头干不一致。")
        if self.actual_pillar is not None and self.expected_pillar is not None:
            if self.actual_pillar[1] != self.expected_pillar[1] or (
                self.matches is not None
                and self.matches != (self.actual_pillar == self.expected_pillar)
            ):
                raise ValueError("干支衔接匹配标记或实际支不一致。")
        return self


class NumerologyPillarLinks(PartialOutput):
    ruleset_id: Literal["heluo_volume7_pillar_links_v1"] | None = None
    version: str | None = None
    source_title: str | None = None
    source_url: str | None = None
    source_pdf_pages: list[int] | None = None
    review_status: str | None = None
    authorship_status: str | None = None
    pillars: dict[str, str] | None = None
    links: list[NumerologyPillarLink] | None = None
    all_links_match: bool | None = None
    basis_policy: (
        Literal[
            "actual_selected_year_and_day_pillars; no_civil_year_or_unrolled_day_substitution"
        ]
        | None
    ) = None
    scope: str | None = None
    complete_calendar_assessment: Literal[False] | None = None
    constraint: str | None = None

    @model_validator(mode="after")
    def coherent_pillar_facts(self) -> "NumerologyPillarLinks":
        if self.links is not None:
            if len(self.links) != 2:
                raise ValueError("应保留起月、起时两条衔接证据。")
            for row, target, basis in zip(
                self.links, ("month", "hour"), ("year", "day")
            ):
                if row.target is not None and row.target != target:
                    raise ValueError("起月起时记录不能互换。")
                if self.pillars is not None:
                    if (
                        basis in self.pillars
                        and row.basis_pillar is not None
                        and row.basis_pillar != self.pillars[basis]
                    ):
                        raise ValueError("衔接证据基准柱不属于本次四柱。")
                    if (
                        target in self.pillars
                        and row.actual_pillar is not None
                        and row.actual_pillar != self.pillars[target]
                    ):
                        raise ValueError("衔接证据实际柱不属于本次四柱。")
            if self.all_links_match is not None and all(
                r.matches is not None for r in self.links
            ):
                if self.all_links_match != all(r.matches for r in self.links):
                    raise ValueError("衔接总标记与两条实际结果不一致。")
        return self


class NumerologyEvidence(PartialOutput):
    corpus_status: str | None = None
    najia_collation: HeluoNajiaCollation | None = None
    yaoci_collation: dict[str, JsonValue] | None = None
    commentary_collation: dict[str, JsonValue] | None = None
    canping_text_collation: dict[str, JsonValue] | None = None
    validation_status: NumerologyValidation | None = None
    interpretation_constraints: list[str] | None = None
    unresolved_rules: list[str] | None = None
    selected_texts: list[dict[str, JsonValue]] | None = None
    birth_clock: NumerologyBirthClock | None = None
    pillar_links: NumerologyPillarLinks | None = None


class CanpingOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    benming: CanpingRow | None = None
    calendar_context: CalendarContext | None = None
    canping_timing: CanpingTiming | None = None
    day_palace_branch: str | None = None
    dayun: list[CanpingRow] | None = None
    element: str | None = None
    four_pillars: FourPillars | None = None
    liunian_series: CanpingSeries | None = None
    ming_gong: str | None = None
    numerology_evidence: NumerologyEvidence | None = None
    part_name: str | None = None
    summary: Object | list[JsonValue] | str | None = None


class HeluoOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    calendar_context: CalendarContext | None = None
    chart: HeluoChart | None = None
    dayun: HeluoDayun | None = None
    four_pillars: FourPillars | None = None
    heluo_timing: HeluoTiming | None = None
    jiehou_evidence: HeluoJiehouEvidence | None = None
    judge: HeluoJudge | None = None
    numerology_evidence: NumerologyEvidence | None = None
    solar_term: HeluoSolarTermEvidence | None = None
    summary: Object | list[JsonValue] | str | None = None

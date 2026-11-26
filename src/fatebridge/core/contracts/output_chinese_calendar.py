"""Birth data and Chinese calendar output contracts."""

from typing import Literal

from pydantic import Field, JsonValue, field_validator, model_validator

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput
from fatebridge.core.contracts.output_civil_time import (
    CivilPointEvidence,
    CivilPointLabelEvidence,
)
from fatebridge.core.contracts.output_clock_labels import UTCDefinitionEvidence
from fatebridge.core.contracts.output_divination import ClassicalHexagram
from fatebridge.core.contracts.output_meihua import (
    MeihuaCalendarPolicy,
    MeihuaCountingVariant,
    MeihuaEvidenceScope,
    MeihuaRuleset,
    MeihuaSeasonalStrength,
    MeihuaStageRelation,
    MeihuaTraceStep,
)
from fatebridge.utils.civil_time import ZonedCalendar

Object = dict[str, JsonValue]


class Pillar(PartialOutput):
    stem: str | None = None
    branch: str | None = None


class FourPillars(PartialOutput):
    year: Pillar | None = None
    month: Pillar | None = None
    day: Pillar | None = None
    hour: Pillar | None = None


class PersonInfo(PartialOutput):
    name: str | None = None
    gender: str | None = None
    birth_datetime: str | None = None
    birth_place: str | None = None
    birth_timezone: str | None = None
    birth_longitude: float | None = None
    birth_latitude: float | None = None
    normalized_birth_datetime: str | None = None
    time_algorithm: str | None = None


class AnalysisContext(PartialOutput):
    context_role: str | None = None
    analysis_year: int | None = None
    analysis_month: int | None = None
    analysis_day: int | None = None
    analysis_hour: int | None = None
    analysis_minute: int | None = None
    input_datetime: str | None = None
    corrected_datetime: str | None = None
    timezone: str | None = None
    longitude: float | None = None
    applied_true_solar: bool | None = None
    time_algorithm: str | None = None
    total_correction_minutes: float | None = None
    current_jieqi: str | None = None
    next_jieqi: str | None = None
    lunar_display: str | None = None
    lunar_date_basis: str | None = None
    lunar_date_provider: str | None = None
    lunar_date_reference: str | None = None
    calendar_date_shift_days: int | None = None
    time_input_status: str | None = None
    time_input_minute_sensitive: bool | None = None
    civil_utc_offset: str | None = None
    civil_instant_utc: str | None = None
    birth_datetime: str | None = None
    analysis_datetime: str | None = None
    age_years: float | None = None
    house_system: str | None = None
    zodiac_type: str | None = None
    orb_profile: str | None = None
    name: str | None = None
    birth_place: str | None = None


class SolarTerm(CivilPointLabelEvidence):
    utc_definition: UTCDefinitionEvidence | None = None
    resolution_provider: str | None = None
    ephemeris_model: str | None = None
    solar_model_details: dict[str, OpenJsonValue] | None = None
    date_key: str | None = None
    datetime: str | None = Field(
        None, description="兼容本地钟面标签；不含偏移，重复小时不能仅据此复原瞬间"
    )
    datetime_with_offset: str | None = Field(
        None,
        description="实际民用钟时的带偏移ISO表示；沿用声明时标政策，不认证绝对UTC精度",
    )
    utc_offset_seconds: float | None = Field(
        None, gt=-86400, lt=86400, allow_inf_nan=False
    )
    fold: Literal[0, 1] | None = None
    timezone: str | None = None
    day_ganzhi: str | None = None
    name: str | None = None
    civil_point: CivilPointEvidence | None = Field(
        None,
        description="保留数值主点的精确名义Gregorian日；十进制字符串分数，不表示UTC quasi-JD、均匀SI日或物理精度认证",
    )
    comparison_policy: Literal["retained_nominal_civil_point_v1"] | None = None

    @field_validator("fold", mode="before")
    @classmethod
    def fold_is_an_integer(cls, value: object) -> int | None:
        # Literal[0, 1] alone also accepts True/False as Python-equal values.
        if value is not None and type(value) is not int:
            raise ValueError("节气fold必须为整数0或1")
        return value

    @model_validator(mode="after")
    def preserve_supplied_instant(self) -> "SolarTerm":
        if self.datetime_utc is not None and any(
            value is not None
            for value in (
                self.datetime,
                self.utc_offset_seconds,
                self.fold,
                self.date_key,
                self.day_ganzhi,
            )
        ):
            raise ValueError("当地钟时未定义时不能同时声明当地钟面或日序")
        if self.datetime_with_offset is None:
            return self
        text = self.datetime_with_offset
        clock = ZonedCalendar.from_isoformat(text)
        offset = clock.offset
        if (
            self.utc_offset_seconds is not None
            and offset.total_seconds() != self.utc_offset_seconds
        ):
            raise ValueError("节气时间字符串与utc_offset_seconds不一致")
        if self.datetime is not None:
            if not clock.matches_wall_label(self.datetime):
                raise ValueError("节气旧钟面标签与带偏移时间不一致")
        return self


class Trigram(PartialOutput):
    name: str | None = None
    cname: str | None = None
    element: str | None = None
    elem: str | None = None
    lines: list[int] | None = None
    nature: str | None = None
    symbol: str | None = None
    value: list[int] | None = None


class Hexagram(PartialOutput):
    classical: ClassicalHexagram | None = None
    name: str | None = None
    binary_code: str | None = None
    code: str | None = None
    lookup_type: str | None = None
    matched_query: str | None = None
    lines: list[int] | None = None
    lower: Trigram | None = None
    upper: Trigram | None = None
    moving_line: int | None = None
    symbol: str | None = None


class GuaLookupResult(Hexagram):
    element: str | None = None
    nature: str | None = None


class MeihuaSeed(PartialOutput):
    casting_method: str | None = None
    parameters: Object | None = None
    ignored_components: Object | None = None
    raw_upper_number: int | None = None
    raw_lower_number: int | None = None
    line_sum: int | None = None
    line_sum_basis: str | None = None
    alternate_moving_line: int | None = None
    count_boundary_status: str | None = None
    text_count_basis: Object | None = None
    text_tone_basis: Object | None = None
    hour_branch: str | None = None
    year_branch: str | None = None
    lunar_day: int | None = None
    lunar_month: int | None = None
    moving_line: int | None = None
    upper_number: int | None = None
    lower_number: int | None = None


class Meihua(PartialOutput):
    counting_variants: list[MeihuaCountingVariant] | None = None
    version: str | None = None
    ruleset: MeihuaRuleset | None = None
    calendar_policy: MeihuaCalendarPolicy | None = None
    rule_trace: list[MeihuaTraceStep] | None = None
    stage_relations: list[MeihuaStageRelation] | None = None
    seasonal_strength: MeihuaSeasonalStrength | None = None
    evidence_scope: MeihuaEvidenceScope | None = None
    ruleset_id: str | None = None
    year_boundary: str | None = None
    leap_month_rule: str | None = None
    mutual_rule: str | None = None
    source_url: str | None = None
    method: str | None = None
    seed: MeihuaSeed | None = None
    base_hexagram: Hexagram | None = None
    changed_hexagram: Hexagram | None = None
    mutual_hexagram: Hexagram | None = None
    cuo_hexagram: Hexagram | None = None
    zong_hexagram: Hexagram | None = None
    body_trigram: Trigram | None = None
    use_trigram: Trigram | None = None
    body_use_relation: str | None = None
    body_use_summary: str | None = None
    element_relation: str | None = None
    moving_palace: str | None = None
    summary: str | None = None


class LunarCalendar(PartialOutput):
    conversion_source: dict[str, str] | None = None
    year: int | None = None
    month: int | None = None
    day: int | None = None
    is_leap_month: bool | None = None
    year_cn: str | None = None
    month_cn: str | None = None
    day_cn: str | None = None
    birth: str | None = None
    display: str | None = None
    day_ganzhi: str | None = None
    month_ganzhi: str | None = None
    time_ganzhi: str | None = None
    year_jieqi_ganzhi: str | None = None
    solar_datetime: str | None = None
    timezone: str | None = None
    jieqi: str | None = None
    jiedelta: str | None = None
    days_until_next_jieqi: float | None = None
    previous_jieqi: SolarTerm | None = None
    next_jieqi: SolarTerm | None = None
    meihua: Meihua | None = None


class MonthBoundary(PartialOutput):
    branch: str | None = None
    month_index: int | None = None
    comparison_datetime: str | None = None
    elapsed_basis: Literal["utc_instant_seconds"] | None = None
    elapsed_seconds_since_start: float | None = Field(default=None, ge=0)
    elapsed_seconds_until_next: float | None = Field(default=None, ge=0)
    days_since_start: float | None = None
    days_until_next: float | None = None
    start_term: SolarTerm | None = None
    next_term: SolarTerm | None = None


class SolarTermDelta(PartialOutput):
    days_since_current: float | None = None
    days_until_next: float | None = None
    description: str | None = None


class LunarSupport(PartialOutput):
    supported: bool | None = None
    supported_range: dict[str, str] | None = None


class BirthTimeInput(PartialOutput):
    method_id: Literal["birth_clock_components_v1"] | None = None
    supplied_components: list[str] | None = None
    omitted_components: list[str] | None = None
    calculation_defaults: dict[str, int] | None = None
    nominal_civil_datetime: str | None = None
    corrected_clock_datetime: str | None = None
    timezone: str | None = None
    requested_utc_offset: str | None = None
    civil_utc_offset: str | None = None
    civil_instant_utc: str | None = None
    civil_fold: Literal[0, 1] | None = None
    civil_time_ambiguous: bool | None = None
    timezone_source: str | None = None
    timezone_rules: dict[str, str] | None = None
    offset_selection_scope: str | None = None
    uncertainty_interval: dict[str, str] | None = None
    observed_precision_certified: Literal[False] | None = None
    scope: str | None = None


class CalendarContext(PartialOutput):
    solar_datetime: str | None = None
    timezone: str | None = None
    lunar_calendar: LunarCalendar | None = None
    current_solar_term: SolarTerm | None = None
    next_solar_term: SolarTerm | None = None
    bazi_month_boundary: MonthBoundary | None = None
    solar_term_delta: SolarTermDelta | None = None
    lunar_calendar_support: LunarSupport | None = None
    birth_time_input: BirthTimeInput | None = None


class BranchName(PartialOutput):
    branch: str | None = None
    name: str | None = None


class LunarDate(PartialOutput):
    year: int | None = None
    month: int | None = None
    day: int | None = None
    is_leap_month: bool | None = None

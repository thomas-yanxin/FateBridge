"""Shared civil-time, UT1, birth, pillar, and Chinese calendar contracts."""

from __future__ import annotations

from datetime import timedelta
from fractions import Fraction
from typing import Annotated, Literal

from pydantic import Field, ValidationInfo, field_validator, model_validator

from fatebridge.core.contracts.base import (
    FULL_FACT,
    PRESENT_FACT,
    OpenJsonValue,
    PartialOutput,
)
from fatebridge.core.contracts.meihua import Meihua
from fatebridge.core.receipt_models import Object as Object
from fatebridge.utils.civil_time import CivilPoint, ZonedCalendar


class CivilRationalEvidence(PartialOutput):
    numerator: Annotated[str | None, FULL_FACT] = Field(
        None, pattern=r"^-?(0|[1-9][0-9]*)$"
    )
    denominator: Annotated[str | None, FULL_FACT] = Field(
        None, pattern=r"^[1-9][0-9]*$"
    )

    def known_day(self) -> Fraction | None:
        """Read a projected coordinate only when both decimal integers exist."""
        if self.numerator is None or self.denominator is None:
            return None
        return Fraction(int(self.numerator), int(self.denominator))


class CivilPointEvidence(CivilRationalEvidence):
    unit: Annotated[Literal["nominal_gregorian_day"] | None, FULL_FACT] = None
    excluded_before: Annotated[CivilRationalEvidence | None, PRESENT_FACT] = None

    def known_point(self) -> CivilPoint | None:
        """A missing projected cap is unknown, distinct from explicit null."""
        day = self.known_day()
        if day is None or "excluded_before" not in self.model_fields_set:
            return None
        if self.excluded_before is None:
            return CivilPoint(day)
        cap = self.excluded_before.known_day()
        return CivilPoint(day, cap) if cap is not None else None

    @model_validator(mode="after")
    def preserve_qualified_interval(self) -> "CivilPointEvidence":
        point = self.known_point()
        if (
            point is not None
            and point.excluded_before is not None
            and point.day >= point.excluded_before
        ):
            raise ValueError("民用时刻必须早于其已限定的排除端点")
        return self


class CivilPointLabelEvidence(PartialOutput):
    """A retained coordinate and its display, shared by source receipts."""

    civil_point: CivilPointEvidence | None = None
    datetime_with_offset: str | None = None
    datetime_utc: str | None = Field(
        None,
        description="当地钟时未定义时的带零偏移UTC显示，沿用名义日期及排除端点政策",
    )
    comparison_policy: Literal["retained_nominal_civil_point_v1"] | None = None

    @property
    def display_with_offset(self) -> str | None:
        if self.datetime_utc is not None:
            return self.datetime_utc
        return self.datetime_with_offset

    @model_validator(mode="after")
    def point_matches_display(self, info: ValidationInfo) -> "CivilPointLabelEvidence":
        point = self.civil_point.known_point() if self.civil_point is not None else None
        display = self.display_with_offset
        if (
            info.context
            and info.context.get("full_result")
            and self.comparison_policy == "retained_nominal_civil_point_v1"
            and (point is None or display is None)
        ):
            raise ValueError("完整的精确民用比较回执须保留主点和显示标签")
        if self.datetime_utc is not None and self.datetime_with_offset is not None:
            raise ValueError("当地钟时未定义时不能同时声明当地带偏移时间")
        if display is not None and (point is not None or self.datetime_utc is not None):
            clock = ZonedCalendar.from_isoformat(display)
            if self.datetime_utc is not None and clock.offset != timedelta(0):
                raise ValueError("节气UTC显示须采用零偏移")
            if point is not None and point.as_calendar() != clock.utc:
                raise ValueError("精确民用主点与显示时间不一致")
        return self


class UTCDefinitionEvidence(PartialOutput):
    policy_id: str | None = None
    leap_table_expires_at: str | None = None


class WesternUTCRepresentation(PartialOutput):
    utc_label: str | None = None
    utc_is_leap_second: bool | None = None
    datetime_representable: bool | None = None
    label_status: str | None = None
    primary_axis: str | None = None
    scope: str | None = None


class C04UT1Evidence(PartialOutput):
    method_id: str | None = None
    source_series: str | None = None
    tidal_model_id: str | None = None
    source_url: str | None = None
    mirror_url: str | None = None
    mirror_commit: str | None = None
    coverage_start_utc: str | None = None
    coverage_end_utc: str | None = None
    published_daily_records: int | None = None
    query_julian_day_tt: float | None = None
    query_julian_day_ut1: float | None = None
    numerical_jd_resolution_seconds: float | None = None
    source_mjd: list[int] | None = None
    source_ut1_minus_utc_seconds: list[float] | None = None
    source_formal_sigma_seconds: list[float] | None = None
    interpolation_weights: list[float] | None = None
    interpolation_axis: str | None = None
    instant_value_kind: str | None = None
    ut1_minus_tai_seconds: float | None = None
    base_ut1_minus_tai_seconds: float | None = Field(
        default=None,
        description=(
            "Restored daily UT1-TAI base, including query Z62 after four-point "
            "interpolation of zonal-regularized source values. Add only the "
            "subdaily field; the zonal field must not be added again."
        ),
    )
    zonal_ut1_seconds: float | None = None
    subdaily_ut1_seconds: float | None = None
    delta_t_seconds: float | None = None
    solver_residual_seconds: float | None = Field(
        default=None,
        description=(
            "Absolute forward pair-equation residual at the retained TT/UT1, "
            "in seconds. Numerical solver diagnostic, not a physical error bound."
        ),
    )
    solver_tolerance_seconds: float | None = Field(
        default=None,
        description="Forward solve convergence threshold in seconds.",
    )
    solver_iterations: int | None = Field(
        default=None,
        description="Iterations in the forward solve used to check source agreement.",
    )
    measured_ut1_series_applied: bool | None = None
    polar_motion_applied: bool | None = None
    celestial_pole_offsets_applied: bool | None = None
    subdaily_tides_applied: bool | None = None
    interpolation_error_bound_seconds: float | None = None
    absolute_accuracy_certified: bool | None = None
    epoch_scope: str | None = None
    scope: str | None = None


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

"""Stateless multi-subject, multi-tool batch execution shared across transports."""

from __future__ import annotations

import types
from collections.abc import Mapping
from copy import deepcopy
from datetime import date, datetime, timezone
from typing import Annotated, Literal, cast, get_args, get_origin

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)
from pydantic.fields import FieldInfo
from pydantic_core import PydanticCustomError

from fatebridge.application.execution import (
    execute_with_receipt,
    result_is_error,
)
from fatebridge.application.response_delivery import (
    deliver_response,
    validate_delivery_controls,
)
from fatebridge.application.tool_spec import BatchInputPolicy, ToolSpec
from fatebridge.core.batch_cache import batch_cache_scope
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.utils.civil_time import (
    parse_strict_date_text,
    parse_strict_datetime_text,
    parse_strict_time_text,
)
from fatebridge.utils.errors import (
    ParameterError,
    error_response_payload,
    handle_calculation_error,
    unknown_tool_error,
)

MAX_BATCH_CALLS = 32
_UNION_ORIGINS = (types.UnionType, get_origin(Annotated[int, "u"] | None))


class AnalysisContext(BaseModel):
    """Shared analysis clock and location context."""

    model_config = ConfigDict(extra="forbid")

    analysis_datetime: str | None = Field(
        default=None, description="YYYY-MM-DDTHH:MM[:SS][±HH:MM]"
    )
    date: str | None = None
    time: str | None = None
    year: int | None = None
    month: int | None = Field(default=None, ge=1, le=12)
    day: int | None = Field(default=None, ge=1, le=31)
    hour: int | None = Field(default=None, ge=0, le=23)
    minute: int | None = Field(default=None, ge=0, le=59)
    second: int | None = Field(default=None, ge=0, le=59)
    place: str | None = Field(default=None, description="分析地点")
    timezone: str | None = None
    utc_offset: str | None = None
    longitude: float | None = Field(default=None, ge=-180, le=180)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    use_true_solar_time: bool | None = None

    @model_validator(mode="after")
    def _normalize_clock_and_place(self) -> AnalysisContext:
        if self.analysis_datetime is not None:
            try:
                parsed_dt_date, (hour_i, min_i, sec_i), offset_s = (
                    parse_strict_datetime_text(self.analysis_datetime)
                )
            except ValueError as exc:
                message = str(exc)
                if "格式" in message:
                    raise PydanticCustomError(
                        "invalid_analysis_datetime",
                        "analysis_datetime 须为 YYYY-MM-DDTHH:MM[:SS][±HH:MM] 格式",
                        {"path": "analysis_datetime"},
                    ) from exc
                if "范围" in message:
                    raise PydanticCustomError(
                        "invalid_analysis_time",
                        "analysis_datetime 超出有效时分秒范围",
                        {"path": "analysis_datetime"},
                    ) from exc
                raise PydanticCustomError(
                    "invalid_calendar_date",
                    "analysis_datetime 不是有效的公历日期",
                    {"path": "analysis_datetime"},
                ) from exc
            date_str = parsed_dt_date.isoformat()
            time_str = (
                f"{hour_i:02d}:{min_i:02d}:{sec_i:02d}"
                if sec_i is not None
                else f"{hour_i:02d}:{min_i:02d}"
            )
            if self.date is None:
                self.date = date_str
            elif self.date != date_str:
                raise PydanticCustomError(
                    "conflicting_analysis_datetime",
                    "analysis_datetime 与 date 不一致",
                    {"path": "analysis_datetime"},
                )
            if self.time is None:
                self.time = time_str
            elif self.time != time_str:
                raise PydanticCustomError(
                    "conflicting_analysis_datetime",
                    "analysis_datetime 与 time 不一致",
                    {"path": "analysis_datetime"},
                )
            if offset_s is not None:
                norm_offset = "+00:00" if offset_s == "Z" else offset_s
                if self.utc_offset is None:
                    self.utc_offset = norm_offset
                elif self.utc_offset != norm_offset:
                    raise PydanticCustomError(
                        "conflicting_analysis_offset",
                        "analysis_datetime 偏移与 utc_offset 不一致",
                        {"path": "utc_offset"},
                    )
                if self.timezone is None:
                    self.timezone = norm_offset

        if self.date is not None:
            try:
                parsed_date = parse_strict_date_text(self.date)
            except ValueError as exc:
                if "格式" in str(exc):
                    raise PydanticCustomError(
                        "invalid_analysis_date_format",
                        "context.date 须为 YYYY-MM-DD 格式",
                        {"path": "date"},
                    ) from exc
                raise PydanticCustomError(
                    "invalid_calendar_date",
                    "context.date 不是有效的公历日期",
                    {"path": "date"},
                ) from exc
            if self.year is None:
                self.year = parsed_date.year
            elif self.year != parsed_date.year:
                raise PydanticCustomError(
                    "conflicting_analysis_date",
                    "context.date 与 year 不一致",
                    {"path": "date"},
                )
            if self.month is None:
                self.month = parsed_date.month
            elif self.month != parsed_date.month:
                raise PydanticCustomError(
                    "conflicting_analysis_date",
                    "context.date 与 month 不一致",
                    {"path": "date"},
                )
            if self.day is None:
                self.day = parsed_date.day
            elif self.day != parsed_date.day:
                raise PydanticCustomError(
                    "conflicting_analysis_date",
                    "context.date 与 day 不一致",
                    {"path": "date"},
                )
        elif (
            self.year is not None
            and self.month is not None
            and self.day is not None
            and 1 <= self.year <= 9999
        ):
            try:
                date(self.year, self.month, self.day)
            except ValueError as exc:
                raise PydanticCustomError(
                    "invalid_calendar_date",
                    "context 年月日不是有效的公历日期",
                    {"path": "date"},
                ) from exc

        if self.time is not None:
            try:
                hour_i, min_i, sec_i = parse_strict_time_text(self.time)
            except ValueError as exc:
                if "格式" in str(exc):
                    raise PydanticCustomError(
                        "invalid_analysis_time_format",
                        "context.time 须为 HH:MM 或 HH:MM:SS 格式",
                        {"path": "time"},
                    ) from exc
                raise PydanticCustomError(
                    "invalid_analysis_time",
                    "context.time 超出有效时分秒范围",
                    {"path": "time"},
                ) from exc
            if self.hour is None:
                self.hour = hour_i
            elif self.hour != hour_i:
                raise PydanticCustomError(
                    "conflicting_analysis_time",
                    "context.time 与 hour 不一致",
                    {"path": "time"},
                )
            if self.minute is None:
                self.minute = min_i
            elif self.minute != min_i:
                raise PydanticCustomError(
                    "conflicting_analysis_time",
                    "context.time 与 minute 不一致",
                    {"path": "time"},
                )
            if sec_i is not None:
                if self.second is None:
                    self.second = sec_i
                elif self.second != sec_i:
                    raise PydanticCustomError(
                        "conflicting_analysis_time",
                        "context.time 与 second 不一致",
                        {"path": "time"},
                    )

        place_text = (self.place or "").strip()
        if (
            place_text
            and place_text != "未提供"
            and (
                self.longitude is None or self.latitude is None or self.timezone is None
            )
        ):
            from fatebridge.utils.places import resolve_place_location

            resolved = resolve_place_location(place_text, place_field="place")
            if self.longitude is None:
                self.longitude = resolved.longitude
            if self.latitude is None:
                self.latitude = resolved.latitude
            if self.timezone is None and resolved.timezone is not None:
                self.timezone = resolved.timezone

        return self


class SubjectProfile(BaseModel):
    """Reusable subject birth and location profile for batch calls."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    gender: Literal["male", "female", "男", "女"] | None = None
    birth_year: int | None = None
    birth_month: int | None = Field(default=None, ge=1, le=12)
    birth_day: int | None = Field(default=None, ge=1, le=31)
    birth_hour: int | None = Field(default=None, ge=0, le=23)
    birth_minute: int | None = Field(default=None, ge=0, le=59)
    birth_second: int | None = Field(default=None, ge=0, le=59)
    birth_date: str | None = Field(default=None, description="YYYY-MM-DD")
    birth_time: str | None = Field(default=None, description="HH:MM[:SS]")
    birth_place: str | None = None
    birth_longitude: float | None = Field(default=None, ge=-180, le=180)
    birth_latitude: float | None = Field(default=None, ge=-90, le=90)
    birth_utc_offset: str | None = None
    timezone: str | None = None
    birth_time_unknown: bool | None = Field(default=None, description="未知时辰")
    use_true_solar_time: bool | None = None

    @model_validator(mode="after")
    def _parse_and_validate_birth_clock(self) -> SubjectProfile:
        if self.birth_date is not None:
            try:
                parsed_date = parse_strict_date_text(self.birth_date)
            except ValueError as exc:
                if "格式" in str(exc):
                    raise PydanticCustomError(
                        "invalid_birth_date_format",
                        "birth_date 须为 YYYY-MM-DD 格式",
                        {"path": "birth_date"},
                    ) from exc
                raise PydanticCustomError(
                    "invalid_calendar_date",
                    "birth_date 不是有效的公历日期",
                    {"path": "birth_date"},
                ) from exc
            if self.birth_year is None:
                self.birth_year = parsed_date.year
                if self.birth_month is None:
                    self.birth_month = parsed_date.month
                elif self.birth_month != parsed_date.month:
                    raise PydanticCustomError(
                        "conflicting_birth_date",
                        "birth_date 与 birth_month 不一致",
                        {"path": "birth_date"},
                    )
                if self.birth_day is None:
                    self.birth_day = parsed_date.day
                elif self.birth_day != parsed_date.day:
                    raise PydanticCustomError(
                        "conflicting_birth_date",
                        "birth_date 与 birth_day 不一致",
                        {"path": "birth_date"},
                    )
            else:
                if (
                    self.birth_year != parsed_date.year
                    or (
                        self.birth_month is not None
                        and self.birth_month != parsed_date.month
                    )
                    or (
                        self.birth_day is not None and self.birth_day != parsed_date.day
                    )
                ):
                    raise PydanticCustomError(
                        "conflicting_birth_date",
                        "birth_date 与 birth_year/birth_month/birth_day 不一致",
                        {"path": "birth_date"},
                    )
        elif (
            self.birth_year is not None
            and self.birth_month is not None
            and self.birth_day is not None
            and 1 <= self.birth_year <= 9999
        ):
            try:
                date(self.birth_year, self.birth_month, self.birth_day)
            except ValueError as exc:
                raise PydanticCustomError(
                    "invalid_calendar_date",
                    "出生年月日不是有效的公历日期",
                    {"path": "birth_date"},
                ) from exc

        if self.birth_time is not None:
            try:
                hour, minute, second = parse_strict_time_text(self.birth_time)
            except ValueError as exc:
                if "格式" in str(exc):
                    raise PydanticCustomError(
                        "invalid_birth_time_format",
                        "birth_time 须为 HH:MM 或 HH:MM:SS 格式",
                        {"path": "birth_time"},
                    ) from exc
                raise PydanticCustomError(
                    "invalid_birth_time",
                    "birth_time 超出有效时分秒范围",
                    {"path": "birth_time"},
                ) from exc
            if self.birth_hour is None:
                self.birth_hour = hour
                if self.birth_minute is None:
                    self.birth_minute = minute
                elif self.birth_minute != minute:
                    raise PydanticCustomError(
                        "conflicting_birth_time",
                        "birth_time 与 birth_minute 不一致",
                        {"path": "birth_time"},
                    )
                if second is not None:
                    if self.birth_second is None:
                        self.birth_second = second
                    elif self.birth_second != second:
                        raise PydanticCustomError(
                            "conflicting_birth_time",
                            "birth_time 与 birth_second 不一致",
                            {"path": "birth_time"},
                        )
            else:
                if (
                    self.birth_hour != hour
                    or (self.birth_minute is not None and self.birth_minute != minute)
                    or (
                        second is not None
                        and self.birth_second is not None
                        and self.birth_second != second
                    )
                ):
                    raise PydanticCustomError(
                        "conflicting_birth_time",
                        "birth_time 与 birth_hour/birth_minute/birth_second 不一致",
                        {"path": "birth_time"},
                    )

        return self


class BatchCall(BaseModel):
    """Single tool invocation inside a batch request."""

    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    tool: str = Field(min_length=1, description="工具名")
    subject: str | None = Field(default=None, description="单对象键")
    subjects: list[str] | None = Field(
        default=None, min_length=1, description="多对象键"
    )
    arguments: dict[str, object] = Field(default_factory=dict, description="工具参数")
    include: list[str] | None = None
    fields: list[str] | None = None

    @model_validator(mode="after")
    def _reject_conflicting_controls(self) -> BatchCall:
        if self.subject is not None and self.subjects is not None:
            raise PydanticCustomError(
                "conflicting_subject_fields",
                "subject 与 subjects 不能同时指定",
                {"path": "subjects"},
            )
        validate_delivery_controls(self.include, self.fields)
        return self


class BatchRequest(BaseModel):
    """Stateless multi-subject, multi-tool batch execution request."""

    model_config = ConfigDict(extra="forbid")

    subjects: dict[str, SubjectProfile] = Field(
        default_factory=dict, description="共享对象档案字典，供 calls 引用"
    )
    context: AnalysisContext | None = Field(
        default=None,
        description="跨工具共享的问事/分析时刻与地点上下文，按目标工具契约自动映射",
    )
    defaults: dict[str, object] = Field(
        default_factory=dict,
        description="跨工具共享默认参数，按目标工具输入模型字段自动过滤",
    )
    calls: list[BatchCall] = Field(
        min_length=1,
        max_length=MAX_BATCH_CALLS,
        description="要顺序执行的计算调用列表（1-32 条）",
    )
    as_of: str | None = Field(
        default=None,
        description="冻结整批计算的当前时刻（含时区的 ISO 8601 字符串）",
    )
    stop_on_error: bool = Field(
        default=False, description="为真时遇首个工具调用失败即停止执行后续调用"
    )

    @field_validator("as_of")
    @classmethod
    def _validate_as_of(cls, value: str | None) -> str | None:
        return ExecutionOptions.aware_timestamp(value)


def _subject_date_string(profile: SubjectProfile) -> str | None:
    if profile.birth_date is not None:
        return profile.birth_date
    if (
        profile.birth_year is not None
        and profile.birth_month is not None
        and profile.birth_day is not None
    ):
        return f"{profile.birth_year:04d}-{profile.birth_month:02d}-{profile.birth_day:02d}"
    return None


def _subject_time_string(profile: SubjectProfile) -> str | None:
    if profile.birth_time is not None:
        return profile.birth_time
    if profile.birth_hour is not None:
        if profile.birth_second is not None:
            minute = profile.birth_minute if profile.birth_minute is not None else 0
            return f"{profile.birth_hour:02d}:{minute:02d}:{profile.birth_second:02d}"
        if profile.birth_minute is not None:
            return f"{profile.birth_hour:02d}:{profile.birth_minute:02d}"
        return f"{profile.birth_hour:02d}:00"
    return None


def _unwrap_list_item_model(annotation: object) -> type[BaseModel] | None:
    while get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]
    if get_origin(annotation) in _UNION_ORIGINS:
        for branch in get_args(annotation):
            if branch is not type(None):
                resolved = _unwrap_list_item_model(branch)
                if resolved is not None:
                    return resolved
    if get_origin(annotation) is list:
        members = get_args(annotation)
        if members:
            item = members[0]
            while get_origin(item) is Annotated:
                item = get_args(item)[0]
            if isinstance(item, type) and issubclass(item, BaseModel):
                return item
    return None


def _map_subject_to_minggua(
    subject_key: str,
    profile: SubjectProfile,
    target_fields: Mapping[str, FieldInfo],
    *,
    include_subject_id: bool,
) -> dict[str, object]:
    mapped: dict[str, object] = {}
    if include_subject_id and "subject_id" in target_fields:
        mapped["subject_id"] = subject_key
    if "timezone_name" in target_fields and profile.timezone is not None:
        mapped["timezone_name"] = profile.timezone
    if profile.gender is not None:
        if "gender" in target_fields:
            mapped["gender"] = profile.gender
        elif "gender_convention" in target_fields:
            mapped["gender_convention"] = profile.gender

    # note (minggua): MingguaRequest/Occupant reject providing both birth_date and birth_year.
    birth_date_text = _subject_date_string(profile)
    if birth_date_text is not None and "birth_date" in target_fields:
        mapped["birth_date"] = birth_date_text
    elif profile.birth_year is not None:
        if "birth_year" in target_fields:
            mapped["birth_year"] = profile.birth_year
        elif "effective_birth_year" in target_fields:
            mapped["effective_birth_year"] = profile.birth_year
    return mapped


def _map_subject_with_prefix(
    subject_key: str,
    profile: SubjectProfile,
    target_fields: Mapping[str, FieldInfo],
    *,
    prefix: str,
    require_name: bool,
) -> dict[str, object]:
    mapped: dict[str, object] = {}
    name_value = (
        profile.name
        if profile.name is not None
        else (subject_key if require_name else None)
    )
    candidate_values: dict[str, object | None] = {
        f"{prefix}name": name_value,
        f"{prefix}gender": profile.gender,
        f"{prefix}birth_year": profile.birth_year,
        f"{prefix}birth_month": profile.birth_month,
        f"{prefix}birth_day": profile.birth_day,
        f"{prefix}birth_hour": profile.birth_hour,
        f"{prefix}birth_minute": profile.birth_minute,
        f"{prefix}birth_second": profile.birth_second,
        f"{prefix}birth_date": _subject_date_string(profile),
        f"{prefix}birth_time_unknown": profile.birth_time_unknown,
        f"{prefix}birth_place": profile.birth_place,
        f"{prefix}birth_longitude": profile.birth_longitude,
        f"{prefix}birth_latitude": profile.birth_latitude,
        f"{prefix}birth_utc_offset": profile.birth_utc_offset,
        f"{prefix}birth_timezone": profile.timezone,
        f"{prefix}use_true_solar_time": profile.use_true_solar_time,
    }
    for key, value in candidate_values.items():
        if key in target_fields and value is not None:
            mapped[key] = value
    return mapped


def _map_single_subject(
    subject_key: str,
    profile: SubjectProfile,
    target_fields: Mapping[str, FieldInfo],
    *,
    policy: BatchInputPolicy,
) -> dict[str, object]:
    if policy.subject_mode == "exclusive_birth_record":
        return _map_subject_to_minggua(
            subject_key, profile, target_fields, include_subject_id=False
        )

    if policy.subject_mode == "date_clock":
        mapped: dict[str, object] = {}
        date_text = _subject_date_string(profile)
        time_text = _subject_time_string(profile)
        candidate_values: dict[str, object | None] = {
            "name": profile.name,
            "date": date_text,
            "time": time_text,
            "place": profile.birth_place,
            "timezone": profile.timezone,
            "longitude": profile.birth_longitude,
            "latitude": profile.birth_latitude,
            "birth_utc_offset": profile.birth_utc_offset,
            "gender": profile.gender,
            "use_true_solar_time": profile.use_true_solar_time,
        }
        if (
            "analysis_utc_offset" in target_fields
            and "birth_utc_offset" not in target_fields
        ):
            candidate_values["analysis_utc_offset"] = profile.birth_utc_offset
        for key, value in candidate_values.items():
            if key in target_fields and value is not None:
                mapped[key] = value
        return mapped

    return _map_subject_with_prefix(
        subject_key, profile, target_fields, prefix="", require_name=False
    )


def _map_multi_subjects(
    spec: ToolSpec,
    subject_keys: list[str],
    subjects: Mapping[str, SubjectProfile],
    target_fields: Mapping[str, FieldInfo],
) -> dict[str, object]:
    policy = spec.batch_policy
    if (
        policy.subject_mode == "subject_list"
        and policy.list_field is not None
        and policy.list_field in target_fields
    ):
        list_field = policy.list_field
        item_model = _unwrap_list_item_model(target_fields[list_field].annotation)
        item_fields = item_model.model_fields if item_model is not None else {}
        return {
            list_field: [
                _map_subject_to_minggua(
                    key,
                    subjects[key],
                    item_fields,
                    include_subject_id=True,
                )
                for key in subject_keys
            ]
        }

    if policy.subject_mode == "pair":
        if len(subject_keys) != 2:
            raise ParameterError(
                f"工具 {spec.name} 需要恰好 2 个 subjects",
                [
                    {
                        "path": "subjects",
                        "code": "invalid_subject_count",
                        "constraints": {
                            "expected_count": 2,
                            "actual_count": len(subject_keys),
                        },
                    }
                ],
            )
        merged: dict[str, object] = {}
        if policy.pair_style == "birth_fields":
            for key, prefix in zip(subject_keys, policy.pair_prefixes, strict=True):
                merged.update(
                    _map_subject_with_prefix(
                        key,
                        subjects[key],
                        target_fields,
                        prefix=prefix,
                        require_name=True,
                    )
                )
            return merged
        for key, prefix in zip(subject_keys, policy.pair_prefixes, strict=True):
            profile = subjects[key]
            date_text = _subject_date_string(profile)
            time_text = _subject_time_string(profile)
            pair_values: dict[str, object | None] = {
                f"{prefix}name": profile.name if profile.name is not None else key,
                f"{prefix}date": date_text,
                f"{prefix}time": time_text,
                f"{prefix}zone": profile.timezone,
            }
            for field_name, value in pair_values.items():
                if field_name in target_fields and value is not None:
                    merged[field_name] = value
        return merged

    raise ParameterError(
        f"工具 {spec.name} 不支持多对象 subjects 映射",
        [{"path": "subjects", "code": "unsupported_subjects"}],
    )


def _context_date_string(context: AnalysisContext) -> str | None:
    if context.date is not None:
        return context.date
    if (
        context.year is not None
        and context.month is not None
        and context.day is not None
    ):
        return f"{context.year:04d}-{context.month:02d}-{context.day:02d}"
    return None


def _context_time_string(context: AnalysisContext) -> str | None:
    if context.time is not None:
        return context.time
    if context.hour is not None:
        minute = context.minute if context.minute is not None else 0
        if context.second is not None:
            return f"{context.hour:02d}:{minute:02d}:{context.second:02d}"
        return f"{context.hour:02d}:{minute:02d}"
    return None


def _map_analysis_context(
    context: AnalysisContext,
    target_fields: Mapping[str, FieldInfo],
    *,
    policy: BatchInputPolicy,
    is_birth_date_mapped: bool,
    explicit_args: Mapping[str, object],
    defaults: Mapping[str, object],
) -> dict[str, object]:
    """Map shared AnalysisContext clock and location fields to a tool's contract."""
    mapped: dict[str, object] = {}
    candidate_values: dict[str, object | None] = {}
    for prefix in policy.context_prefixes:
        candidate_values.update(
            {
                f"{prefix}year": context.year,
                f"{prefix}month": context.month,
                f"{prefix}day": context.day,
                f"{prefix}hour": context.hour,
                f"{prefix}minute": context.minute,
                f"{prefix}second": context.second,
                f"{prefix}place": context.place,
                f"{prefix}timezone": context.timezone,
                f"{prefix}utc_offset": context.utc_offset,
                f"{prefix}longitude": context.longitude,
                f"{prefix}latitude": context.latitude,
            }
        )
    if not is_birth_date_mapped:
        candidate_values.update(
            {
                "date": _context_date_string(context),
                "time": _context_time_string(context),
                "place": context.place,
                "timezone": context.timezone,
                "longitude": context.longitude,
                "latitude": context.latitude,
                "use_true_solar_time": context.use_true_solar_time,
            }
        )
        clock_basis = (
            (
                explicit_args.get(policy.context_clock_basis_field)
                or defaults.get(policy.context_clock_basis_field)
            )
            if policy.context_clock_basis_field is not None
            else None
        )
        if not (
            isinstance(clock_basis, str) and clock_basis in policy.solar_clock_bases
        ):
            candidate_values["timezone_name"] = context.timezone

    for key, value in candidate_values.items():
        if key in target_fields and value is not None:
            mapped[key] = value
    return mapped


def resolve_call_arguments(
    spec: ToolSpec,
    call: BatchCall,
    *,
    subjects: Mapping[str, SubjectProfile],
    defaults: Mapping[str, object],
    context: AnalysisContext | None = None,
) -> dict[str, object]:
    """Resolve tool arguments with precedence defaults < context < subject(s) < call.arguments."""
    policy = spec.batch_policy
    model_fields = spec.request_model.model_fields
    resolved: dict[str, object] = {
        key: deepcopy(value) for key, value in defaults.items() if key in model_fields
    }

    if context is not None:
        is_birth_date_mapped = (
            call.subject is not None or call.subjects is not None
        ) and policy.subject_mode == "date_clock"
        resolved.update(
            _map_analysis_context(
                context,
                model_fields,
                policy=policy,
                is_birth_date_mapped=is_birth_date_mapped,
                explicit_args=call.arguments,
                defaults=defaults,
            )
        )

    available = sorted(subjects)
    if call.subjects is not None:
        for idx, ref in enumerate(call.subjects):
            if ref not in subjects:
                raise ParameterError(
                    f"未知对象引用: {ref}",
                    [
                        {
                            "path": f"subjects.{idx}",
                            "code": "unknown_subject",
                            "constraints": {"available": available},
                        }
                    ],
                )
        resolved.update(
            _map_multi_subjects(spec, call.subjects, subjects, model_fields)
        )
    elif call.subject is not None:
        if call.subject not in subjects:
            raise ParameterError(
                f"未知对象引用: {call.subject}",
                [
                    {
                        "path": "subject",
                        "code": "unknown_subject",
                        "constraints": {"available": available},
                    }
                ],
            )
        if policy.subject_mode == "pair":
            raise ParameterError(
                f"工具 {spec.name} 需要使用 subjects（2 个对象），不能使用单个 subject",
                [{"path": "subject", "code": "pair_subjects_required"}],
            )
        if policy.subject_mode == "subject_list":
            resolved.update(
                _map_multi_subjects(spec, [call.subject], subjects, model_fields)
            )
        else:
            resolved.update(
                _map_single_subject(
                    call.subject, subjects[call.subject], model_fields, policy=policy
                )
            )

    for key, value in call.arguments.items():
        resolved[key] = deepcopy(value)
    return resolved


def _validate_subject_references(request: BatchRequest) -> None:
    available = sorted(request.subjects)
    issues: list[dict[str, object]] = []
    for call_index, call in enumerate(request.calls):
        if call.subject is not None and call.subject not in request.subjects:
            issues.append(
                {
                    "path": f"calls.{call_index}.subject",
                    "code": "unknown_subject",
                    "message": f"未知对象引用: {call.subject}",
                    "constraints": {"available": available},
                }
            )
        if call.subjects is not None:
            for subject_index, ref in enumerate(call.subjects):
                if ref not in request.subjects:
                    issues.append(
                        {
                            "path": f"calls.{call_index}.subjects.{subject_index}",
                            "code": "unknown_subject",
                            "message": f"未知对象引用: {ref}",
                            "constraints": {"available": available},
                        }
                    )
    if issues:
        raise ParameterError("批量请求包含未知的 subject 引用", issues)


def execute_batch(
    specs_by_name: Mapping[str, ToolSpec],
    request: BatchRequest,
) -> dict[str, JsonValue]:
    """Validate subject references and execute batch calls under one frozen clock."""
    _validate_subject_references(request)
    shared_as_of = (
        request.as_of
        if request.as_of is not None
        else datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    allowed_tools = set(specs_by_name)
    results: list[JsonValue] = []
    succeeded = 0
    failed = 0
    raw_call_cache: dict[tuple[str, str, str], dict[str, JsonValue]] = {}

    with batch_cache_scope():
        for call in request.calls:
            spec = specs_by_name.get(call.tool)
            if spec is None:
                failed += 1
                unknown_payload = unknown_tool_error(
                    call.tool, allowed_tools
                ).as_result()
                unknown_payload["error_code"] = "unknown_tool"
                results.append(
                    {
                        "id": call.id,
                        "tool": call.tool,
                        "ok": False,
                        "error": cast(
                            JsonValue,
                            error_response_payload(unknown_payload, call.tool),
                        ),
                    }
                )
                if request.stop_on_error:
                    break
                continue

            try:
                options = ExecutionOptions.model_validate({"as_of": shared_as_of})
                resolved_args = resolve_call_arguments(
                    spec,
                    call,
                    subjects=request.subjects,
                    defaults=request.defaults,
                    context=request.context,
                )
                tool_request = spec.request_model.model_validate(resolved_args)
                is_cacheable = (
                    "seed" not in spec.request_model.model_fields
                    or "seed" in tool_request.model_fields_set
                )
                cache_key = (
                    spec.name,
                    tool_request.model_dump_json(),
                    shared_as_of,
                )
                if is_cacheable and cache_key in raw_call_cache:
                    raw_result = deepcopy(raw_call_cache[cache_key])
                else:
                    raw_result = execute_with_receipt(
                        spec,
                        tool_request,
                        options=options,
                    )
                    if is_cacheable and not result_is_error(raw_result):
                        raw_call_cache[cache_key] = deepcopy(raw_result)
                if result_is_error(raw_result):
                    failed += 1
                    results.append(
                        {
                            "id": call.id,
                            "tool": call.tool,
                            "ok": False,
                            "error": cast(
                                JsonValue,
                                error_response_payload(
                                    raw_result, spec.operation_label_zh
                                ),
                            ),
                        }
                    )
                    if request.stop_on_error:
                        break
                    continue

                delivered = deliver_response(
                    raw_result,
                    spec=spec,
                    include=call.include,
                    fields=call.fields,
                )
                succeeded += 1
                results.append(
                    {
                        "id": call.id,
                        "tool": call.tool,
                        "ok": True,
                        "result": delivered,
                    }
                )
            except Exception as exc:  # noqa: BLE001 - isolate per-call failures
                failed += 1
                failure = handle_calculation_error(
                    exc,
                    spec.operation_label_zh,
                    allowed_fields=spec.request_model.model_fields.keys(),
                    root_model=spec.request_model,
                )
                results.append(
                    {
                        "id": call.id,
                        "tool": call.tool,
                        "ok": False,
                        "error": cast(
                            JsonValue,
                            error_response_payload(failure, spec.operation_label_zh),
                        ),
                    }
                )
                if request.stop_on_error:
                    break

    status: Literal["ok", "partial_error", "error"]
    if failed == 0:
        status = "ok"
    elif succeeded == 0:
        status = "error"
    else:
        status = "partial_error"

    return {
        "status": status,
        "as_of": shared_as_of,
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }

"""Stateless multi-subject, multi-tool batch execution shared across transports."""

from __future__ import annotations

import difflib
import re
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

from fatebridge.application.execution import execute_with_receipt, result_is_error
from fatebridge.application.response_delivery import deliver_response
from fatebridge.application.tool_spec import DetailLevel, ToolSpec
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.utils.errors import (
    ParameterError,
    error_response_payload,
    handle_calculation_error,
)

MAX_BATCH_CALLS = 32
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^(\d{2}):(\d{2})(?::(\d{2}))?$")
_UNION_ORIGINS = (types.UnionType, get_origin(Annotated[int, "u"] | None))


class SubjectProfile(BaseModel):
    """Reusable subject birth and location profile for batch calls."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, description="姓名或对象标签")
    gender: Literal["male", "female"] | None = Field(
        default=None, description="性别：male 或 female"
    )
    birth_year: int | None = Field(default=None, description="出生公历年")
    birth_month: int | None = Field(
        default=None, ge=1, le=12, description="出生公历月（1-12）"
    )
    birth_day: int | None = Field(
        default=None, ge=1, le=31, description="出生公历日（1-31）"
    )
    birth_hour: int | None = Field(
        default=None, ge=0, le=23, description="出生时（0-23）"
    )
    birth_minute: int | None = Field(
        default=None, ge=0, le=59, description="出生分（0-59）"
    )
    birth_second: int | None = Field(
        default=None, ge=0, le=59, description="出生秒（0-59）"
    )
    birth_date: str | None = Field(
        default=None,
        description="出生公历日期（YYYY-MM-DD）；省略 birth_year 时自动解析为年月日",
    )
    birth_time: str | None = Field(
        default=None,
        description="出生当地钟时（HH:MM 或 HH:MM:SS）；省略 birth_hour 时自动解析为时分秒",
    )
    birth_place: str | None = Field(default=None, description="出生地点")
    birth_longitude: float | None = Field(
        default=None, ge=-180, le=180, description="出生经度（度）"
    )
    birth_latitude: float | None = Field(
        default=None, ge=-90, le=90, description="出生纬度（度）"
    )
    birth_utc_offset: str | None = Field(
        default=None, description="已确认的出生民用 UTC 偏移（如 +08:00）"
    )
    timezone: str | None = Field(
        default=None, description="出生或分析时区（IANA 名称或 UTC 偏移）"
    )
    use_true_solar_time: bool | None = Field(
        default=None, description="是否启用真太阳时校正"
    )

    @model_validator(mode="after")
    def _parse_and_validate_birth_clock(self) -> SubjectProfile:
        if self.birth_date is not None:
            if not _DATE_RE.fullmatch(self.birth_date):
                raise ValueError("birth_date 须为 YYYY-MM-DD 格式")
            try:
                parsed_date = date.fromisoformat(self.birth_date)
            except ValueError as exc:
                raise ValueError("birth_date 不是有效的公历日期") from exc
            if self.birth_year is None:
                self.birth_year = parsed_date.year
                if self.birth_month is None:
                    self.birth_month = parsed_date.month
                elif self.birth_month != parsed_date.month:
                    raise ValueError("birth_date 与 birth_month 不一致")
                if self.birth_day is None:
                    self.birth_day = parsed_date.day
                elif self.birth_day != parsed_date.day:
                    raise ValueError("birth_date 与 birth_day 不一致")
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
                    raise ValueError(
                        "birth_date 与 birth_year/birth_month/birth_day 不一致"
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
                raise ValueError("出生年月日不是有效的公历日期") from exc

        if self.birth_time is not None:
            match = _TIME_RE.fullmatch(self.birth_time)
            if match is None:
                raise ValueError("birth_time 须为 HH:MM 或 HH:MM:SS 格式")
            hour = int(match.group(1))
            minute = int(match.group(2))
            second = int(match.group(3)) if match.group(3) is not None else None
            if not (0 <= hour <= 23 and 0 <= minute <= 59) or (
                second is not None and not 0 <= second <= 59
            ):
                raise ValueError("birth_time 超出有效时分秒范围")
            if self.birth_hour is None:
                self.birth_hour = hour
                if self.birth_minute is None:
                    self.birth_minute = minute
                elif self.birth_minute != minute:
                    raise ValueError("birth_time 与 birth_minute 不一致")
                if second is not None:
                    if self.birth_second is None:
                        self.birth_second = second
                    elif self.birth_second != second:
                        raise ValueError("birth_time 与 birth_second 不一致")
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
                    raise ValueError(
                        "birth_time 与 birth_hour/birth_minute/birth_second 不一致"
                    )

        return self


class BatchCall(BaseModel):
    """Single tool invocation inside a batch request."""

    model_config = ConfigDict(extra="forbid")

    id: str | None = Field(default=None, description="可选调用标识，原样回传到结果项")
    tool: str = Field(min_length=1, description="要调用的公开工具名")
    subject: str | None = Field(
        default=None, description="单对象工具引用的 subject 键名"
    )
    subjects: list[str] | None = Field(
        default=None,
        min_length=1,
        description="多对象或合盘工具引用的 subject 键名列表",
    )
    arguments: dict[str, object] = Field(
        default_factory=dict,
        description="显式工具参数，优先级高于 subject(s) 与 defaults",
    )
    detail: DetailLevel | None = Field(
        default=None, description="覆盖批量默认 detail（compact 或 audit）"
    )
    fields: list[str] | None = Field(
        default=None, description="仅返回选定的业务字段或点号子路径"
    )

    @model_validator(mode="after")
    def _reject_both_subject_forms(self) -> BatchCall:
        if self.subject is not None and self.subjects is not None:
            raise ValueError("subject 与 subjects 不能同时指定")
        return self


class BatchRequest(BaseModel):
    """Stateless multi-subject, multi-tool batch execution request."""

    model_config = ConfigDict(extra="forbid")

    subjects: dict[str, SubjectProfile] = Field(
        default_factory=dict, description="共享对象档案字典，供 calls 引用"
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
    detail: DetailLevel = Field(
        default="compact", description="批量默认输出详细级别：compact 或 audit"
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


def _is_minggua_like(target_fields: Mapping[str, FieldInfo]) -> bool:
    return (
        "birth_at" in target_fields
        or "gender_convention" in target_fields
        or "effective_birth_year" in target_fields
        or ("birth_date" in target_fields and "timezone_name" in target_fields)
    )


def _is_pair_birth_tuple_tool(target_fields: Mapping[str, FieldInfo]) -> bool:
    return (
        "person1_birth_year" in target_fields and "person2_birth_year" in target_fields
    ) or ("inner_birth_year" in target_fields and "outer_birth_year" in target_fields)


def _is_sukuyo_pair_tool(target_fields: Mapping[str, FieldInfo]) -> bool:
    return "person1_date" in target_fields and "person2_date" in target_fields


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
) -> dict[str, object]:
    if _is_minggua_like(target_fields):
        return _map_subject_to_minggua(
            subject_key, profile, target_fields, include_subject_id=False
        )

    if "date" in target_fields and "birth_year" not in target_fields:
        mapped: dict[str, object] = {}
        date_text = _subject_date_string(profile)
        time_text = _subject_time_string(profile)
        candidate_values: dict[str, object | None] = {
            "name": profile.name,
            "date": date_text,
            "time": time_text,
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
    if "occupants" in target_fields:
        occupant_model = _unwrap_list_item_model(target_fields["occupants"].annotation)
        occupant_fields = (
            occupant_model.model_fields if occupant_model is not None else {}
        )
        return {
            "occupants": [
                _map_subject_to_minggua(
                    key,
                    subjects[key],
                    occupant_fields,
                    include_subject_id=True,
                )
                for key in subject_keys
            ]
        }

    if _is_pair_birth_tuple_tool(target_fields):
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
        prefixes = (
            ("person1_", "person2_")
            if "person1_birth_year" in target_fields
            else ("inner_", "outer_")
        )
        merged: dict[str, object] = {}
        for key, prefix in zip(subject_keys, prefixes, strict=True):
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

    if _is_sukuyo_pair_tool(target_fields):
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
        merged = {}
        for key, prefix in zip(subject_keys, ("person1_", "person2_"), strict=True):
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


def resolve_call_arguments(
    spec: ToolSpec,
    call: BatchCall,
    *,
    subjects: Mapping[str, SubjectProfile],
    defaults: Mapping[str, object],
) -> dict[str, object]:
    """Resolve tool arguments with precedence defaults < subject(s) < call.arguments."""
    model_fields = spec.request_model.model_fields
    resolved: dict[str, object] = {
        key: deepcopy(value) for key, value in defaults.items() if key in model_fields
    }

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
        if _is_pair_birth_tuple_tool(model_fields) or _is_sukuyo_pair_tool(
            model_fields
        ):
            raise ParameterError(
                f"工具 {spec.name} 需要使用 subjects（2 个对象），不能使用单个 subject",
                [{"path": "subject", "code": "pair_subjects_required"}],
            )
        if "occupants" in model_fields:
            resolved.update(
                _map_multi_subjects(spec, [call.subject], subjects, model_fields)
            )
        else:
            resolved.update(
                _map_single_subject(call.subject, subjects[call.subject], model_fields)
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


def _unknown_tool_error(tool_name: str, allowed_tools: set[str]) -> JsonValue:
    suggestions = difflib.get_close_matches(
        tool_name, sorted(allowed_tools), n=5, cutoff=0.4
    )
    issue: dict[str, object] = {"path": "tool", "code": "unknown_tool"}
    if suggestions:
        issue["constraints"] = {"suggestions": suggestions}
    return cast(
        JsonValue,
        error_response_payload(
            {
                "error": f"未知工具: {tool_name}",
                "error_code": "unknown_tool",
                "status_code": 404,
                "retryable": False,
                "issues": [issue],
            },
            tool_name,
        ),
    )


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

    for call in request.calls:
        spec = specs_by_name.get(call.tool)
        if spec is None:
            failed += 1
            results.append(
                {
                    "id": call.id,
                    "tool": call.tool,
                    "ok": False,
                    "error": _unknown_tool_error(call.tool, allowed_tools),
                }
            )
            if request.stop_on_error:
                break
            continue

        try:
            call_detail = call.detail if call.detail is not None else request.detail
            options = ExecutionOptions.model_validate(
                {"as_of": shared_as_of, "detail": call_detail}
            )
            resolved_args = resolve_call_arguments(
                spec,
                call,
                subjects=request.subjects,
                defaults=request.defaults,
            )
            tool_request = spec.request_model.model_validate(resolved_args)
            raw_result = execute_with_receipt(
                spec,
                tool_request,
                options=options,
            )
            if result_is_error(raw_result):
                failed += 1
                results.append(
                    {
                        "id": call.id,
                        "tool": call.tool,
                        "ok": False,
                        "error": cast(
                            JsonValue,
                            error_response_payload(raw_result, spec.operation_label_zh),
                        ),
                    }
                )
                if request.stop_on_error:
                    break
                continue

            delivered = deliver_response(
                raw_result,
                spec=spec,
                fields=call.fields,
                detail=options.detail,
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
            failure = handle_calculation_error(exc, spec.operation_label_zh)
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

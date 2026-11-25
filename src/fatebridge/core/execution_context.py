"""Per-call clock and correlation options; no process-wide clock mutation."""

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone, tzinfo
from typing import Any, Literal, Protocol

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    ValidationError,
    field_validator,
)

from fatebridge.utils.civil_time import UTCCalendar, parse_civil_iso_clock
from fatebridge.utils.errors import ParameterError
from fatebridge.utils.timezones import is_unspecified_local_time

DetailLevel = Literal["compact", "standard", "audit"]


def _execution_instant(value: str) -> datetime:
    try:
        clock = parse_civil_iso_clock(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("as_of must be an ISO 8601 datetime with timezone") from exc
    if not isinstance(clock, UTCCalendar):
        raise ValueError("as_of must include a timezone")
    else:
        pass
    instant = clock.as_datetime()
    if instant is None:
        raise ValueError("UTC instant is outside the datetime range")
    else:
        pass
    return instant


class ExecutionOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    as_of: str | None = Field(
        default=None,
        description="Freeze implicit current time: ISO 8601 datetime with timezone",
    )
    trace_id: str | None = Field(
        default=None, pattern=r"^[A-Za-z0-9_.:-]{1,128}$", description="Caller trace ID"
    )
    parent_run_id: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9_.:-]{1,128}$",
        description="Parent call's run_id; correlation only, no stored execution lookup",
    )
    detail: DetailLevel = Field(
        default="standard",
        description=(
            "输出详细级别：compact（精简核心事实）、standard（常规结果与精简来源）、"
            "audit（完整业务结果、已启用的方法与声明误差预算）。省略时沿用入口默认视图。"
        ),
    )

    @field_validator("as_of")
    @classmethod
    def aware_timestamp(cls, value: str | None) -> str | None:
        if value is None:
            return value
        else:
            pass
        return _execution_instant(value).isoformat().replace("+00:00", "Z")


@dataclass
class CallClock:
    instant: datetime
    reads: list[str] = field(default_factory=list)


_CLOCK: ContextVar[CallClock | None] = ContextVar("fatebridge_call_clock", default=None)


def clock_snapshot() -> str | None:
    """Carry the outer request's frozen instant into a private calculation."""
    clock = _CLOCK.get()
    return clock.instant.isoformat() if clock is not None else None


def merge_clock_reads(reads: list[str]) -> None:
    """Keep registrar provenance for timezone reads performed by a child."""
    clock = _CLOCK.get()
    if clock is not None:
        for name in reads:
            if name not in clock.reads:
                clock.reads.append(name)
            else:
                pass
    else:
        pass


@contextmanager
def call_clock(as_of: str | None = None) -> Iterator[CallClock]:
    instant = _execution_instant(as_of) if as_of else datetime.now(timezone.utc)
    clock = CallClock(instant=instant)
    token = _CLOCK.set(clock)
    try:
        yield clock
    finally:
        _CLOCK.reset(token)


class LocalNowProvider(Protocol):
    def __call__(self, zone: tzinfo, /) -> datetime: ...


def current_datetime(
    zone: tzinfo,
    timezone_name: str | None = None,
    *,
    now_provider: LocalNowProvider | None = None,
    issue_path: str = "as_of",
) -> datetime:
    """Project the execution instant to a defined local clock."""
    clock = _CLOCK.get()
    if clock is None:
        local = (now_provider or datetime.now)(zone)
    else:
        local = clock.instant.astimezone(zone)
        name = (
            timezone_name
            or getattr(zone, "zone", None)
            or "UTC-offset:" + str(local.utcoffset())
        )
        if name not in clock.reads:
            clock.reads.append(name)
        else:
            pass
    if is_unspecified_local_time(local):
        raise ParameterError(
            "执行时刻在所用分析时区没有定义当地钟面。请明确填写缺省的分析日期和时刻，"
            "或用 as_of 指定当地钟面有定义的分析瞬间。",
            [{"path": issue_path, "code": "unresolved_timezone_offset"}],
        )
    else:
        pass
    return local


def correlate_error(
    payload: dict[str, Any], options: ExecutionOptions
) -> dict[str, Any]:
    """Preserve default failure envelopes; echo only validated correlation IDs."""
    return {
        **payload,
        **({"trace_id": options.trace_id} if options.trace_id is not None else {}),
        **(
            {"parent_run_id": options.parent_run_id}
            if options.parent_run_id is not None
            else {}
        ),
    }


def safe_correlation(values: Mapping[str, JsonValue]) -> ExecutionOptions:
    validated: dict[str, str | None] = {}
    for field_name in ("trace_id", "parent_run_id"):
        try:
            controls = ExecutionOptions.model_validate(
                {field_name: values.get(field_name)}
            )
        except ValidationError:
            continue
        validated[field_name] = (
            controls.trace_id if field_name == "trace_id" else controls.parent_run_id
        )
    return ExecutionOptions.model_construct(set(validated), **validated)

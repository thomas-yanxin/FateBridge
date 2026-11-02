"""Per-call clock and correlation options; no process-wide clock mutation."""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone, tzinfo
from typing import Callable, Iterator, List, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from fatebridge.utils.civil_clock import parse_iso_datetime


class ExecutionOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    as_of: Optional[str] = Field(
        default=None,
        description="Freeze implicit current time: ISO 8601 datetime with timezone",
    )
    trace_id: Optional[str] = Field(
        default=None, pattern=r"^[A-Za-z0-9_.:-]{1,128}$", description="Caller trace ID"
    )
    parent_run_id: Optional[str] = Field(
        default=None,
        pattern=r"^[A-Za-z0-9_.:-]{1,128}$",
        description="Parent call's run_id; correlation only, no stored execution lookup",
    )

    @field_validator("as_of")
    @classmethod
    def aware_timestamp(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        moment = parse_iso_datetime(value.replace("Z", "+00:00"))
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("as_of must include a timezone")
        return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class CallClock:
    instant: datetime
    reads: List[str] = field(default_factory=list)


_CLOCK: ContextVar[Optional[CallClock]] = ContextVar(
    "fatebridge_call_clock", default=None
)


def clock_snapshot() -> Optional[str]:
    """Carry the outer request's frozen instant into a private calculation."""
    clock = _CLOCK.get()
    return clock.instant.isoformat() if clock is not None else None


def merge_clock_reads(reads: List[str]) -> None:
    """Keep registrar provenance for timezone reads performed by a child."""
    clock = _CLOCK.get()
    if clock is not None:
        for name in reads:
            if name not in clock.reads:
                clock.reads.append(name)


@contextmanager
def call_clock(as_of: Optional[str] = None) -> Iterator[CallClock]:
    instant = (
        parse_iso_datetime(as_of.replace("Z", "+00:00"))
        if as_of
        else datetime.now(timezone.utc)
    )
    clock = CallClock(instant)
    token = _CLOCK.set(clock)
    try:
        yield clock
    finally:
        _CLOCK.reset(token)


def current_datetime(
    zone: tzinfo,
    timezone_name: Optional[str] = None,
    *,
    now_provider: Optional[Callable[[tzinfo], datetime]] = None,
) -> datetime:
    """Match datetime.now(zone) outside a transport execution context."""
    clock = _CLOCK.get()
    if clock is None:
        return now_provider(zone) if now_provider else datetime.now(zone)
    name = (
        timezone_name
        or getattr(zone, "zone", None)
        or "UTC-offset:" + str(clock.instant.astimezone(zone).utcoffset())
    )
    if name not in clock.reads:
        clock.reads.append(name)
    return clock.instant.astimezone(zone)


def correlate_error(payload: dict, options: ExecutionOptions) -> dict:
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


def safe_correlation(values: dict) -> ExecutionOptions:
    validated = {}
    for key in ("trace_id", "parent_run_id"):
        try:
            controls = ExecutionOptions.model_validate({key: values.get(key)})
        except ValidationError:
            continue
        validated[key] = getattr(controls, key)
    return ExecutionOptions.model_validate(validated)

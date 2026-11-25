"""Physical instant ordering and explicit-offset resolution of local clocks."""

import re
from datetime import datetime, time, timedelta, timezone

from fatebridge.utils.civil_time import utc_ordering_key
from fatebridge.utils.errors import ParameterError
from fatebridge.utils.timezones import (
    is_unspecified_local_time,
    parse_timezone_name,
    validate_local_clock,
)

_OFFSET = re.compile(r"^([+-])(\d{2}):(\d{2})(?::(\d{2}))?$")


def utc_instant(moment: datetime) -> datetime:
    """Never compare same-zone wall labels when an actual instant is intended."""
    if moment.utcoffset() is None:
        raise ValueError("实际时刻比较必须带时区，不能默认服务器时区")
    return moment.astimezone(timezone.utc)


def format_utc_offset(offset: timedelta) -> str:
    """Render the actual offset at the same precision as an ISO clock label."""
    return time(tzinfo=timezone(offset)).isoformat().removeprefix("00:00:00")


def resolve_civil_clock(
    wall: datetime,
    zone: str,
    explicit_offset: str | None = None,
    *,
    offset_field: str = "analysis_utc_offset",
    timezone_field: str | None = None,
    recorded_offset: str | None = None,
) -> datetime:
    """Resolve a local label without inventing a side of a fold or a gap.

    The named zone remains the calendar zone. An offset only selects and
    verifies the actual instant, including historical offsets with seconds.
    """
    if wall.utcoffset() is not None:
        raise ValueError("本地钟表字段须为无时区标签，实际时刻另外明确偏移")
    if recorded_offset is not None:
        if explicit_offset is None:
            explicit_offset = recorded_offset
        elif explicit_offset != recorded_offset:
            requested = resolve_civil_clock(
                wall,
                zone,
                explicit_offset,
                offset_field=offset_field,
                timezone_field=timezone_field,
            )
            recorded = resolve_civil_clock(
                wall,
                zone,
                recorded_offset,
                offset_field=offset_field,
                timezone_field=timezone_field,
            )
            if utc_ordering_key(requested) != utc_ordering_key(recorded):
                raise ParameterError(
                    f"{offset_field}与已确认出生记录的UTC偏移选择冲突",
                    [{"path": offset_field, "code": "conflicting_utc_offset"}],
                    status_code=400,
                )
            return requested
    zone_info = parse_timezone_name(zone, issue_path=timezone_field)
    local = wall.replace(tzinfo=zone_info)
    if explicit_offset is None:
        validate_local_clock(local)
        return local
    match = (
        _OFFSET.fullmatch(explicit_offset.strip())
        if type(explicit_offset) is str
        else None
    )
    if match is None:
        raise ParameterError(
            f"{offset_field}须为±HH:MM或±HH:MM:SS",
            [{"path": offset_field, "code": "invalid_utc_offset"}],
            status_code=400,
        )
    sign, hour, minute, second = match.groups()
    h, m, s = int(hour), int(minute), int(second or 0)
    if h >= 24 or m >= 60 or s >= 60:
        raise ParameterError(
            f"{offset_field}超出有效UTC偏移范围",
            [{"path": offset_field, "code": "invalid_utc_offset"}],
            status_code=400,
        )
    expected = timedelta(hours=h, minutes=m, seconds=s) * (1 if sign == "+" else -1)
    candidates = local.replace(fold=0), local.replace(fold=1)
    for candidate in candidates:
        if candidate.utcoffset() == expected:
            # The parsed types are fold-aware. Validate the selected member
            # and keep fold=0 for an ordinary label with equal offsets.
            validate_local_clock(candidate, allow_ambiguous=True)
            return candidate
    defined = next(
        (
            candidate
            for candidate in candidates
            if not is_unspecified_local_time(candidate)
        ),
        candidates[0],
    )
    validate_local_clock(defined, allow_ambiguous=True)
    allowed = sorted(
        {
            format_utc_offset(offset)
            for candidate in candidates
            if not is_unspecified_local_time(candidate)
            and (offset := candidate.utcoffset()) is not None
        }
    )
    raise ParameterError(
        f"{offset_field}={explicit_offset!r}与该钟时在时区{zone!r}的实际偏移不一致。"
        f"该时区规则给出的偏移为{'、'.join(allowed)}，请核对原始钟时和时区。",
        [
            {
                "path": offset_field,
                "code": "utc_offset_mismatch",
                "constraints": {"expected": allowed},
            }
        ],
        status_code=400,
    )

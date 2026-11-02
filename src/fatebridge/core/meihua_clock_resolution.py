"""A selected named-zone clock must have a defined local time type.

TZif -00 is a placeholder, not evidence that the location used UTC.  Inspect
the selected fold after the shared resolver so another, defined candidate at
the same wall label remains usable with its verified offset.
"""

from datetime import datetime

from pydantic_core import PydanticCustomError

from fatebridge.utils.civil_clock import resolve_civil_clock


class MeihuaUnspecifiedClockError(ValueError):
    """The selected regional time type cannot verify a civil instant."""


_UNSPECIFIED_MESSAGE = (
    "所选时区在该起卦钟时没有已定义的当地时间规则，不能按零偏移核验或计算。"
    "若已核实实际固定UTC偏移，请在analysis_timezone直接提供该明确偏移；"
    "analysis_utc_offset只核验地区规则，不能替代缺失的地区钟时定义。"
)


def resolve_meihua_civil_clock(
    wall: datetime, zone: str, explicit_offset: str | None = None
) -> datetime:
    """Retain shared gap/fold rules and reject an unspecified selected type."""
    try:
        resolved = resolve_civil_clock(wall, zone, explicit_offset)
    except PydanticCustomError as error:
        if error.type == "unresolved_timezone_offset":
            raise MeihuaUnspecifiedClockError(_UNSPECIFIED_MESSAGE) from error
        raise
    if resolved.tzname() in {"-00", "zzz"}:
        raise MeihuaUnspecifiedClockError(_UNSPECIFIED_MESSAGE)
    return resolved

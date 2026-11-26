"""Translate the shared civil clock error into the Meihua field contract."""

from datetime import datetime

from pydantic_core import PydanticCustomError

from fatebridge.utils.civil_clock import format_utc_offset, resolve_civil_clock
from fatebridge.utils.errors import ParameterError
from fatebridge.utils.timezones import LocalClockError


class MeihuaUnspecifiedClockError(ValueError):
    """The selected regional time type cannot verify a civil instant."""


UNSPECIFIED_MESSAGE = (
    "所选时区在该起卦钟时没有已定义的当地时间规则，不能按零偏移核验或计算。"
    "若已核实实际固定UTC偏移，请在analysis_timezone直接提供该明确偏移；"
    "analysis_utc_offset只核验地区规则，不能替代缺失的地区钟时定义。"
)


def resolve_meihua_civil_clock(
    wall: datetime, zone: str, explicit_offset: str | None = None
) -> datetime:
    """Retain shared gap/fold rules and reject an unspecified selected type."""
    try:
        return resolve_civil_clock(
            wall, zone, explicit_offset, timezone_field="analysis_timezone"
        )
    except LocalClockError as error:
        issue: dict[str, object]
        if error.code == "ambiguous_local_time":
            offsets = [
                format_utc_offset(offset)
                for fold in (0, 1)
                if (offset := error.moment.replace(fold=fold).utcoffset()) is not None
            ]
            message = (
                "起卦钟时处于时区回拨造成的重复区间。"
                "请核实当时的 UTC 偏移并填写 analysis_utc_offset。"
            )
            issue = {
                "path": "analysis_utc_offset",
                "code": error.code,
                "constraints": {"expected": offsets},
            }
        else:
            message = "起卦钟时处于时区跳时区间。请核对当地日期、时刻和时区。"
            issue = {"path": "analysis_hour", "code": error.code}
        raise ParameterError(message, [issue]) from error
    except PydanticCustomError as error:
        if error.type == "unresolved_timezone_offset":
            raise MeihuaUnspecifiedClockError(UNSPECIFIED_MESSAGE) from error
        raise

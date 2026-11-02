"""Choose a real current instant or the declared partial-date convention once."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fatebridge.core.execution_context import current_datetime
from fatebridge.utils.timezones import parse_timezone_name, validate_local_clock

DATE_FIELDS = (
    "analysis_year",
    "analysis_month",
    "analysis_day",
    "analysis_hour",
    "analysis_minute",
)
METHOD_ID = "bazi_analysis_instant_v1"


@dataclass(frozen=True)
class AnalysisMoment:
    moment: datetime
    reference: Dict[str, Any]


def resolve_analysis_moment(
    tool: str,
    timezone_name: str,
    *,
    analysis_year: Optional[int] = None,
    analysis_month: Optional[int] = None,
    analysis_day: Optional[int] = None,
    analysis_hour: Optional[int] = None,
    analysis_minute: Optional[int] = None,
) -> AnalysisMoment:
    """Implicit now retains its instant; explicit components retain old defaults.

    An aware execution clock already identifies the correct DST occurrence.
    Explicit wall components do not, and must pass the local-clock validator.
    """
    inherited = {
        "timing_analysis": DATE_FIELDS[:2],
        "liuyue_analysis": DATE_FIELDS[:2],
        "liuri_analysis": DATE_FIELDS[:3],
        "liushi_analysis": DATE_FIELDS[:4],
        "dayun_analysis": DATE_FIELDS[:1],
    }
    if tool not in inherited:
        raise ValueError("Unsupported BaZi analysis clock: " + tool)
    zone = parse_timezone_name(timezone_name)
    supplied = dict(
        zip(
            DATE_FIELDS,
            (
                analysis_year,
                analysis_month,
                analysis_day,
                analysis_hour,
                analysis_minute,
            ),
        )
    )
    provided = [name for name in DATE_FIELDS if supplied[name] is not None]
    fixed = {}
    if not provided:
        # Do not reconstruct a wall datetime or floor seconds: either would
        # lose information already present in the frozen as_of instant.
        moment = current_datetime(zone, timezone_name)
        aware = moment
        defaulted = list(DATE_FIELDS)
        basis = "implicit_execution_clock"
        precision = "execution_clock"
    else:
        defaulted = [name for name in inherited[tool] if supplied[name] is None]
        now = current_datetime(zone, timezone_name) if defaulted else None
        values = []
        for field, attribute in zip(
            DATE_FIELDS, ("year", "month", "day", "hour", "minute")
        ):
            value = supplied[field]
            if value is None:
                if field in defaulted:
                    assert now is not None
                    value = getattr(now, attribute)
                else:
                    value = (
                        15
                        if tool == "liuyue_analysis" and field == "analysis_day"
                        else 1 if field in DATE_FIELDS[:3] else 0
                    )
                    fixed[field] = value
            values.append(value)
        # Preserve the existing naive explicit-component contract after
        # validating which physical instant that wall label can represent.
        moment = datetime(values[0], values[1], values[2], values[3], values[4])
        aware = moment.replace(tzinfo=zone)
        try:
            validate_local_clock(aware)
        except ValueError as exc:
            reason = str(exc).split("；", 1)[0].replace("出生钟时", "分析钟时")
            raise ValueError(
                reason
                + "；请更正分析钟时，或省略analysis_*日期分量并用含时区as_of提供已确认的目标瞬间；勿改出生时区来消歧。"
            ) from exc
        basis = (
            "legacy_partial_components" if len(provided) < 5 else "explicit_components"
        )
        precision = "minute"
    reference = {
        "method_id": METHOD_ID,
        "basis": basis,
        "analysis_datetime": aware.isoformat(),
        "utc_datetime": aware.astimezone(timezone.utc).isoformat(),
        "timezone": timezone_name,
        "fold": aware.fold,
        "precision": precision,
        "provided_fields": provided,
        "defaulted_from_clock": defaulted,
        "fixed_defaults": fixed,
        "scope": "实际分析民用瞬间，不是出生太阳钟。完全省略日期用本次as_of或执行开始时刻，保留UTC偏移、fold及秒微秒；显式部分日期沿用各工具补齐约定。旧流时内的整点仅是时柱缓存粒度，不用于交气、交运比较。秒微秒是输入表示精度，不认证天文或出生记录精度。",
    }
    return AnalysisMoment(moment, reference)


def age_only_reference() -> Dict[str, Any]:
    return {
        "method_id": METHOD_ID,
        "basis": "explicit_age_reference",
        "provided_fields": [],
        "defaulted_from_clock": [],
        "fixed_defaults": {},
        "scope": "显式年龄仅用于大运年龄参考，没有据此补造分析日时。",
    }


def analysis_clock_snapshot_lines(reference: Dict[str, Any]) -> list[str]:
    if reference.get("basis") != "implicit_execution_clock":
        return []
    return [
        f"本次分析民用瞬间：{reference['analysis_datetime']}；UTC：{reference['utc_datetime']}。",
        "日期全部省略，使用本次as_of或执行开始时刻，未替换为月初、月中或零点。",
        "流时表中的整点只表示时柱粒度；交气、交运与流年流月比较使用上列完整瞬间。",
    ]

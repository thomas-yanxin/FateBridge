"""Choose a real current instant or the declared partial-date convention once."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, TypedDict

from fatebridge.core.execution_context import current_datetime
from fatebridge.utils.civil_time import utc_calendar
from fatebridge.utils.errors import ParameterError
from fatebridge.utils.timezones import parse_timezone_name, validate_local_clock

DATE_FIELDS = (
    "analysis_year",
    "analysis_month",
    "analysis_day",
    "analysis_hour",
    "analysis_minute",
)
METHOD_ID: Literal["bazi_analysis_instant_v1"] = "bazi_analysis_instant_v1"


class AnalysisClockFields(TypedDict):
    method_id: Literal["bazi_analysis_instant_v1"]
    provided_fields: list[str]
    defaulted_from_clock: list[str]
    fixed_defaults: dict[str, int]
    scope: str


class AnalysisInstantReference(AnalysisClockFields):
    basis: Literal[
        "implicit_execution_clock", "declared_partial_components", "explicit_components"
    ]
    analysis_datetime: str
    utc_datetime: str
    timezone: str
    fold: int
    precision: Literal["execution_clock", "minute"]


class AnalysisAgeReference(AnalysisClockFields):
    basis: Literal["explicit_age_reference"]


AnalysisClockReference = AnalysisInstantReference | AnalysisAgeReference


@dataclass(frozen=True, kw_only=True)
class AnalysisMoment:
    moment: datetime
    reference: AnalysisInstantReference


def resolve_analysis_moment(
    tool: str,
    timezone_name: str,
    *,
    analysis_year: int | None = None,
    analysis_month: int | None = None,
    analysis_day: int | None = None,
    analysis_hour: int | None = None,
    analysis_minute: int | None = None,
) -> AnalysisMoment:
    """Preserve the implicit instant or validate the explicitly supplied local wall label."""
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
    fixed: dict[str, int] = {}
    basis: Literal[
        "implicit_execution_clock", "declared_partial_components", "explicit_components"
    ]
    precision: Literal["execution_clock", "minute"]
    if not provided:
        # note (clock): Keep seconds and the selected fold from the frozen instant.
        moment = current_datetime(zone, timezone_name)
        aware = moment
        defaulted = list(DATE_FIELDS)
        basis = "implicit_execution_clock"
        precision = "execution_clock"
    else:
        defaulted = [name for name in inherited[tool] if supplied[name] is None]
        now = current_datetime(zone, timezone_name) if defaulted else None
        clock_components = (
            (now.year, now.month, now.day, now.hour, now.minute)
            if now is not None
            else (None, None, None, None, None)
        )
        values: list[int] = []
        for field, clock_component in zip(DATE_FIELDS, clock_components):
            value = supplied[field]
            if value is None:
                if field in defaulted:
                    assert clock_component is not None
                    value = clock_component
                else:
                    value = (
                        15
                        if tool == "liuyue_analysis" and field == "analysis_day"
                        else 1 if field in DATE_FIELDS[:3] else 0
                    )
                    fixed[field] = value
            values.append(value)
        # note (clock): Explicit components return a naive wall label after validation.
        moment = datetime(values[0], values[1], values[2], values[3], values[4])
        aware = moment.replace(tzinfo=zone)
        try:
            validate_local_clock(aware, clock_label="分析钟时")
        except ParameterError:
            raise
        except ValueError as exc:
            reason = str(exc).split("；", 1)[0]
            raise ValueError(
                reason
                + "；请更正分析钟时，或省略analysis_*日期分量并用含时区as_of提供已确认的目标瞬间；勿改出生时区来消歧。"
            ) from exc
        basis = (
            "declared_partial_components"
            if len(provided) < 5
            else "explicit_components"
        )
        precision = "minute"
    reference: AnalysisInstantReference = {
        "method_id": METHOD_ID,
        "basis": basis,
        "analysis_datetime": aware.isoformat(),
        "utc_datetime": utc_calendar(aware).isoformat(),
        "timezone": timezone_name,
        "fold": aware.fold,
        "precision": precision,
        "provided_fields": provided,
        "defaulted_from_clock": defaulted,
        "fixed_defaults": fixed,
        "scope": "实际分析民用瞬间，不是出生太阳钟。完全省略日期用本次as_of或执行开始时刻，保留UTC偏移、fold及秒微秒；显式部分日期沿用各工具补齐约定。旧流时内的整点仅是时柱缓存粒度，不用于交气、交运比较。秒微秒是输入表示精度，不认证天文或出生记录精度。",
    }
    return AnalysisMoment(moment=moment, reference=reference)


def age_only_reference() -> AnalysisAgeReference:
    return {
        "method_id": METHOD_ID,
        "basis": "explicit_age_reference",
        "provided_fields": [],
        "defaulted_from_clock": [],
        "fixed_defaults": {},
        "scope": "显式年龄仅用于大运年龄参考，没有据此补造分析日时。",
    }


def analysis_clock_snapshot_lines(reference: AnalysisClockReference) -> list[str]:
    if reference["basis"] != "implicit_execution_clock":
        return []
    return [
        f"本次分析民用瞬间：{reference['analysis_datetime']}；UTC：{reference['utc_datetime']}。",
        "日期全部省略，使用本次as_of或执行开始时刻，未替换为月初、月中或零点。",
        "流时表中的整点只表示时柱粒度；交气、交运与流年流月比较使用上列完整瞬间。",
    ]

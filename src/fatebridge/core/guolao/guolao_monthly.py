"""Source-ordinal monthly limits with explicitly chosen modern month mapping."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any, Literal

from fatebridge.core.almanac import get_bazi_month_context, get_lunar_context
from fatebridge.core.astro.physical_epoch import PhysicalEpoch
from fatebridge.core.guolao.guolao_classical import month_limit_branch
from fatebridge.core.guolao.guolao_epoch import native_month_context
from fatebridge.utils.civil_time import (
    CivilPoint,
    NominalClockLabel,
    ZonedCalendar,
    nominal_calendar_bracket,
    utc_calendar,
)

MonthBasis = Literal["jie_month", "chinese_lunar_utc8"]
BASES = {"jie_month", "chinese_lunar_utc8"}
MONTH_TIMEZONE = "Etc/GMT-8"  # Fixed UTC+08, including years with Chinese DST.
DATA = Path(__file__).resolve().parents[2] / "data" / "guolao" / "month-limit-v1.json"


def month_context(
    moment: datetime | PhysicalEpoch,
    basis: MonthBasis,
    *,
    source_calendar: CivilPoint | None = None,
) -> dict[str, Any]:
    """Map the recorded physical instant, never a shifted true-solar display."""
    if basis not in BASES:
        raise ValueError("须显式选择jie_month或chinese_lunar_utc8月序政策")
    if isinstance(moment, PhysicalEpoch):
        return native_month_context(moment, basis)
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("月限月序换算须提供带偏移的物理瞬间")
    clocks: dict[str, Any] = {
        "instant_utc": utc_calendar(moment).isoformat(),
        "calendar_datetime": None,
        "timezone": "UTC+08:00",
    }
    # Only an actually unrepresentable UTC+08 label makes this layer
    # unavailable. A valid local label may have UTC in year0 or10000.
    calendar = ZonedCalendar(utc_calendar(moment), timezone(timedelta(hours=8)))
    if calendar.as_datetime() is None:
        return {
            **clocks,
            "status": "outside_datetime_calendar_range",
            "month_number": None,
            "is_leap_month": None,
            "unavailable_reason": "fixed_utc8_label_outside_datetime_range",
        }
    clocks["calendar_datetime"] = calendar.isoformat()
    if basis == "jie_month":
        context = get_bazi_month_context(moment, MONTH_TIMEZONE)
        index = context["month_index"]
        if type(index) is not int or not 0 <= index < 12:
            raise ValueError("节月换算未给出有效月序，不能据此分配月限")
        # The shared calendar indexes 寅 at zero. Keep actual term boundaries.
        return {
            "status": "available",
            "month_number": index + 1,
            "month_branch": context["branch"],
            "start_boundary": context["start_term"],
            "next_boundary": context["next_term"],
            **clocks,
            "boundary_basis": "calculated_jie_instants_half_open",
            "is_leap_month": False,
        }
    lunar_label: datetime | NominalClockLabel = moment
    if source_calendar is not None:
        # A pre-atomic mean-solar carrier rounds to microseconds for display.
        # Select the lunar date from the unrounded fixed-offset coordinate.
        lower, _ = nominal_calendar_bracket(source_calendar.day + Fraction(1, 3))
        if lower.ordinal != calendar.local_ordinal:
            year, month, day = lower.date_parts
            lunar_label = NominalClockLabel(lower.ordinal, 0)
            clocks.update(
                calendar_date=f"{year:04d}-{month:02d}-{day:02d}",
                calendar_lookup_basis="retained_nominal_source_point_fixed_utc8_date",
            )
    lunar_context = get_lunar_context(
        lunar_label, timezone_name=MONTH_TIMEZONE, civil_datetime=moment
    )
    if lunar_context is None:
        return {
            "status": "calendar_unavailable",
            "month_number": None,
            **clocks,
            "boundary_basis": "shared_chinese_lunar_table_utc8_civil_date",
        }
    return {
        "status": "available",
        "month_number": lunar_context["month"],
        "lunar_year": lunar_context["year"],
        "lunar_day": lunar_context["day"],
        "is_leap_month": lunar_context["is_leap_month"],
        **clocks,
        "boundary_basis": "shared_chinese_lunar_table_utc8_civil_date",
        "conversion_source": lunar_context.get("conversion_source"),
    }


def build_month_limit(
    *,
    annual_branch: str,
    birth_instant: datetime | PhysicalEpoch,
    target_instant: datetime,
    basis: MonthBasis,
    palaces: list[dict[str, Any]],
    birth_source_calendar: CivilPoint | None = None,
) -> dict[str, Any]:
    raw = DATA.read_bytes()
    source = json.loads(raw)
    birth = month_context(birth_instant, basis, source_calendar=birth_source_calendar)
    target = month_context(target_instant, basis)
    result: dict[str, Any] = {
        "model_id": source["model_id"],
        "source_id": source["source_id"],
        "source_url": source["source_url"],
        "source_title": source["title"],
        "source_data_sha256": hashlib.sha256(raw).hexdigest(),
        "source_image_sha256": source["source_image_sha256"],
        "locator": source["locator"],
        "month_basis": basis,
        "method": "birth_month_on_annual_small_limit_reverse_to_target_month",
        "annual_branch": annual_branch,
        "birth_month": birth,
        "target_month": target,
        "branch": None,
        "natal_functional_palace": None,
        "palace_lord": None,
        "ordinal_rule_collated": True,
        "calendar_mapping_classical_acceptance": False,
        "clock_basis": "recorded_physical_instant_not_true_solar_display",
        "intercalary_policy": "regular_month_numbers_1_to_12_only_intercalary_month_unassigned",
        "limitations": [
            "原页核对的是十二月序逆转；节月与现代农历映射均未由该页裁定",
            "年小限仍沿用本次明示的立春换年研究政策，选择月制不会更改年界",
            "现代农历取UTC+08民用日，出生月或目标月为闰月时不分配月限宫",
            "只计算条件落宫，不据此推断晋升、岗位变动或事件概率",
        ],
    }
    if birth["status"] != "available" or target["status"] != "available":
        result["status"] = "unassigned_calendar_unavailable"
    elif basis == "chinese_lunar_utc8" and (
        birth["is_leap_month"] or target["is_leap_month"]
    ):
        result["status"] = "unassigned_intercalary_policy_unresolved"
    else:
        result["status"] = "research_partial"
        branch = month_limit_branch(
            annual_branch, birth["month_number"], target["month_number"]
        )
        palace = next(p for p in palaces if p["branch"] == branch)
        result.update(
            branch=branch,
            natal_functional_palace=palace["palace"],
            palace_lord=palace["lord"],
        )
    return result

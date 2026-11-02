"""Ziwei clock receipts: a solar date label is not a second civil instant.

This records the existing placement policy; it does not resolve the historical
choice of clock, move stars, or recompute lunations for a foreign time zone.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from dateutil import tz

from fatebridge.core.almanac import get_lunar_context, localize_datetime
from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.core.ziwei_date_sources import (
    LIBRARY_ADAPTER,
    date_conversion_provenance,
)
from fatebridge.utils.civil_clock import format_utc_offset, utc_instant
from fatebridge.utils.timezones import parse_timezone_name, timezone_rules_metadata


def _date_fields(lunar: dict[str, Any] | None) -> dict[str, Any] | None:
    if not lunar:
        return None
    return {key: lunar[key] for key in ("year", "month", "day", "is_leap_month")}


def calendar_basis(seed: MetaphysicsSeed) -> dict[str, Any]:
    """Compare date-table lookups while preserving the physical civil instant."""
    placement_context = seed.calendar_context.get("lunar_calendar")
    civil_context = get_lunar_context(seed.input_datetime, timezone_name=seed.timezone)
    placement = _date_fields(placement_context)
    civil = _date_fields(civil_context)
    # Explicit UTC+8 is the reference of the frozen date tables. Do not use
    # historical Asia/Hong_Kong offsets or attach a zone to the solar label.
    reference = localize_datetime(seed.input_datetime, seed.timezone).astimezone(
        parse_timezone_name("+08:00")
    )
    reference_context = get_lunar_context(reference, timezone_name="+08:00")
    reference_lunar = _date_fields(reference_context)
    provenance = date_conversion_provenance(
        {
            "placement": seed.corrected_datetime.date().isoformat(),
            "civil": seed.input_datetime.date().isoformat(),
            "reference_utc_plus_08": reference.date().isoformat(),
        },
        {
            "placement": placement_context,
            "civil": civil_context,
            "reference_utc_plus_08": reference_context,
        },
    )
    reference_id = provenance["lookups"]["reference_utc_plus_08"][
        "printed_date_reference"
    ]
    result = {
        "method_id": "ziwei_calendar_basis_v1",
        "placement_clock": "apparent_solar" if seed.applied_true_solar else "civil",
        "placement_datetime": seed.corrected_datetime.strftime("%Y-%m-%d %H:%M:%S"),
        "civil_datetime": seed.input_datetime.strftime("%Y-%m-%d %H:%M:%S"),
        "timezone": seed.timezone,
        "date_shift_days": (
            seed.corrected_datetime.date() - seed.input_datetime.date()
        ).days,
        "placement_lunar_date": placement,
        "civil_date_lunar_date": civil,
        "reference_datetime_utc_plus_08": reference.strftime("%Y-%m-%d %H:%M:%S"),
        "reference_lunar_date": reference_lunar,
        "date_lookup_convention": "fixed_east_asian_date_table_not_local_lunation_recalculation",
        "day_boundary": "00:00_in_selected_clock",
        "solar_terms_basis": "physical_civil_instant",
        "classical_clock_rule_verified": False,
        "source_scope": "HKO verifies published UTC+08 civil dates, not the apparent-solar placement policy",
        "reference_source": (
            provenance["printed_date_references"][reference_id]["url"]
            if reference_id
            else None
        ),
        "date_conversion_provenance": provenance,
        "time_input": None,
        "civil_clock": None,
    }
    if reference_id == "tam_1900":
        result["source_scope"] = (
            "TAM supplies printed 1900 civil-date labels; the apparent-solar "
            "placement policy and historical clock choice remain unverified"
        )
    elif reference_id is None:
        result["source_scope"] = (
            "No selected printed date witness for this reference date"
        )
    if seed.birth_time_normalization is not None:
        result["time_input"] = deepcopy(seed.birth_time_normalization)
    if seed.input_datetime.utcoffset() is not None:
        civil_instant = localize_datetime(seed.input_datetime, seed.timezone)
        offset = civil_instant.utcoffset()
        assert offset is not None
        result["civil_clock"] = {
            "method_id": "ziwei_explicit_civil_offset_v1",
            "selection": "explicit_offset_matching_named_zone",
            "timezone": seed.timezone,
            "resolved_utc_offset": format_utc_offset(offset),
            "wall_datetime": civil_instant.replace(tzinfo=None).isoformat(sep=" "),
            "was_ambiguous": tz.datetime_ambiguous(civil_instant),
            "fold": civil_instant.fold,
            "instant_utc": utc_instant(civil_instant).isoformat(),
            "timezone_rules": timezone_rules_metadata(seed.timezone),
        }
    return result


def context_basis(basis: dict[str, Any]) -> dict[str, Any]:
    """Small first-turn receipt; the full comparison has its own evidence view."""
    result = {
        "lunar_date_basis": basis["placement_clock"] + "_date_label_at_midnight",
        "calendar_date_shift_days": basis["date_shift_days"],
    }
    if basis.get("time_input"):
        result["time_input_status"] = basis["time_input"]["status"]
        sensitivity = basis["time_input"].get("minute_sensitivity", {})
        if sensitivity.get("crosses_hour_branch") or sensitivity.get(
            "crosses_placement_date"
        ):
            result["time_input_minute_sensitive"] = True
    if basis.get("civil_clock"):
        result["civil_utc_offset"] = basis["civil_clock"]["resolved_utc_offset"]
        result["civil_instant_utc"] = basis["civil_clock"]["instant_utc"]
    if provenance := basis.get("date_conversion_provenance"):
        lookup = provenance["lookups"]["placement"]
        if any(
            row["printed_date_reference"] == "tam_1900"
            or row["implementation_provider"] != LIBRARY_ADAPTER
            or row["applied_year_info_correction"] is not None
            for row in provenance["lookups"].values()
        ):
            result["lunar_date_provider"] = lookup["implementation_provider"]
            result["lunar_date_reference"] = lookup["printed_date_reference"]
    return result


def basis_text(basis: dict[str, Any]) -> str:
    clock = "真太阳日期" if basis["placement_clock"] == "apparent_solar" else "钟表日期"
    civil = basis["civil_date_lunar_date"]
    label = (
        f"{civil['year']}年{civil['month']}月{civil['day']}日"
        f"{'（闰月）' if civil['is_leap_month'] else ''}"
        if civil
        else "超出支持范围"
    )
    text = (
        f"排盘农历依据：{clock}，所选时钟00:00换日；"
        f"相对钟表日期偏移{basis['date_shift_days']:+d}日；钟表日期查表农历：{label}；"
        "节气按实际钟表时刻判定；真太阳日期口径未获原典认证"
    )
    advisories = (basis.get("time_input") or {}).get("advisories", [])
    if advisories:
        text += "；校时依据提示：" + "；".join(advisories)
    if civil_clock := basis.get("civil_clock"):
        text += (
            f"；明确民用偏移{civil_clock['resolved_utc_offset']}，fold={civil_clock['fold']}，"
            f"实际UTC瞬间{civil_clock['instant_utc']}；偏移只核对所选时区，不证明出生钟表记录"
        )
    sensitivity = (basis.get("time_input") or {}).get("minute_sensitivity", {})
    if sensitivity.get("crosses_hour_branch") or sensitivity.get(
        "crosses_placement_date"
    ):
        text += "；给定钟表分钟内的假设秒数端点会跨时辰或排盘日期，基准仍按秒0计算，未替换出生资料或命盘"
    if provenance := basis.get("date_conversion_provenance"):
        lookup = provenance["lookups"]["placement"]
        provider = lookup["implementation_provider"]
        if any(
            row["printed_date_reference"] == "tam_1900"
            or row["implementation_provider"] != LIBRARY_ADAPTER
            or row["applied_year_info_correction"] is not None
            for row in provenance["lookups"].values()
        ):
            implementation = provenance["implementation_sources"].get(provider)
            label = implementation["publisher"] if implementation else "离线农历库表"
            witness = provenance["printed_date_references"].get(
                lookup["printed_date_reference"]
            )
            text += f"；排盘日期换算使用{label}"
            if witness:
                text += f"，印刷日期参照为{witness['publisher']}"
            text += "；实现输入与日期参照分列，不据此认证古典时钟"
    return text

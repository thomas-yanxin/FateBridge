"""Reconcile returned solar instants with frozen published civil-date labels."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from importlib.resources import files
from typing import Any

from fatebridge.utils.civil_time import datetime_fromisoformat_preserving_offset

from .meihua_clock_iso import parse_meihua_clock_label

_TERMS = frozenset(
    "小寒 大寒 立春 雨水 惊蛰 春分 清明 谷雨 立夏 小满 芒种 夏至 "
    "小暑 大暑 立秋 处暑 白露 秋分 寒露 霜降 立冬 小雪 大雪 冬至".split()
)
_PROFILE_SHA256 = "5f762b1eb728afecda36ad7c9d6c50df13f7f331ee4bafa2f8f5dc0258f46832"
_REFERENCE_OFFSET = timezone(timedelta(hours=8))
_COMPARED = {"published_date_match", "published_date_disagreement"}


@lru_cache(maxsize=1)
def _profile() -> tuple[dict[str, Any], str]:
    content = (
        files("fatebridge.data").joinpath("meihua/solar-dates-hko-v1.json").read_bytes()
    )
    if hashlib.sha256(content).hexdigest() != _PROFILE_SHA256:
        raise ValueError("Frozen HKO solar-date profile content changed")
    raw: dict[str, Any] = json.loads(content)
    if raw["id"] != "meihua_hko_solar_dates_v1" or raw["version"] != "1.0.0":
        raise ValueError("Unknown Mei Hua solar-date reference profile")
    if raw["source_scope"]["comparison_offset"] != "+08:00":
        raise ValueError("The reference uses fixed UTC+08 date labels")
    if set(raw["years"]) != {str(y) for y in range(1901, 2101)}:
        raise ValueError("Retain all200 published HKO years")
    for year, entry in raw["years"].items():
        if set(entry["terms"]) != _TERMS:
            raise ValueError("Retain all24 published solar-term dates per year")
        if any(
            date.fromisoformat(value).year != int(year)
            for value in entry["terms"].values()
        ):
            raise ValueError("Published solar dates must retain their source year")
    named = {(e["year"], e["term"]) for e in raw["publisher_named_events"]}
    if named != {(2021, "冬至"), (2051, "春分"), (2083, "立春"), (2084, "春分")}:
        raise ValueError(
            "Retain the four named solar events without adding moon episodes"
        )
    return raw, hashlib.sha256(content).hexdigest()


def _text(record: Mapping[str, Any], key: str) -> str | None:
    value = record.get(key)
    return value if isinstance(value, str) else None


def parse_solar_reference_datetime(value: str) -> datetime:
    """Use the declared Meihua profile, retaining other native accepted forms.

    The exact-microsecond profile handles UTC Z/basic/week labels uniformly.
    The shared fallback retains the native grammar and repairs its known
    zero-whole-second fractional-offset collapse; no timezone is guessed.
    """
    try:
        return parse_meihua_clock_label(value)
    except ValueError:
        return datetime_fromisoformat_preserving_offset(value)


def compare_solar_term_date(term: Any, *, fact_path: str) -> dict[str, Any]:
    """Compare one supplied aware instant; never infer offset from a day label.

    UTC+08 is the declared fixed comparison convention, not a reconstruction
    of historical legal clocks. The caller's local date is not the reference
    day. Historical UT1 and assumed future UTC conventions remain those of
    the actual returned term; this function does not adjudicate them.
    """
    profile, _ = _profile()
    term = term if isinstance(term, Mapping) else {}
    details = term.get("solar_model_details")
    details = details if isinstance(details, Mapping) else {}
    actual = _text(term, "datetime_with_offset")
    result: dict[str, Any] = {
        "event_name": _text(term, "name"),
        "fact_path": fact_path,
        "actual_datetime_with_offset": actual,
        "actual_resolution_provider": _text(term, "resolution_provider"),
        "actual_ephemeris_model": _text(term, "ephemeris_model"),
        "actual_civil_time_method": _text(details, "civil_time_method"),
        "computed_datetime_at_reference_offset": None,
        "computed_date": None,
        "published_date": None,
        "date_difference_days": None,
        "comparison_status": "actual_instant_unavailable",
        "source": None,
        "publisher_named_near_midnight": None,
    }
    if actual is None:
        return result
    try:
        moment = parse_solar_reference_datetime(actual)
        if moment.utcoffset() is None:
            return result
        at_reference = moment.astimezone(_REFERENCE_OFFSET)
    except (ValueError, OverflowError):
        return result
    result.update(
        computed_datetime_at_reference_offset=at_reference.isoformat(),
        computed_date=at_reference.date().isoformat(),
    )
    entry = profile["years"].get(str(at_reference.year))
    if entry is None:
        result["comparison_status"] = "outside_published_year_range"
        return result
    published = entry["terms"].get(result["event_name"])
    if published is None:
        result["comparison_status"] = "term_not_in_reference"
        return result
    difference = (at_reference.date() - date.fromisoformat(published)).days
    result.update(
        published_date=published,
        date_difference_days=difference,
        comparison_status=(
            "published_date_match" if difference == 0 else "published_date_disagreement"
        ),
        source=deepcopy(entry["source"]),
        publisher_named_near_midnight=any(
            e["year"] == at_reference.year and e["term"] == result["event_name"]
            for e in profile["publisher_named_events"]
        ),
    )
    return result


def solar_term_date_reference(calendar_context: Mapping[str, Any]) -> dict[str, Any]:
    """Compare the returned adjacent terms and the actual month anchors."""
    profile, loaded_sha = _profile()
    boundary = calendar_context.get("bazi_month_boundary")
    boundary = boundary if isinstance(boundary, Mapping) else {}
    selected = [
        (
            calendar_context.get("current_solar_term"),
            "calendar_context.current_solar_term",
        ),
        (calendar_context.get("next_solar_term"), "calendar_context.next_solar_term"),
        (boundary.get("start_term"), "calendar_context.bazi_month_boundary.start_term"),
        (boundary.get("next_term"), "calendar_context.bazi_month_boundary.next_term"),
    ]
    events = [compare_solar_term_date(term, fact_path=path) for term, path in selected]
    compared = [e for e in events if e["comparison_status"] in _COMPARED]
    groups: dict[tuple[str, str], set[str]] = {}
    for event in compared:
        key = (event["published_date"][:4], event["event_name"])
        groups.setdefault(key, set()).add(
            event["computed_datetime_at_reference_offset"]
        )
    inconsistent = any(len(instants) > 1 for instants in groups.values())
    disagreements = {
        (e["published_date"][:4], e["event_name"])
        for e in compared
        if e["comparison_status"] == "published_date_disagreement"
    }
    named = {
        (e["published_date"][:4], e["event_name"])
        for e in compared
        if e["publisher_named_near_midnight"] is True
    }
    complete = len(compared) == len(selected)
    return {
        "profile_id": profile["id"],
        "version": profile["version"],
        "loaded_profile_sha256": loaded_sha,
        "comparison_offset": "+08:00",
        "source_scope": deepcopy(profile["source_scope"]),
        "time_basis_source": deepcopy(profile["time_basis_source"]),
        "caveat_source": deepcopy(profile["caveat_source"]),
        "selected_record_paths": [path for _, path in selected],
        "events": events,
        "status": (
            "inconsistent_returned_instants"
            if inconsistent
            else (
                "published_date_disagreement"
                if disagreements
                else (
                    "published_dates_match"
                    if complete
                    else "partially_compared" if compared else "not_compared"
                )
            )
        ),
        "compared_record_count": len(compared),
        "compared_reference_event_count": len(groups),
        "date_disagreement_count": len(disagreements),
        "publisher_named_event_count": len(named),
        "all_selected_records_compared": complete,
        "same_reference_event_has_multiple_instants": inconsistent,
        "source_uncertainty_interval_seconds": None,
        "original_solar_instants_retained": True,
        "original_month_branch_retained": True,
        "original_lunar_seed_retained": True,
        "alternate_event_time_inferred": False,
        "published_date_match_certifies_exactness": False,
        "exact_astronomical_accuracy_established": False,
        "predictive_efficacy_established": False,
    }


def solar_reference_notice(reference: Mapping[str, Any]) -> str | None:
    """Explain only an actual disagreement or an explicitly named source note."""
    if reference["same_reference_event_has_multiple_instants"]:
        return (
            "返回的同年同名节气记录含不同交节时刻；当前资料不足以确定一个一致的"
            "月令时间依据，须复核相关时刻来源。"
        )
    parts = []
    seen = set()
    for event in reference["events"]:
        identity = (
            event["event_name"],
            event["computed_date"],
            event["published_date"],
        )
        if (
            event["comparison_status"] == "published_date_disagreement"
            and identity not in seen
        ):
            seen.add(identity)
            parts.append(
                f"{event['event_name']}计算日期{event['computed_date']}，"
                f"香港天文台固定年表标为{event['published_date']}。"
            )
    named = list(
        dict.fromkeys(
            e["published_date"][:4] + "年" + e["event_name"]
            for e in reference["events"]
            if e["publisher_named_near_midnight"] is True
        )
    )
    if named:
        parts.append(
            "香港天文台固定说明点名" + "、".join(named) + "为接近午夜的日期复核案例。"
        )
    if not parts:
        return None
    return (
        "节气日期对照（固定UTC+08）："
        + "".join(parts)
        + "本次仍按实际返回的交节时刻确定月令，起卦数沿用已返回的农历资料；"
        "日标签对照未产生另一交节时刻。"
    )

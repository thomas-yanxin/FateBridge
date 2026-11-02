"""Bind complete Ren results to the actual request, before any projection.

This repeats the domain's seed and small input-derived metadata checks, not
board construction. It does not certify astronomy, a classical reading or a
prediction, and never changes the returned object or fills missing user data.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel

TOOLS = frozenset({"liureng_gods", "liureng_runyear", "jinkou", "sanshiunited"})
MISSING = object()


def _get(value: Any, path: str) -> Any:
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return MISSING
        value = value[part]
    return value


def _same(value: Any, path: str, expected: Any) -> None:
    actual = _get(value, path)
    if actual is MISSING or json.dumps(
        actual, sort_keys=True, allow_nan=False
    ) != json.dumps(expected, sort_keys=True, allow_nan=False):
        raise ValueError("完整六壬结果的" + path + "与本次请求不符")


def _mapping(actual: Any, expected: dict[str, Any], prefix: str = "") -> None:
    for key, value in expected.items():
        path = prefix + key
        if isinstance(value, dict) and value:
            _mapping(actual, value, path + ".")
        else:
            _same(actual, path, value)


def _gender(holder: Any, path: str, expected: Any) -> None:
    from fatebridge.utils.birth_input import normalize_gender

    actual = _get(holder, path)
    if actual is MISSING or normalize_gender(actual) != normalize_gender(expected):
        raise ValueError("完整六壬结果的性别来源与本次请求不符")


def require_request_binding(
    key: str, result: dict[str, Any], request: BaseModel
) -> None:
    """Validate an unprojected success against independently bound inputs."""
    if key not in TOOLS:
        return
    from fatebridge.application.bindings import _build_person
    from fatebridge.core.almanac import get_lunar_context, localize_datetime
    from fatebridge.core.local_techniques.chart import (
        _build_metaphysics_analysis_context,
        _build_metaphysics_seed,
        _normalize_date_text,
        _normalize_time_text,
    )
    from fatebridge.core.metaphysics.jinkou_natal_course import natal_course_metadata
    from fatebridge.core.metaphysics.jinkou_year_fate import ordinal_year_fate
    from fatebridge.core.metaphysics.liureng import (
        _liureng_month_general_for_term,
        build_liureng_runyear,
    )
    from fatebridge.core.metaphysics.ren_calendar import (
        resolve_runyear_birth_clock,
        resolve_runyear_birth_zone,
    )
    from fatebridge.core.metaphysics.ren_diurnal import resolve_diurnal
    from fatebridge.services.metaphysics import (
        _analysis_context_payload,
        _build_analysis_seed,
    )
    from fatebridge.utils.civil_clock import (
        format_utc_offset,
        resolve_civil_clock,
        utc_instant,
    )
    from fatebridge.utils.formatting import create_pillar_dict
    from fatebridge.utils.places import DEFAULT_BIRTH_TIMEZONE

    data = request.model_dump()
    gender: Any
    if key == "sanshiunited":
        normalized = {
            "date": _normalize_date_text(data["date"]),
            "time": _normalize_time_text(data["time"]),
            "zone": data.get("zone") or DEFAULT_BIRTH_TIMEZONE,
            "lat": data.get("lat"),
            "lon": data.get("lon"),
            "gpsLat": data.get("gps_lat"),
            "gpsLon": data.get("gps_lon"),
            "qimen_options": data.get("qimen_options") or {},
            "taiyi_options": data.get("taiyi_options") or {},
            "liureng_yue": data.get("liureng_yue"),
            "liureng_is_diurnal": data.get("liureng_is_diurnal"),
            "liureng_guiren_profile": data["liureng_guiren_profile"],
            "use_true_solar_time": data["use_true_solar_time"],
        }
        _same(result, "input_normalized", normalized)
        seed = _build_metaphysics_seed(
            date_text=normalized["date"],
            time_text=normalized["time"],
            timezone_name=normalized["zone"],
            lat=data.get("lat"),
            lon=data.get("lon"),
            gps_lat=data.get("gps_lat"),
            gps_lon=data.get("gps_lon"),
            use_true_solar_time=data["use_true_solar_time"],
        )
        context = _build_metaphysics_analysis_context(seed)
        ren_result = _get(result, "subresults.liureng_gods")
        profile = data["liureng_guiren_profile"]
        explicit = data.get("liureng_is_diurnal")
        override = data.get("liureng_yue")
        gender = "未知"
        offset = None
        _mapping(result, context, "analysis_context.")
    else:
        seed = _build_analysis_seed(
            **{
                name: data[name]
                for name in (
                    "analysis_year",
                    "analysis_month",
                    "analysis_day",
                    "analysis_hour",
                    "analysis_minute",
                    "analysis_second",
                    "analysis_timezone",
                    "analysis_utc_offset",
                    "analysis_longitude",
                    "use_true_solar_time",
                )
            },
            # person_invoke currently does not forward this service flag.
            true_solar_explicit=(
                True
                if key == "liureng_runyear"
                else "use_true_solar_time" in request.model_fields_set
            ),
        )
        context = _analysis_context_payload(seed)
        ren_result = result
        profile = data["guiren_profile"]
        explicit = data.get("is_diurnal")
        override = None
        gender = data.get("gender")
        offset = data.get("analysis_utc_offset")

    if not isinstance(ren_result, dict):
        raise ValueError("本次请求缺少完整六壬计算对象")
    _mapping(ren_result, context, "analysis_context.")
    _mapping(ren_result, create_pillar_dict(seed.pillars), "four_pillars.")
    civil = localize_datetime(seed.input_datetime, seed.timezone)
    clock = seed.corrected_datetime
    policy = dict(
        civil_datetime=civil.isoformat(),
        civil_instant_utc=utc_instant(civil).isoformat(),
        day_hour_clock="apparent_solar" if seed.applied_true_solar else "civil",
        corrected_clock=(
            clock.replace(tzinfo=None).isoformat()
            if seed.applied_true_solar
            else clock.isoformat()
        ),
        effective_day_date=(
            clock.date() + timedelta(days=int(clock.hour == 23))
        ).isoformat(),
        effective_day_ganzhi="".join(seed.pillars["day"]),
        month_general_override=override,
    )
    _mapping(ren_result, policy, "calendar_context.ren_calendar_policy.")
    if offset is None:
        if (
            _get(ren_result, "calendar_context.ren_calendar_policy").get(
                "civil_clock_resolution"
            )
            is not None
        ):
            raise ValueError("不能把未指定的起课UTC偏移改称显式选择")
    else:
        resolved = resolve_civil_clock(
            civil.replace(tzinfo=None, fold=0), seed.timezone, offset
        )
        resolved_offset = resolved.utcoffset()
        if resolved_offset is None:
            raise ValueError("起课UTC偏移未能解析为实际时刻")
        _mapping(
            ren_result,
            dict(
                method="explicit_offset_checked_against_analysis_timezone",
                timezone=seed.timezone,
                input_utc_offset=offset,
                resolved_utc_offset=format_utc_offset(resolved_offset),
                wall_datetime=resolved.replace(tzinfo=None).isoformat(),
                was_ambiguous=(
                    resolved.replace(fold=0).utcoffset()
                    != resolved.replace(fold=1).utcoffset()
                ),
                fold=resolved.fold,
                instant_utc=utc_instant(resolved).isoformat(),
            ),
            "calendar_context.ren_calendar_policy.civil_clock_resolution.",
        )
    board = _get(ren_result, "liureng")
    _mapping(board, policy, "calendar_policy.")
    _same(board, "meta.guiren_profile", profile)
    hour = seed.pillars["hour"][1]
    _mapping(board, resolve_diurnal(hour, explicit), "meta.diurnal_evidence.")
    _gender(board, "meta.questioner_gender", gender)
    current_term = seed.calendar_context["current_solar_term"]["name"]
    general = override or _liureng_month_general_for_term(current_term)
    _same(board, "month_general.branch", general)
    _same(
        board,
        "meta.month_general_basis",
        "explicit_override" if override is not None else "中气换将",
    )

    if key == "jinkou":
        jinkou = _get(result, "jinkou")
        _mapping(jinkou, policy, "calendar_policy.")
        _same(jinkou, "overview.di_fen", data.get("di_fen") or hour)
        _same(
            jinkou,
            "overview.di_fen_source",
            (
                "explicit"
                if data.get("di_fen")
                else "hour_branch_fallback_not_observed_direction"
            ),
        )
        _gender(jinkou, "overview.gender", gender)
        _mapping(jinkou, resolve_diurnal(hour, explicit), "overview.diurnal_evidence.")
        natal = natal_course_metadata(
            data.get("birth_year_ganzhi"), data.get("natal_branch")
        )
        annual = ordinal_year_fate(
            birth_year_ganzhi=data.get("birth_year_ganzhi"),
            age=data.get("year_fate_age"),
            gender=gender,
        )
        annual["natal_branch"] = natal["natal_branch"]
        annual["natal_branch_source"] = natal["natal_branch_source"]
        _mapping(jinkou, natal, "natal_course.")
        _mapping(jinkou, annual, "year_fate.")
        for wrapper in ("natal_course", "year_fate"):
            child = _get(jinkou, wrapper + ".course")
            if child is not None:
                _mapping(child, policy, "calendar_policy.")
                _mapping(
                    child, resolve_diurnal(hour, explicit), "overview.diurnal_evidence."
                )
                _gender(child, "overview.gender", gender)

    if key == "liureng_runyear":
        person = _build_person(
            data,
            true_solar_explicit="use_true_solar_time" in request.model_fields_set,
            supplied_fields=request.model_fields_set,
        )
        zone, zone_source = resolve_runyear_birth_zone(
            person.birth_timezone, person.birth_place, person.birth_longitude
        )
        birth, birth_clock = resolve_runyear_birth_clock(
            datetime(
                person.birth_year,
                person.birth_month,
                person.birth_day,
                person.birth_hour,
                person.birth_minute,
                person.birth_second or 0,
            ),
            zone,
            data.get("birth_utc_offset"),
            recorded_offset=person.birth_utc_offset,
        )
        birth_clock.update(zone_source)
        _mapping(result, birth_clock, "runyear.birth_civil_clock.")
        if utc_instant(civil) < utc_instant(birth):
            raise ValueError("成功行年结果不能绑定到出生前的分析瞬间")
        lunar = get_lunar_context(birth, timezone_name=zone)
        if lunar is None:
            raise ValueError("成功行年结果缺少请求出生日期的农历年")
        birth_lunar_year = lunar.get("year")
        if type(birth_lunar_year) is not int:
            raise ValueError("成功行年结果的出生农历年不是有效整数")
        expected = build_liureng_runyear(
            seed,
            gender=person.gender or "未知",
            birth_year=person.birth_year,
            birth_lunar_year=birth_lunar_year,
            age_reference_timezone=zone,
        )
        _mapping(result, expected, "runyear.")

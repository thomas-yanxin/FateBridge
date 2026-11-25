"""Bind Ren results to the submitted civil clock and rule selections."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from fatebridge.application.bindings import _build_person
from fatebridge.application.tool_spec import ServiceResult
from fatebridge.core.almanac import localize_datetime
from fatebridge.core.metaphysics.jinkou_year_fate import confirmed_natal_branch
from fatebridge.core.metaphysics.ren_diurnal import resolve_diurnal
from fatebridge.core.requests.divination import SanShiUnitedRequest
from fatebridge.core.requests.metaphysics import (
    JinkouAnalysisRequest,
    LiuRengGodsRequest,
    LiuRengRunyearRequest,
)
from fatebridge.utils.birth_input import normalize_gender
from fatebridge.utils.civil_clock import resolve_civil_clock
from fatebridge.utils.civil_time import utc_calendar
from fatebridge.utils.json_values import same_value
from fatebridge.utils.places import DEFAULT_BIRTH_TIMEZONE

TOOLS = frozenset({"liureng_gods", "liureng_runyear", "jinkou", "sanshiunited"})
MISSING = object()


def _get(value: Any, path: str) -> Any:
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return MISSING
        else:
            pass
        value = value[part]
    return value


def _same(value: Any, path: str, expected: Any) -> None:
    actual = _get(value, path)
    if actual is MISSING or not same_value(actual, expected):
        raise ValueError("完整六壬结果的" + path + "与本次请求不符")
    else:
        pass


def _mapping(actual: Any, expected: dict[str, Any], prefix: str = "") -> None:
    for key, value in expected.items():
        path = prefix + key
        if isinstance(value, dict) and value:
            _mapping(actual, value, path + ".")
        else:
            _same(actual, path, value)


def _gender(holder: Any, path: str, expected: str | None) -> None:
    actual = _get(holder, path)
    if actual is MISSING or normalize_gender(actual) != normalize_gender(expected):
        raise ValueError("完整六壬结果的性别来源与本次请求不符")
    else:
        pass


def require_request_binding(
    key: str, result: ServiceResult, request: BaseModel
) -> None:
    """Check request facts against the same run's recorded operands."""
    if key not in TOOLS:
        return
    else:
        pass
    # note (catalog): These engine helpers load only when validating a Ren result.
    from fatebridge.core.local_techniques.chart import (
        _normalize_date_text,
        _normalize_time_text,
        _resolve_coordinates,
        parse_local_datetime,
    )
    from fatebridge.core.metaphysics.liureng import _liureng_month_general_for_term
    from fatebridge.core.metaphysics.ren_calendar import (
        resolve_runyear_birth_clock,
        resolve_runyear_birth_zone,
    )

    gender: str | None
    if key == "sanshiunited":
        assert isinstance(request, SanShiUnitedRequest)
        date_text = _normalize_date_text(request.date)
        time_text = _normalize_time_text(request.time)
        zone = request.zone or DEFAULT_BIRTH_TIMEZONE
        serialized_options = request.model_dump(
            include={"qimen_options", "taiyi_options"}
        )
        normalized = {
            "date": date_text,
            "time": time_text,
            "zone": zone,
            "lat": request.lat,
            "lon": request.lon,
            "gpsLat": request.gps_lat,
            "gpsLon": request.gps_lon,
            "qimen_options": serialized_options["qimen_options"] or {},
            "taiyi_options": serialized_options["taiyi_options"] or {},
            "liureng_yue": request.liureng_yue,
            "liureng_is_diurnal": request.liureng_is_diurnal,
            "liureng_guiren_profile": request.liureng_guiren_profile,
            "use_true_solar_time": request.use_true_solar_time,
        }
        _same(result, "input_normalized", normalized)
        civil = parse_local_datetime(date_text, time_text, zone, validate_wall=True)
        longitude: float | None
        _, longitude = _resolve_coordinates(
            lat=request.lat,
            lon=request.lon,
            gps_lat=request.gps_lat,
            gps_lon=request.gps_lon,
        )
        applied_solar = request.use_true_solar_time
        ren_result = _get(result, "subresults.liureng_gods")
        profile = request.liureng_guiren_profile
        explicit = request.liureng_is_diurnal
        override = request.liureng_yue
        gender = "未知"
        offset = None
        _same(result, "analysis_context", _get(ren_result, "analysis_context"))
    else:
        assert isinstance(request, (LiuRengGodsRequest, LiuRengRunyearRequest))
        zone = request.analysis_timezone or DEFAULT_BIRTH_TIMEZONE
        offset = request.analysis_utc_offset
        civil = resolve_civil_clock(
            datetime(
                request.analysis_year,
                request.analysis_month,
                request.analysis_day,
                request.analysis_hour,
                request.analysis_minute,
                request.analysis_second,
            ),
            zone,
            offset,
        )
        longitude = request.analysis_longitude
        if (
            request.use_true_solar_time
            and longitude is None
            and (
                key == "liureng_runyear"
                or "use_true_solar_time" in request.model_fields_set
            )
        ):
            raise ValueError("显式真太阳时请求需要经度")
        else:
            pass
        applied_solar = request.use_true_solar_time and longitude is not None
        ren_result = result
        profile = request.guiren_profile
        explicit = request.is_diurnal
        override = None
        gender = request.gender
    _mapping(
        ren_result,
        dict(
            input_datetime=civil.strftime("%Y-%m-%d %H:%M:%S"),
            timezone=zone,
            longitude=longitude,
            time_algorithm="真太阳时" if applied_solar else "直接时间",
        ),
        "analysis_context.",
    )
    calendar = _get(ren_result, "calendar_context")
    policy = dict(
        civil_datetime=civil.isoformat(),
        civil_instant_utc=utc_calendar(civil).isoformat(),
        day_hour_clock="apparent_solar" if applied_solar else "civil",
        month_general_override=override,
    )
    _mapping(calendar, policy, "ren_calendar_policy.")
    clock = calendar["ren_calendar_policy"].get("civil_clock_resolution")
    if offset is None:
        if clock is not None:
            raise ValueError("不能把未指定的起课UTC偏移改称显式选择")
        else:
            pass
    else:
        _mapping(
            clock,
            dict(
                input_utc_offset=offset,
                fold=civil.fold,
                instant_utc=policy["civil_instant_utc"],
            ),
        )
    board = _get(result, "liureng")
    _mapping(board, policy, "calendar_policy.")
    _same(board, "meta.guiren_profile", profile)
    hour = ren_result["four_pillars"]["hour"]["branch"]
    diurnal = resolve_diurnal(hour, explicit)
    _mapping(board, diurnal, "meta.diurnal_evidence.")
    _gender(board, "meta.questioner_gender", gender)
    current_term = calendar["current_solar_term"]["name"]
    general = override or _liureng_month_general_for_term(current_term)
    _same(board, "month_general.branch", general)
    _same(
        board,
        "meta.month_general_basis",
        "explicit_override" if override is not None else "中气换将",
    )

    if key == "jinkou":
        assert isinstance(request, JinkouAnalysisRequest)
        jinkou = _get(result, "jinkou")
        _mapping(jinkou, policy, "calendar_policy.")
        _same(jinkou, "overview.di_fen", request.di_fen or hour)
        _same(
            jinkou,
            "overview.di_fen_source",
            (
                "explicit"
                if request.di_fen
                else "hour_branch_fallback_not_observed_direction"
            ),
        )
        _gender(jinkou, "overview.gender", gender)
        _mapping(jinkou, diurnal, "overview.diurnal_evidence.")
        birth_ganzhi = request.birth_year_ganzhi
        natal_branch = request.natal_branch
        age = request.year_fate_age
        natal = dict(
            birth_year_ganzhi=birth_ganzhi,
            natal_branch=confirmed_natal_branch(birth_ganzhi, natal_branch, age),
            natal_branch_source=(
                "explicit_natal_branch"
                if natal_branch is not None
                else (
                    "explicit_birth_year_ganzhi"
                    if birth_ganzhi is not None
                    else "missing"
                )
            ),
        )
        _mapping(jinkou, natal, "natal_course.")
        _mapping(jinkou, dict(natal, age_ordinal=age), "year_fate.")
        _gender(jinkou, "year_fate.gender", gender)
        for wrapper in ("natal_course", "year_fate"):
            child = _get(jinkou, wrapper + ".course")
            if child is not None:
                _mapping(child, policy, "calendar_policy.")
                _mapping(child, diurnal, "overview.diurnal_evidence.")
                _gender(child, "overview.gender", gender)
            else:
                pass
    elif key == "liureng_runyear":
        assert isinstance(request, LiuRengRunyearRequest)
        person = _build_person(
            request.model_dump(),
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
            request.birth_utc_offset,
            recorded_offset=person.birth_utc_offset,
        )
        birth_clock.update(zone_source)
        _mapping(result, birth_clock, "runyear.birth_civil_clock.")
        if (
            utc_calendar(civil).julian_day_exact()
            < utc_calendar(birth).julian_day_exact()
        ):
            raise ValueError("成功行年结果不能绑定到出生前的分析瞬间")
        else:
            pass
        _gender(result, "runyear.gender", person.gender)
        analysis_civil = localize_datetime(civil, zone)
        years = result["runyear"]["age_calendar"]
        birth_year = years["birth_lunar_year"]
        analysis_year = years["analysis_lunar_year"]
        age = analysis_year - birth_year + 1
        if (
            birth_year not in (birth.year - 1, birth.year)
            or analysis_year not in (analysis_civil.year - 1, analysis_civil.year)
            or age < 1
        ):
            raise ValueError("行年农历年份与同次民用年份范围不符")
        else:
            pass
        _mapping(
            result["runyear"],
            dict(
                age=age,
                birth_lunar_year=birth_year,
                age_calendar=dict(
                    timezone=zone, analysis_civil_datetime=analysis_civil.isoformat()
                ),
            ),
        )
    else:
        pass

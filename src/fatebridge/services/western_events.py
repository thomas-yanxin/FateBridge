"""Cast and render Western ingress and planetary return charts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import JsonValue

from fatebridge.core.astro.astrology_events import (
    CARDINAL_INGRESS_LABELS,
    CARDINAL_INGRESSES,
    RETURN_BODIES,
    planet_motion_at_utc,
    resolve_cardinal_ingress,
    resolve_planet_returns,
)
from fatebridge.core.astro.physical_epoch import (
    PhysicalEpoch,
    local_leap_second_label,
    utc_representation,
)
from fatebridge.core.predictive._common import (
    build_analysis_datetime,
    build_predictive_birth_info,
    build_subject,
    extract_reference_points,
    longitude_to_point_dict,
    planet_label,
)
from fatebridge.services.snapshot_builders import (
    format_snapshot_json,
)
from fatebridge.services.snapshot_builders import (
    render_snapshot_text as _render_snapshot_text,
)
from fatebridge.utils.civil_time import ZonedCalendar, utc_calendar
from fatebridge.utils.errors import handle_calculation_error
from fatebridge.utils.house_systems import house_system_fields, normalize_house_system
from fatebridge.utils.timezones import is_unspecified_local_time, parse_timezone_name


def calculate_mundane(
    *,
    year: int,
    ingress_term: Literal["春分", "夏至", "秋分", "冬至"] = "春分",
    longitude: float,
    latitude: float,
    timezone_name: str = "+08:00",
    name: str | None = None,
    house_system: str = "P",
    zodiac_type: str = "Tropic",
    render_snapshot: bool = True,
) -> dict[str, Any]:
    """在某年某节气（春分/夏至/秋分/冬至）的精确入宫时刻排世俗盘。"""
    label = "世俗入宫盘"
    try:
        house_system = normalize_house_system(house_system)
        ingress = resolve_cardinal_ingress(year, ingress_term)
        epoch = PhysicalEpoch.from_tt(ingress.tt)
        ingress_utc = epoch.require_datetime()
        utc_label = ingress_utc.isoformat()

        subject = build_subject(
            name=name or f"{year}{ingress_term}世俗盘",
            physical_epoch=epoch,
            longitude=longitude,
            latitude=latitude,
            timezone_name=timezone_name,
            house_system=house_system,
            zodiac_type=zodiac_type,
        )
        local_label = subject.iso_formatted_local_datetime
        points = extract_reference_points(subject)
        calculation_basis = subject.calculation_basis
        house_fields = house_system_fields(house_system)

        context: dict[str, JsonValue] = {
            "tool": label,
            "year": year,
            "ingress_term": ingress_term,
            "ingress_term_label": CARDINAL_INGRESS_LABELS[ingress_term],
            "ingress_longitude": CARDINAL_INGRESSES[ingress_term]["longitude"],
            "ingress_datetime_utc": utc_label,
            "ingress_datetime_local": local_label,
            "location": {
                "longitude": longitude,
                "latitude": latitude,
                "timezone": timezone_name,
            },
            "house_system": house_fields["house_system"],
            "house_system_code": house_fields["house_system_code"],
            "house_system_label_zh": house_fields["house_system_label_zh"],
            "zodiac_type": zodiac_type,
            "engine": calculation_basis["engine_backend"],
        }
        payload: dict[str, JsonValue] = {
            "calculation_basis": calculation_basis,
            "system": "mundane_ingress",
            "system_label": "世俗入宫盘",
            "ingress_term": ingress_term,
            "ingress_datetime_utc": utc_label,
            "ingress_datetime_local": local_label,
            "ascendant": points["ascendant"],
            "medium_coeli": points["medium_coeli"],
            "points": {**points},
        }
        if local_label is None:
            clock_summary = f"{ingress_utc:%Y-%m-%d %H:%M} UTC（当地钟时未定义）"
        else:
            clock_summary = f"{local_label[:16].replace('T', ' ')}（当地）"
        summary = (
            f"{year} 年{ingress_term}入宫盘：入宫时刻 {clock_summary}，"
            f"上升 {points['ascendant']['sign_label']}。"
        )
        result: dict[str, JsonValue] = {
            "analysis_type": "西占世俗入宫盘",
            "engine": calculation_basis["engine_backend"],
            "analysis_context": context,
            "mundane": payload,
            "summary": summary,
        }
        if render_snapshot:
            result["snapshot_text"] = _render_snapshot_text(
                [
                    ("起盘信息", format_snapshot_json(context)),
                    ("入宫盘星与角", format_snapshot_json(payload)),
                ]
            )
        return result
    except Exception as exc:
        return handle_calculation_error(exc, label)


def calculate_extrareturns(
    *,
    analysis_year: int | None = None,
    analysis_month: int | None = None,
    analysis_day: int | None = None,
    house_system: str = "P",
    zodiac_type: str = "Tropic",
    render_snapshot: bool = True,
    **birth_kwargs: Any,
) -> dict[str, Any]:
    """求土星 / 木星 / 月交点回到本命黄经的最近一次与下一次返照时刻。"""
    label = "多重回归"
    try:
        zodiac = zodiac_type.strip().casefold()
        if zodiac not in {"tropic", "tropical", "sidereal"}:
            raise ValueError(
                "Unsupported zodiac_type; use Tropic, Tropical or Sidereal"
            )
        sidereal = zodiac == "sidereal"
        house_system = normalize_house_system(house_system)
        birth_info = build_predictive_birth_info(
            birth_year=birth_kwargs["birth_year"],
            birth_month=birth_kwargs["birth_month"],
            birth_day=birth_kwargs["birth_day"],
            birth_hour=birth_kwargs["birth_hour"],
            birth_minute=birth_kwargs.get("birth_minute", 0),
            birth_timezone=birth_kwargs.get("birth_timezone"),
            birth_longitude=birth_kwargs["birth_longitude"],
            birth_latitude=birth_kwargs["birth_latitude"],
            name=birth_kwargs.get("name"),
            birth_place=birth_kwargs.get("birth_place"),
        )
        analysis_local = build_analysis_datetime(
            birth_info,
            analysis_year=analysis_year,
            analysis_month=analysis_month,
            analysis_day=analysis_day,
        )
        reference_utc = utc_calendar(analysis_local)
        local_tz = parse_timezone_name(birth_info.timezone)

        returns: list[JsonValue] = []
        return_summaries: list[str] = []
        for body_name, spec in RETURN_BODIES.items():
            planet_id = int(spec["planet_id"])  # type: ignore[call-overload]
            try:
                natal_motion = planet_motion_at_utc(
                    planet_id,
                    birth_info.utc_calendar,
                    sidereal=sidereal,
                )
                natal_longitude = natal_motion[0]
                resolved = resolve_planet_returns(
                    planet_id,
                    natal_longitude,
                    period_days=float(spec["period_days"]),  # type: ignore[arg-type]
                    reference_utc=reference_utc,
                    past=1,
                    future=1,
                    sidereal=sidereal,
                    natal_motion=natal_motion,
                )
            except Exception as body_err:
                if body_name == "Chiron":
                    returns.append(
                        {
                            "body": body_name,
                            "body_label": "凯龙星",
                            "status": "unavailable",
                            "unavailable_reason": str(body_err),
                            "natal_longitude": None,
                            "most_recent_return": None,
                            "next_return": None,
                        }
                    )
                    continue
                raise
            most_recent = resolved.past[-1] if resolved.past else None
            upcoming = resolved.future[0] if resolved.future else None
            return_moments: dict[str, JsonValue] = {}
            next_date = "—"
            for key, event in (
                ("most_recent_return", most_recent),
                ("next_return", upcoming),
            ):
                if event is None:
                    return_moments[key] = None
                    continue
                moment, utc_label = event.utc_datetime, event.utc_label
                local_label = None
                if moment is not None:
                    utc_label = moment.isoformat()
                if utc_label is not None:
                    if event.utc_is_leap_second:
                        local_label = local_leap_second_label(utc_label, local_tz)
                    else:
                        calendar = (
                            utc_calendar(moment)
                            if moment is not None
                            else ZonedCalendar.from_isoformat(utc_label).utc
                        )
                        local = ZonedCalendar(calendar, local_tz)
                        if not is_unspecified_local_time(local.rule_sample()):
                            local_label = local.isoformat()
                event_record: dict[str, JsonValue] = {
                    "datetime_utc": utc_label,
                    "datetime_local": local_label,
                }
                if moment is None:
                    event_record["julian_day_tt"] = event.tt.as_float()
                    event_record["utc_representation"] = utc_representation(
                        utc_label, moment, event.utc_is_leap_second
                    )
                return_moments[key] = event_record
                if key == "next_return":
                    if local_label is not None:
                        next_date = local_label.partition("T")[0]
                    elif utc_label is not None:
                        next_date = f"{utc_label.partition('T')[0]}（UTC）"
                    else:
                        next_date = "UTC 钟面无唯一表示"
            body_label = "凯龙星" if body_name == "Chiron" else planet_label(body_name)
            returns.append(
                {
                    "body": body_name,
                    "body_label": body_label,
                    "natal_longitude": longitude_to_point_dict(
                        body_name, natal_longitude
                    ),
                    **return_moments,
                }
            )
            return_summaries.append(f"{body_label}下次返照 {next_date}")

        house_fields = house_system_fields(house_system)
        context: dict[str, JsonValue] = {
            "tool": label,
            "birth_datetime": birth_info.local_datetime.isoformat(),
            "timezone": birth_info.timezone,
            "reference_datetime": analysis_local.isoformat(),
            "house_system": house_fields["house_system"],
            "house_system_code": house_fields["house_system_code"],
            "house_system_label_zh": house_fields["house_system_label_zh"],
            "zodiac_type": zodiac_type,
            "engine": "fatebridge-offline",
        }
        payload: dict[str, JsonValue] = {
            "system": "extra_returns",
            "system_label": "多重回归（土/木/火/金/水/月交/凯龙返照）",
            "reference_datetime": analysis_local.isoformat(),
            "returns": returns,
        }
        summary = "多重回归：" + "；".join(return_summaries)
        result: dict[str, JsonValue] = {
            "analysis_type": "西占多重回归",
            "engine": "fatebridge-offline",
            "analysis_context": context,
            "extrareturns": payload,
            "summary": summary,
        }
        if render_snapshot:
            result["snapshot_text"] = _render_snapshot_text(
                [
                    ("起盘信息", format_snapshot_json(context)),
                    ("返照时刻", format_snapshot_json(returns)),
                ]
            )
        return result
    except Exception as exc:
        return handle_calculation_error(exc, label)

"""
Service surfaces for the western *event* techniques (世俗入宫盘 / 多重回归).

These differ from the lifespan family: they first solve an astronomical moment
(a cardinal solar ingress, or a planetary return to its natal longitude) and
then read the sky at that instant. Moment-solving lives in
:mod:`fatebridge.core.astrology_events`; chart casting and rendering live here.
"""

from __future__ import annotations

import json
from datetime import timezone
from typing import Any, Dict, List, Optional

from fatebridge.core.astrology_events import (
    CARDINAL_INGRESS_LABELS,
    CARDINAL_INGRESSES,
    RETURN_BODIES,
    find_cardinal_ingress_utc,
    find_planet_returns,
    planet_longitude_at_utc,
)
from fatebridge.core.predictive._common import (
    build_analysis_datetime,
    build_natal_subject,
    build_predictive_birth_info,
    build_subject,
    extract_reference_points,
    longitude_to_point_dict,
    planet_label,
)
from fatebridge.services.snapshot_builders import (
    render_snapshot_text as _render_snapshot_text,
)
from fatebridge.utils.errors import handle_calculation_error
from fatebridge.utils.house_systems import house_system_fields, normalize_house_system
from fatebridge.utils.timezones import parse_timezone_name


def _json_block(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


# ---------------------------------------------------------------------------
# 世俗入宫盘 (astro_mundane).
# ---------------------------------------------------------------------------


def calculate_mundane(
    *,
    year: int,
    ingress_term: str = "春分",
    longitude: float,
    latitude: float,
    timezone_name: str = "+08:00",
    name: Optional[str] = None,
    house_system: str = "P",
    zodiac_type: str = "Tropic",
) -> Dict[str, Any]:
    """在某年某节气（春分/夏至/秋分/冬至）的精确入宫时刻排世俗盘。"""
    label = "世俗入宫盘"
    try:
        if ingress_term not in CARDINAL_INGRESSES:
            ingress_term = "春分"
        house_system = normalize_house_system(house_system)
        ingress_utc = find_cardinal_ingress_utc(year, ingress_term)
        local_tz = parse_timezone_name(timezone_name)
        ingress_local = ingress_utc.astimezone(local_tz)

        subject = build_subject(
            name=name or f"{year}{ingress_term}世俗盘",
            local_datetime=ingress_local,
            longitude=longitude,
            latitude=latitude,
            timezone_name=timezone_name,
            house_system=house_system,
            zodiac_type=zodiac_type,
        )
        points = extract_reference_points(subject)
        calculation_basis = subject.calculation_basis

        context = {
            "tool": label,
            "year": year,
            "ingress_term": ingress_term,
            "ingress_term_label": CARDINAL_INGRESS_LABELS[ingress_term],
            "ingress_longitude": CARDINAL_INGRESSES[ingress_term]["longitude"],
            "ingress_datetime_utc": ingress_utc.isoformat(),
            "ingress_datetime_local": ingress_local.isoformat(),
            "location": {
                "longitude": longitude,
                "latitude": latitude,
                "timezone": timezone_name,
            },
            **house_system_fields(house_system),
            "zodiac_type": zodiac_type,
            "engine": calculation_basis["engine_backend"],
        }
        payload = {
            "calculation_basis": calculation_basis,
            "system": "mundane_ingress",
            "system_label": "世俗入宫盘",
            "ingress_term": ingress_term,
            "ingress_datetime_utc": ingress_utc.isoformat(),
            "ingress_datetime_local": ingress_local.isoformat(),
            "ascendant": points["ascendant"],
            "medium_coeli": points["medium_coeli"],
            "points": points,
        }
        summary = (
            f"{year} 年{ingress_term}入宫盘：入宫时刻 "
            f"{ingress_local.strftime('%Y-%m-%d %H:%M')}（当地），"
            f"上升 {points['ascendant']['sign_label']}。"
        )
        sections = [
            ("起盘信息", _json_block(context)),
            ("入宫盘星与角", _json_block(payload)),
        ]
        return {
            "analysis_type": "西占世俗入宫盘",
            "engine": calculation_basis["engine_backend"],
            "analysis_context": context,
            "mundane": payload,
            "summary": summary,
            "snapshot_text": _render_snapshot_text(sections),
        }
    except Exception as exc:
        return handle_calculation_error(exc, label)


# ---------------------------------------------------------------------------
# 多重回归 (astro_extrareturns).
# ---------------------------------------------------------------------------


def calculate_extrareturns(
    *,
    analysis_year: Optional[int] = None,
    analysis_month: Optional[int] = None,
    analysis_day: Optional[int] = None,
    house_system: str = "P",
    zodiac_type: str = "Tropic",
    **birth_kwargs: Any,
) -> Dict[str, Any]:
    """求土星 / 木星 / 月交点回到本命黄经的最近一次与下一次返照时刻。"""
    label = "多重回归"
    try:
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
        # build the natal subject so the tool also fails fast if the backend is absent
        build_natal_subject(
            birth_info, house_system=house_system, zodiac_type=zodiac_type
        )

        analysis_local = build_analysis_datetime(
            birth_info,
            analysis_year=analysis_year,
            analysis_month=analysis_month,
            analysis_day=analysis_day,
        )
        reference_utc = analysis_local.astimezone(timezone.utc)
        local_tz = parse_timezone_name(birth_info.timezone)

        returns: List[Dict[str, Any]] = []
        for body_name, spec in RETURN_BODIES.items():
            planet_id = int(spec["planet_id"])  # type: ignore[call-overload]
            natal_longitude = planet_longitude_at_utc(
                planet_id,
                birth_info.require_utc_datetime,
                sidereal=zodiac_type == "Sidereal",
            )
            moments = find_planet_returns(
                planet_id,
                natal_longitude,
                period_days=float(spec["period_days"]),  # type: ignore[arg-type]
                reference_utc=reference_utc,
                past=1,
                future=1,
                sidereal=zodiac_type == "Sidereal",
            )
            most_recent = next(
                (m for m in reversed(moments) if m <= reference_utc), None
            )
            upcoming = next((m for m in moments if m > reference_utc), None)
            returns.append(
                {
                    "body": body_name,
                    "body_label": planet_label(body_name),
                    "natal_longitude": longitude_to_point_dict(
                        body_name, natal_longitude
                    ),
                    "most_recent_return": (
                        {
                            "datetime_utc": most_recent.isoformat(),
                            "datetime_local": most_recent.astimezone(
                                local_tz
                            ).isoformat(),
                        }
                        if most_recent is not None
                        else None
                    ),
                    "next_return": (
                        {
                            "datetime_utc": upcoming.isoformat(),
                            "datetime_local": upcoming.astimezone(local_tz).isoformat(),
                        }
                        if upcoming is not None
                        else None
                    ),
                }
            )

        context = {
            "tool": label,
            "birth_datetime": birth_info.local_datetime.isoformat(),
            "timezone": birth_info.timezone,
            "reference_datetime": analysis_local.isoformat(),
            **house_system_fields(house_system),
            "zodiac_type": zodiac_type,
            "engine": "fatebridge-offline",
        }
        payload = {
            "system": "extra_returns",
            "system_label": "多重回归（土/木/月交返照）",
            "reference_datetime": analysis_local.isoformat(),
            "returns": returns,
        }
        summary = "多重回归：" + "；".join(
            f"{item['body_label']}下次返照 "
            f"{item['next_return']['datetime_local'][:10] if item['next_return'] else '—'}"
            for item in returns
        )
        sections = [
            ("起盘信息", _json_block(context)),
            ("返照时刻", _json_block(returns)),
        ]
        return {
            "analysis_type": "西占多重回归",
            "engine": "fatebridge-offline",
            "analysis_context": context,
            "extrareturns": payload,
            "summary": summary,
            "snapshot_text": _render_snapshot_text(sections),
        }
    except Exception as exc:
        return handle_calculation_error(exc, label)

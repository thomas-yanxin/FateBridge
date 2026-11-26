"""Standalone Guolao Xingzong service orchestration and <6 KB compact projection."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.guolao.ephemeris import MansionFrame
from fatebridge.core.guolao.guolao import LifeDegreeMethod, build_chart
from fatebridge.core.guolao.guolao_timing import enrich_guolao_timing
from fatebridge.utils.errors import calculation_guard


def compact_guolao_chart(result: dict[str, Any]) -> dict[str, Any]:
    """Return a clean <6 KB structured compact view of a Guolao Xingzong chart."""
    g = result["guolao"]
    life = g["life_palace"]
    body = g.get("body_palace", {})
    dw = g.get("dongwei_daxian", {})
    gods = g.get("god_positions", {})
    compact_bodies = [
        {
            "id": b["id"],
            "zh": b["name_zh"],
            "lon": round(b["zodiac_longitude"], 3),
            "palace": b["palace_branch"],
            "lord": b["palace_lord"],
            "natal": b.get("natal_functional_palace"),
            "rx": b.get("retrograde", False),
            "su28": f"{b['mansion']['su28']}({b['mansion']['degree_lord']}) {round(b['mansion']['degree_in_mansion'], 2)}°",
            "yao": b.get("hua_yao"),
            "role": b.get("role_vs_life_lord"),
        }
        for b in g.get("bodies", [])
    ]
    compact_g: dict[str, Any] = {
        "mansion_frame": g.get("mansion_frame"),
        "weekday_ruler": g.get("weekday_ruler"),
        "moon_mansion": g.get("moon_mansion"),
        "conditions": {
            "is_day": g.get("conditions", {}).get("is_day"),
            "season": g.get("conditions", {}).get("season"),
        },
        "life_palace": {
            "branch": life["branch"],
            "lord": life["palace_lord"],
            "lon": life["longitude"],
            "deg": life.get("degree_in_palace"),
            "method": life.get("life_degree_method"),
            "su28": life["mansion"]["su28"] if life.get("mansion") else None,
            "degree_lord": life.get("degree_lord"),
        },
        "body_palace": {
            "branch": body.get("branch"),
            "lord": body.get("palace_lord"),
            "lon": body.get("longitude"),
            "su28": body["mansion"]["su28"] if body.get("mansion") else None,
            "degree_lord": body.get("degree_lord"),
        },
        "palaces": {
            p["palace"]: f"{p['branch']}({p['lord']})" for p in g.get("palaces", [])
        },
        "bodies": compact_bodies,
        "hua_yao": g.get("hua_yao", {}).get("by_transformation"),
        "en_yong_nan_chou": g.get("en_yong_nan_chou"),
        "god_positions": {
            "year": f"{gods.get('year_stem', '')}{gods.get('year_branch', '')}",
            "month": gods.get("month_branch"),
            "noble": f"{gods.get('selected_noble')}:{gods.get('selected_noble_branch')}",
            "branches": gods.get("branches"),
        },
        "dongwei_daxian": {
            "exit_age": dw.get("childhood_exit_age"),
            "periods": [
                f"{p['palace']}({p['branch']}/{p['palace_lord']}):{p['start_age']}-{p['end_age']}"
                for p in dw.get("periods", [])
            ],
        },
        "moira_patterns": [p["name"] for p in g.get("moira_patterns", [])],
    }
    timing = g.get("timing", {})
    if timing.get("status") not in (None, "not_requested"):
        sl = timing.get("small_limit", {})
        tdw = timing.get("dongwei_daxian", {})
        compact_timing: dict[str, Any] = {
            "analysis_datetime": timing.get("analysis_datetime"),
            "small_limit": {
                "branch": sl.get("branch"),
                "palace": sl.get("natal_functional_palace"),
                "lord": sl.get("palace_lord"),
                "target_year": f"{sl.get('target_year_stem', '')}{sl.get('target_year_branch', '')}",
            },
            "dongwei_current": tdw.get("current_period"),
            "target_age": tdw.get("target_age"),
        }
        if "month_limit" in timing:
            ml = timing["month_limit"]
            compact_timing["month_limit"] = {
                "branch": ml.get("branch"),
                "palace": ml.get("natal_functional_palace"),
                "lord": ml.get("palace_lord"),
                "month_basis": ml.get("month_basis"),
            }
        compact_g["timing"] = compact_timing
    return {
        "person_info": {
            "name": result["person_info"].get("name"),
            "birth_datetime": result["person_info"].get("birth_datetime"),
            "birth_timezone": result["person_info"].get("birth_timezone"),
            "utc_datetime": result["person_info"].get("utc_datetime"),
        },
        "chart_profile": {
            "chart_type": "guolao_chart",
            "zodiac": result["chart_profile"].get("zodiac"),
            "ayanamsha": result["chart_profile"].get("ayanamsha"),
        },
        "guolao": compact_g,
    }


@calculation_guard("果老星宗计算")
def calculate_guolao_chart(
    *,
    birth_year: int,
    birth_month: int,
    birth_day: int,
    birth_hour: int,
    birth_minute: int = 0,
    birth_second: int = 0,
    name: str | None = None,
    birth_place: str | None = None,
    birth_timezone: str | None = None,
    birth_longitude: float | None = 116.4074,
    birth_latitude: float | None = 39.9042,
    use_true_solar_time: bool = True,
    house_system: int | str | None = None,
    zodiac_type: str | None = None,
    zodiacal: int | str | None = None,
    mansion_frame: MansionFrame = "modern_equatorial",
    life_degree_method: LifeDegreeMethod = "sun_degree_in_palace",
    analysis_datetime: datetime | None = None,
    month_basis: str | None = None,
    seasonal_anchor_policy: str | None = None,
) -> dict[str, Any]:
    """Compute a complete Guolao Xingzong chart with optional timing."""
    birth = build_astro_birth_info(
        birth_year=birth_year,
        birth_month=birth_month,
        birth_day=birth_day,
        birth_hour=birth_hour,
        birth_minute=birth_minute,
        birth_second=birth_second,
        name=name,
        birth_place=birth_place,
        birth_timezone=birth_timezone,
        birth_longitude=birth_longitude,
        birth_latitude=birth_latitude,
        use_true_solar_time=use_true_solar_time,
        preserve_instant=True,
        require_resolved_timezone=True,
    )
    if zodiacal is not None:
        selected_zodiacal: int | str | None = zodiacal
    elif isinstance(zodiac_type, str):
        selected_zodiacal = {
            "tropic": 0,
            "tropical": 0,
            "sidereal": 1,
        }.get(zodiac_type.strip().lower(), zodiac_type)
    else:
        selected_zodiacal = None
    payload = build_chart(
        birth,
        hsys=house_system,
        zodiacal=selected_zodiacal,
        seasonal_anchor_policy=seasonal_anchor_policy,
        mansion_frame=mansion_frame,
        life_degree_method=life_degree_method,
    )
    if analysis_datetime is not None or month_basis is not None:
        enrich_guolao_timing(
            payload,
            birth,
            analysis_datetime,
            zodiacal=selected_zodiacal,
            month_basis=month_basis,
        )
    return payload

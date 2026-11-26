"""Standalone Jyotish (Vedic chart & Dasha) service orchestration and <10 KB / <5 KB compact projections."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, TypedDict

from typing_extensions import Required, Unpack

from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.execution_context import current_datetime
from fatebridge.core.jyotish.dasha import (
    DashaGrid,
    ashtottari_dasha,
    chara_dasha,
    vimshottari,
    yogini_dasha,
)
from fatebridge.core.jyotish.ephemeris import moon_longitude as calc_moon_longitude
from fatebridge.core.jyotish.ephemeris import positions
from fatebridge.core.jyotish.jyotish import build_india
from fatebridge.core.jyotish.vargas import LABELS
from fatebridge.utils.errors import ParameterError, calculation_guard
from fatebridge.utils.house_systems import (
    normalize_offline_zodiac_code,
    resolve_offline_house_code,
)
from fatebridge.utils.timezones import (
    is_unspecified_local_time,
    parse_timezone_name,
    validate_local_clock,
)


def compact_vedic_chart(result: dict[str, Any]) -> dict[str, Any]:
    """Return a clean <10 KB structured compact view of a Vedic chart."""
    india = result.get("india", result)
    charts_compact = {}
    for name, ch in india.get("charts", {}).items():
        charts_compact[name] = {
            "asc": f"{ch['ascendant']['sign']} {round(ch['ascendant']['degree_in_sign'], 2) if ch['ascendant'].get('degree_in_sign') is not None else ''}",
            "planets": [
                {
                    "id": p["id"],
                    "sign": p["sign"],
                    "deg": (
                        round(p["degree_in_sign"], 2)
                        if p.get("degree_in_sign") is not None
                        else None
                    ),
                    "house": p["house"],
                    "dig": p["dignity"]["state"],
                    **(
                        {"rx": True}
                        if p.get("physical_state", {}).get("retrograde")
                        else {}
                    ),
                }
                for p in ch.get("planets", [])
            ],
        }

    panch = india.get("panchanga", {})
    panch_compact = {
        "tithi": f"{panch.get('tithi', {}).get('paksha')} {panch.get('tithi', {}).get('name')}",
        "vara": panch.get("vara", {}).get("name"),
        "nakshatra": f"{panch.get('nakshatra', {}).get('name')} pada {panch.get('nakshatra', {}).get('pada')}",
        "yoga": panch.get("yoga", {}).get("name"),
        "karana": panch.get("karana", {}).get("name"),
    }
    shad = india.get("strengths", {}).get("shadbala_assessment", {})
    sav_d1 = india.get("ashtakavarga", {}).get("charts", {}).get("D1", {})
    return {
        "person_info": result.get("person_info"),
        "ayanamsa": india.get("ayanamsa"),
        "ayanamsha": round(india.get("ayanamsha", 0.0), 4),
        "moon_nakshatra": india.get("moon_nakshatra"),
        "rising_nakshatra": india.get("rising_nakshatra"),
        "panchanga": panch_compact,
        "charts": charts_compact,
        "bhava_chalit_shifts": india.get("bhava_chalit", {}).get("shifted_planets", []),
        "shadbala": {
            "total_rupa": shad.get("total_rupa"),
            "is_strong": shad.get("is_strong"),
            "ishta_kashta": shad.get("ishta_kashta"),
        },
        "bhava_bala_rupa": [
            {f"H{h['house']}({h['sign'][:3]})": h["total_rupa"]}
            for h in india.get("strengths", {}).get("bhava_bala", [])
        ],
        "ashtakavarga_d1": {
            "profile": india.get("ashtakavarga", {}).get("profile"),
            "samudaya": sav_d1.get("samudaya"),
            "sodhya_pinda": {
                p: row.get("sodhya_pinda") for p, row in sav_d1.get("pinda", {}).items()
            },
        },
        "yogas": [y["name"] for y in india.get("yogas", {}).get("yogas", [])],
        "chara_karakas": [
            f"{k['karaka']}:{k['planet']}" for k in india.get("chara_karakas", [])
        ],
        "arudha_padas": {
            k: v["sign"] for k, v in india.get("arudha_padas", {}).items()
        },
        "upagrahas": {
            k: f"{v['sign']} {round(v['degree_in_sign'], 2)}°" if v else None
            for k, v in india.get("upagrahas", {}).items()
        },
    }


def compact_vimshottari(result: dict[str, Any]) -> dict[str, Any]:
    """Return a clean <5 KB compact view of Vimshottari (and optional Yogini/Chara/Ashtottari) Dasha."""
    vim = result["vimshottari"]
    compact_vim = {
        "year_basis": vim.get("year_basis"),
        "seed": {
            "name": vim["seed"]["name"],
            "lord": vim["seed"]["lord"],
            "pada": vim["seed"]["pada"],
            "moon_longitude": round(vim["seed"]["moon_longitude"], 4),
        },
        "birth_balance": {
            "lord": vim["birth_balance"]["lord"],
            "remaining_years": round(vim["birth_balance"]["remaining_years"], 4),
            "major_end": vim["birth_balance"]["major_end"],
        },
        "current_major": vim.get("current_major"),
        "current_sub": vim.get("current_sub"),
        "timeline": [
            {
                "lord": m["lord"],
                "start": m["start"],
                "end": m["end"],
                "years": m["duration_years"],
            }
            for m in vim.get("timeline", [])
        ],
    }
    if "subdivisions" in vim:
        compact_vim["current_levels"] = [
            {
                "level": r["abbreviation"],
                "lord": r["lord"],
                "start": r["start"],
                "end": r["end"],
            }
            for r in vim["subdivisions"].get("current_levels", [])
        ]
    out: dict[str, Any] = {
        "person_info": result.get("person_info"),
        "analysis_context": {
            "analysis_datetime": result["analysis_context"].get("analysis_datetime"),
            "timezone": result["analysis_context"].get("timezone"),
        },
        "vimshottari": compact_vim,
        "summary": result.get("summary"),
    }
    for extra_key in ("yogini", "ashtottari", "chara"):
        if extra_key in result:
            out[extra_key] = {
                "current_major": result[extra_key].get("current_major"),
                "current_sub": result[extra_key].get("current_sub"),
            }
    return out


@calculation_guard("印占全盘计算")
def calculate_vedic_chart(
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
    birth_longitude: float | None = 77.2090,
    birth_latitude: float | None = 28.6139,
    ayanamsa: str = "lahiri",
    node_mode: str = "mean",
    divisions: list[int] | None = None,
    ashtakavarga_profile: Literal["rao", "aiyar"] = "rao",
    saptavargaja_profile: str = "santhanam_27",
    drekkana_profile: str = "santhanam_27_6",
    cheshta_model: str = "simon1994_j2000",
    ephemeris_policy: str = "auto",
) -> dict[str, Any]:
    """Standalone Vedic Chart calculation without 135 KB Western natal payload (<10 ms)."""
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
        use_true_solar_time=False,
        preserve_instant=True,
        require_resolved_timezone=True,
    )
    india = build_india(
        birth,
        ayanamsa=ayanamsa,
        node_mode=node_mode,
        divisions=divisions,
        ashtakavarga_profile=ashtakavarga_profile,
        ephemeris_policy=ephemeris_policy,
        saptavargaja_profile=saptavargaja_profile,
        drekkana_profile=drekkana_profile,
        cheshta_model=cheshta_model,
    )
    asc = india["charts"]["D1"]["ascendant"]
    return {
        "person_info": {
            "name": birth.name,
            "birth_datetime": birth.local_datetime.isoformat(),
            "utc_datetime": birth.utc_isoformat,
            "birth_timezone": birth.timezone,
            "birth_longitude": birth.longitude,
            "birth_latitude": birth.latitude,
            "birth_place": birth.birth_place,
        },
        "india": india,
        "summary": (
            f"印占本命（{ayanamsa}）：上升{asc['sign_zh']}，月宿{india['moon_nakshatra']}；已计算{', '.join(india['charts'])}。"
        ),
    }


class VimshottariBirthArguments(TypedDict, total=False):
    birth_year: Required[int]
    birth_month: Required[int]
    birth_day: Required[int]
    birth_hour: Required[int]
    birth_minute: int
    birth_second: int
    birth_microsecond: int
    birth_clock_basis: str
    birth_timezone: str | None
    birth_longitude: float | None
    birth_latitude: float | None
    name: str | None
    birth_place: str | None
    use_true_solar_time: bool
    preserve_instant: bool
    solar_clock_ephemeris_policy: str
    require_resolved_timezone: bool
    allow_native_solar_epoch: bool


@calculation_guard("印占 Vimshottari 分期")
def calculate_vimshottari(
    *,
    analysis_timezone: str | None = None,
    analysis_year: int | None = None,
    analysis_month: int | None = None,
    analysis_day: int | None = None,
    analysis_hour: int | None = None,
    analysis_minute: int | None = None,
    year_basis: str = "julian_365_25",
    dasha_depth: int = 2,
    ayanamsa: str = "lahiri",
    node_mode: str = "mean",
    ephemeris_policy: str = "auto",
    include_yogini: bool = False,
    include_ashtottari: bool = False,
    include_chara: bool = False,
    birth_time_uncertainty_minutes: float | None = None,
    house_system: int | str | None = None,
    zodiac_type: str | None = None,
    gender: str | None = None,
    **birth_kwargs: Unpack[VimshottariBirthArguments],
) -> dict[str, Any]:
    """Fast (<3 ms) Vimshottari / Yogini / Ashtottari / Chara Dasha calculation."""
    hsys = None if house_system is None else resolve_offline_house_code(house_system)
    zodiacal = (
        None if zodiac_type is None else normalize_offline_zodiac_code(zodiac_type)
    )
    if hsys not in {None, 0} or zodiacal not in {None, 1}:
        raise ValueError("Vimshottari 使用恒星黄道与整宫制。")

    birth_args: dict[str, Any] = {
        k: v
        for k, v in birth_kwargs.items()
        if k in VimshottariBirthArguments.__annotations__
    }
    birth_args["preserve_instant"] = True
    birth_args["solar_clock_ephemeris_policy"] = ephemeris_policy
    birth_args["require_resolved_timezone"] = True
    if birth_args.get("birth_clock_basis", "civil") == "civil":
        birth_args["use_true_solar_time"] = False
    birth = build_astro_birth_info(**birth_args)

    target_timezone = birth.timezone if analysis_timezone is None else analysis_timezone
    zone = parse_timezone_name(target_timezone)
    now = (
        current_datetime(zone, target_timezone, issue_path="analysis_timezone")
        if analysis_year is None
        else datetime(analysis_year, 1, 1, tzinfo=zone)
    )
    year = now.year if analysis_year is None else analysis_year
    month = (
        analysis_month
        if analysis_month is not None
        else (1 if analysis_year is not None else now.month)
    )
    day = (
        analysis_day
        if analysis_day is not None
        else (1 if analysis_year is not None or analysis_month is not None else now.day)
    )
    analysis = datetime(
        year, month, day, analysis_hour or 0, analysis_minute or 0, tzinfo=zone
    )
    if is_unspecified_local_time(analysis):
        return ParameterError(
            "分析钟时的当地 UTC 偏移未指定。",
            [{"path": "analysis_timezone", "code": "unresolved_timezone_offset"}],
        ).as_result()
    validate_local_clock(analysis, clock_label="分析钟时")

    if include_chara:
        pos = positions(
            birth,
            ayanamsa=ayanamsa,
            node_mode=node_mode,
            ephemeris_policy=ephemeris_policy,
        )
        moon_lon = pos["longitudes"]["Moon"]
        ayanamsha_val = float(pos["ayanamsha"])
    else:
        pos = None
        moon_info = calc_moon_longitude(
            birth, ayanamsa=ayanamsa, ephemeris_policy=ephemeris_policy
        )
        moon_lon = moon_info["moon_longitude"]
        ayanamsha_val = float(moon_info["ayanamsha"])

    result = vimshottari(
        birth.utc_calendar,
        moon_lon,
        analysis,
        year_basis=year_basis,
        dasha_depth=dasha_depth,
    )
    grid = DashaGrid(analysis, year_basis, None, dasha_depth)
    grid.observe_moon(0.0, moon_lon)
    result["birth_time_sensitivity"] = grid.result()

    output: dict[str, Any] = {
        "analysis_context": {
            "analysis_datetime": analysis.isoformat(),
            "timezone": target_timezone,
            "ayanamsa": ayanamsa,
        },
        "person_info": {
            "name": birth.name,
            "birth_datetime": birth.local_datetime.isoformat(),
            "utc_datetime": birth.utc_isoformat,
            "birth_timezone": birth.timezone,
            "birth_longitude": birth.longitude,
            "birth_latitude": birth.latitude,
            "birth_place": birth.birth_place,
        },
        "vimshottari": result,
        "summary": f"按名义生时，目标时刻为{LABELS[result['current_major']['lord']]}主运／{LABELS[result['current_sub']['lord']]}次运（{year_basis}）。",
    }
    if dasha_depth > 2:
        chain = "／".join(
            f"{row['abbreviation']}={LABELS[row['lord']]}"
            for row in result["subdivisions"]["current_levels"]
        )
        output["summary"] = f"按名义生时，目标时刻运主链为{chain}（{year_basis}）。"
    if include_yogini:
        output["yogini"] = yogini_dasha(
            birth.utc_calendar, moon_lon, analysis, year_basis=year_basis
        )
    if include_ashtottari:
        output["ashtottari"] = ashtottari_dasha(
            birth.utc_calendar, moon_lon, analysis, year_basis=year_basis
        )
    if include_chara and pos is not None:
        output["chara"] = chara_dasha(
            birth.utc_calendar,
            pos["longitudes"],
            pos["ascendant"],
            analysis,
            year_basis=year_basis,
        )
    return output

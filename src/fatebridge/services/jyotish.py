"""Indian astrology service composition; shared by REST, MCP and CLI."""

from __future__ import annotations

from datetime import datetime
from typing import Any, TypedDict

from typing_extensions import Required, Unpack

from fatebridge.core.astro.birth import AstroBirthInfo, build_astro_birth_info
from fatebridge.core.execution_context import current_datetime
from fatebridge.core.jyotish.jyotish import build_india
from fatebridge.core.jyotish.jyotish_charts import LABELS
from fatebridge.core.jyotish.jyotish_dasha_grid import DashaGrid
from fatebridge.core.jyotish.jyotish_dasha_levels import (
    QUANTIZATION_RULE,
    QUANTIZATION_SOURCE,
    vimshottari,
)
from fatebridge.core.jyotish.jyotish_display import normalize_solar_display
from fatebridge.core.jyotish.jyotish_sources import coherent_sources
from fatebridge.utils.errors import ParameterError, calculation_guard
from fatebridge.utils.timezones import (
    is_unspecified_local_time,
    parse_timezone_name,
    validate_local_clock,
)


def enrich_india_chart(
    result: dict[str, Any],
    birth: AstroBirthInfo,
    *,
    node_mode: str,
    ephemeris_policy: str,
    saptavargaja_profile: str,
    drekkana_profile: str,
    cheshta_model: str,
    divisions: list[int] | None,
    birth_time_uncertainty_minutes: float | None,
) -> None:
    """Keep the public Western reference view separate from Indian calculations."""
    if (
        result["chart_profile"]["zodiac"] != "sidereal"
        or result["chart_profile"]["house_system"] != "whole_sign"
    ):
        result["india"].update(
            {
                "status": "configuration_not_supported",
                "interpretation_scope": "Requested public zodiac/house configuration selected. Parashari D1/D9/D10 require sidereal Lahiri and whole-sign; not computed for this configuration.",
            }
        )
        return
    india = build_india(
        birth,
        node_mode=node_mode,
        ephemeris_policy=ephemeris_policy,
        saptavargaja_profile=saptavargaja_profile,
        drekkana_profile=drekkana_profile,
        cheshta_model=cheshta_model,
        divisions=divisions,
        birth_time_uncertainty_minutes=birth_time_uncertainty_minutes,
    )
    result["india"] = india
    asc = india["charts"]["D1"]["ascendant"]
    result["summary"] = (
        f"印占本命（名义生时）：上升{asc['sign_zh']}，月宿{india['moon_nakshatra']}；已计算{', '.join(india['charts'])}。"
        + (
            "给定生时范围内存在月宿／宿足候选，须一并读取reading_basis。"
            if len(india["reading_basis"]["moon_nakshatra_options"]) > 1
            else ""
        )
    )


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
@coherent_sources
def calculate_vimshottari(
    *,
    analysis_timezone: str | None = None,
    analysis_year: int | None = None,
    analysis_month: int | None = None,
    analysis_day: int | None = None,
    analysis_hour: int | None = None,
    analysis_minute: int | None = None,
    year_basis: str = "sidereal_365_25636",
    dasha_depth: int = 2,
    node_mode: str = "mean",
    ephemeris_policy: str = "auto",
    saptavargaja_profile: str = "santhanam_27",
    drekkana_profile: str = "santhanam_27_6",
    cheshta_model: str = "unadjudicated",
    divisions: list[int] | None = None,
    birth_time_uncertainty_minutes: float | None = None,
    hsys: int | None = None,
    zodiacal: int | None = None,
    gender: str | None = None,
    **birth_kwargs: Unpack[VimshottariBirthArguments],
) -> dict[str, Any]:
    if hsys not in {None, 0} or zodiacal not in {None, 1}:
        raise ValueError("Vimshottari 使用 Lahiri 恒星黄道与整宫制。")
    # The solar option is a display label. It cannot change the ephemeris epoch
    # or enter a different mean-model window by moving to a neighbouring date.
    birth_kwargs["preserve_instant"] = True
    birth_kwargs["solar_clock_ephemeris_policy"] = ephemeris_policy
    # The birth's civil zone must be supplied or resolved from its place.
    # An analysis zone and a solar-display request cannot establish it.
    birth_kwargs["require_resolved_timezone"] = True
    display_requested = birth_kwargs.get("use_true_solar_time", False)
    if birth_kwargs.get("birth_clock_basis", "civil") == "civil":
        # Build the recorded instant without the generic UTC-as-UT1 display.
        # Noncivil conflicting options still reach the builder's validation.
        birth_kwargs["use_true_solar_time"] = False
    birth = build_astro_birth_info(**birth_kwargs)
    birth, _ = normalize_solar_display(
        birth, ephemeris_policy, requested=display_requested
    )
    target_timezone = birth.timezone if analysis_timezone is None else analysis_timezone
    zone = parse_timezone_name(target_timezone)
    now = (
        current_datetime(zone, target_timezone, issue_path="analysis_timezone")
        if analysis_year is None
        else datetime(analysis_year, 1, 1, tzinfo=zone)
    )
    # A specified year anchors Jan 1, a specified month anchors day 1. A
    # completely omitted date uses the frozen call date. Date-only = midnight.
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
            "分析钟时的当地 UTC 偏移未指定。请提供有效的分析时区或已核实的 UTC 偏移。",
            [{"path": "analysis_timezone", "code": "unresolved_timezone_offset"}],
        ).as_result()
    validate_local_clock(analysis, clock_label="分析钟时")
    grid = DashaGrid(analysis, year_basis, divisions, dasha_depth)
    india = build_india(
        birth,
        node_mode=node_mode,
        ephemeris_policy=ephemeris_policy,
        saptavargaja_profile=saptavargaja_profile,
        drekkana_profile=drekkana_profile,
        cheshta_model=cheshta_model,
        divisions=divisions,
        birth_time_uncertainty_minutes=birth_time_uncertainty_minutes,
        _dasha_grid=grid,
    )
    moon = next(p for p in india["charts"]["D1"]["planets"] if p["id"] == "Moon")
    india["rulesets"].append(dict(QUANTIZATION_SOURCE))
    india["rule_trace"].append(
        {
            "rule_id": QUANTIZATION_RULE,
            "source_id": QUANTIZATION_SOURCE["id"],
            "section": "FateBridge numerical policy: one common birth epoch and final rational quantization; Rao16.2-16.3 supply the ratios, not a microsecond accuracy claim",
        }
    )
    result = vimshottari(
        birth.utc_calendar,
        moon["longitude"],
        analysis,
        year_basis=year_basis,
        dasha_depth=dasha_depth,
    )
    result["birth_time_sensitivity"] = {
        **grid.result(),
        "reading_basis": india["reading_basis"],
    }
    current_lords = {result["current_major"]["lord"], result["current_sub"]["lord"]}
    if dasha_depth > 2:
        current_lords.update(
            row["lord"] for row in result["subdivisions"]["current_levels"]
        )
    result["natal_ruler_context"] = [
        {
            "reference": "nominal_birth_instant_only",
            "chart": name,
            "planet": planet,
            **(
                {
                    "period_roles": [
                        row["name"]
                        for row in result["subdivisions"]["current_levels"]
                        if row["lord"] == planet["id"]
                    ]
                }
                if dasha_depth > 2
                else {}
            ),
            "owned_houses": [
                h["house"] for h in chart["houses"] if h["lord"] == planet["id"]
            ],
        }
        for name, chart in india["charts"].items()
        for planet in chart["planets"]
        if planet["id"] in current_lords
    ]
    output = {
        "analysis_context": {
            "analysis_datetime": analysis.isoformat(),
            "timezone": target_timezone,
            "timezone_basis": (
                "explicit_analysis_timezone"
                if analysis_timezone is not None
                else (
                    "UTC_default_for_solar_input"
                    if birth.clock_conversion
                    else "resolved_birth_civil_timezone"
                )
            ),
            "date_anchor_policy": "explicit year: Jan 1; explicit month: day 1; omitted date: frozen call date; omitted clock: 00:00",
        },
        "person_info": {
            "name": birth.name,
            "birth_datetime": birth.local_datetime.isoformat(),
            "utc_datetime": birth.utc_isoformat,
            "birth_timezone": birth.timezone,
            "birth_longitude": birth.longitude,
            "birth_latitude": birth.latitude,
            "birth_place": birth.birth_place,
            **(
                {"clock_conversion": dict(birth.clock_conversion)}
                if birth.clock_conversion is not None
                else {}
            ),
        },
        "india": india,
        "vimshottari": result,
        "summary": f"按名义生时，目标时刻为{LABELS[result['current_major']['lord']]}主运／{LABELS[result['current_sub']['lord']]}次运；起止按{year_basis}计算，给定生时误差另见敏感性记录。",
    }
    if dasha_depth > 2:
        chain = "／".join(
            f"{row['abbreviation']}={LABELS[row['lord']]}"
            for row in result["subdivisions"]["current_levels"]
        )
        output["summary"] = (
            f"按名义生时，目标时刻运主链为{chain}；按{year_basis}递归细分，"
            "给定生时误差另见完整运主链候选；细分边界不代表现实事件精度。"
        )
    return output

"""Indian astrology service composition; shared by REST, MCP and CLI."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fatebridge.core.astro.birth import AstroBirthInfo, build_astro_birth_info
from fatebridge.core.execution_context import current_datetime
from fatebridge.core.jyotish import LABELS, build_india, validate_clock, vimshottari
from fatebridge.core.jyotish_dasha_grid import DashaGrid
from fatebridge.core.jyotish_dasha_levels import QUANTIZATION_RULE, QUANTIZATION_SOURCE
from fatebridge.core.jyotish_display import normalize_solar_display
from fatebridge.core.jyotish_evidence import natal_prose
from fatebridge.core.jyotish_sources import coherent_sources
from fatebridge.services.structured_snapshot import render_structured_snapshot_text
from fatebridge.utils.errors import calculation_guard
from fatebridge.utils.timezones import parse_timezone_name


def enrich_india_chart(
    result: Dict[str, Any], birth: AstroBirthInfo, **options: Any
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
    india = build_india(birth, **options)
    result["india"] = india
    asc = india["charts"]["D1"]["ascendant"]
    prose = natal_prose(india)
    reading = {
        "scope": "india only; generic Western top-level fields form a separate public reference view",
        **prose,
        "reading_basis": india["reading_basis"],
        "variant_note": f"{india['ruleset_id']}；Lahiri，{india['profile']['node_mode']} node。",
        "topic_evidence": india["topic_evidence"],
        "development_advice": "把传统结构描述与实际职责、相处经历核对；分盘变化先核对出生时间范围。",
    }
    # Each public view retains its own coordinate and interpretive doctrine.
    result["interpretation"][
        "scope"
    ] = "western_reference_view_only; Indian reading: india and interpretation.vedic"
    result["interpretation"]["vedic"] = reading
    result["summary"] = (
        f"印占本命（名义生时）：上升{asc['sign_zh']}，月宿{india['moon_nakshatra']}；已计算{', '.join(india['charts'])}。"
        + (
            "给定生时范围内存在月宿／宿足候选，须一并读取reading_basis。"
            if len(india["reading_basis"]["moon_nakshatra_options"]) > 1
            else ""
        )
    )


@calculation_guard("印占 Vimshottari 分期")
@coherent_sources
def calculate_vimshottari(
    *,
    analysis_timezone: Optional[str] = None,
    analysis_year: Optional[int] = None,
    analysis_month: Optional[int] = None,
    analysis_day: Optional[int] = None,
    analysis_hour: Optional[int] = None,
    analysis_minute: Optional[int] = None,
    year_basis: str = "sidereal_365_25636",
    dasha_depth: int = 2,
    node_mode: str = "mean",
    ephemeris_policy: str = "auto",
    saptavargaja_profile: str = "santhanam_27",
    drekkana_profile: str = "santhanam_27_6",
    cheshta_model: str = "unadjudicated",
    divisions: Optional[List[int]] = None,
    birth_time_uncertainty_minutes: Optional[float] = None,
    hsys: Optional[int] = None,
    zodiacal: Optional[int] = None,
    gender: Optional[str] = None,
    **birth_kwargs: Any,
) -> Dict[str, Any]:
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
    validate_clock(birth.local_datetime, "解析后的出生时刻")
    target_timezone = birth.timezone if analysis_timezone is None else analysis_timezone
    zone = parse_timezone_name(target_timezone)
    now = (
        current_datetime(zone, target_timezone)
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
    validate_clock(analysis, "分析钟时")
    grid = DashaGrid(
        birth.require_utc_datetime, analysis, year_basis, divisions, dasha_depth
    )
    india = build_india(
        birth,
        node_mode=node_mode,
        ephemeris_policy=ephemeris_policy,
        saptavargaja_profile=saptavargaja_profile,
        drekkana_profile=drekkana_profile,
        cheshta_model=cheshta_model,
        divisions=divisions,
        birth_time_uncertainty_minutes=birth_time_uncertainty_minutes,
        _sample_observer=grid.observe,
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
        birth.require_utc_datetime,
        moon["longitude"],
        analysis,
        year_basis=year_basis,
        dasha_depth=dasha_depth,
    )
    sensitivity = []
    omitted_samples = []
    for sample in india["birth_time_sensitivity"].get("moon_samples", []):
        from datetime import timedelta

        shifted = birth.require_utc_datetime + timedelta(
            seconds=sample["offset_seconds"]
        )
        if analysis >= shifted:
            alternative = vimshottari(
                shifted,
                sample["longitude"],
                analysis,
                year_basis=year_basis,
                dasha_depth=dasha_depth,
            )
            sensitivity.append(
                {
                    "offset_seconds": sample["offset_seconds"],
                    "birth_balance": alternative["birth_balance"],
                    "time_quantization": alternative["time_quantization"],
                    "current_major": alternative["current_major"],
                    "current_sub": alternative["current_sub"],
                    **(
                        {"subdivisions": alternative["subdivisions"]}
                        if dasha_depth > 2
                        else {}
                    ),
                }
            )
        else:
            omitted_samples.append(
                {
                    "offset_seconds": sample["offset_seconds"],
                    "reason": "analysis_precedes_candidate_birth",
                }
            )
    result["birth_time_sensitivity"] = {
        **grid.result(),
        "samples": sensitivity,
        "samples_scope": "legacy endpoints and center subset; stage_variants covers the full grid",
        "endpoint_subset_requested_count": len(
            india["birth_time_sensitivity"].get("moon_samples", [])
        ),
        "endpoint_subset_evaluated_count": len(sensitivity),
        "endpoint_subset_omitted_samples": omitted_samples,
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
            "utc_datetime": birth.require_utc_datetime.isoformat(),
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
    output["snapshot_text"] = render_structured_snapshot_text(
        output, title="印占 Vimshottari 分期"
    )
    return output

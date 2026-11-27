"""Unified Jyotish Vedic Chart orchestration (<10 ms in-process, zero subprocesses)."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from typing import Any, Literal

from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.jyotish.ashtakavarga import for_charts as ashtakavarga_for_charts
from fatebridge.core.jyotish.dasha import nakshatra
from fatebridge.core.jyotish.ephemeris import positions
from fatebridge.core.jyotish.panchanga import compute_panchanga
from fatebridge.core.jyotish.shadbala import calculate_shadbala_bundle
from fatebridge.core.jyotish.vargas import (
    GRAHAS,
    SUPPORTED_DIVISIONS,
    bhava_chalit,
    divisional_chart,
    partition_longitudes,
)
from fatebridge.core.jyotish.yogas import (
    arudha_padas,
    chara_karakas,
    evaluate_yogas,
    upagrahas_and_special_lagnas,
)
from fatebridge.utils.timezones import validate_local_clock

RULESET = "parashari_jyotish_core_v30"


def build_india(
    birth: AstroBirthInfo,
    *,
    ayanamsa: str = "lahiri",
    node_mode: str = "mean",
    divisions: list[int] | None = None,
    ashtakavarga_profile: Literal["rao", "aiyar"] = "rao",
    birth_time_uncertainty_minutes: float | None = None,
    ephemeris_policy: str = "auto",
    saptavargaja_profile: str = "santhanam_27",
    drekkana_profile: str = "santhanam_27_6",
    cheshta_model: str = "simon1994_j2000",
    _sample_observer: Any = None,
    _dasha_grid: Any = None,
) -> dict[str, Any]:
    """Compute a complete fast (<10 ms) deterministic Parashari + Jaimini Vedic chart."""
    validate_local_clock(
        birth.local_datetime, clock_label="出生钟时", allow_ambiguous=True
    )
    selected = [9, 10] if divisions is None else divisions
    if any(d not in SUPPORTED_DIVISIONS for d in selected) or len(selected) != len(
        set(selected)
    ):
        raise ValueError(
            "divisions 仅接受不重复的十六分盘（2,3,4,7,9,10,12,16,20,24,27,30,40,45,60）；D1 始终计算。"
        )
    if (
        birth_time_uncertainty_minutes is not None
        and not 0 <= birth_time_uncertainty_minutes <= 120
    ):
        raise ValueError("出生时间不确定范围须在 0–120 分钟内。")

    raw = positions(
        birth,
        node_mode=node_mode,
        ephemeris_policy=ephemeris_policy,
        cheshta_model=cheshta_model,
        ayanamsa=ayanamsa,
    )
    nominal_longitudes = partition_longitudes(raw)
    nominal_nakshatras = {
        p: nakshatra(lon)
        for p, lon in {**nominal_longitudes, "Ascendant": raw["ascendant"]}.items()
    }
    charts = {
        f"D{d}": divisional_chart(raw, d, partition_longitudes_map=nominal_longitudes)
        for d in [1, *selected]
    }
    ashtakavarga = ashtakavarga_for_charts(charts, profile=ashtakavarga_profile)
    chalit = bhava_chalit(raw["longitudes"], raw["ascendant"], raw["midheaven"])
    shadbala_bundle = calculate_shadbala_bundle(
        raw,
        birth.longitude,
        birth.latitude,
        saptavargaja_profile=saptavargaja_profile,
        drekkana_profile=drekkana_profile,
        cheshta_model=cheshta_model,
    )
    solar_ctx = shadbala_bundle["solar_context"]
    panchanga = compute_panchanga(
        nominal_longitudes["Sun"],
        nominal_longitudes["Moon"],
        dict(nominal_nakshatras["Moon"]),
        local_datetime=birth.local_datetime,
        solar_context=solar_ctx,
        sun_speed=raw["speeds"]["Sun"],
        moon_speed=raw["speeds"]["Moon"],
        jd_ut1=raw["julian_day_ut"],
    )
    yogas = evaluate_yogas(raw["longitudes"], raw["ascendant"])
    karakas = chara_karakas(raw["longitudes"])
    arudhas = arudha_padas(raw["longitudes"], raw["ascendant"])
    upagrahas = upagrahas_and_special_lagnas(
        sun_longitude=raw["longitudes"]["Sun"],
        ascendant=raw["ascendant"],
        jd_ut1=raw["julian_day_ut"],
        solar_context=solar_ctx,
    )

    sensitivity: dict[str, Any] = {
        "status": "not_assessed",
        "uncertainty_minutes": birth_time_uncertainty_minutes,
    }
    if birth_time_uncertainty_minutes is not None:
        step = 30.0 if birth_time_uncertainty_minutes < 1.0 else 60.0
        half_sec = birth_time_uncertainty_minutes * 60.0
        n_steps = max(1, int(round(half_sec / step)))
        offsets = [i * step for i in range(-n_steps, n_steps + 1)]
        alts: dict[str, dict[str, list[dict[str, Any]]]] = {
            f"D{d}": {p: [] for p in GRAHAS} for d in [1, *selected]
        }
        seen_signs: dict[str, dict[str, set[str]]] = {
            f"D{d}": {p: set() for p in GRAHAS} for d in [1, *selected]
        }
        nak_counts: dict[str, dict[tuple[int, int], dict[str, Any]]] = {
            p: {} for p in GRAHAS
        }
        assert birth.utc_datetime is not None
        for off in offsets:
            if off == 0.0:
                s_raw, s_lons = raw, nominal_longitudes
            else:
                s_moment = birth.utc_datetime + timedelta(seconds=off)
                s_raw = positions(
                    birth,
                    moment=s_moment,
                    node_mode=node_mode,
                    ephemeris_policy=ephemeris_policy,
                    cheshta_model="unadjudicated",
                    ayanamsa=ayanamsa,
                )
                s_lons = partition_longitudes(s_raw)
            for d in [1, *selected]:
                s_chart = divisional_chart(s_raw, d, partition_longitudes_map=s_lons)
                for pt in s_chart["planets"]:
                    pid = pt["id"]
                    if pt["sign"] not in seen_signs[f"D{d}"][pid]:
                        seen_signs[f"D{d}"][pid].add(pt["sign"])
                        alts[f"D{d}"][pid].append(
                            {"sign": pt["sign"], "house": pt["house"]}
                        )
            for p in GRAHAS:
                nk = nakshatra(s_lons[p])
                key = (nk["index"], nk["pada"])
                if key not in nak_counts[p]:
                    nak_counts[p][key] = {**nk, "sample_count": 0}
                nak_counts[p][key]["sample_count"] += 1
        sensitivity = {
            "status": "assessed",
            "uncertainty_minutes": birth_time_uncertainty_minutes,
            "sample_count": len(offsets),
            "alternatives": alts,
            "nakshatra_alternatives": {
                p: list(v.values()) for p, v in nak_counts.items()
            },
        }

    return {
        "status": "complete",
        "ruleset_id": RULESET,
        "ayanamsa": ayanamsa,
        "ayanamsha": raw["ayanamsha"],
        "moon_nakshatra": nominal_nakshatras["Moon"]["name"],
        "rising_nakshatra": nominal_nakshatras["Ascendant"]["name"],
        "panchanga": panchanga,
        "profile": {
            "engine": "swisseph_api",
            "zodiac": "sidereal",
            "ayanamsa": ayanamsa,
            "ayanamsa_id": raw["ayanamsa_id"],
            "house_system": "whole_sign",
            "node_mode": node_mode,
            "swisseph_version": raw["swisseph_version"],
            "ephemeris_models": raw["ephemeris_models"],
            "ephemeris_by_body": raw["ephemeris_by_body"],
            "physical_ephemeris_source": raw["physical_ephemeris_source"],
            "julian_day_ut": raw["julian_day_ut"],
            "julian_day_tt": raw["julian_day_tt"],
            "julian_day_utc": raw["julian_day_utc"],
            "time_scale_context": raw["time_scale_context"],
            "saptavargaja_profile": saptavargaja_profile,
            "drekkana_profile": drekkana_profile,
            "cheshta_model": cheshta_model,
        },
        "nakshatras": nominal_nakshatras,
        "charts": charts,
        "bhava_chalit": chalit,
        "strengths": shadbala_bundle["strengths"],
        "ashtakavarga": ashtakavarga,
        "yogas": yogas,
        "chara_karakas": karakas,
        "arudha_padas": arudhas,
        "upagrahas": upagrahas,
        "birth_time_sensitivity": sensitivity,
    }

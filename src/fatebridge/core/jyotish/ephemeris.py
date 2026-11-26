"""Direct in-process Swiss Ephemeris calculation for Jyotish (no subprocesses)."""

from __future__ import annotations

import math
from datetime import datetime
from fractions import Fraction
from typing import Any, Literal

from fatebridge.core.astro import runtime
from fatebridge.core.astro.birth import AstroBirthInfo, require_resolved_birth_timezone
from fatebridge.core.astro.geometry import combine_longitudes
from fatebridge.core.astro.physical_epoch import PhysicalEpoch
from fatebridge.core.astro.profiles import native_factor_model
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.utils.civil_time import utc_calendar

AyanamsaMode = Literal["lahiri", "true_citra", "raman", "kp", "true_pushya"]

SEVEN_GRAHAS = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")
NINE_GRAHAS = (*SEVEN_GRAHAS, "Rahu", "Ketu")

# Simon et al. (1994) secular mean longitudes (degrees + arcsec polynomial in J2000 millennia)
SIMON_LOWER_TT, SIMON_UPPER_TT = 2415020.5, 2470172.5  # 1900-01-01 to 2050-12-31
SIMON_LONGITUDE_COEFFICIENTS = {
    "Mercury": ("252.25090552", "5381016286.88982", "-1.92789", "0.00639"),
    "Venus": ("181.97980085", "2106641364.33548", "0.59381", "-0.00627"),
    "Earth": ("100.46645683", "1295977422.83429", "-2.04411", "-0.00523"),
    "Mars": ("355.43299958", "689050774.93988", "0.94264", "-0.01043"),
    "Jupiter": (
        "34.35151874",
        "109256603.77991",
        "-30.60378",
        "0.05706",
        "0.04667",
        "0.00591",
        "-0.00034",
    ),
    "Saturn": (
        "50.07744430",
        "43996098.55732",
        "75.61614",
        "-0.16618",
        "-0.11484",
        "-0.01452",
        "0.00083",
    ),
}


def resolve_sid_mode(swe: Any, ayanamsa: str) -> tuple[int, str]:
    """Map public ayanamsa identifier to Swiss Ephemeris SIDM constant."""
    mapping = {
        "lahiri": (swe.SIDM_LAHIRI, "swiss_lahiri_sidm_1"),
        "true_citra": (swe.SIDM_TRUE_CITRA, "swiss_true_citra_sidm_27"),
        "raman": (swe.SIDM_RAMAN, "swiss_raman_sidm_3"),
        "kp": (swe.SIDM_KRISHNAMURTI, "swiss_kp_sidm_5"),
        "true_pushya": (swe.SIDM_TRUE_PUSHYA, "swiss_true_pushya_sidm_29"),
    }
    if ayanamsa not in mapping:
        raise ValueError(
            "不支持的 ayanamsa；须为 lahiri、true_citra、raman、kp 或 true_pushya。"
        )
    return mapping[ayanamsa]


def simon1994_mean_longitudes(jd_tt: float) -> dict[str, float] | None:
    """Compute Simon et al. (1994) secular mean ecliptic J2000 longitudes for 1900-2050 TT."""
    if not (math.isfinite(jd_tt) and SIMON_LOWER_TT <= jd_tt < SIMON_UPPER_TT):
        return None
    t = (Fraction(jd_tt) - 2451545) / 365250
    result: dict[str, Fraction] = {}
    for planet, values in SIMON_LONGITUDE_COEFFICIENTS.items():
        power_sum = Fraction(0)
        for coefficient in reversed(values[1:]):
            power_sum = (power_sum + Fraction(coefficient)) * t
        result[planet] = (Fraction(values[0]) + power_sum / 3600) % 360
    result["Sun"] = (result["Earth"] + 180) % 360
    return {planet: float(lon) for planet, lon in result.items()}


def _require_recorded_instant(birth: AstroBirthInfo) -> None:
    require_resolved_birth_timezone(birth.timezone_source)
    recorded = birth.recorded_datetime or birth.local_datetime
    physical = (
        birth.require_utc_datetime
        if birth.clock_conversion is not None
        else birth.physical_datetime
    )
    if physical.utcoffset() is None or recorded.utcoffset() is None:
        raise ValueError("印占的记录钟时与物理时刻必须带时区。")
    if utc_calendar(physical) != utc_calendar(recorded):
        raise ValueError(
            "印占须保留记录钟时所指的物理时刻；请以 preserve_instant=True 构造。"
        )


def moon_longitude(
    birth: AstroBirthInfo,
    *,
    ayanamsa: str = "lahiri",
    ephemeris_policy: str = "auto",
) -> dict[str, Any]:
    """Fast (<1 ms) single-body sidereal Moon longitude for standalone Dasha calculations."""
    _require_recorded_instant(birth)
    if ephemeris_policy not in {"auto", "require_data_files"}:
        raise ValueError("ephemeris_policy 必须为 auto 或 require_data_files。")
    if runtime.swe is None:
        raise ValueError("印占需要可用的 Swiss Ephemeris。")
    swe = runtime.swe
    sid_mode, ayanamsa_id = resolve_sid_mode(swe, ayanamsa)
    times = birth.time_scales
    if times.tt is None:
        raise ValueError("印占不以缺失的 TT 时间尺度计算星位。")
    jd_tt = times.tt.as_float()
    with runtime.preserve_ephemeris_path():
        swe.set_sid_mode(sid_mode, 0.0, 0.0)
        flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED
        coords, flag = runtime.ephemeris_call("calc", jd_tt, swe.MOON, flags)
        if flag < 0 or not math.isfinite(coords[0]):
            raise ValueError("Swiss Ephemeris 无法计算 Moon。")
        model = runtime.ephemeris_model_from_retflag(flag)
        if ephemeris_policy == "require_data_files" and model not in {"swieph", "jpl"}:
            raise ValueError(
                f"Moon 实际使用 {model}；require_data_files 禁止星历降级。"
            )
        ayan_flag, ayan_val = runtime.ephemeris_call(
            "get_ayanamsa_ex", jd_tt, swe.FLG_SWIEPH
        )
        if ayan_flag < 0:
            raise ValueError("Swiss Ephemeris 无法计算岁差。")
    return {
        "moon_longitude": float(coords[0]) % 360.0,
        "moon_speed": float(coords[3]),
        "ayanamsa": ayanamsa,
        "ayanamsa_id": ayanamsa_id,
        "ayanamsha": float(ayan_val),
        "ephemeris_model": model,
        "julian_day_tt": jd_tt,
        "julian_day_ut": times.ut1.as_float(),
    }


def positions(
    birth: AstroBirthInfo,
    moment: datetime | PhysicalEpoch | None = None,
    node_mode: str = "mean",
    ephemeris_policy: str = "auto",
    cheshta_model: str = "simon1994_j2000",
    ayanamsa: str = "lahiri",
) -> dict[str, Any]:
    """Compute sidereal Jyotish longitudes, declinations, houses, and J2000 true positions (<3 ms)."""
    _require_recorded_instant(birth)
    if node_mode not in {"mean", "true"}:
        raise ValueError("node_mode 必须为 mean 或 true。")
    if ephemeris_policy not in {"auto", "require_data_files"}:
        raise ValueError("ephemeris_policy 必须为 auto 或 require_data_files。")
    if cheshta_model not in {"unadjudicated", "simon1994_j2000"}:
        raise ValueError("cheshta_model 须为 simon1994_j2000 或 unadjudicated。")
    if runtime.swe is None:
        raise ValueError("印占核心需要可用的 Swiss Ephemeris。")

    swe = runtime.swe
    sid_mode, ayanamsa_id = resolve_sid_mode(swe, ayanamsa)
    instant = (
        moment.utc_datetime
        if isinstance(moment, PhysicalEpoch)
        else moment or birth.physical_datetime
    )
    if instant is not None and instant.utcoffset() is None:
        raise ValueError("印占计算时刻必须带时区。")

    if isinstance(moment, PhysicalEpoch):
        times = moment.time
    else:
        times = birth.time_scales if moment is None else ephemeris_time(moment)
    tt, jd = times.tt, times.ut1
    if tt is None:
        raise ValueError("印占不以缺失的 TT 时间尺度计算星位。")
    jd_tt = tt.as_float()
    jd_ut1 = jd.as_float()

    values: dict[str, float] = {}
    speeds: dict[str, float] = {}
    equatorial: dict[str, dict[str, float]] = {}
    motion_true_j2000: dict[str, dict[str, Any]] = {}
    body_models: dict[str, str] = {}
    models: set[str] = set()

    with runtime.preserve_ephemeris_path():
        swe.set_sid_mode(sid_mode, 0.0, 0.0)
        sid_flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED
        eq_flags = swe.FLG_SWIEPH | swe.FLG_EQUATORIAL
        j2000_flags = swe.FLG_SWIEPH | swe.FLG_J2000 | swe.FLG_NOABERR | swe.FLG_NOGDEFL

        ayan_flag, ayanamsha = runtime.ephemeris_call(
            "get_ayanamsa_ex", jd_tt, swe.FLG_SWIEPH
        )
        if ayan_flag < 0 or not math.isfinite(ayanamsha):
            raise ValueError("Swiss Ephemeris 无法计算岁差。")

        for planet in (*SEVEN_GRAHAS, "Rahu"):
            pid = (
                (swe.MEAN_NODE if node_mode == "mean" else swe.TRUE_NODE)
                if planet == "Rahu"
                else getattr(swe, planet.upper())
            )
            coords, flag = runtime.ephemeris_call("calc", jd_tt, pid, sid_flags)
            if flag < 0 or not all(math.isfinite(coords[i]) for i in (0, 1, 3)):
                raise ValueError(f"Swiss Ephemeris 无法计算 {planet}。")
            model = runtime.ephemeris_model_from_retflag(flag)
            if planet != "Rahu":
                models.add(model)
            body_models[planet] = native_factor_model(pid, flag)
            if (
                ephemeris_policy == "require_data_files"
                and planet != "Rahu"
                and model not in {"swieph", "jpl"}
            ):
                raise ValueError(
                    f"{planet} 实际使用 {model}；require_data_files 禁止星历降级。"
                )
            values[planet] = float(coords[0]) % 360.0
            speeds[planet] = float(coords[3])

            if planet != "Rahu":
                eq_coords, eq_flag = runtime.ephemeris_call(
                    "calc", jd_tt, pid, eq_flags
                )
                if eq_flag < 0 or not all(math.isfinite(eq_coords[i]) for i in (0, 1)):
                    raise ValueError(f"Swiss Ephemeris 无法计算 {planet} 赤道坐标。")
                equatorial[planet] = {
                    "right_ascension": float(eq_coords[0]) % 360.0,
                    "declination": float(eq_coords[1]),
                }
                if planet not in {"Sun", "Moon"} and cheshta_model == "simon1994_j2000":
                    j_coords, j_flag = runtime.ephemeris_call(
                        "calc", jd_tt, pid, j2000_flags
                    )
                    if j_flag >= 0 and math.isfinite(j_coords[0]):
                        motion_true_j2000[planet] = {
                            "longitude": float(j_coords[0]) % 360.0,
                            "frame": "mean_dynamical_ecliptic_equinox_J2000",
                        }

        # Ketu = exact 180° antipode of Rahu
        values["Ketu"] = combine_longitudes(values["Rahu"], 180.0)
        speeds["Ketu"] = speeds["Rahu"]
        body_models["Ketu"] = body_models["Rahu"]

        # Sidereal Ascendant & Midheaven + local apparent sidereal meridian
        cusps, ascmc = runtime.ephemeris_call(
            "houses_ex",
            jd_ut1,
            birth.latitude,
            birth.longitude,
            b"W",
            swe.FLG_SIDEREAL,
            _julian_day_tt=tt,
        )
        ascendant = float(ascmc[0]) % 360.0
        midheaven = float(ascmc[1]) % 360.0
        armc = float(ascmc[2]) % 360.0

    return {
        "ayanamsa": ayanamsa,
        "ayanamsha": float(ayanamsha),
        "ayanamsa_id": ayanamsa_id,
        "ascendant": ascendant,
        "midheaven": midheaven,
        "armc": armc,
        "local_apparent_sidereal_meridian": armc,
        "house_cusps": [float(c) % 360.0 for c in cusps[:12]],
        "longitudes": values,
        "speeds": speeds,
        "equatorial": equatorial,
        "motion_true_j2000": motion_true_j2000,
        "cheshta_model": cheshta_model,
        "node_mode": node_mode,
        "ephemeris_policy": ephemeris_policy,
        "ephemeris_models": sorted(models),
        "ephemeris_by_body": body_models,
        "physical_ephemeris_source": models.pop() if len(models) == 1 else "mixed",
        "julian_day_ut": jd_ut1,
        "julian_day_ut1": jd_ut1,
        "julian_day_tt": jd_tt,
        "julian_day_utc": float(birth.utc_calendar.julian_day()),
        "time_scale_context": {
            "method": times.method,
            "future_leap_seconds_assumed_unchanged": times.future_leap_seconds_assumed_unchanged,
        },
        "swisseph_version": str(swe.version),
    }

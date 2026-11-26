"""Auditable Guolao research chart, with astronomy and classical rules separated.

The modern equatorial anchor set is explicit, unequal, epoch-dependent, and is
NOT claimed to reconstruct the mansion boundaries of the cited printed edition.
The older Moira DSL is retained as a separately identified compatibility layer.
"""

from __future__ import annotations

import hashlib
import json
import math
from bisect import bisect_right
from dataclasses import replace
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

from fatebridge.core.almanac import get_bazi_year
from fatebridge.core.astro import runtime
from fatebridge.core.astro.astrology_tables import (
    ELEMENT_BY_SIGN,
    MODALITY_BY_SIGN,
    SIGN_LABELS_ZH,
)
from fatebridge.core.astro.birth import AstroBirthInfo, require_resolved_birth_timezone
from fatebridge.core.astro.earth_attitude import earth_attitude
from fatebridge.core.astro.geometry import _degree_in_sign, _sign_name, _week_ruler
from fatebridge.core.astro.longitude_motion import corrected_longitude_motion
from fatebridge.core.astro.native_coordinates import (
    require_altitude,
    require_spherical_coordinates,
)
from fatebridge.core.astro.native_motion import require_longitude_speed
from fatebridge.core.astro.parts import _build_houses, _build_planet_record
from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
from fatebridge.core.astro.profiles import (
    _resolve_core_chart_house_system,
    _resolve_core_chart_zodiacal_mode,
)
from fatebridge.core.astro.reference_frames import Matrix, rotate_spherical
from fatebridge.core.astro.source_session import coherent_ephemeris_sources
from fatebridge.core.calendar import BaZiCalendar
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.core.fixed_star_paths import fixed_star_catalogue
from fatebridge.core.guolao import guolao_classical, guolao_moira
from fatebridge.core.guolao.guolao_anchor_days import (
    DAY_RULESET,
    POLICIES,
    apparent_solar_day_anchor,
)
from fatebridge.core.guolao.guolao_birth_clock import (
    apparent_clock_required,
    solar_input_context,
)
from fatebridge.core.guolao.guolao_clock import apparent_solar_clock
from fatebridge.core.guolao.guolao_epoch import (
    birth_time_scales,
    birth_utc_label,
    native_birth_epoch,
    native_year_context,
)
from fatebridge.core.guolao.guolao_geometry import reference_geometry
from fatebridge.core.guolao.guolao_moira_native import (
    MoiraNativeProvider,
    native_source_facts,
)
from fatebridge.core.guolao.guolao_moira_provider import (
    MoiraCalendarFacts,
    resolve_source_provider_facts,
)
from fatebridge.core.guolao.guolao_moira_rules import (
    CompiledProfile,
    evaluate_source_profile,
    pattern_records,
)
from fatebridge.core.jpl_ephemeris import configured_jpl_file
from fatebridge.utils.civil_time import utc_calendar
from fatebridge.utils.errors import EphemerisSourceError
from fatebridge.utils.timezones import validate_local_clock

RULESET = "guolao_research_v7"
DATA = Path(__file__).resolve().parents[2] / "data" / "guolao"
EDITION = "tohoku_luwei_10020000001141"
EDITION_URL = "https://touda.tohoku.ac.jp/collection/en/database/library/10020000001141"
# Independently transcribed from volume 1, images 6 and 10 (not Western dignity).
PALACE_BRANCHES = [
    "戌",
    "酉",
    "申",
    "未",
    "午",
    "巳",
    "辰",
    "卯",
    "寅",
    "丑",
    "子",
    "亥",
]
PALACE_LORDS = ["火", "金", "水", "月", "日", "水", "金", "火", "木", "土", "土", "木"]
MANSION_NAMES = list("角亢氐房心尾箕斗牛女虚危室壁奎娄胃昴毕觜参井鬼柳星张翼轸")
MANSION_LORDS = dict(zip((n + "宿" for n in MANSION_NAMES), list("木金土日月火水") * 4))
CN = dict(
    Sun="日", Moon="月", Mercury="水", Venus="金", Mars="火", Jupiter="木", Saturn="土"
)
GENERATES = dict(zip("木火土金水", "火土金水木"))
OVERCOMES = dict(zip("木土水火金", "土水火金木"))


def relation(target: str, other: str) -> str:
    """Directional 五星生克: `other` acts on the designated target lord."""
    if target == other:
        return "同主"
    if target not in GENERATES or other not in GENERATES:
        return "未分配"
    if GENERATES[other] == target:
        return "生我"
    if OVERCOMES[other] == target:
        return "克我"
    if GENERATES[target] == other:
        return "我生"
    return "我克"


def mansion_at(
    right_ascension: float | Fraction, boundaries: list[dict[str, Any]]
) -> dict[str, Any]:
    """Half-open intervals on actual RA, sorted anew at the requested epoch.

    Do not subtract then modulo before locating the interval: that can round a
    value immediately below a boundary onto it. No arbitrary cusp tolerance.
    """
    ordered = sorted(boundaries, key=lambda b: b["right_ascension"])
    values = [b["right_ascension"] for b in ordered]
    if (
        len(ordered) != 28
        or len(set(values)) != 28
        or not all(math.isfinite(v) and 0 <= v < 360 for v in values)
        or not math.isfinite(right_ascension)
    ):
        raise ValueError("宿界须为28个不同的有限赤经")
    starts = [Fraction(v) for v in values]
    exact_ra = Fraction(right_ascension) % 360
    ra = min(float(exact_ra), math.nextafter(360.0, 0.0))
    index = (bisect_right(starts, exact_ra) - 1) % 28
    edge, end = ordered[index], ordered[(index + 1) % 28]
    exact_width = (
        Fraction(end["right_ascension"]) - Fraction(edge["right_ascension"])
    ) % 360
    width = float(exact_width)
    offset = min(
        float((exact_ra - Fraction(edge["right_ascension"])) % 360),
        math.nextafter(width, 0.0),
    )
    return {
        "su28": edge["su28"],
        "degree_lord": MANSION_LORDS[edge["su28"]],
        "right_ascension": ra,
        "degree_in_mansion": offset,
        "mansion_width": width,
        "boundary_distance": float(
            min(
                (exact_ra - Fraction(edge["right_ascension"])) % 360,
                (Fraction(end["right_ascension"]) - exact_ra) % 360,
            )
        ),
        "determinative_star": edge["star"],
        "coordinate_unit": "modern_degree_360",
        "placement_basis": "modern_equatorial_research_anchors_v1",
    }


def season(solar_longitude: float) -> str:
    """Northern traditional solar seasons, starting at 315/45/135/225 deg."""
    return ["春", "夏", "秋", "冬"][
        int(((Fraction(solar_longitude) % 360 + 45) % 360) // 90)
    ]


def positions(
    birth: AstroBirthInfo,
    *,
    hsys: int | str | None = None,
    zodiacal: int | str | None = None,
    observer_geometry: bool = True,
    correct_motion: bool = True,
) -> dict[str, Any]:
    """Compute positions and optional source-derived longitude-rate corrections."""
    if runtime.swe is None:
        raise ValueError("果老研究盘需要 Swiss Ephemeris；不以近似轨道生成宿度和格局。")
    native = native_birth_epoch(birth)
    if native is None:
        validate_local_clock(birth.local_datetime)
    swe = runtime.swe
    hi = _resolve_core_chart_house_system(hsys, chart_variant="guolao_chart")
    zi = _resolve_core_chart_zodiacal_mode(zodiacal, chart_variant="guolao_chart")
    states: dict[str, Any] = {}
    models: set[str] = set()
    body_provenance = {}
    nonphysical_flags = {}
    motion_metadata: dict[str, Any] = {}
    source_bytes = (DATA / "sources.json").read_bytes()
    sources = json.loads(source_bytes.decode("utf-8"))
    catalogue_bytes = (DATA / "sefstars.txt").read_bytes()
    catalogue_hash = hashlib.sha256(catalogue_bytes).hexdigest()
    if catalogue_hash != sources["catalogue_sha256"]:
        raise ValueError("果老距星表与来源指纹不一致")
    with runtime.preserve_ephemeris_path():
        # Swiss C state may be thread-local; initialize inside this worker.
        selected_path = configured_ephemeris_path()
        selected_jpl = configured_jpl_file()
        path = selected_path or ""
        swe.set_ephe_path(path)
        times = birth_time_scales(birth)
        if times.tt is None:
            raise ValueError("果老研究盘需要可用的TT/UT1转换")
        tt, ut = times.tt, times.ut1
        # Native coordinates keep their scalar source epoch; only the
        # physical target geometry consumes the retained TT point.
        jd_tt = tt.as_float()
        flags = swe.FLG_SWIEPH | swe.FLG_SPEED
        motion_sources = PhysicalEphemerisTrace()
        for name in CN:
            ecliptic, flag = runtime.ephemeris_call(
                "calc", jd_tt, getattr(swe, name.upper()), flags
            )
            longitude, latitude, _ = require_spherical_coordinates(
                ecliptic, flag, native=swe
            )
            require_longitude_speed(ecliptic, flag, swe.FLG_SPEED)
            model = runtime.ephemeris_model_from_retflag(flag)
            motion_sources.observe(name, model)
            equatorial, eq_flag = runtime.ephemeris_call(
                "calc",
                jd_tt,
                getattr(swe, name.upper()),
                flags | swe.FLG_EQUATORIAL,
            )
            right_ascension, declination, _ = require_spherical_coordinates(
                equatorial, eq_flag, native=swe, equatorial=True
            )
            equatorial_model = runtime.ephemeris_model_from_retflag(eq_flag)
            if model != equatorial_model:
                raise EphemerisSourceError("coordinate_model_changed")
            motion_sources.observe(name, equatorial_model)
            models.update((model, equatorial_model))
            body_provenance[name] = {
                "ecliptic_model": model,
                "equatorial_model": equatorial_model,
                "ecliptic_return_flags": int(flag),
                "equatorial_return_flags": int(eq_flag),
            }
            states[name] = {
                "longitude": longitude % 360,
                "latitude": latitude,
                "longitude_speed": float(ecliptic[3]),
                "right_ascension": right_ascension % 360,
                "declination": declination,
            }
            if correct_motion:
                states[name].update(
                    corrected_longitude_motion(
                        name,
                        jd_tt,
                        ecliptic,
                        model,
                        source_trace=motion_sources,
                        context=motion_metadata,
                    )
                )
                states[name][
                    "longitude_speed_reference_frame"
                ] = "tropical_ecliptic_of_date"
        # This read set concerns the seven physical states and derivative
        # probes. The subsequent star-observer transaction has its own receipt.
        motion_metadata.update(
            reference_frame="tropical_ecliptic_of_date",
            unit="degree_per_day",
            physical_ephemeris_source=motion_sources.finish(),
            scope="Source-derived physical-body longitude-rate corrections with native rates retained. The separate zodiac_longitude is a display placement; these rates remain tropical. Analytical/symbolic extras are unmodified. Not full motion, station-time, classical-rule or prediction certification.",
        )
        if correct_motion and "moshier" in models:
            motion_metadata["scope"] += (
                " Moshier rates differentiate its own analytical positions;"
                " this does not remove the underlying physical-model error."
            )
        if not correct_motion:
            motion_metadata.update(
                status="not_requested",
                scope="Position-only consumer did not request rate corrections. Native rates are retained without a precision claim; no auxiliary derivative epochs are evaluated. Physical-position source checks still apply.",
            )
        extra: dict[str, Any] = {}
        for name, body in [("罗", swe.MEAN_NODE), ("孛", swe.MEAN_APOG)]:
            coords, flag = runtime.ephemeris_call("calc", jd_tt, body, flags)
            longitude, latitude, _ = require_spherical_coordinates(
                coords, flag, native=swe
            )
            speed = require_longitude_speed(coords, flag, swe.FLG_SPEED)
            eq, eq_flag = runtime.ephemeris_call(
                "calc", jd_tt, body, flags | swe.FLG_EQUATORIAL
            )
            right_ascension, _, _ = require_spherical_coordinates(
                eq, eq_flag, native=swe, equatorial=True
            )
            nonphysical_flags[name] = {
                "ecliptic": int(flag),
                "equatorial": int(eq_flag),
            }
            extra[name] = {
                "longitude": longitude % 360,
                "latitude": latitude,
                "right_ascension": right_ascension % 360,
                "longitude_speed": speed,
                "model": "mean_lunar_node" if name == "罗" else "mean_lunar_apogee",
            }
        extra["计"] = {
            **extra["罗"],
            "longitude": float((Fraction(extra["罗"]["longitude"]) + 180) % 360)
            % 360.0,
            "right_ascension": float(
                (Fraction(extra["罗"]["right_ascension"]) + 180) % 360
            )
            % 360.0,
            "latitude": -extra["罗"]["latitude"],
            "model": "opposite_mean_lunar_node",
            "derived_from": "罗",
            "derivation_source_longitude": extra["罗"]["longitude"],
            "derivation_source_right_ascension": extra["罗"]["right_ascension"],
        }
        purple = guolao_moira.purple_clouds_longitude(ut.as_float())
        obliquity, obliquity_flag = runtime.ephemeris_call("calc", jd_tt, swe.ECL_NUT)
        # ECL_NUT is a four-angle pseudo-body, not spherical coordinates; its
        # return value does not identify a physical ephemeris model.
        if (
            obliquity_flag < 0
            or len(obliquity) < 4
            or not all(math.isfinite(value) for value in obliquity[:4])
        ):
            raise EphemerisSourceError("coordinate_values_unavailable")
        purple_ra, _, _ = swe.cotrans((purple, 0, 1), -obliquity[0])
        extra["炁"] = {
            "longitude": purple,
            "latitude": 0.0,
            "right_ascension": purple_ra,
            "longitude_speed": guolao_moira.PURPLE_CLOUDS_RATE_DEG_PER_DAY,
            "model": guolao_moira.PURPLE_CLOUDS_MODEL_ID,
        }
        asc = mc = asc_ra = altitude = None
        cusps = ()
        if observer_geometry:
            _, altitude, _ = runtime.ephemeris_call(
                "azalt",
                ut,
                swe.EQU2HOR,
                (birth.longitude, birth.latitude, 0),
                0,
                0,
                (states["Sun"]["right_ascension"], states["Sun"]["declination"], 1),
                _julian_day_tt=tt,
            )
            require_altitude(altitude)
        solar_clock = None
        solar_clock_native_to_physical: Matrix | None = None
        if observer_geometry and apparent_clock_required(birth):
            attitude = earth_attitude(swe, ut, julian_day_tt=tt)
            solar_clock_native_to_physical = attitude.reduction.native_to_target
            solar_ra, _ = rotate_spherical(
                solar_clock_native_to_physical,
                states["Sun"]["right_ascension"],
                states["Sun"]["declination"],
            )
            solar_clock = apparent_solar_clock(
                julian_day_ut1=ut,
                sun_right_ascension=solar_ra,
                greenwich_apparent_sidereal_degrees=runtime.ephemeris_call(
                    "sidtime", ut, _julian_day_tt=tt
                )
                * 15,
                longitude=birth.longitude,
                civil_datetime=birth.local_datetime,
            )
            solar_clock["equatorial_frame"] = (
                "selected_physical_equator_and_equinox_of_date"
            )
            if native is not None:
                solar_clock["reference_clock_basis"] = (
                    "explicit_solar_label_ordinal_reference_not_civil_instant"
                )
                solar_clock["total_correction_scope"] = (
                    "apparent_label_minus_input_solar_label_not_a_civil_epoch_shift"
                )
        ayanamsha = 0.0
        zodiac_layout: dict[str, Any] = {
            "ascendant": asc,
            "midheaven": mc,
            "house_cusps": list(cusps),
            "method": "swisseph_houses_ex_tropical",
        }
        if zi["sidereal"] and not observer_geometry:
            # A target sky needs no observer location, ASC or house partition.
            swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
            flag, ayanamsha = runtime.ephemeris_call(
                "get_ayanamsa_ex", jd_tt, swe.FLG_SWIEPH
            )
            if flag < 0 or not math.isfinite(ayanamsha):
                raise ValueError("目标时刻Lahiri偏移计算失败")
        if observer_geometry:
            zodiac_layout = reference_geometry(
                jd_ut1=ut,
                tt=tt,
                latitude=birth.latitude,
                longitude=birth.longitude,
                house_info=hi,
                sidereal=zi["sidereal"],
            )
            ayanamsha = zodiac_layout["ayanamsha"]
            asc, mc = (
                zodiac_layout["tropical_ascendant"],
                zodiac_layout["tropical_midheaven"],
            )
            cusps = zodiac_layout["house_cusps"]
            if asc is not None:
                asc_ra, _, _ = swe.cotrans((asc, 0, 1), -obliquity[0])
        # The star flag may echo SWIEPH even with an analytical Earth.
        with fixed_star_catalogue(swe, catalogue_bytes):
            earth, earth_flags = runtime.ephemeris_call(
                "calc", jd_tt, swe.EARTH, swe.FLG_SWIEPH | swe.FLG_HELCTR
            )
            if earth_flags < 0 or not all(math.isfinite(v) for v in earth):
                raise EphemerisSourceError("coordinate_values_unavailable")
            boundaries = []
            star_flags = set()
            for index, star in enumerate(sources["stars"]):
                coord, _, flag = runtime.ephemeris_call(
                    "fixstar2",
                    f"FBJ{index:02}",
                    jd_tt,
                    swe.FLG_SWIEPH | swe.FLG_EQUATORIAL,
                )
                right_ascension, _, _ = require_spherical_coordinates(
                    coord, flag, native=swe, equatorial=True
                )
                star_flags.add(int(flag))
                boundaries.append(
                    {
                        "su28": star["mansion"],
                        "star": star["star"],
                        "right_ascension": right_ascension % 360,
                    }
                )
        if (
            configured_ephemeris_path() != selected_path
            or configured_jpl_file() != selected_jpl
        ):
            raise EphemerisSourceError("physical_configuration_changed")
    return {
        "states": states,
        "extra": extra,
        "boundaries": boundaries,
        "ascendant": asc,
        "ascendant_ra": asc_ra,
        "midheaven": mc,
        "cusps": list(cusps),
        "zodiac_house_layout": zodiac_layout,
        "ayanamsha": ayanamsha,
        "house_info": hi,
        "zodiac_info": zi,
        "julian_day_tt": jd_tt,
        "julian_day_ut1": ut.as_float(),
        "_ut1_instant": ut,
        "time_conversion": times.method,
        "future_leap_seconds_assumed_unchanged": times.future_leap_seconds_assumed_unchanged,
        "solar_altitude": altitude,
        "solar_clock": solar_clock,
        "_solar_clock_native_to_physical": solar_clock_native_to_physical,
        "models": sorted(models),
        "longitude_motion": motion_metadata,
        "ephemeris_provenance": {
            "physical_backend_policy": "strict_jpl" if selected_jpl else "auto",
            "physical_model_scope": "seven_bodies_ecliptic_and_equatorial",
            "by_body": body_provenance,
            "nonphysical_factor_models": {
                name: state["model"] for name, state in extra.items()
            },
            "nonphysical_return_flags": nonphysical_flags,
            "fixed_star_observer_ephemeris_model": runtime.ephemeris_model_from_retflag(
                earth_flags
            ),
            "fixed_star_observer_return_flags": int(earth_flags),
            "fixed_star_native_return_flags": sorted(star_flags),
            "fixed_star_flag_scope": "native star flags and actual Earth observer model are separate; mean node/apogee flags do not identify physical vector files",
            "absolute_astronomical_accuracy_certified": False,
        },
        "catalogue_sha256": catalogue_hash,
        "catalogue_sources_sha256": hashlib.sha256(source_bytes).hexdigest(),
    }


def body_placement(
    name: str,
    state: dict[str, Any],
    boundaries: list[dict[str, Any]],
    ayanamsha: float,
) -> dict[str, Any]:
    """The same declared palace/mansion mapping for natal and target skies."""
    chinese = CN.get(name, name)
    source_longitude = Fraction(state["longitude"])
    right_ascension = Fraction(state["right_ascension"])
    if state.get("derived_from") == "罗":
        # The displayed antipode can round across a palace or mansion edge.
        # Preserve the exact native source through both discrete decisions.
        source_longitude = (Fraction(state["derivation_source_longitude"]) + 180) % 360
        right_ascension = (
            Fraction(state["derivation_source_right_ascension"]) + 180
        ) % 360
    # Compare the exact supplied doubles before rounding the rotated value.
    # A tiny negative remainder otherwise rounds to 360 and indexes palace 12.
    exact = (source_longitude - Fraction(ayanamsha)) % 360
    index = int(exact // 30)
    longitude = min(float(exact), math.nextafter(float(30 * (index + 1)), -math.inf))
    mansion = mansion_at(right_ascension, boundaries)
    lord = PALACE_LORDS[index]
    return {
        "id": name,
        "name_zh": chinese,
        **state,
        "zodiac_longitude": longitude,
        "palace_branch": PALACE_BRANCHES[index],
        "palace_lord": lord,
        "mansion": mansion,
        "in_own_palace": chinese == lord,
        "in_own_mansion": chinese == mansion["degree_lord"],
    }


@coherent_ephemeris_sources
def build_chart(
    birth: AstroBirthInfo,
    *,
    hsys: int | str | None = None,
    zodiacal: int | str | None = None,
    seasonal_anchor_policy: str | None = None,
    moira_profile: CompiledProfile | None = None,
    moira_provider: MoiraNativeProvider | None = None,
) -> dict[str, Any]:

    if seasonal_anchor_policy is not None and seasonal_anchor_policy not in POLICIES:
        raise ValueError("未知果老安命交节政策")
    if seasonal_anchor_policy in POLICIES[1:] and not apparent_clock_required(birth):
        raise ValueError("太阳日安命须明确use_true_solar_time=true")
    if moira_provider is not None:
        if moira_profile is None:
            raise ValueError("Moira源提供器须与显式源规则profile一起选择")
        if (
            moira_provider.profile.source_commit != moira_profile.source_commit
            or moira_provider.profile.source_property_sha256
            != moira_profile.source_property_sha256
        ):
            raise ValueError("Moira规则与提供器须来自同一已声明源版本")
    require_resolved_birth_timezone(birth.timezone_source)
    if birth.recorded_datetime is not None:
        birth = replace(
            birth,
            local_datetime=birth.recorded_datetime,
            utc_datetime=utc_calendar(birth.recorded_datetime).as_datetime(),
        )
    raw = positions(birth, hsys=hsys, zodiacal=zodiacal)
    input_clock = solar_input_context(birth, raw)
    shift = raw["ayanamsha"]
    layout = raw["zodiac_house_layout"]
    asc, mc = layout["ascendant"], layout["midheaven"]
    hi, zi = raw["house_info"], raw["zodiac_info"]
    cusps = layout["house_cusps"]
    planets = []
    mansions = []
    signs = {}
    bodies = []
    moira_longitudes: dict[str, Fraction] = {}
    trace = []
    for name, state in list(raw["states"].items()) + list(raw["extra"].items()):
        body = body_placement(name, state, raw["boundaries"], shift)
        chinese = body["name_zh"]
        if moira_profile is not None:
            source_longitude = (
                Fraction(state["derivation_source_longitude"]) + 180
                if state.get("derived_from") == "罗"
                else Fraction(state["longitude"])
            )
            moira_longitudes[chinese] = (source_longitude - Fraction(shift)) % 360
        signs[chinese] = int(body["zodiac_longitude"] // 30)
        mansion = body["mansion"]
        mansions.append({"id": name, **mansion})
        palace_lord = body["palace_lord"]
        bodies.append(body)
        trace.append(
            {
                "rule_id": "palace_lord_and_mansion_lord",
                "source_id": EDITION,
                "locator": "卷一·宫分所属/入门看法·宫、度（图像6、10）",
                "subject": chinese,
                "inputs": {
                    "palace_branch": body["palace_branch"],
                    "su28": mansion["su28"],
                },
                "outputs": {
                    "palace_lord": palace_lord,
                    "degree_lord": mansion["degree_lord"],
                },
                "placement_classical_acceptance": False,
            }
        )
        if name in CN:
            if cusps:
                record = _build_planet_record(
                    name,
                    state["longitude"],
                    state["latitude"],
                    asc,
                    hi["key"],
                    house_cusps=cusps,
                    sidereal=zi["sidereal"],
                    ayanamsha=shift,
                    zodiac_longitude=body["zodiac_longitude"],
                )
            else:
                longitude = body["zodiac_longitude"]
                sign = _sign_name(longitude)
                record = {
                    "id": name,
                    "longitude": longitude,
                    "latitude": state["latitude"],
                    "sign": sign,
                    "sign_zh": SIGN_LABELS_ZH[sign],
                    "degree_in_sign": _degree_in_sign(longitude),
                    "house": None,
                    "element": ELEMENT_BY_SIGN[sign],
                    "modality": MODALITY_BY_SIGN[sign],
                }
            # No Western exaltation/fall labels are attributed to Guolao.
            record["dignity"] = None
            record["su28"] = mansion["su28"]
            planets.append(record)
    # Apply the edition's ordinal algorithm to declared research inputs. Neither
    # a palace branch nor an astronomical ASC establishes the original 命度.
    solar_clock = raw["solar_clock"]
    if input_clock and input_clock["hour_from_input_label"]:
        hour_branch = input_clock["input_hour_branch"]
        birth_clock = input_clock["input_wall_datetime"]
    elif apparent_clock_required(birth):
        if solar_clock is None:
            raise ValueError("请求真太阳钟面时必须有同次太阳/UT1计算，不以民用钟时补位")
        hour_branch = solar_clock["birth_hour_branch"]
        birth_clock = solar_clock["display"]
    else:
        hour_branch = guolao_classical.BRANCHES[
            ((birth.local_datetime.hour + 1) // 2) % 12
        ]
        birth_clock = birth.local_datetime.isoformat()
    sun_branch = PALACE_BRANCHES[signs["日"]]
    anchor = guolao_classical.counting_anchor(raw["states"]["Sun"]["longitude"])
    anchor_evidence = None
    if seasonal_anchor_policy in POLICIES[1:]:
        assert solar_clock is not None and seasonal_anchor_policy is not None
        anchor_evidence = apparent_solar_day_anchor(
            birth,
            birth_clock=solar_clock,
            birth_ut1=raw["_ut1_instant"],
            expected_sun_model=raw["ephemeris_provenance"]["by_body"]["Sun"][
                "ecliptic_model"
            ],
            birth_sun_source=raw["longitude_motion"]["physical_ephemeris_source"],
            policy=seasonal_anchor_policy,
        )
        anchor = anchor_evidence["anchor_branch"]
    ruleset_id = DAY_RULESET if anchor_evidence else RULESET
    life_branch = guolao_classical.life_branch(sun_branch, hour_branch, anchor)
    life_idx = PALACE_BRANCHES.index(life_branch)
    life = {
        "longitude": None,
        "branch": life_branch,
        "palace_lord": PALACE_LORDS[life_idx],
        "mansion": None,
        "method": "source_hour_count_with_declared_research_inputs_v1",
        "sun_palace_branch": sun_branch,
        "sun_palace_basis": "selected_modern_zodiac_30_degree_palaces_not_historical_calibration",
        "birth_hour_branch": hour_branch,
        "birth_clock": birth_clock,
        "clock_basis": (
            input_clock["hour_clock_basis"]
            if input_clock
            else (
                "apparent_solar_display"
                if birth.applied_true_solar
                else "recorded_civil_clock"
            )
        ),
        "counting_anchor_branch": anchor,
        "seasonal_anchor_policy": (
            seasonal_anchor_policy
            if anchor_evidence
            else "tropical_term_instants_half_open_270_300_90_105"
        ),
        **({"seasonal_anchor_evidence": anchor_evidence} if anchor_evidence else {}),
        "degree_status": "unresolved_no_ascendant_substitution",
        "degree_reason": "原典对度换算尚无法同时复现横看表和刊载算例，命度与命宿未裁定。",
    }
    trace.append(
        {
            "rule_id": "source_life_palace_hour_count",
            "source_id": EDITION,
            "locator": "卷一·安命、十二宫例（图像9）",
            "inputs": {
                "sun_palace_branch": sun_branch,
                "birth_hour_branch": hour_branch,
                "counting_anchor_branch": anchor,
                "clock_basis": life["clock_basis"],
                "sun_palace_basis": life["sun_palace_basis"],
                "seasonal_anchor_policy": life["seasonal_anchor_policy"],
                **(
                    {"seasonal_anchor_evidence": anchor_evidence}
                    if anchor_evidence
                    else {}
                ),
                **({"apparent_solar_clock": solar_clock} if solar_clock else {}),
            },
            "outputs": {
                "life_branch": life_branch,
                "degree_status": life["degree_status"],
            },
            "placement_classical_acceptance": False,
        }
    )
    # Only the LiChun year is a dependency of the year gods. Resolving all
    # four pillars also requests adjacent-year months and a late-Zi next day,
    # which can overflow even when this instant and its year are valid.
    native = native_birth_epoch(birth)
    native_year_evidence = None
    if native is not None:
        selected_year, native_year_evidence = native_year_context(birth)
    else:
        selected_year = get_bazi_year(birth.local_datetime, birth.timezone)
    year_stem, year_branch = BaZiCalendar.calculate_year_pillar(selected_year)
    is_day = raw["solar_altitude"] >= 0
    god_branches = guolao_classical.year_god_branches(year_stem, year_branch)
    gods = {
        name: PALACE_BRANCHES.index(branch) for name, branch in god_branches.items()
    }
    year_boundary_basis = "bazi_calendar_lichun_research_policy_not_source_adjudicated"
    god_positions = {
        **(
            {"native_year_comparison": native_year_evidence}
            if native_year_evidence
            else {}
        ),
        "year_stem": year_stem,
        "year_branch": year_branch,
        "year_boundary_basis": year_boundary_basis,
        "branches": god_branches,
        "aliases": {"天贵": "天乙（昼贵）", "玉贵": "玉堂（夜贵）"},
        "selected_noble": "天贵" if is_day else "玉贵",
        "selected_noble_branch": god_branches["天贵" if is_day else "玉贵"],
        "source_id": EDITION,
        "locator": "馆藏卷1–2·天乙/玉堂（图像33）、岁驾（图像34）",
    }
    trace.append(
        {
            "rule_id": "source_year_god_branches",
            "source_id": EDITION,
            "locator": god_positions["locator"],
            "inputs": {
                "year_stem": year_stem,
                "year_branch": year_branch,
                "year_boundary_basis": god_positions["year_boundary_basis"],
                "is_day": is_day,
            },
            "outputs": {
                "god_branches": god_branches,
                "selected_noble": god_positions["selected_noble"],
                "selected_noble_branch": god_positions["selected_noble_branch"],
            },
            "placement_classical_acceptance": False,
        }
    )
    current_season = season(raw["states"]["Sun"]["longitude"])
    pattern_model_id = guolao_moira.PATTERN_MODEL_ID
    pattern_scope = "software_compatibility_conditions_not_classical_pattern_acceptance"
    pattern_inputs: dict[str, object] = {
        "life_sign_idx": life_idx,
        "planet_signidx": signs,
        "god_signidx": gods,
        "is_day": is_day,
        "is_winter": current_season == "冬",
    }
    source_evaluation = None
    source_provider_record = None
    patterns: list[dict[str, object]]
    if moira_profile is None:
        patterns = guolao_moira.calculate(pattern_inputs)
    else:

        source_provider = None
        if moira_provider is not None:

            calendar = moira_provider.calendar
            if calendar is None:
                calendar = MoiraCalendarFacts(
                    year_pillar=year_stem + year_branch,
                    hour_branch=hour_branch,
                    provenance={
                        "policy_id": "fatebridge_existing_guolao_year_hour_inputs_v1",
                        "year_basis": year_boundary_basis,
                        "hour_basis": life["clock_basis"],
                        "original_moira_calendar": "not_reproduced",
                        "month_lunar_day": "unresolved_not_filled_from_solar_season",
                    },
                )
            source_provider = resolve_source_provider_facts(
                profile=moira_provider.profile,
                calendar=calendar,
                longitudes=moira_longitudes,
                is_day=is_day,
            )
            source_provider_record = {
                "profile_id": moira_provider.profile.profile_id,
                "source_commit": moira_provider.profile.source_commit,
                "source_url": moira_provider.profile.source_url,
                "calendar": {
                    "year_pillar": calendar.year_pillar,
                    "month_pillar": calendar.month_pillar,
                    "hour_branch": calendar.hour_branch,
                    "lunar_day": calendar.lunar_day,
                    "provenance": dict(calendar.provenance),
                },
                "known_absent": list(source_provider.known_absent),
                "provenance": dict(source_provider.facts.provenance),
                "scope": "explicit source god/calendar facts; modern star backend not admitted",
            }
        source_facts = native_source_facts(
            longitudes=moira_longitudes,
            palace_indices=signs,
            life_sign_index=life_idx,
            god_sign_indices=gods,
            is_day=is_day,
            season=current_season,
            source_provider=source_provider,
        )
        source_evaluation = evaluate_source_profile(source_facts, profile=moira_profile)
        patterns = [dict(record) for record in pattern_records(source_evaluation)]
        pattern_model_id = moira_profile.profile_id
        pattern_scope = "source_rule_graph_with_explicit_partial_native_facts_not_classical_acceptance"
        pattern_inputs = {
            "palaces": dict(source_facts.palaces),
            "mansions": dict(source_facts.mansions),
            "strings": dict(source_facts.strings),
            "booleans": dict(source_facts.booleans),
            "unavailable": dict(source_facts.unavailable),
            "provenance": dict(source_facts.provenance),
        }
    for pattern in patterns:
        pattern["classical_acceptance"] = False
        pattern["basis"] = (
            "moira_source_graph_with_declared_research_facts"
            if moira_profile is not None
            else "moira_compatibility_with_source_hour_count_and_research_placements"
        )
    trace.append(
        {
            "rule_id": pattern_model_id,
            "source_id": "moira_software_conditions",
            "inputs": pattern_inputs,
            "outputs": {
                "matched_patterns": [
                    {
                        "name": p["name"],
                        "rule_id": p["rule_id"],
                        "source": p["source"],
                        "evidence": p["evidence"],
                    }
                    for p in patterns
                ],
                "scope": pattern_scope,
            },
            "placement_classical_acceptance": False,
        }
    )
    palace_records = []
    branches = guolao_classical.palace_branches(life_branch)
    trace.append(
        {
            "rule_id": "source_reverse_twelve_palaces",
            "source_id": EDITION,
            "locator": "卷一·十二宫例（图像9）",
            "inputs": {"life_branch": life_branch},
            "outputs": {"palace_branches": branches},
            "placement_classical_acceptance": False,
        }
    )
    for name, branch in branches.items():
        idx = PALACE_BRANCHES.index(branch)
        lord = PALACE_LORDS[idx]
        palace_records.append(
            {
                "palace": name,
                "branch": PALACE_BRANCHES[idx],
                "lord": lord,
                "lord_sign_index": signs[lord],
                "lord_relations": {p: relation(lord, p) for p in "木火土金水"},
            }
        )
    missing = [
        "安命顺数与二至例外已按底本转录；太阳宫仍为所选现代30度黄道，钟时与交节端点为明示研究约定",
        "原典命度、晨昏度法尚未重建；命度/命宿留空，不以ASC替代",
        "现代赤经距星宿界不等同底本宿界；未将古度按比例强制归一化",
        "紫气采用具名Horosa均行虚点公式；已找到古今律历考的历元策数与周积舍入问题，但未校准原典现代黄经，不能只改周期或强制归一化",
        "天乙/玉堂与岁驾已按底本校勘；年干支暂用八字立春换年，其他神煞尚未逐项校勘",
        "可选目标时刻仅提供原页小限逆数及当时十一曜研究位置；洞微大限、童限和完整流年判断尚未实现",
        "无独立前瞻现实样本，现实预测效力尚未验证",
    ]
    if layout["availability"]["houses_status"] != "available":
        missing.insert(
            0,
            "所选天文参考宫头不可用，行星参考落宫留空且未换用其他宫制；七政四余、研究宿位与逆布功能宫仍有效",
        )
    moon = next(m for m in mansions if m["id"] == "Moon")
    guolao = {
        "lunar_mansion_system": "modern_equatorial_research_anchors_v1",
        "weekday_ruler": _week_ruler(birth.local_datetime),
        "planetary_mansions": mansions,
        "moon_mansion": moon["su28"],
        "si_yu_sign_index": {k: signs[k] for k in "孛罗计炁"},
        "god_sign_index": gods,
        "god_positions": god_positions,
        "purple_model_audit": {
            "model_in_use": guolao_moira.PURPLE_CLOUDS_MODEL_ID,
            "period_days": guolao_moira.PURPLE_CLOUDS_PERIOD_DAYS,
            "epoch_jd": guolao_moira.PURPLE_CLOUDS_EPOCH_JD,
            "epoch_longitude": guolao_moira.PURPLE_CLOUDS_EPOCH_LONGITUDE,
            "software_source_url": guolao_moira.PURPLE_CLOUDS_SOURCE_URL,
            "software_source_commit": guolao_moira.PURPLE_CLOUDS_SOURCE_COMMIT,
            "software_source_function": "pcLon",
            "fixture_fitting_used": False,
            "source_id": "xing_yunlu_gujinlvlikao_58",
            "source_epoch_description": "至元辛巳天正冬至（1280年末），以箕初为周行原点；非现代UTC历元",
            "source_validation_status": "selected_facsimile_pages_and_28_purple_intervals_collated_modern_epoch_unresolved",
            "source_period_days": "10227.1792",
            "source_offset_days": "1256.5224",
            "source_days_per_historical_du": "28",
            "source_circle_historical_du": "365.2575",
            "source_circle_basis": "author_reference_circle_not_printed_purple_table",
            "source_printed_circle_historical_du": "365.2564",
            "source_printed_xu_width_du": "9.0064",
            "source_facsimile_locator": "四库787-635、642、643、647；完整紫气立成与年份异文已留图，非全书校勘",
            "source_corrected_period_days": "10227.21",
            "source_rounding_discrepancy_days": "0.0308",
            "modern_epoch_calibration_status": "unresolved",
            "historical_period_used_as_modern_longitude": False,
            "corrected_offset_recalibrated": False,
        },
        "moira_patterns": patterns,
        "bodies": bodies,
        "timing": {"status": "not_requested"},
        "life_palace": life,
        "palaces": palace_records,
        "conditions": {
            "is_day": is_day,
            "solar_altitude": raw["solar_altitude"],
            "day_night_basis": "geocentric_solar_center_geometric_altitude_ge_0_no_refraction",
            "season": current_season,
            "season_basis": "northern_solar_terms_315_45_135_225",
        },
        "profile": {
            "ruleset_id": ruleset_id,
            "pattern_model_id": pattern_model_id,
            "calendar": "proleptic_gregorian",
            "utc_datetime": birth_utc_label(birth),
            **(
                {
                    "native_time_axis": {
                        **native.representation(),
                        "julian_day_tt": native.time.jd_tt,
                        "julian_day_ut1": native.time.jd_ut1,
                    }
                }
                if native
                else {}
            ),
            "julian_day_tt": raw["julian_day_tt"],
            "julian_day_ut1": raw["julian_day_ut1"],
            "time_conversion": raw["time_conversion"],
            "future_leap_seconds_assumed_unchanged": raw[
                "future_leap_seconds_assumed_unchanged"
            ],
            "solar_clock_display": (solar_clock["display"] if solar_clock else None),
            **({"apparent_solar_clock": solar_clock} if solar_clock else {}),
            "solar_clock_changes_instant": False,
            **({"input_clock": input_clock} if input_clock else {}),
            "ephemeris_models": raw["models"],
            "ephemeris_provenance": raw["ephemeris_provenance"],
            "longitude_motion": raw["longitude_motion"],
            "mansion_unit": "360 modern degrees, not historical du",
            "anchor_order": "sorted_by_date_right_ascension_including_epoch_crossings",
            "astronomical_house_role": "angles_houses_and_planets_house_are_reference_only_not_functional_palaces",
            "astronomical_house_frame": (
                "selected_lahiri_sidereal_zodiac"
                if zi["sidereal"]
                else "tropical_zodiac"
            ),
            "astronomical_house_method": layout["method"],
            "reference_geometry": layout["availability"],
            "functional_palace_basis": "source_reverse_twelve_palaces_from_hour_count_life_branch",
        },
        "mansion_boundaries": raw["boundaries"],
        "rulesets": [
            {
                "id": ruleset_id,
                "edition_id": EDITION,
                "title": "新编评注通玄先生张果星宗大全，陆位辑校，卷一至二",
                "source_url": EDITION_URL,
                "verified_subset": "宫主/度主归属、五星生克、安命顺数与二至例外、逆布十二宫、小限逆数、天乙/玉堂/岁驾表；现代输入映射与全盘尚未验收",
            },
            {
                "id": "swiss_ephemeris_astronomy",
                "title": "Swiss Ephemeris Programmer's Manual",
                "source_url": "https://www.astro.com/swisseph/swephprg.htm",
                "verified_subset": "天文计算接口与时间尺度；不是果老原典认证",
            },
            {
                "id": "iers_leap_seconds",
                "title": "IERS Bulletin C leap-second table",
                "source_url": "https://hpiers.obspm.fr/iers/bul/bulc/Leap_Second.dat",
                "verified_subset": "冻结UTC/TT闰秒表；有效期外采用不变假设并回显",
            },
            {
                "id": "cds_simbad_research_anchors",
                "title": "CDS SIMBAD ICRS research anchor catalogue",
                "source_url": "https://simbad.cds.unistra.fr/simbad/",
                "verified_subset": "28颗研究锚星的天文参数；非底本历史距星认定",
            },
            {
                "id": "xing_yunlu_gujinlvlikao_58",
                "title": "古今律历考卷五十八，明邢云路撰，文渊阁四库影印787册",
                "source_url": "https://commons.wikimedia.org/w/index.php?curid=71219540",
                "verified_subset": "原页787-635、642、643、647的紫气至后策、完整刊表、周期及年份异文；未校准现代位置，不代替陆位本",
            },
        ],
        "rule_trace": trace,
        "validation": {
            "classical_acceptance_passed": False,
            "real_world_prediction_status": "not_tested",
            "full_marks_established": False,
            "limitations": missing,
        },
    }
    if source_evaluation is not None and moira_profile is not None:
        guolao["moira_rule_evaluation"] = source_evaluation.to_record()
        guolao["validation"]["limitations"].append(
            "完整Moira源规则解释器使用显式外置规则版本；原生事实缺项、未求值与可能抑制分别保留，不能将确定展示子集当作完整原软件或原典验收"
        )
        guolao["rulesets"].append(
            {
                "id": moira_profile.profile_id,
                "title": "Moira1.50Final explicit source-rule profile",
                "source_url": moira_profile.source_url,
                "verified_subset": "完整源声明目录与规则图；事实提供范围和独立比较结论分别记录",
            }
        )
    if source_provider_record is not None and moira_provider is not None:
        guolao["moira_source_provider"] = source_provider_record
        guolao["rulesets"].append(
            {
                "id": moira_provider.profile.profile_id,
                "title": "Moira1.50Final explicit natal god provider",
                "source_url": moira_provider.profile.source_url,
                "verified_subset": "源年/月/时表、分组、资格与别名；本次历法字段及缺项另列，不认证原历法或星位模型",
            }
        )
    if solar_clock:
        guolao["rulesets"].append(
            {
                "id": solar_clock["method_id"],
                "title": "USNO Equation of Time: apparent solar time from local hour angle",
                "source_url": solar_clock["source_url"],
                "verified_subset": "复用同次地心视太阳赤经与所选UT1视恒星角；两处独立JPL参照，不认证实测亚秒精度或原典钟时政策",
            }
        )

    if input_clock:
        guolao["weekday_ruler"] = _week_ruler(
            datetime.fromisoformat(input_clock["input_wall_datetime"])
        )
        guolao["rulesets"].append(
            {
                "id": input_clock["ruleset_id"],
                "title": "FateBridge explicit LMT/LAT input and physical-carrier separation",
                "source_url": "https://www.astro.com/swisseph/swephprg.htm",
                "verified_subset": "9.2/9.4时间尺度和太阳钟定义；时支标签与UTC载体分离为明示现代研究政策，未裁定底本历史钟制",
            }
        )
        guolao["rule_trace"].append(
            {
                "rule_id": input_clock["ruleset_id"],
                "source_id": "swiss_ephemeris",
                "locator": "9.2/9.4; FateBridge declared solar-label hour policy",
                "inputs": {
                    "input_clock_basis": input_clock["input_clock_basis"],
                    "input_wall_datetime": input_clock["input_wall_datetime"],
                    "true_solar_requested": birth.applied_true_solar,
                },
                "outputs": {
                    "converted_utc": birth_utc_label(birth),
                    "birth_hour_branch": hour_branch,
                    "clock_basis": life["clock_basis"],
                },
                "placement_classical_acceptance": False,
            }
        )

    def angle(value: float | None) -> dict[str, Any]:
        if value is None:
            return {"longitude": None, "sign": None, "sign_zh": None}
        return {
            "longitude": value,
            "sign": _sign_name(value),
            "sign_zh": SIGN_LABELS_ZH[_sign_name(value)],
        }

    return {
        "person_info": {
            "name": birth.name,
            "birth_place": birth.birth_place,
            "birth_timezone": None if input_clock else birth.timezone,
            "birth_longitude": birth.longitude,
            "birth_latitude": birth.latitude,
            "birth_datetime": (
                input_clock["input_wall_datetime"]
                if input_clock
                else birth.local_datetime.isoformat()
            ),
            "utc_datetime": birth_utc_label(birth),
            **({"clock_conversion": birth.clock_conversion} if input_clock else {}),
            "true_solar": {
                "applied": apparent_clock_required(birth),
                "correction_minutes": (
                    round(input_clock["additional_correction_to_input_seconds"] / 60, 4)
                    if input_clock
                    else (
                        round(solar_clock["total_correction_seconds"] / 60, 4)
                        if solar_clock
                        else birth.solar_correction_minutes
                    )
                ),
                "changes_instant": False,
            },
        },
        "chart_profile": {
            "chart_type": "guolao_chart",
            "zodiac": zi["zodiac"],
            "zodiacal": zi["value"],
            "zodiac_label_zh": zi["label_zh"],
            "ayanamsha": shift,
            "house_system": hi["key"],
            "house_system_code": hi["value"],
            "house_system_label_zh": hi["label_zh"],
            "house_system_source": hi.get("source", "explicit"),
            "tradition": True,
            "engine_precision": "ephemeris_runtime_model",
            "engine_backend": "swisseph_api",
            "ephemeris_model": raw["models"][0] if len(raw["models"]) == 1 else "mixed",
        },
        "angles": {"ascendant": angle(asc), "midheaven": angle(mc)},
        "houses": _build_houses(asc, hi["key"], house_cusps=cusps) if cusps else [],
        "planets": planets,
        "guolao": guolao,
    }

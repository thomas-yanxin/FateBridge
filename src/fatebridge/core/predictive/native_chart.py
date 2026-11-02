"""Full-precision chart facts for timing, without civil-as-UT1 adaptation.

The point attributes form the internal protocol consumed by timing/event
techniques. Every position uses the same TT/UT1 policy as the natal chart.
No third-party latitude clamping, second truncation or hidden ayanamsha.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict

from fatebridge.core.astro.angle_definitions import (
    native_ecliptic_horizon_angle_definition,
)
from fatebridge.core.astro.ephemeris import _swisseph_planet_state
from fatebridge.core.astro.geometry import (
    _house_for_longitude,
    combine_longitudes,
    is_prograde_house_partition,
    native_lahiri_ayanamsha,
    normalize_angle,
)
from fatebridge.core.astro.horizon import horizon_altitude
from fatebridge.core.astro.house_axes import canonical_house_geometry
from fatebridge.core.astro.house_positions import build_ecliptic_house_projection
from fatebridge.core.astro.physical_epoch import PhysicalEpoch
from fatebridge.core.astro.physical_sources import (
    PhysicalEphemerisTrace,
    assert_physical_configuration,
)
from fatebridge.core.astro.profiles import physical_ephemeris_summary
from fatebridge.core.astro.reference import PLANET_SEQUENCE
from fatebridge.core.astro.reference_points import ephemeris_reference_points
from fatebridge.core.astro.solar_position import apparent_position_policy
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.astro_models import earth_rotation_policy
from fatebridge.core.astrology_tables import SIGNS
from fatebridge.core.ephemeris_runtime import (
    configured_ephemeris_path,
    ephemeris_call,
    preserve_ephemeris_path,
)
from fatebridge.utils.timezones import parse_timezone_name, validate_local_clock

HOUSE_ATTRIBUTES = (
    "first_house",
    "second_house",
    "third_house",
    "fourth_house",
    "fifth_house",
    "sixth_house",
    "seventh_house",
    "eighth_house",
    "ninth_house",
    "tenth_house",
    "eleventh_house",
    "twelfth_house",
)
HOUSE_NAMES = tuple(name.title() for name in HOUSE_ATTRIBUTES)


@dataclass(frozen=True)
class NativePoint:
    name: str
    abs_pos: float
    position: float
    sign: str
    sign_num: int
    house: str
    retrograde: bool = False
    speed: float = 0.0
    latitude: float = 0.0
    declination: float | None = None


@dataclass(frozen=True)
class NativeSubject:
    name: str
    lng: float
    lat: float
    tz_str: str
    iso_formatted_utc_datetime: str | None
    iso_formatted_local_datetime: str | None
    julian_day: float  # UT1, never the civil-clock JD
    julian_day_tt: float
    houses_system_identifier: str
    zodiac_type: str
    sidereal_mode: str | None
    is_diurnal: bool
    points: Dict[str, NativePoint]
    calculation_basis: Dict[str, Any]

    def __getattr__(self, name: str) -> NativePoint:
        try:
            return self.points[name]
        except KeyError:
            raise AttributeError(name) from None


@preserve_ephemeris_path()
def build_native_subject(
    *,
    name: str,
    local_datetime: datetime | None = None,
    longitude: float,
    latitude: float,
    timezone_name: str,
    house_system: str = "P",
    zodiac_type: str = "Tropic",
    physical_epoch: PhysicalEpoch | None = None,
) -> NativeSubject:
    if (local_datetime is None) == (physical_epoch is None):
        raise ValueError("Supply exactly one civil datetime or physical epoch")
    chart_timezone = parse_timezone_name(timezone_name)
    if local_datetime is not None and local_datetime.utcoffset() is None:
        local_datetime = local_datetime.replace(tzinfo=chart_timezone)
        validate_local_clock(local_datetime)
    if not math.isfinite(longitude) or not -180 <= longitude <= 180:
        raise ValueError("Invalid chart longitude")
    if not math.isfinite(latitude) or not -90 < latitude < 90:
        raise ValueError("Chart latitude must be strictly between the geographic poles")
    if zodiac_type not in {"Tropic", "Tropical", "Sidereal"}:
        raise ValueError("Unsupported zodiac_type; use Tropic, Tropical or Sidereal")
    # Swiss distinguishes the two Sunshine variants I/i.
    code = house_system if house_system == "i" else house_system.upper()
    if len(code) != 1 or not code.isascii():
        raise ValueError(
            "Timing house system must resolve to one Swiss Ephemeris letter"
        )
    moment: datetime | None
    utc_label: str | None
    if physical_epoch is None:
        assert local_datetime is not None
        moment = local_datetime.astimezone(timezone.utc)
        times = ephemeris_time(moment)
        utc_label = moment.isoformat()
    else:
        moment = physical_epoch.utc_datetime
        times = physical_epoch.time
        utc_label = physical_epoch.utc_label
    if times.jd_tt is None:
        raise ImportError("Swiss Ephemeris is required for predictive chart positions")
    sidereal = zodiac_type == "Sidereal"
    offset = native_lahiri_ayanamsha(julian_day_tt=times.jd_tt) if sidereal else 0.0
    offset_speed = (
        math.remainder(
            native_lahiri_ayanamsha(julian_day_tt=times.jd_tt + 0.5)
            - native_lahiri_ayanamsha(julian_day_tt=times.jd_tt - 0.5),
            360.0,
        )
        if sidereal
        else 0.0
    )
    # Fail if a requested quadrant system is undefined; never clamp latitude.
    try:
        cusps, angles = ephemeris_call(
            "houses_ex", times.jd_ut1, latitude, longitude, code.encode("ascii")
        )
    except Exception as error:
        raise ValueError(
            f"Cannot compute {code} houses at the supplied latitude "
            f"({type(error).__name__}); no substitute house system was used"
        ) from error
    cusps, angles, house_axis_convention = canonical_house_geometry(
        julian_day_ut1=times.jd_ut1,
        latitude=latitude,
        longitude=longitude,
        house_code=code.encode("ascii"),
        native_angles=angles,
        native_cusps=cusps,
    )
    angle_definition = native_ecliptic_horizon_angle_definition(
        julian_day_ut1=times.jd_ut1,
        latitude=latitude,
        armc=float(angles[2]),
    )
    tropical_cusps = tuple(float(value) for value in cusps[:12])
    cusps = [(value - offset) % 360 for value in tropical_cusps]
    asc = (float(angles[0]) - offset) % 360
    if code == "W":
        cusps = [(int(asc // 30) * 30 + index * 30) % 360 for index in range(12)]
    house_projection = (
        build_ecliptic_house_projection(
            julian_day_ut1=times.jd_ut1,
            julian_day_tt=times.jd_tt,
            geographic_latitude=latitude,
            geographic_longitude=longitude,
            house_code=code.encode("ascii"),
        )
        if not is_prograde_house_partition(cusps)
        else None
    )
    points = {}

    def point(
        name: str,
        lon: float,
        *,
        speed: float = 0.0,
        beta: float = 0.0,
        dec: float | None = None,
        tropical_longitude: float | None = None,
    ) -> NativePoint:
        lon = normalize_angle(lon)
        number = (
            int(
                house_projection.position(
                    tropical_longitude
                    if tropical_longitude is not None
                    else combine_longitudes(lon, offset)
                )
            )
            if house_projection is not None
            else _house_for_longitude(
                lon, asc, "whole_sign" if code == "W" else "cusps", cusps
            )
        )
        return NativePoint(
            name,
            lon,
            lon % 30,
            SIGNS[int(lon // 30)],
            int(lon // 30),
            HOUSE_NAMES[number - 1],
            speed < 0,
            speed,
            beta,
            dec,
        )

    selected_path = configured_ephemeris_path()
    models: Dict[str, str] = {}
    source_trace = PhysicalEphemerisTrace()
    motion_metadata: Dict[str, Any] = {}
    states = {}
    for planet in PLANET_SEQUENCE:
        result = _swisseph_planet_state(
            planet,
            julian_day_tt=times.jd_tt,
            source_trace=source_trace,
            motion_metadata=motion_metadata,
        )
        if result is None:
            raise ValueError(
                f"Native ephemeris failed for {planet}; predictive charts cannot use an orbital approximation"
            )
        state, model = result
        assert_physical_configuration(selected_path)
        models[planet] = model
        states[planet] = state
        key = "mean_north_lunar_node" if planet == "North Node" else planet.lower()
        points[key] = point(
            planet,
            state["longitude"] - offset,
            speed=state["longitude_speed"] - offset_speed,
            beta=state["latitude"],
            dec=state.get("declination"),
            tropical_longitude=state["longitude"],
        )
    for index, (key, lon, tropical_lon) in enumerate(
        zip(HOUSE_ATTRIBUTES, cusps, tropical_cusps)
    ):
        points[key] = point(HOUSE_NAMES[index], lon, tropical_longitude=tropical_lon)
    for key, lon in {
        "ascendant": float(angles[0]),
        "medium_coeli": float(angles[1]),
        "descendant": float(angles[0]) + 180,
        "imum_coeli": float(angles[1]) + 180,
    }.items():
        points[key] = point(key, lon - offset, tropical_longitude=lon)
    altitude, method = horizon_altitude(
        times.jd_ut1,
        longitude,
        latitude,
        states["Sun"]["longitude"],
        states["Sun"]["latitude"],
    )
    assert_physical_configuration(selected_path)
    position_policy = apparent_position_policy(times.jd_tt, models, source_trace)
    basis: Dict[str, Any] = {
        "apparent_position_policy": position_policy,
        "engine_backend": (
            "fatebridge_swisseph_native"
            if method == "swisseph_true_altitude"
            else "mixed_native_approximate_geometry"
        ),
        "engine_precision": (
            "ephemeris_runtime_model"
            if method == "swisseph_true_altitude"
            else "mixed_precision_runtime_model"
        ),
        "ephemeris_model": physical_ephemeris_summary(models),
        "physical_ephemeris_source": source_trace.finish(),
        "ephemeris_reference_points": ephemeris_reference_points(
            models, ["Ascendant", "Medium_Coeli", "Descendant", "Imum_Coeli"]
        ),
        "longitude_motion": {
            **motion_metadata,
            "display_frame": (
                "sidereal_lahiri" if sidereal else "tropical_true_ecliptic_of_date"
            ),
            "display_longitude_offset_speed_degrees_per_day": offset_speed,
            "scope": "Question/natal epoch native rate and source-derived corrections; display speed subtracts declared offset derivative. Not an accuracy certificate.",
        },
        "calendar": "proleptic_gregorian",
        "time_scale": times.method,
        "earth_rotation": earth_rotation_policy(times.jd_tt, times.jd_ut1),
        "julian_day_tt": times.jd_tt,
        "julian_day_ut1": times.jd_ut1,
        "future_leap_seconds_assumed_unchanged": times.future_leap_seconds_assumed_unchanged,
        "horizon_method": method,
        "ayanamsha_model": "Lahiri" if sidereal else None,
        "ayanamsha_degrees": offset,
    }
    if angle_definition is not None:
        basis["angle_definition"] = angle_definition
    if house_projection is not None:
        basis["house_position_projection"] = house_projection.metadata()
    if physical_epoch is not None:
        basis["utc_representation"] = physical_epoch.representation()
    if house_axis_convention is not None:
        if sidereal:
            house_axis_convention = {
                **house_axis_convention,
                "longitude_frame": "sidereal_lahiri",
                **{
                    key: (house_axis_convention[key] - offset) % 360
                    for key in (
                        "public_midheaven",
                        "native_house_midheaven",
                        "public_ascendant",
                        "native_house_ascendant",
                    )
                },
            }
            precision = house_axis_convention.get("eastern_direction_precision")
            if precision is not None:
                precision = dict(precision)
                for key in ("native_common_ascendant", "delivered_ascendant"):
                    precision[key] = (precision[key] - offset) % 360
                for key in ("native_cusps", "delivered_cusps"):
                    if key in precision:
                        precision[key] = [(v - offset) % 360 for v in precision[key]]
                precision["coordinate_frame"] = "sidereal_lahiri"
                house_axis_convention["eastern_direction_precision"] = precision
        precision = house_axis_convention.get("eastern_direction_precision")
        if precision is not None:
            precision["delivered_ascendant"] = asc
            precision["delivered_cusps"] = cusps
        basis["house_axis_convention"] = house_axis_convention
    return NativeSubject(
        name,
        longitude,
        latitude,
        timezone_name,
        utc_label,
        (
            moment.astimezone(chart_timezone).isoformat()
            if moment is not None
            else utc_label if timezone_name == "UTC" else None
        ),
        times.jd_ut1,
        times.jd_tt,
        code,
        "Sidereal" if sidereal else "Tropical",
        "LAHIRI" if sidereal else None,
        altitude >= 0,
        points,
        basis,
    )

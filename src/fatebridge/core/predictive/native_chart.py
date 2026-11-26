"""Full-precision chart facts for timing, without civil-as-UT1 adaptation.

The point attributes form the internal protocol consumed by timing/event
techniques. Every position uses the same TT/UT1 policy as the natal chart.
No third-party latitude clamping, second truncation or hidden ayanamsha.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fatebridge.core.astro.angle_definitions import (
    native_ecliptic_horizon_angle_definition,
)
from fatebridge.core.astro.astrology_tables import SIGNS
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
from fatebridge.core.astro.physical_epoch import PhysicalEpoch, local_leap_second_label
from fatebridge.core.astro.physical_sources import (
    PhysicalEphemerisTrace,
    assert_physical_configuration,
)
from fatebridge.core.astro.profiles import physical_ephemeris_summary
from fatebridge.core.astro.reference import PLANET_SEQUENCE
from fatebridge.core.astro.reference_points import ephemeris_reference_points
from fatebridge.core.astro.rotation_policy import earth_rotation_policy
from fatebridge.core.astro.solar_position import apparent_position_policy
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.astro.ut1_epoch import UT1Instant
from fatebridge.core.astro.utc_policy import utc_definition_evidence
from fatebridge.core.ephemeris_runtime import (
    configured_ephemeris_path,
    ephemeris_call,
    preserve_ephemeris_path,
    swe,
)
from fatebridge.utils.civil_time import (
    UTCCalendar,
    ZonedCalendar,
    utc_calendar,
)
from fatebridge.utils.timezones import (
    is_unspecified_local_time,
    parse_timezone_name,
    validate_local_clock,
)

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
    ut1: UT1Instant
    tt: TTInstant
    houses_system_identifier: str
    zodiac_type: str
    sidereal_mode: str | None
    is_diurnal: bool
    points: dict[str, NativePoint]
    calculation_basis: dict[str, Any]

    @property
    def julian_day(self) -> float:
        """Scalar native-query/display adapter of the sole retained UT1."""
        return self.ut1.as_float()

    @property
    def julian_day_tt(self) -> float:
        """Native-query/display adapter of the sole retained TT point."""
        return self.tt.as_float()

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
    high_latitude_fallback: str = "error",
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
    civil: UTCCalendar | None
    utc_label: str | None
    if physical_epoch is None:
        assert local_datetime is not None
        civil = utc_calendar(local_datetime)
        times = ephemeris_time(civil)
        utc_label = civil.isoformat()
    else:
        times = physical_epoch.time
        utc_label = physical_epoch.utc_label
        if physical_epoch.utc_datetime is not None:
            civil = utc_calendar(physical_epoch.utc_datetime)
        elif utc_label is not None and not physical_epoch.utc_is_leap_second:
            civil = ZonedCalendar.from_isoformat(utc_label).utc
        else:
            civil = None
    projected_clock = (
        ZonedCalendar(civil, chart_timezone).as_datetime()
        if civil is not None
        else None
    )
    tt = times.tt
    if tt is None:
        raise ModuleNotFoundError(
            "Swiss Ephemeris is required for predictive chart positions"
        )
    native_tt = tt.as_float()
    sidereal = zodiac_type == "Sidereal"
    offset = native_lahiri_ayanamsha(julian_day_tt=native_tt) if sidereal else 0.0
    offset_speed = (
        math.remainder(
            native_lahiri_ayanamsha(julian_day_tt=native_tt + 0.5)
            - native_lahiri_ayanamsha(julian_day_tt=native_tt - 0.5),
            360.0,
        )
        if sidereal
        else 0.0
    )
    # Fail if a requested quadrant system is undefined unless fallback requested.
    swe_error = getattr(swe, "Error", None)
    house_errors = (
        (swe_error,)
        if isinstance(swe_error, type) and issubclass(swe_error, BaseException)
        else ()
    )
    use_fallback = (
        high_latitude_fallback in {"porphyry", "whole_sign"}
        and abs(latitude) > 66.5
        and code in {"P", "K", "B", "T"}
    )
    if use_fallback:
        fb_code = "W" if high_latitude_fallback == "whole_sign" else "O"
        cusps, angles = ephemeris_call(
            "houses_ex",
            times.ut1,
            latitude,
            longitude,
            fb_code.encode("ascii"),
            _julian_day_tt=tt,
        )
        code = fb_code
    else:
        try:
            cusps, angles = ephemeris_call(
                "houses_ex",
                times.ut1,
                latitude,
                longitude,
                code.encode("ascii"),
                _julian_day_tt=tt,
            )
        except house_errors as error:
            if high_latitude_fallback in {"porphyry", "whole_sign"}:
                fb_code = "W" if high_latitude_fallback == "whole_sign" else "O"
                cusps, angles = ephemeris_call(
                    "houses_ex",
                    times.ut1,
                    latitude,
                    longitude,
                    fb_code.encode("ascii"),
                    _julian_day_tt=tt,
                )
                code = fb_code
            else:
                raise ValueError(
                    f"Cannot compute {code} houses at the supplied latitude "
                    f"({type(error).__name__}); no substitute house system was used"
                ) from error
    cusps, angles, house_axis_convention = canonical_house_geometry(
        julian_day_ut1=times.ut1,
        julian_day_tt=tt,
        latitude=latitude,
        longitude=longitude,
        house_code=code.encode("ascii"),
        native_angles=angles,
        native_cusps=cusps,
    )
    angle_definition = native_ecliptic_horizon_angle_definition(
        julian_day_ut1=times.ut1,
        julian_day_tt=tt,
        latitude=latitude,
        longitude=longitude,
        armc=float(angles[2]),
    )
    tropical_cusps = tuple(float(value) for value in cusps[:12])
    cusps = [(value - offset) % 360 for value in tropical_cusps]
    asc = (float(angles[0]) - offset) % 360
    if code == "W":
        cusps = [(int(asc // 30) * 30 + index * 30) % 360 for index in range(12)]
    house_projection = (
        build_ecliptic_house_projection(
            julian_day_ut1=times.ut1,
            julian_day_tt=tt,
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
        labelled_house: int | None = None,
    ) -> NativePoint:
        lon = normalize_angle(lon)
        number = labelled_house
        if number is None:
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
    models: dict[str, str] = {}
    source_trace = PhysicalEphemerisTrace()
    motion_metadata: dict[str, Any] = {}
    states = {}
    for planet in PLANET_SEQUENCE:
        result = _swisseph_planet_state(
            planet,
            julian_day_tt=native_tt,
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
        # The lowercase Sunshine forward result defines these labels. Swiss's
        # nonprograde inverse uses the uppercase variant for both codes.
        points[key] = point(
            HOUSE_NAMES[index],
            lon,
            tropical_longitude=tropical_lon,
            labelled_house=index + 1 if code == "i" else None,
        )
    for key, lon in {
        "ascendant": float(angles[0]),
        "medium_coeli": float(angles[1]),
        "descendant": float(angles[0]) + 180,
        "imum_coeli": float(angles[1]) + 180,
    }.items():
        points[key] = point(key, lon - offset, tropical_longitude=lon)
    altitude, method = horizon_altitude(
        times.ut1,
        longitude,
        latitude,
        states["Sun"]["longitude"],
        states["Sun"]["latitude"],
        julian_day_tt=tt,
    )
    assert_physical_configuration(selected_path)
    basis: dict[str, Any] = {
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
        "calendar": "proleptic_gregorian",
        "time_scale": times.method,
        "julian_day_tt": native_tt,
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
    if projected_clock is not None:
        local_label = (
            None
            if is_unspecified_local_time(projected_clock)
            else projected_clock.isoformat()
        )
    elif (
        physical_epoch is not None
        and physical_epoch.utc_is_leap_second
        and utc_label is not None
    ):
        local_label = local_leap_second_label(utc_label, chart_timezone)
    else:
        local_label = utc_label if timezone_name == "UTC" else None
    return NativeSubject(
        name,
        longitude,
        latitude,
        timezone_name,
        utc_label,
        local_label,
        times.ut1,
        tt,
        code,
        "Sidereal" if sidereal else "Tropical",
        "LAHIRI" if sidereal else None,
        altitude >= 0,
        points,
        basis,
    )

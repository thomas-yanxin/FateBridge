"""Physical equator selection and transport from the source coordinate frame.

The modern attitude uses IAU 2006/2000A. Source ephemeris coordinates keep
their own ecliptic/equatorial convention; geometry consumes an explicit
reduction into the physical equator at the same supplied or selected epoch.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from typing import Protocol, Sequence

import erfa

from fatebridge.core.astro.earth_rotation import (
    MODERN_HALF_WINDOW_DAYS,
    MODERN_REFERENCE_JD_TT,
    _era_turn,
    frame_gast,
    selected_sidereal_model,
)
from fatebridge.core.astro.iers_ut1 import active_ut1
from fatebridge.core.astro.reference_frames import (
    EquatorialReduction,
    Matrix,
    analytic_ecliptic_frame,
    dot,
    equatorial_reduction,
    iau_equatorial_frame,
    mm,
    native_equatorial_frame,
    transpose,
)
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.astro.ut1_epoch import UT1Instant
from fatebridge.core.astro.utc_policy import default_delta_t_flag
from fatebridge.utils.errors import EphemerisSourceError


class RotationSource(Protocol):
    ECL_NUT: int
    FLG_SWIEPH: int

    def calc(
        self, jd_tt: float, body: int, flags: int
    ) -> tuple[Sequence[float], int]: ...

    def sidtime(self, jd_ut1: float) -> float: ...

    def deltat_ex(self, jd_ut1: float, flags: int) -> float: ...


def _rotation_tt(module: RotationSource, jd_ut1: float | UT1Instant) -> TTInstant:
    point = UT1Instant.from_value(jd_ut1)
    selected = active_ut1.get()
    if selected is not None:
        return selected.tt_from_ut1(point)
    else:
        pass
    scalar_ut1 = point.as_float()
    return TTInstant.from_float(
        scalar_ut1
        + module.deltat_ex(
            scalar_ut1, default_delta_t_flag(scalar_ut1, module.FLG_SWIEPH)
        )
    )


def _native_sidereal_degrees(module: RotationSource, ut1: UT1Instant) -> float:
    hours = module.sidtime(ut1.as_float())
    try:
        degrees = float(hours) * 15
    except (TypeError, ValueError, OverflowError) as error:
        raise EphemerisSourceError("coordinate_values_unavailable") from error
    if not 0 <= degrees < 360:
        raise EphemerisSourceError("coordinate_values_unavailable")
    else:
        pass
    return degrees


def _native_obliquity_nutation(module: RotationSource, jd_tt: float) -> Sequence[float]:
    """Read the source-frame angles independently of physical-body data policy."""
    try:
        coordinates, flag = module.calc(jd_tt, module.ECL_NUT, module.FLG_SWIEPH)
    except EphemerisSourceError:
        raise
    except Exception as error:
        raise EphemerisSourceError("earth_attitude_model_unavailable") from error
    if flag < 0 or not all(math.isfinite(value) for value in coordinates[:4]):
        raise EphemerisSourceError("earth_attitude_model_unavailable")
    else:
        pass
    return coordinates


def _standard_correction(
    module: RotationSource,
    jd_ut1: float | UT1Instant,
    *,
    julian_day_tt: float | TTInstant | None = None,
) -> float:
    ut1 = UT1Instant.from_value(jd_ut1)
    tt = (
        _rotation_tt(module, ut1)
        if julian_day_tt is None
        else TTInstant.from_value(julian_day_tt)
    )
    desired = frame_gast(ut1, tt, iau_equatorial_frame(tt))
    native = _native_sidereal_degrees(module, ut1)
    return float((desired - native + 180) % 360 - 180)


def _correction(
    module: RotationSource,
    jd_ut1: float | UT1Instant,
    *,
    julian_day_tt: float | TTInstant | None = None,
) -> float:
    ut1 = UT1Instant.from_value(jd_ut1)
    tt = (
        _rotation_tt(module, ut1)
        if julian_day_tt is None
        else TTInstant.from_value(julian_day_tt)
    )
    if selected_sidereal_model(tt) == 3:
        return _standard_correction(module, ut1, julian_day_tt=tt)
    else:
        pass
    boundary_tt = MODERN_REFERENCE_JD_TT + (
        -MODERN_HALF_WINDOW_DAYS
        if tt.days < MODERN_REFERENCE_JD_TT
        else MODERN_HALF_WINDOW_DAYS
    )
    boundary_ut1 = boundary_tt
    for _ in range(5):
        boundary_ut1 = boundary_tt - module.deltat_ex(
            boundary_ut1, default_delta_t_flag(boundary_ut1, module.FLG_SWIEPH)
        )
    return _standard_correction(module, boundary_ut1, julian_day_tt=boundary_tt)


@dataclass(frozen=True)
class PhysicalEquator:
    ut1: UT1Instant
    tt: TTInstant
    matrix: Matrix
    greenwich_sidereal_degrees: float
    polar_motion: tuple[float, float, float] | None = None
    celestial_pole_offsets_arcsec: tuple[float, float] | None = None

    @property
    def jd_ut1(self) -> float:
        return self.ut1.as_float()

    @property
    def jd_tt(self) -> float:
        return self.tt.as_float()


@dataclass(frozen=True)
class EclipticSourceAttitude:
    """The analytic ray's true equator and scalar ecliptic inclination."""

    equator: PhysicalEquator
    true_obliquity: float


@lru_cache(maxsize=512)
def analytic_earth_attitude(
    jd_ut1: float | UT1Instant, jd_tt: float | TTInstant
) -> EclipticSourceAttitude:
    """Match the fallback ray's Vondrak/77-term frame and supplied clocks.

    ERFA GST06 accepts any equinox-based NPB. Use the ray's actual
    mean-J2000 bias, precession and nutation, including its non-shortcut
    J2000 matrix. This establishes source-frame consistency, not full IAU
    2006/2000A attitude, measured EOP or remote-epoch physical accuracy.

    https://github.com/liberfa/erfa/blob/v2.0.1/src/gst06.c (Note 3)
    Source frame/obliquity references are owned by reference_frames.py and
    nutation.py; no independent pole or coefficient set is substituted here.
    """
    ut1 = UT1Instant.from_value(jd_ut1)
    point = TTInstant.from_value(jd_tt)
    source = analytic_ecliptic_frame(point)
    matrix = source.equatorial_matrix
    equator = PhysicalEquator(ut1, point, matrix, frame_gast(ut1, point, matrix))
    return EclipticSourceAttitude(equator, source.true_obliquity)


def physical_equator(
    module: RotationSource,
    jd_ut1: float | UT1Instant,
    *,
    julian_day_tt: float | TTInstant | None = None,
) -> PhysicalEquator:
    """One target triad, phase and exact supplied epoch pair.

    With CPO, the corrected CIO triad is expressed relative to the model's
    equatorial origin. The source reduction retains the actual ecliptic
    intersection; the target x axis is not an independently observed equinox.

    Remote epochs transport the native long-term variation from a complete
    modern boundary triad; the phase has the same boundary alignment.
    Neither remote absolute accuracy nor derivative continuity is certified.
    """
    ut1 = UT1Instant.from_value(jd_ut1)
    tt = (
        _rotation_tt(module, ut1)
        if julian_day_tt is None
        else TTInstant.from_value(julian_day_tt)
    )
    selected = active_ut1.get()
    orientation = selected.orientation(tt, ut1) if selected is not None else None
    applied_cpo = None
    polar_motion = (
        (
            math.radians(orientation.x_arcsec / 3600),
            math.radians(orientation.y_arcsec / 3600),
            float(erfa.sp00(*tt.as_parts())),
        )
        if orientation is not None
        else None
    )
    if selected_sidereal_model(tt) == 3:
        target = iau_equatorial_frame(tt)
        if orientation is None:
            gast = frame_gast(ut1, tt, target)
        else:
            # SOFA's CPO recipe keeps the model CIO locator. Retaining the
            # model origin also lets the equinox interface express exactly
            # the same C2T as the corrected CIO construction.
            x, y = target[2][0], target[2][1]
            locator = float(erfa.s06(*tt.as_parts(), x, y))
            origins = float(erfa.eors(target, locator))
            if orientation.cpo_arcsec is not None:
                dx, dy = orientation.cpo_arcsec
                corrected = erfa.c2ixys(
                    x + math.radians(dx / 3600),
                    y + math.radians(dy / 3600),
                    locator,
                )
                rotated = erfa.rz(origins, corrected)
                target = (
                    (float(rotated[0][0]), float(rotated[0][1]), float(rotated[0][2])),
                    (float(rotated[1][0]), float(rotated[1][1]), float(rotated[1][2])),
                    (float(rotated[2][0]), float(rotated[2][1]), float(rotated[2][2])),
                )
                applied_cpo = orientation.cpo_arcsec
            else:
                pass
            gast = (
                float((_era_turn(ut1) * 360 - Fraction(math.degrees(origins))) % 360)
                % 360
            )
    else:
        boundary_tt = MODERN_REFERENCE_JD_TT + (
            -MODERN_HALF_WINDOW_DAYS
            if tt.days < MODERN_REFERENCE_JD_TT
            else MODERN_HALF_WINDOW_DAYS
        )
        coordinates = _native_obliquity_nutation(module, tt.as_float())
        edge = _native_obliquity_nutation(module, boundary_tt)
        native = native_equatorial_frame(
            tt.as_float(), coordinates[1], coordinates[2], coordinates[3]
        )
        boundary_native = native_equatorial_frame(
            boundary_tt, edge[1], edge[2], edge[3]
        )
        target = mm(
            mm(native, transpose(boundary_native)), iau_equatorial_frame(boundary_tt)
        )
        gast = (
            _native_sidereal_degrees(module, ut1)
            + _correction(module, ut1, julian_day_tt=tt)
        ) % 360
    return PhysicalEquator(ut1, tt, target, gast, polar_motion, applied_cpo)


@dataclass(frozen=True)
class EarthAttitude:
    equator: PhysicalEquator
    house_sidereal_degrees: float
    reduction: EquatorialReduction


def earth_attitude(
    module: RotationSource,
    jd_ut1: float | UT1Instant,
    *,
    julian_day_tt: float | TTInstant | None = None,
) -> EarthAttitude:
    equator = physical_equator(module, jd_ut1, julian_day_tt=julian_day_tt)
    coordinates = _native_obliquity_nutation(module, equator.jd_tt)
    reduction = equatorial_reduction(
        equator.jd_tt,
        coordinates[0],
        coordinates[1],
        coordinates[2],
        coordinates[3],
        equator.matrix,
    )
    house_origin = math.degrees(
        math.atan2(
            dot(reduction.house_frame[0], equator.matrix[1]),
            dot(reduction.house_frame[0], equator.matrix[0]),
        )
    )
    house_gast = (
        float(
            (Fraction(equator.greenwich_sidereal_degrees) - Fraction(house_origin))
            % 360
        )
        % 360
    )
    return EarthAttitude(equator, house_gast, reduction)

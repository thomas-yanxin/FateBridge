"""Physical equator selection and transport from the source coordinate frame.

The modern attitude uses IAU 2006/2000A. Source ephemeris coordinates keep
their own ecliptic/equatorial convention; geometry consumes an explicit
reduction into the physical equator at the same supplied or selected epoch.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Protocol, Sequence

from fatebridge.core.astro.earth_rotation import (
    MODERN_HALF_WINDOW_DAYS,
    MODERN_REFERENCE_JD_TT,
    frame_gast,
    selected_sidereal_model,
)
from fatebridge.core.astro.iers_ut1 import active_ut1
from fatebridge.core.astro.reference_frames import (
    EquatorialReduction,
    Matrix,
    dot,
    equatorial_reduction,
    iau_equatorial_frame,
    mm,
    native_equatorial_frame,
    transpose,
)
from fatebridge.core.astro.utc_policy import default_delta_t_flag


class RotationSource(Protocol):
    ECL_NUT: int
    FLG_SWIEPH: int

    def calc(
        self, jd_tt: float, body: int, flags: int
    ) -> tuple[Sequence[float], int]: ...

    def sidtime(self, jd_ut1: float) -> float: ...

    def deltat_ex(self, jd_ut1: float, flags: int) -> float: ...


def _rotation_tt(module: RotationSource, jd_ut1: float) -> float:
    selected = active_ut1.get()
    return (
        selected.tt_from_ut1(jd_ut1)
        if selected is not None
        else jd_ut1
        + module.deltat_ex(jd_ut1, default_delta_t_flag(jd_ut1, module.FLG_SWIEPH))
    )


def _standard_correction(
    module: RotationSource, jd_ut1: float, *, julian_day_tt: float | None = None
) -> float:
    tt = _rotation_tt(module, jd_ut1) if julian_day_tt is None else julian_day_tt
    desired = frame_gast(jd_ut1, tt, iau_equatorial_frame(tt))
    native = module.sidtime(jd_ut1) * 15
    return float((desired - native + 180) % 360 - 180)


def _correction(
    module: RotationSource, jd_ut1: float, *, julian_day_tt: float | None = None
) -> float:
    tt = _rotation_tt(module, jd_ut1) if julian_day_tt is None else julian_day_tt
    if selected_sidereal_model(tt) == 3:
        return _standard_correction(module, jd_ut1, julian_day_tt=tt)
    boundary_tt = MODERN_REFERENCE_JD_TT + (
        -MODERN_HALF_WINDOW_DAYS
        if tt < MODERN_REFERENCE_JD_TT
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
    jd_ut1: float
    jd_tt: float
    matrix: Matrix
    greenwich_sidereal_degrees: float


def physical_equator(
    module: RotationSource, jd_ut1: float, *, julian_day_tt: float | None = None
) -> PhysicalEquator:
    """A single target pole, equinox, phase and exact supplied epoch pair.

    Remote epochs transport the native long-term variation from a complete
    modern boundary triad; the phase has the same boundary alignment.
    Neither remote absolute accuracy nor derivative continuity is certified.
    """
    tt = _rotation_tt(module, jd_ut1) if julian_day_tt is None else julian_day_tt
    if selected_sidereal_model(tt) == 3:
        target = iau_equatorial_frame(tt)
        gast = frame_gast(jd_ut1, tt, target)
    else:
        boundary_tt = MODERN_REFERENCE_JD_TT + (
            -MODERN_HALF_WINDOW_DAYS
            if tt < MODERN_REFERENCE_JD_TT
            else MODERN_HALF_WINDOW_DAYS
        )
        coordinates, flag = module.calc(tt, module.ECL_NUT, module.FLG_SWIEPH)
        edge, returned = module.calc(boundary_tt, module.ECL_NUT, module.FLG_SWIEPH)
        if min(flag, returned) < 0:
            raise ValueError("Nutation/obliquity unavailable for Earth attitude")
        native = native_equatorial_frame(
            tt, coordinates[1], coordinates[2], coordinates[3]
        )
        boundary_native = native_equatorial_frame(
            boundary_tt, edge[1], edge[2], edge[3]
        )
        target = mm(
            mm(native, transpose(boundary_native)), iau_equatorial_frame(boundary_tt)
        )
        gast = (
            module.sidtime(jd_ut1) * 15 + _correction(module, jd_ut1, julian_day_tt=tt)
        ) % 360
    return PhysicalEquator(jd_ut1, tt, target, gast)


@dataclass(frozen=True)
class EarthAttitude:
    equator: PhysicalEquator
    house_sidereal_degrees: float
    reduction: EquatorialReduction


def earth_attitude(
    module: RotationSource, jd_ut1: float, *, julian_day_tt: float | None = None
) -> EarthAttitude:
    equator = physical_equator(module, jd_ut1, julian_day_tt=julian_day_tt)
    coordinates, flag = module.calc(equator.jd_tt, module.ECL_NUT, module.FLG_SWIEPH)
    if flag < 0:
        raise ValueError("Nutation/obliquity unavailable for Earth attitude")
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

"""Declared ecliptic projection when labelled cusps reverse or fold.

Swiss Ephemeris programmer documentation section 16 distinguishes house
positions from comparing cusp longitudes. xpin must be tropical; setting its
latitude to zero preserves a longitude-only convention, not a body's spatial
placement. Never sort/relabel polar cusps to fabricate a forward partition.
R/C phases are checked by independent scalar plane equations; native values
remain in the calculation record. T uses its actual, unclipped latitude in a
bounded physical-quadrant inverse. Other methods retain their native policy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any

from fatebridge.core.astro import runtime
from fatebridge.core.astro.earth_attitude import earth_attitude
from fatebridge.core.astro.geometry import normalize_angle
from fatebridge.core.astro.house_projection_precision import (
    PHASE_FORWARD_OFFSET_ARCSECONDS,
    RC_PLANE_PROJECTION_METHOD,
    checked_house_plane_position,
)
from fatebridge.core.astro.terrestrial_observer import house_site
from fatebridge.core.astro.topocentric_precision import (
    NATIVE_INVERSE_LATITUDE_LIMIT,
    TOPOCENTRIC_BRANCH_POLICY,
    TOPOCENTRIC_PROJECTION_METHOD,
    checked_topocentric_position,
)
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.astro.ut1_epoch import UT1Instant
from fatebridge.utils.errors import EphemerisSourceError

NATIVE_PROJECTION_METHOD = "swisseph_house_pos_zero_ecliptic_latitude"
HOUSE_POSITION_SOURCE = "https://www.astro.com/swisseph/swephprg.htm"


@dataclass(frozen=True)
class HouseCoordinate:
    position: float
    phase_degrees: Fraction


@dataclass(frozen=True)
class EclipticHouseProjection:
    armc: float
    geographic_latitude: float
    obliquity: float
    house_code: bytes
    longitude_origin: float = 0.0
    rotation_latitude: float | None = field(default=None, kw_only=True)
    sun_declination: float | None = field(default=None, kw_only=True)
    _precision_records: list[dict[str, Any]] = field(
        default_factory=list, compare=False, repr=False
    )

    @property
    def _latitude(self) -> float:
        return (
            self.geographic_latitude
            if self.rotation_latitude is None
            else self.rotation_latitude
        )

    @property
    def _native_pole_convention(self) -> bool:
        return self.house_code in (b"R", b"T") and abs(self._latitude) == 90

    def position(
        self,
        tropical_longitude: float,
        *,
        exact_longitude: Fraction | None = None,
    ) -> float:
        return self.coordinate(
            tropical_longitude, exact_longitude=exact_longitude
        ).position

    def coordinate(
        self,
        tropical_longitude: float,
        *,
        exact_longitude: Fraction | None = None,
    ) -> HouseCoordinate:
        if runtime.swe is None:
            raise ValueError("非单圈宫头的原生落宫投影需要Swiss Ephemeris")
        source_longitude = (
            exact_longitude
            if exact_longitude is not None
            else Fraction(tropical_longitude)
        )
        backend_longitude = source_longitude - Fraction(self.longitude_origin)
        longitude = normalize_angle(float(backend_longitude % 360))
        options = {}
        if self.house_code in (b"I", b"i"):
            if self.sun_declination is None:
                raise ValueError(
                    "Sunshine house projection requires the frame's Sun declination"
                )
            options["_sun_declination"] = self.sun_declination
        position = float(
            runtime.ephemeris_call(
                "house_pos",
                self.armc,
                self._latitude,
                self.obliquity,
                (longitude, 0.0),
                self.house_code,
                **options,
            )
        )
        if self._native_pole_convention:
            if not math.isfinite(position) or not 1 <= position < 13:
                raise EphemerisSourceError("house_projection_precision_unavailable")
            self._precision_records.append(
                {
                    "tropical_longitude": float(tropical_longitude),
                    "native_tropical_longitude": longitude,
                    "native_position": position,
                    "delivered_position": position,
                    "house": int(position),
                    "phase_degrees": (position - 1) * 30,
                    "working_decimal_digits": [],
                    "action": (
                        "native_geographic_pole_convention_retained_not_requalified"
                        if self.rotation_latitude is None
                        else "native_rotation_pole_convention_retained_not_requalified"
                    ),
                }
            )
            return HouseCoordinate(position, (Fraction(position) - 1) * 30)
        if self.house_code == b"T":
            if not math.isfinite(position) or not 1 <= position < 13:
                raise ValueError("原生黄经落宫投影无有效结果，不能钳制或补默认宫位")
            try:
                checked_t = checked_topocentric_position(
                    latitude=self._latitude,
                    armc=self.armc,
                    obliquity=self.obliquity,
                    # A rounded [0,360) float can move an almost-zero input
                    # enough to cross a T phase boundary near a pole. Preserve
                    # the supplied binary64 value for the precision solver.
                    longitude=backend_longitude,
                    native_position=position,
                )
            except (ArithmeticError, ValueError) as error:
                raise EphemerisSourceError(
                    "house_projection_precision_unavailable"
                ) from error
            branch = checked_t.branch
            if self.rotation_latitude is not None:
                branch = dict(branch)
                branch["rotation_axis_latitude_used"] = branch.pop(
                    "geographic_latitude_used"
                )
                branch["geographic_latitude_input"] = self.geographic_latitude
            self._precision_records.append(
                {
                    "tropical_longitude": float(tropical_longitude),
                    "native_tropical_longitude": longitude,
                    "native_position": position,
                    "delivered_position": checked_t.position,
                    "house": checked_t.house,
                    "phase_degrees": checked_t.phase_degrees,
                    "phase_degrees_decimal": checked_t.phase_degrees_decimal,
                    "working_decimal_digits": list(checked_t.working_digits),
                    "action": checked_t.action,
                    **(
                        {
                            "exact_tropical_longitude_ratio": list(
                                exact_longitude.as_integer_ratio()
                            )
                        }
                        if exact_longitude is not None
                        else {}
                    ),
                    "topocentric_branch": branch,
                }
            )
            return HouseCoordinate(checked_t.position, checked_t.phase_degrees_working)
        if self.house_code in (b"R", b"C"):
            try:
                checked = checked_house_plane_position(
                    latitude=self._latitude,
                    armc=self.armc,
                    obliquity=self.obliquity,
                    longitude=backend_longitude,
                    house_code=self.house_code,
                    native_position=position,
                )
            except (ArithmeticError, ValueError) as error:
                raise EphemerisSourceError(
                    "house_projection_precision_unavailable"
                ) from error
            self._precision_records.append(
                {
                    "tropical_longitude": float(tropical_longitude),
                    "native_tropical_longitude": longitude,
                    "native_position": position if math.isfinite(position) else None,
                    "delivered_position": checked.position,
                    "house": checked.house,
                    "phase_degrees": checked.phase_degrees,
                    "phase_degrees_decimal": checked.phase_degrees_decimal,
                    "working_decimal_digits": list(checked.working_digits),
                    "action": checked.action,
                    **(
                        {
                            "exact_tropical_longitude_ratio": list(
                                exact_longitude.as_integer_ratio()
                            )
                        }
                        if exact_longitude is not None
                        else {}
                    ),
                }
            )
            return HouseCoordinate(checked.position, checked.phase_degrees_working)
        if not math.isfinite(position) or not 1.0 <= position < 13.0:
            raise ValueError("原生黄经落宫投影无有效结果，不能钳制或补默认宫位")
        return HouseCoordinate(position, (Fraction(position) - 1) * 30)

    def metadata(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "method": (
                RC_PLANE_PROJECTION_METHOD
                if self.house_code in (b"R", b"C") and not self._native_pole_convention
                else NATIVE_PROJECTION_METHOD
            ),
            "library_version": runtime.swe.version if runtime.swe is not None else None,
            "reason": "labelled_cusps_not_single_prograde_partition",
            "armc": self.armc,
            "geographic_latitude": self.geographic_latitude,
            "true_obliquity": self.obliquity,
            "house_code": self.house_code.decode("ascii"),
            "input_frame": "tropical_true_ecliptic_of_date",
            "backend_longitude_origin": self.longitude_origin,
            "backend_frame": "intersection_of_physical_equator_and_source_ecliptic",
            "input_ecliptic_latitude": 0.0,
            "source_url": HOUSE_POSITION_SOURCE,
            "source_section": "16",
            "scope": "Longitude-only native projection; not actual-body spatial placement",
        }
        if self.house_code == b"i":
            result["scope"] = (
                "Lowercase i labels are retained from the forward calculation. "
                "Swiss Ephemeris uses uppercase I for inverse placement at zero ecliptic latitude."
            )
        if self.house_code in (b"R", b"C"):
            result["note_zh"] = (
                "落宫方法：非单圈顺行宫头，按R／C几何平面复核黄纬0°投影；不是计入星体实际黄纬的空间落宫。原生值与交付值另列。"
            )
            result["scope"] = (
                "Precision-checked R/C plane projection at zero ecliptic latitude; not actual-body spatial placement"
            )
            result["precision"] = {
                "method_id": RC_PLANE_PROJECTION_METHOD,
                "phase_forward_offset_arcseconds": PHASE_FORWARD_OFFSET_ARCSECONDS,
                "boundary_policy": "geometric_phase_plus_forward_offset_not_longitude_cusp_snap",
                "input_precision_scope": "exact_supplied_binary64_angles_and_rational_derived_longitudes_when_recorded",
                "maximum_physical_error_arcseconds": None,
                # The per-chart projector is also consumed by later lots. Keep
                # those actual calls in the same record rather than truncating.
                "checks": self._precision_records,
            }
            if self._native_pole_convention:
                result["precision"]["phase_forward_offset_arcseconds"] = None
                result["precision"][
                    "input_precision_scope"
                ] = "native_pole_convention_preserved_without_independent_geometry_qualification"
                result["precision"][
                    "status"
                ] = "native_geographic_pole_convention_not_requalified"
                result["precision"][
                    "boundary_policy"
                ] = "native_geographic_pole_limit_convention"
                result["precision"]["method_id"] = NATIVE_PROJECTION_METHOD
                result["scope"] = (
                    "Native geographic-pole convention retained; no independent unique geometric division certified"
                )
                result["note_zh"] = (
                    "地理极点的R落宫保留原生极限约定；本轮未认证其几何唯一性，也不是计入星体实际黄纬的空间落宫。"
                )
            else:
                result["precision"]["status"] = "supplied_model_checked"
        if self.house_code == b"T":
            result["method"] = (
                NATIVE_PROJECTION_METHOD
                if self._native_pole_convention
                else TOPOCENTRIC_PROJECTION_METHOD
            )
            result["precision"] = {
                "method_id": result["method"],
                "phase_forward_offset_arcseconds": (
                    None if self._native_pole_convention else 0.0
                ),
                "boundary_policy": (
                    "native_geographic_pole_limit_convention"
                    if self._native_pole_convention
                    else "continuous_geometric_phase_half_open_without_cusp_snap"
                ),
                "input_precision_scope": (
                    "native_pole_convention_preserved_without_independent_geometry_qualification"
                    if self._native_pole_convention
                    else "exact_supplied_binary64_angles_and_rational_derived_longitudes_when_recorded_without_native_inverse_clip"
                ),
                "maximum_physical_error_arcseconds": None,
                "checks": self._precision_records,
                "branch_policy": TOPOCENTRIC_BRANCH_POLICY,
                "native_inverse_latitude_limit_degrees": NATIVE_INVERSE_LATITUDE_LIMIT,
                "latitude_clamped": None if self._native_pole_convention else False,
                "status": (
                    "native_geographic_pole_convention_not_requalified"
                    if self._native_pole_convention
                    else (
                        "not_assessed"
                        if not self._precision_records
                        else (
                            "supplied_model_checked_with_boundary_candidates"
                            if any(
                                len(r["topocentric_branch"]["candidate_root_degrees"])
                                > 1
                                for r in self._precision_records
                            )
                            else "supplied_model_checked"
                        )
                    )
                ),
            }
            result["scope"] = (
                "Native geographic-pole convention retained; no independent unique geometric division certified"
                if self._native_pole_convention
                else "Bounded T physical-quadrant inverse at zero ecliptic latitude, without latitude clipping; native formal cusp labels are not a forward longitude partition"
            )
            result["note_zh"] = (
                "地理极点的T落宫保留原生极限约定；未认证其几何唯一性，也不是计入星体实际黄纬的空间落宫。"
                if self._native_pole_convention
                else "落宫方法：按实际纬度求解T的黄纬0°位线，未使用原生逆算的89.999°纬度钳制；以地平半球与东西分支选支，边界候选另列。原生值与交付值并列，原生形式宫头不能强展开成顺行区间；不是计入星体实际黄纬的空间落宫。"
            )
        if self.rotation_latitude is not None:
            result["rotation_axis_latitude"] = self.rotation_latitude
            if self._native_pole_convention:
                result["precision"][
                    "status"
                ] = "native_rotation_pole_convention_not_requalified"
                result["precision"][
                    "input_precision_scope"
                ] = "native_rotation_pole_convention_preserved_without_independent_geometry_qualification"
                result["precision"][
                    "boundary_policy"
                ] = "native_rotation_pole_limit_convention"
                result["scope"] = (
                    "Native rotation-pole convention retained; no independent unique geometric division certified"
                )
                result["note_zh"] = result["note_zh"].replace(
                    "地理极点", "所选旋转模型的极点"
                )
        return result


def build_ecliptic_house_projection(
    *,
    julian_day_ut1: float | UT1Instant,
    julian_day_tt: float | TTInstant | None,
    geographic_latitude: float,
    geographic_longitude: float,
    house_code: bytes,
) -> EclipticHouseProjection:
    if runtime.swe is None:
        raise ValueError("非单圈宫头的原生落宫投影需要Swiss Ephemeris")
    with runtime.preserve_ephemeris_path():
        # ARMC is an equatorial Earth-rotation angle, not a sidereal longitude.
        sunshine = house_code in (b"I", b"i")
        options = {"_return_sun_declination": True} if sunshine else {}
        house_result = runtime.ephemeris_call(
            "houses_ex",
            julian_day_ut1,
            geographic_latitude,
            geographic_longitude,
            house_code,
            _julian_day_tt=julian_day_tt,
            **options,
        )
        if sunshine:
            _, angles, sun_declination = house_result
        else:
            _, angles = house_result
            sun_declination = None
        attitude = earth_attitude(
            runtime.swe, julian_day_ut1, julian_day_tt=julian_day_tt
        )
        _, rotation_latitude = house_site(
            attitude,
            longitude=geographic_longitude,
            latitude=geographic_latitude,
        )
    if not math.isfinite(angles[2]):
        raise ValueError("原生落宫投影的ARMC或真黄赤交角无效")
    return EclipticHouseProjection(
        float(angles[2]),
        geographic_latitude,
        attitude.reduction.house_obliquity,
        house_code,
        longitude_origin=attitude.reduction.house_longitude_origin,
        sun_declination=sun_declination,
        rotation_latitude=(
            rotation_latitude if attitude.equator.polar_motion is not None else None
        ),
    )

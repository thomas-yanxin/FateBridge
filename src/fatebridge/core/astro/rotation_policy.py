"""Describe the Earth orientation actually selected for a chart or clock."""

from __future__ import annotations

import erfa

from fatebridge.core.astro import runtime
from fatebridge.core.astro.earth_attitude import physical_equator
from fatebridge.core.astro.earth_rotation import (
    MODERN_HALF_WINDOW_DAYS,
    MODERN_REFERENCE_JD_TT,
    selected_sidereal_model,
)
from fatebridge.core.astro.iers_ut1 import active_ut1, ut1_reference
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.astro.ut1_epoch import UT1Instant

POLICY_ID = "fatebridge_physical_earth_attitude_v6"
NATIVE_IERS_UT1_INTERVAL = (2396758.5, 2469807.5)


def earth_rotation_policy(
    julian_day_tt: float | TTInstant | None = None,
    julian_day_ut1: float | UT1Instant | None = None,
) -> dict[str, object]:
    tt = TTInstant.from_value(julian_day_tt) if julian_day_tt is not None else None
    tt_label = tt.as_float() if tt is not None else None
    model = selected_sidereal_model(tt) if tt is not None else None
    extension = julian_day_tt is not None and julian_day_ut1 is not None
    value: dict[str, object] = {
        "policy_id": POLICY_ID,
        "sidereal_time_model": (
            (
                "IAU2006_2000A_CIO"
                if model == 3
                else "Swiss_longterm_with_boundary_phase_alignment"
            )
            if extension and julian_day_tt is not None
            else (
                "Swiss_native"
                if julian_day_tt is not None
                else "not_selected_without_epoch"
            )
        ),
        "implementation": (
            "explicit_source_frame_reduction_and_physical_earth_attitude"
            if extension
            else "native_public_API"
        ),
        "model_epoch_jd_tt": tt_label,
        "model_epoch_jd_ut1": (
            julian_day_ut1.as_float()
            if isinstance(julian_day_ut1, UT1Instant)
            else julian_day_ut1
        ),
        "modern_adoption_window_tt": {
            "reference_jd": MODERN_REFERENCE_JD_TT,
            "half_window_julian_centuries": 2.0,
        },
        "native_iers_interval_ut1": {
            "start": NATIVE_IERS_UT1_INTERVAL[0],
            "end": NATIVE_IERS_UT1_INTERVAL[1],
        },
        "native_interval_role": "Documented native switch points; not an application bypass",
        "celestial_frame_model": (
            "IAU2006_2000A"
            if model == 3
            else (
                "native_longterm_triad_with_IAU_boundary_alignment"
                if julian_day_tt is not None
                else "not_selected_without_epoch"
            )
        ),
        "celestial_frame_scope": "Physical pole and equinox; source coordinates are explicitly reduced from their own frame. Does not replace source ecliptic longitudes or dynamical ephemerides.",
        "source_equatorial_frame_model": "Swiss2.10.03_default_Vondrak_nutation2000B_native_bias",
        "origin_method": "ERFA_S06_and_equation_of_origins_from_the_same_NPB",
        "erfa_version": str(erfa.version.erfa_version),
        "selection_basis": "FateBridge near-J2000 window; longterm phase and complete equatorial triad aligned at each outer edge",
        "longterm_phase_alignment": (
            {
                "method": "constant_GAST_offset_and_native_triad_transport_from_IAU_boundary",
                "boundary_tt_jd": (
                    MODERN_REFERENCE_JD_TT
                    + (
                        -MODERN_HALF_WINDOW_DAYS
                        if tt is not None and tt.days < MODERN_REFERENCE_JD_TT
                        else MODERN_HALF_WINDOW_DAYS
                    )
                    if model == 4
                    else None
                ),
                "native_longterm_variation_retained": True,
                "absolute_accuracy_certified": False,
                "derivative_continuity_certified": False,
                "source_url": "https://www.astro.com/swisseph/swisseph.htm",
                "source_section": "6.1",
                "attribution": "FateBridge window placement and computed constants; Swiss documents the constant-offset continuity method",
            }
            if model == 4
            else None
        ),
        "nutation_model": (
            "IAU2000A_with_IAU2006_adjustments"
            if model == 3
            else (
                "native_longterm_variation_after_boundary_triad_alignment"
                if julian_day_tt is not None
                else "not_selected_without_epoch"
            )
        ),
        "tt_argument_policy": (
            (
                "retained_supplied_TT_else_selected_IERS_C04_UT1_inverse"
                if active_ut1.get() is not None
                else "retained_supplied_TT_else_shared_default_DeltaT_minus1_before1960_SWIEPH_from1960"
            )
            if extension
            else "native_internal_sidereal_time_argument"
        ),
        "other_astronomical_models": "not_mutated_by_rotation_adapter",
        "geographic_longitude_policy": "Supplied terrestrial location retained; source-frame rays, house plane and receiver are reduced into the selected physical attitude",
        "native_event_api_scope": "Raw SDK rise_trans/true_hor retain native conventions; published solar-event consumers use the physical domain solver",
        "scope": "Managed sidereal time, houses, horizons and the two published solar-event definitions",
        "measured_eop_applied": False,
        "precision_scope": "Finite model/frame/observer/root agreement; no measured polar motion, remote absolute accuracy, derivative or all-input certification",
        "source_url": "https://iers-conventions.obspm.fr/content/chapter5/icc5.pdf",
        "origin_source_url": "https://github.com/liberfa/erfa/blob/v2.0.1/src/gst06.c",
        "frame_source_url": "https://www.iausofa.org/2023-10-11c",
        "native_frame_source_url": "https://github.com/aloistr/swisseph/blob/175e1fcb3108bcd5c0d146c803f51dcf23508012/swephlib.c",
    }
    reference = ut1_reference(tt, julian_day_ut1)
    if reference is not None and tt is not None and julian_day_ut1 is not None:
        value.update(
            measured_eop_applied=True,
            ut1_reference=reference,
            precision_scope="Selected final daily EOP and declared interpolation/tides. The nested UT1 receipt describes the time evaluation; terrestrial_orientation describes geometry. Formal errors and solver residuals are not complete physical uncertainty or station-motion certification.",
        )
        equator = physical_equator(runtime.swe, julian_day_ut1, julian_day_tt=tt)
        motion = equator.polar_motion
        if motion is not None:
            cpo = equator.celestial_pole_offsets_arcsec
            cpo_applied = cpo is not None
            value.update(
                policy_id="fatebridge_physical_earth_attitude_v7_c04",
                sidereal_time_model=(
                    "IAU2006_2000A_model_EO_with_C04_CIP_and_polar_motion"
                    if cpo_applied
                    else "IAU2006_2000A_model_CIP_and_EO_with_C04_polar_motion"
                ),
                celestial_frame_model=(
                    "IAU2006_2000A_with_published_C04_CPO"
                    if cpo_applied
                    else "IAU2006_2000A_without_source_qualified_CPO"
                ),
                origin_method=(
                    "model_S06_and_EO_retained_with_corrected_CIO_triad"
                    if cpo_applied
                    else "model_S06_and_EO_from_the_IAU2006_2000A_NPB"
                ),
                celestial_frame_scope=(
                    "Source rays are reduced into the CPO-corrected CIO triad, expressed "
                    "relative to the model origin. This does not relabel native ecliptic "
                    "longitudes or certify the dynamical ephemeris."
                    if cpo_applied
                    else "Source rays are reduced into the IAU 2006/2000A model pole and "
                    "equinox. C04 polar motion is applied in the terrestrial frame. "
                    "Native ecliptic longitudes retain their source convention."
                ),
                terrestrial_orientation={
                    "polar_motion_applied": True,
                    "celestial_pole_offsets_applied": cpo_applied,
                    "polar_motion_x_radians": motion[0],
                    "polar_motion_y_radians": motion[1],
                    "tio_locator_radians": motion[2],
                    "celestial_pole_offsets_arcseconds": (
                        list(cpo) if cpo is not None else None
                    ),
                    "cio_locator_policy": (
                        "retain_IAU2006_model_s_before_CPO"
                        if cpo_applied
                        else "IAU2006_model_s_from_model_CIP"
                    ),
                    "origin_policy": (
                        "corrected_CIO_triad_rotated_by_model_EO"
                        if cpo_applied
                        else "IAU2006_2000A_model_equinox"
                    ),
                    "local_frame_policy": "same_polar_motion_and_GAST_for_receiver_and_geodetic_ENU",
                    "orientation_asset_sha256": reference["orientation_asset_sha256"],
                    "tidal_model_id": reference["tidal_model_id"],
                    "cpo_application_policy": (
                        "Source-year1984 onwards, with four qualified TT nodes; "
                        "earlier CPO column semantics remain unqualified, not measured zeros."
                    ),
                    "station_velocity_scope": (
                        "SOFA nominal instantaneous rotation per UT1 second; "
                        "not a full LOD/pole-rate/deformation velocity."
                    ),
                    "vertical_scope": "WGS84 ellipsoid normal, not a surveyed plumb line",
                },
            )
        else:
            pass
    else:
        pass
    return value

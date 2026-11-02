"""Checked complete Mercury/Venus rate from continuous DE441 source formulas."""

from __future__ import annotations

import math
from importlib.metadata import version
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

from fatebridge.core.astro import continuous_lahiri as frames
from fatebridge.core.astro import runtime
from fatebridge.core.astro.inner_source import (
    METHOD_ID,
    SourceDerivativeUnavailable,
    apparent_source,
)
from fatebridge.core.astro.jpl_kinematics import checked_fixed_acceleration
from fatebridge.core.astro.jpl_records import source_records
from fatebridge.core.astro.lunar_tropical_frame import nutation
from fatebridge.core.astro.native_identity import binding_distribution_version
from fatebridge.core.astro.physical_sources import (
    PhysicalEphemerisTrace,
    assert_physical_configuration,
)
from fatebridge.core.astro.reference import PLANET_SWISSEPH_IDS
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.core.jpl_ephemeris import configured_jpl_file
from fatebridge.utils.errors import EphemerisSourceError

POSITION_LINE_ARCSEC = 0.02
FRAME_LINE_ARCSEC = 1e-7


def complete_inner_rate(
    planet: str,
    epoch: float,
    coordinates: Sequence[float],
    model: str,
    *,
    sidereal: bool = False,
    source_trace: Optional[PhysicalEphemerisTrace] = None,
) -> Tuple[Optional[float], Dict[str, Any]]:
    policy: Dict[str, Any] = {
        "method_id": METHOD_ID,
        "epoch_jd_tt": epoch,
        "ephemeris_model": model,
        "reference_frame": "lahiri" if sidereal else "tropical",
        "positions_unchanged": True,
        "position_reproduction_line_arcsec": POSITION_LINE_ARCSEC,
        "frame_component_reproduction_line_arcsec": FRAME_LINE_ARCSEC,
        "source_url": "https://www.astro.com/swisseph/swephprg.htm",
        "source_function": "pyswisseph2.10.3.2/libswe/sweph.c:app_pos_etc_plan,swi_deflect_light,swi_aberr_light",
        "physical_TT_TDB_equivalence_certified": False,
        "native_binary_function_derivative_certified": False,
        "observational_accuracy_certified": False,
        "scope": "Derivative of the declared unrounded source model on its recorded local polynomial and solar-mass branches, plus the checked analytic date frame. The native numerical argument is retained without physical clock conversion. Displayed native positions are unchanged. Mathematical source agreement is not an observational or prediction certificate.",
    }

    def unavailable(reason: str) -> Tuple[None, Dict[str, Any]]:
        policy.update(status="not_applied", reason=reason)
        return None, policy

    swe = runtime.swe
    if planet not in {"Mercury", "Venus"} or model != "jpl":
        return unavailable("unsupported_target_or_model")
    if swe is None or (
        str(swe.version),
        binding_distribution_version(swe, version),
    ) != ("2.10.03", "2.10.3.2"):
        return unavailable("unverified_native_version")
    if not math.isfinite(epoch) or not 1721425.5 <= epoch <= 5373485.5:
        return unavailable("outside_frame_model_domain")
    if epoch == 2451545.0:
        return unavailable("isolated_native_J2000_precession_identity_shortcut")
    if len(coordinates) != 6 or not all(math.isfinite(x) for x in coordinates):
        raise EphemerisSourceError("coordinate_values_unavailable")

    configuration = (configured_ephemeris_path(), configured_jpl_file())
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED | (swe.FLG_SIDEREAL if sidereal else 0)
    trace = source_trace if source_trace is not None else PhysicalEphemerisTrace()
    with runtime.preserve_ephemeris_path():
        if sidereal:
            runtime.ephemeris_call("set_sid_mode", swe.SIDM_LAHIRI, 0.0, 0.0)
        center, returned = runtime.ephemeris_call(
            "calc", epoch, PLANET_SWISSEPH_IDS[planet], flags
        )
        if runtime.ephemeris_model_from_retflag(returned) != model:
            raise EphemerisSourceError("coordinate_model_changed")
        if tuple(center) != tuple(coordinates):
            raise EphemerisSourceError("coordinate_motion_unavailable")
        file_context = tuple(swe.get_current_file_data(0))
        source_context = trace.observe(
            f"{planet}_analytic_inner_source", model, record_factor=False
        )
        policy["source_context"] = source_context
        try:
            with source_records(Path(file_context[0])) as records:
                try:
                    source = apparent_source(records, planet, epoch)
                finally:
                    policy["source_records"] = records.evidence()
            policy["continuous_source"] = source
            runtime.ephemeris_call(
                "set_sid_mode", swe.SIDM_USER | swe.SIDBIT_ECL_T0, epoch, 0.0
            )
            earth, earth_flags = runtime.ephemeris_call(
                "calc",
                epoch,
                swe.EARTH,
                swe.FLG_SWIEPH
                | swe.FLG_SPEED
                | swe.FLG_TRUEPOS
                | swe.FLG_BARYCTR
                | swe.FLG_XYZ
                | swe.FLG_SIDEREAL,
            )
            if runtime.ephemeris_model_from_retflag(earth_flags) != model:
                raise EphemerisSourceError("coordinate_model_changed")
            raw = [
                float(x) for x in source["earth_state"] + source["earth_acceleration"]
            ]
            _, rotation = checked_fixed_acceleration(raw, earth)
            policy["fixed_reception_rotation"] = rotation
            p = frames.mv(
                rotation["matrix"], [float(x) for x in source["direction_icrf"]]
            )
            v = frames.mv(
                rotation["matrix"],
                [float(x) for x in source["derivative_per_native_argument_day"]],
            )
            frame = frames.frame_state(epoch)
            psi, deps, psi_d, _ = nutation(epoch)
            native, native_flags = runtime.ephemeris_call(
                "calc", epoch, swe.ECL_NUT, swe.FLG_SWIEPH
            )
            if (
                native_flags < 0
                or len(native) < 4
                or not all(math.isfinite(x) for x in native[:4])
            ):
                raise EphemerisSourceError("coordinate_values_unavailable")
            mean_eps = math.degrees(frames.pair(epoch, "pepol", "peper")[0][1])
            model_errors = [
                abs(a - b) * 3600 for a, b in zip((mean_eps, psi, deps), native[1:4])
            ]
            origin = psi
            origin_d = psi_d
            if sidereal:
                runtime.ephemeris_call("set_sid_mode", swe.SIDM_LAHIRI, 0.0, 0.0)
                aya_flags, aya = runtime.ephemeris_call(
                    "get_ayanamsa_ex", epoch, swe.FLG_SWIEPH | swe.FLG_NONUT
                )
                if runtime.ephemeris_model_from_retflag(
                    aya_flags
                ) != model or not math.isfinite(aya):
                    raise EphemerisSourceError("coordinate_model_changed")
                model_errors.append(
                    abs(math.remainder(aya - frame["origin_degrees"], 360)) * 3600
                )
                origin, origin_d = -aya, -frame["origin_rate_degrees_per_TT_day"]
            rho2 = math.fsum(x * x for x in p[:2])
            if rho2 <= 0:
                return unavailable("singular_ecliptic_longitude")
            lon = (math.degrees(math.atan2(p[1], p[0])) + origin) % 360
            lat = math.degrees(math.atan2(p[2], math.sqrt(rho2)))
            position_errors = [
                abs(math.remainder(lon - coordinates[0], 360)) * 3600,
                abs(lat - coordinates[1]) * 3600,
            ]
            policy.update(
                native_frame_component_errors_arcsec=model_errors,
                display_position_reproduction_errors_arcsec=position_errors,
            )
            if max(model_errors) > FRAME_LINE_ARCSEC:
                return unavailable("declared_native_frame_not_reproduced")
            if max(position_errors) > POSITION_LINE_ARCSEC:
                return unavailable("continuous_source_display_position_not_reproduced")
            moving = frames.mv(frame["mean_omega"], p)
            source_rate = math.degrees((p[0] * v[1] - p[1] * v[0]) / rho2)
            frame_rate = math.degrees((p[0] * moving[1] - p[1] * moving[0]) / rho2)
            complete = math.fsum((source_rate, frame_rate, origin_d))
            if not math.isfinite(complete):
                raise EphemerisSourceError("coordinate_motion_unavailable")
            policy.update(
                status="applied",
                fixed_reception_source_rate_degrees_per_native_argument_day=source_rate,
                mean_frame_rate_degrees_per_native_argument_day=frame_rate,
                origin_rate_degrees_per_native_argument_day=origin_d,
                complete_display_rate_degrees_per_native_argument_day=complete,
                selected_stencil="analytic_source_and_date_frame",
                sample_count=0,
            )
            return complete, policy
        except SourceDerivativeUnavailable as error:
            return unavailable(str(error))
        finally:
            runtime.ephemeris_call("set_sid_mode", swe.SIDM_LAHIRI, 0.0, 0.0)
            replay, replay_flags = runtime.ephemeris_call(
                "calc", epoch, PLANET_SWISSEPH_IDS[planet], flags
            )
            assert_physical_configuration(configuration[0])
            if configured_jpl_file() != configuration[1]:
                raise EphemerisSourceError("physical_configuration_changed")
            if tuple(replay) != tuple(center) or replay_flags != returned:
                raise EphemerisSourceError("coordinate_motion_unavailable")
            if tuple(swe.get_current_file_data(0)) != file_context:
                raise EphemerisSourceError("changed_during")
            policy.update(
                center_native_states_reproduced_exactly=True,
                center_file_context_reproduced_exactly=True,
            )

"""True solar arc and explicitly labelled natal/directed Hamburg geometry.

The symbolic key is declared: one TT ephemeris day per 365.25 UTC calendar
days. Directed factors are rotations of natal factors, not future observations.
All contacts use exact rational arithmetic on the supplied IEEE coordinates.
"""

from __future__ import annotations

import math
from datetime import datetime
from fractions import Fraction
from itertools import combinations
from typing import Any, Mapping

from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.astro.day_meridian import RULESET as DAY_MERIDIAN_RULESET
from fatebridge.core.astro.day_meridian import (
    build_day_meridian,
    day_meridian_coordinates,
    target_sun_state,
)
from fatebridge.core.astro.midpoints import HYPOTHETICAL_BODIES
from fatebridge.core.astro.mixed_pairs import (
    mixed_pair_geometry,
    unavailable_mixed_pairs,
)
from fatebridge.core.astro.mixed_sensitivity import mixed_pair_sensitivity
from fatebridge.core.astro.physical_sources import PhysicalSourceCohort
from fatebridge.core.astro.progression_key_sources import (
    progression_key_source_comparison,
)
from fatebridge.core.astro.reference_angles import qualify_reference_geometry
from fatebridge.core.astro.sensitive import original_example_reading
from fatebridge.core.astro.sensitivity_grid import RecordedBirthSample
from fatebridge.core.astro.sensitivity_timing import (
    SpecialtySampleTime,
    SpecialtySampleTimes,
)
from fatebridge.core.astro.solar_arc_state import (
    MAX_KEY_YEARS,
    SolarArcSampleUnavailable,
    SolarArcState,
    SolarArcTimeRangeError,
    resolve_solar_arc_state,
)
from fatebridge.core.astro.solar_ephemeris import SolarEphemerisBatch
from fatebridge.core.astro.source_pattern import (
    source_pattern_sample,
    source_pattern_summary,
)
from fatebridge.core.astro.time_scales import ephemeris_time, utc_clock
from fatebridge.core.astro.witte1925_table import source_table_analysis

RULESET = "hamburg_true_solar_arc_v1"


SOURCES = [
    {
        "id": "bonert_2007_true_solar_arc",
        "author": "Klaus Bonert",
        "title": "Sonnenbogen-Direktionen im Lebenslauf, Chiron 2007, author excerpt",
        "sections": ["Der wahre Sonnenbogen", "Die Sonne und der Sonnenbogen"],
        "scope": "Progressed-Sun displacement rotates natal factors; empirical claims and event delineations are not adopted",
    },
    {
        "id": "witte_al319_static_biwheel",
        "author": "Witte-Verlag Hamburg",
        "title": "AstrologicPC Installation, Registrierung und Hinweise, PDF created 2023-01-19",
        "sections": ["p.7: static natal/8-degree solar-arc example"],
        "scope": "Publisher-authored numerical rotation example, not a date-to-arc oracle or Witte's complete original rulebook",
    },
]


def _display(value: Fraction) -> float:
    return min(float(value % 360), math.nextafter(360.0, 0.0))


def _residual(a: Fraction, b: Fraction, period: int) -> Fraction:
    return (a - b + Fraction(period, 2)) % period - Fraction(period, 2)


def solar_arc_state(
    birth_utc: datetime,
    birth_jd_tt: float,
    analysis_datetime: datetime,
    *,
    _batch: SolarEphemerisBatch | None = None,
) -> dict[str, Any]:
    """Calculate actual tropical solar displacement, with no one-degree shortcut."""
    if _batch is None:
        with SolarEphemerisBatch() as batch:
            result = dict(
                resolve_solar_arc_state(
                    birth_utc, birth_jd_tt, analysis_datetime, batch=batch
                ).to_record()
            )
        result["sun_ephemeris_source"] = batch.result
        return result
    return dict(
        resolve_solar_arc_state(
            birth_utc, birth_jd_tt, analysis_datetime, batch=_batch
        ).to_record()
    )


def rotate_factors(
    longitudes: Mapping[str, float], arc: float | Fraction
) -> dict[str, float]:
    if not isinstance(arc, Fraction) and not math.isfinite(arc):
        raise ValueError("Solar arc must be finite")
    result = {}
    for name, value in longitudes.items():
        if not math.isfinite(value):
            raise ValueError("Natal coordinates must be finite")
        result[name] = _display(Fraction(value) + Fraction(arc))
    return result


def biwheel_geometry(
    longitudes: Mapping[str, float],
    arc_degrees: float | Fraction,
    *,
    orb_degrees: float = 1.0,
) -> dict[str, Any]:
    """Two/three/four labelled factor references, with full untruncated hit lists.

    Each midpoint has two different factor names. The same named factor at
    different layers is a different reference; zero-arc identities are flagged.
    This is not all possible interleaved natal/directed four-factor equations.
    """
    if (
        (not isinstance(arc_degrees, Fraction) and not math.isfinite(arc_degrees))
        or not math.isfinite(orb_degrees)
        or not 0 <= orb_degrees <= 5
    ):
        raise ValueError("Finite arc and an inclusive orb within 0..5 degrees required")
    if any(not math.isfinite(v) for v in longitudes.values()):
        raise ValueError("Natal coordinates must be finite")
    natal = {k: Fraction(v) % 360 for k, v in longitudes.items()}
    arc, orb = Fraction(arc_degrees) % 360, Fraction(orb_degrees)
    directed = {k: (v + arc) % 360 for k, v in natal.items()}
    axes = [
        (a, b, ((natal[a] + natal[b]) / 2) % 180) for a, b in combinations(natal, 2)
    ]
    dials, counts = {}, {}

    def contact(
        equation: str,
        delta: Fraction,
        names: tuple[str, ...],
        identity: bool,
        **refs: Any,
    ) -> dict[str, Any]:
        return {
            "rule_id": "hamburg.solar_arc.biwheel_geometry.v1",
            "equation": equation,
            "orb": float(abs(delta)),
            "signed_orb": float(delta),
            "contains_hypothetical": any(name in HYPOTHETICAL_BODIES for name in names),
            "zero_arc_identity": identity,
            **refs,
        }

    for period in (90, 45):
        half_p_f = period * 0.5
        two, three, four = [], [], []
        arc_f = float(arc)
        natal_f = {k: float(v) for k, v in natal.items()}
        directed_f = {k: float(v) for k, v in directed.items()}
        axes_f = [(a, b, ax, float(ax)) for a, b, ax in axes]
        for a, value in directed.items():
            vf = directed_f[a]
            for b, reference in natal.items():
                delta_f = (vf - natal_f[b] + half_p_f) % period - half_p_f
                if abs(delta_f) > 1.0 + 1e-8:
                    continue
                if abs(delta_f) >= 1.0 - 1e-8:
                    delta = _residual(value, reference, period)
                    if abs(delta) > orb:
                        continue
                else:
                    delta = delta_f
                two.append(
                    contact(
                        f"{a}.solar_arc={b}.natal",
                        delta,
                        (a, b),
                        arc == 0 and a == b,
                        id_a=a,
                        id_b=b,
                        layer_a="solar_arc",
                        layer_b="natal",
                    )
                )
        import bisect as _bisect

        sorted_axes = sorted(
            ((ax_f % period, a, b, axis, ax_f) for a, b, axis, ax_f in axes_f),
            key=lambda item: item[0],
        )
        n_ax = len(sorted_axes)
        orb_guard = 1.0 + 1e-8
        for point in natal:
            p_natal_f = natal_f[point]
            p_dir_f = directed_f[point]
            for is_solar_point, p_val_f in (
                (True, p_dir_f),
                (False, p_natal_f),
            ):
                target_mod = (
                    (p_val_f % period)
                    if is_solar_point
                    else ((p_val_f - arc_f) % period)
                )
                lo_key = target_mod - orb_guard
                ranges = (
                    [(lo_key + period, period), (0.0, target_mod + orb_guard)]
                    if lo_key < 0.0
                    else (
                        [(lo_key, period), (0.0, target_mod + orb_guard - period)]
                        if target_mod + orb_guard > period
                        else [(lo_key, target_mod + orb_guard)]
                    )
                )
                for r_start, r_end in ranges:
                    idx = _bisect.bisect_left(
                        sorted_axes, r_start, key=lambda item: item[0]
                    )
                    while idx < n_ax and sorted_axes[idx][0] <= r_end:
                        _ax_mod, a, b, axis, ax_f = sorted_axes[idx]
                        idx += 1
                        r_val_f = ax_f if is_solar_point else (ax_f + arc_f) % 180.0
                        delta_f = (p_val_f - r_val_f + half_p_f) % period - half_p_f
                        if abs(delta_f) > orb_guard:
                            continue
                        if abs(delta_f) >= 1.0 - 1e-8:
                            if is_solar_point:
                                delta = _residual(directed[point], axis, period)
                            else:
                                delta = _residual(
                                    natal[point], (axis + arc) % 180, period
                                )
                            if abs(delta) > orb:
                                continue
                        else:
                            delta = delta_f
                        point_layer = "solar_arc" if is_solar_point else "natal"
                        axis_layer = "natal" if is_solar_point else "solar_arc"
                        three.append(
                            contact(
                                f"{point}.{point_layer}={a}.{axis_layer}/{b}.{axis_layer}",
                                delta,
                                (point, a, b),
                                False,
                                point=point,
                                point_layer=point_layer,
                                id_a=a,
                                id_b=b,
                                axis_layer=axis_layer,
                            )
                        )
        for a, b, axis, ax_f in axes_f:
            shifted_raw = ax_f + arc_f
            shifted_mod = shifted_raw % period
            lo_key = shifted_mod - orb_guard
            ranges = (
                [(lo_key + period, period), (0.0, shifted_mod + orb_guard)]
                if lo_key < 0.0
                else (
                    [(lo_key, period), (0.0, shifted_mod + orb_guard - period)]
                    if shifted_mod + orb_guard > period
                    else [(lo_key, shifted_mod + orb_guard)]
                )
            )
            for r_start, r_end in ranges:
                idx = _bisect.bisect_left(
                    sorted_axes, r_start, key=lambda item: item[0]
                )
                while idx < n_ax and sorted_axes[idx][0] <= r_end:
                    _ref_mod, c, d, reference, ref_f = sorted_axes[idx]
                    idx += 1
                    delta_f = (shifted_raw - ref_f + half_p_f) % period - half_p_f
                    if abs(delta_f) > orb_guard:
                        continue
                    if abs(delta_f) >= 1.0 - 1e-8:
                        delta = _residual(axis + arc, reference, period)
                        if abs(delta) > orb:
                            continue
                    else:
                        delta = delta_f
                    four.append(
                        contact(
                            f"{a}.solar_arc/{b}.solar_arc={c}.natal/{d}.natal",
                            delta,
                            (a, b, c, d),
                            arc == 0 and a == c and b == d,
                            id_a=a,
                            id_b=b,
                            id_c=c,
                            id_d=d,
                            layer_a="solar_arc",
                            layer_b="solar_arc",
                            layer_c="natal",
                            layer_d="natal",
                        )
                    )
        two.sort(key=lambda r: (r["orb"], r["equation"]))
        three.sort(key=lambda r: (r["orb"], r["equation"]))
        four.sort(key=lambda r: (r["orb"], r["equation"]))
        zero_count = sum(row["zero_arc_identity"] for row in (*two, *three, *four))
        dials[str(period)] = {
            "period_degrees": period,
            "two_factor_contacts": two,
            "three_factor_contacts": three[:5],
            "three_factor_total_count": len(three),
            "four_factor_contacts": four[:5],
            "four_factor_total_count": len(four),
        }
        counts[str(period)] = {
            "two_factor": len(two),
            "three_factor": len(three),
            "four_factor": len(four),
            "zero_arc_identities": zero_count,
        }
    return {"dials": dials, "contact_counts": counts}


def _reading(values: Mapping[str, float], arc: Fraction) -> dict[str, Any] | None:
    factors = {k: Fraction(v) for k, v in values.items()}
    factors["Midheaven"] = (factors["Midheaven"] + Fraction(arc)) % 360
    return original_example_reading(
        "Mars", "Jupiter", "Zeus", "Midheaven", factors, axis_orb=Fraction(1)
    )


def enrich_solar_arc(
    payload: dict[str, Any],
    birth: AstroBirthInfo,
    analysis_datetime: datetime | None,
    *,
    sample_times: SpecialtySampleTimes | None = None,
) -> None:
    if analysis_datetime is None:
        return
    layer = payload["midpoint_analysis"]
    if layer["status"] != "computed":
        layer["solar_arc_analysis"] = {
            "status": "unavailable",
            "ruleset_id": RULESET,
            "reason": "Native natal factors are required",
            "mixed_pair_geometry": unavailable_mixed_pairs(
                "Native natal factors are required",
                uncertainty_minutes=layer.get("time_sensitivity", {}).get(
                    "uncertainty_minutes"
                ),
            ),
            "daily_meridian": {
                "status": "unavailable",
                "ruleset_id": DAY_MERIDIAN_RULESET,
                "reason": "Native natal factors are required",
            },
        }
        return
    uncertainty = layer["time_sensitivity"]
    sample_states: list[SolarArcState | SolarArcSampleUnavailable] = []
    analysis_scales = ephemeris_time(analysis_datetime)
    nominal_clock = (
        sample_times.samples[sample_times.nominal_index]
        if sample_times is not None
        else None
    )
    birth_utc = birth.require_utc_datetime
    # Reuse the retained source calendar, or the modeled UTC calendar from
    # the atomic era. Historical inverse LAT keeps its existing clock rule.
    if (
        nominal_clock is None
        and birth.native_epoch is not None
        and (birth.native_epoch.source_calendar is not None or birth_utc.year >= 1960)
    ):
        recorded = RecordedBirthSample(birth.native_epoch)
        nominal_clock = SpecialtySampleTime(
            recorded, recorded.epoch, recorded.nominal_calendar
        )
    nominal_birth_tt = None
    if nominal_clock is None:
        nominal_birth_tt = (
            birth.native_epoch.time.tt
            if birth.native_epoch is not None
            else utc_clock(birth_utc).tt
        )
    # Collect ephemeris facts under one lock; expensive pure geometry follows
    # outside it. Compare each semantic role across the same birth-time grid,
    # rather than demanding one model across genuinely different epochs.
    with SolarEphemerisBatch() as batch:
        nominal_state = resolve_solar_arc_state(
            birth_utc,
            layer["profile"]["julian_day_tt"],
            analysis_datetime,
            batch=batch,
            clock=nominal_clock,
            birth_tt=nominal_birth_tt,
            analysis_tt=analysis_scales.tt,
        )
        natal_index, progressed_index = nominal_state.sun_observation_indices
        batch.check_native(layer["profile"]["physical_ephemeris_source"], natal_index)
        cohorts = (PhysicalSourceCohort(), PhysicalSourceCohort())
        for cohort, index in zip(cohorts, (natal_index, progressed_index)):
            cohort.add(batch.source(index))
        target = target_sun_state(
            analysis_datetime, _batch=batch, _scales=analysis_scales
        )
        if uncertainty["status"] == "sampled":
            for index, sample in enumerate(uncertainty["samples"]):
                clock = (
                    sample_times.samples[index] if sample_times is not None else None
                )
                try:
                    computed_state = resolve_solar_arc_state(
                        (
                            datetime.fromisoformat(sample["effective_utc"])
                            if clock is None
                            else None
                        ),
                        sample["julian_day_tt"],
                        analysis_datetime,
                        batch=batch,
                        clock=clock,
                        analysis_tt=analysis_scales.tt,
                    )
                except SolarArcSampleUnavailable as error:
                    # The nominal chart is valid. Keep this confirmed sample
                    # as unknown; do not extrapolate, shorten the interval or
                    # reinterpret a model-range failure as absent geometry.
                    sample_states.append(error)
                    continue
                indices = computed_state.sun_observation_indices
                sample_source = uncertainty["physical_ephemeris_sources"][
                    sample["physical_source_index"]
                ]
                batch.check_native(sample_source, indices[0])
                for cohort, index in zip(cohorts, indices):
                    cohort.add(batch.source(index))
                sample_states.append(computed_state)
    profile: dict[str, Any] = dict(nominal_state.to_record())
    profile["sun_ephemeris_source"] = batch.result
    profile["key_source_comparison"] = progression_key_source_comparison()
    values = {f["id"]: f["longitude"] for f in layer["factors"]}
    arc = nominal_state.arc
    rotated = rotate_factors(values, arc)
    reading = _reading(values, arc)
    interpretations = []
    if reading is not None:
        reading = {
            **reading,
            # The source helper identifies the actual coordinate evidence.
            # Keep that identity at zero arc: a second diagram is not new evidence.
            "factor_layers": {
                "Mars": "natal",
                "Jupiter": "natal",
                "Zeus": "natal",
                "Midheaven": "solar_arc",
            },
            "analysis_utc": profile["analysis_utc"],
            "solar_arc_degrees": float(arc),
            "basis_expression": "Mars.natal+Jupiter.natal-Zeus.natal=Midheaven.solar_arc",
            "rule_id": "hamburg.udo1996.directed_mc.v1",
        }
        interpretations.append(reading)
    day_samples = []
    sensitivity = {
        "status": uncertainty["status"],
        "uncertainty_minutes": uncertainty["uncertainty_minutes"],
        "continuous_interval_proven": False,
        "scope": "Directed MC source pattern only; full biwheel contact-set stability not evaluated",
        **(
            {"recorded_physical_grid": uncertainty["recorded_physical_grid"]}
            if "recorded_physical_grid" in uncertainty
            else {}
        ),
        **{
            key: uncertainty[key]
            for key in (
                "input_clock_basis",
                "recorded_interval_start_clock",
                "recorded_interval_end_clock",
                "requested_clock_radius_seconds",
                "recorded_interval_start_utc",
                "recorded_interval_end_utc",
            )
            if "input_clock_basis" in uncertainty and key in uncertainty
        },
    }
    if uncertainty["status"] == "sampled":
        assessments: list[dict[str, Any] | None] = []
        samples = []
        unavailable = sum(
            isinstance(state, SolarArcSampleUnavailable) for state in sample_states
        )
        for sample, state in zip(uncertainty["samples"], sample_states):
            if isinstance(state, SolarArcSampleUnavailable):
                assessments.append(None)
                missing = {
                    "offset_seconds": sample["offset_seconds"],
                    "effective_utc": sample["effective_utc"],
                    "status": "unavailable",
                    "reason_code": state.reason_code,
                    **(
                        {
                            "key_years": state.key_years,
                            "supported_key_years": [0.0, MAX_KEY_YEARS],
                        }
                        if isinstance(state, SolarArcTimeRangeError)
                        else {}
                    ),
                }
                samples.append({**missing, "julian_day_tt": sample["julian_day_tt"]})
                day_samples.append(
                    {
                        **missing,
                        "recorded_utc": sample["recorded_utc"],
                        "julian_day_tt": sample["julian_day_tt"],
                        **(
                            {"angle_definition": sample["angle_definition"]}
                            if "angle_definition" in sample
                            else {}
                        ),
                    }
                )
                continue
            day_samples.append(
                {
                    **({"status": "computed"} if unavailable else {}),
                    "offset_seconds": sample["offset_seconds"],
                    "recorded_utc": sample["recorded_utc"],
                    "effective_utc": sample["effective_utc"],
                    "julian_day_tt": state.birth_julian_day_tt,
                    "progressed_julian_day_tt": state.progressed_julian_day_tt,
                    "sun_observation_indices": list(state.sun_observation_indices),
                    "key_years": state.key_years,
                    **(
                        {"angle_definition": sample["angle_definition"]}
                        if "angle_definition" in sample
                        else {}
                    ),
                    **day_meridian_coordinates(
                        sample["factor_longitudes"]["Midheaven"],
                        state.natal_tropical_sun,
                        state.arc,
                        target["target_tropical_sun"],
                    ),
                }
            )
            assessment = source_pattern_sample(
                sample["factor_longitudes"],
                sample.get("angle_definition"),
                solar_arc_degrees=state.arc,
            )
            assessments.append(assessment)
            samples.append(
                {
                    **({"status": "computed"} if unavailable else {}),
                    "offset_seconds": sample["offset_seconds"],
                    "effective_utc": sample["effective_utc"],
                    "julian_day_tt": sample["julian_day_tt"],
                    "progressed_julian_day_tt": state.progressed_julian_day_tt,
                    "sun_observation_indices": list(state.sun_observation_indices),
                    "sun_ephemeris_models": list(state.sun_ephemeris_models),
                    "solar_arc_degrees": float(state.arc),
                    "directed_midheaven_longitude": assessment["midheaven_longitude"],
                    "source_direct_orb_degrees": assessment["direct_orb_degrees"],
                    "source_condition_met": assessment["condition_met"],
                    **(
                        {
                            "source_reference_geometry_resolved": False,
                            "source_reference_angle_basis": assessment[
                                "reference_angle_basis"
                            ],
                            "backend_convention": {
                                "directed_midheaven_longitude": assessment[
                                    "backend_midheaven_longitude"
                                ],
                                "source_direct_orb_degrees": assessment[
                                    "backend_direct_orb_degrees"
                                ],
                                "source_condition_met": assessment[
                                    "backend_condition_met"
                                ],
                            },
                        }
                        if not assessment["reference_geometry_resolved"]
                        else {}
                    ),
                }
            )
        count = uncertainty["sample_count"]
        computed = count - unavailable
        summary = source_pattern_summary(assessments)
        state_name = summary["sampled_status"]
        unresolved = summary.get("unresolved_reference_sample_count", 0)
        sensitivity.update(
            **(
                {
                    "status": "partial",
                    "computed_sample_count": computed,
                    "unavailable_sample_count": unavailable,
                    "sample_scope_policy": "Keep all confirmed birth-time samples; compute only when a nominal calendar coordinate and a supported key are available",
                }
                if unavailable
                else {}
            ),
            sample_count=count,
            samples=samples,
            source_pattern={
                "source_id": "udo_rudolph_1996_abc_excerpt",
                "basis_expression": "Mars.natal+Jupiter.natal-Zeus.natal=Midheaven.solar_arc",
                **summary,
                "maximum_direct_orb_degrees": 2.0,
            },
        )
        if unresolved:
            sensitivity.update(
                status="partial", unresolved_reference_sample_count=unresolved
            )
        for item in interpretations:
            item["birth_time_sampled_status"] = state_name
    layer["solar_arc_analysis"] = {
        "status": "computed",
        "ruleset_id": RULESET,
        "version": "3",
        "author": "FateBridge",
        "profile": {
            **profile,
            "orb_degrees": 1.0,
            "orb_policy": "inclusive midpoint-axis orb; implementation choice",
            "display_frame": "natal chart frame held fixed; tropical solar arc also used for a natal Lahiri display",
            "directed_factors_are_observations": False,
        },
        "directed_factors": [
            {
                "id": f["id"],
                "longitude": rotated[f["id"]],
                "natal_longitude": f["longitude"],
                "kind": f["kind"],
                "natal_model": f["model"],
                "model": "symbolic_solar_arc_rotation",
                **(
                    {key: f[key] for key in ("coordinate_basis", "angle_definition")}
                    if "coordinate_basis" in f
                    else {}
                ),
            }
            for f in layer["factors"]
        ],
        **biwheel_geometry(values, arc),
        "mixed_pair_geometry": mixed_pair_geometry(
            values, arc, hypothetical_ids=HYPOTHETICAL_BODIES, max_contacts_per_field=2
        ),
        "interpretations": interpretations,
        "birth_time_sensitivity": sensitivity,
        "daily_meridian": build_day_meridian(
            natal_upper_meridian=values["Midheaven"],
            solar_state=nominal_state,
            sun_observations=batch.observations,
            sample_states=sample_states,
            target=target,
            uncertainty=uncertainty,
            samples=day_samples,
            native_profile=layer["profile"],
            native_factors=layer["factors"],
            nominal_effective_utc=birth_utc.isoformat(),
            supported_key_years=(0.0, MAX_KEY_YEARS),
            sample_times=sample_times,
            nominal_clock=nominal_clock,
            nominal_birth_tt=nominal_birth_tt,
            analysis_tt=analysis_scales.tt,
        ),
        "original_table_1925": source_table_analysis(),
    }
    mixed = layer["solar_arc_analysis"]["mixed_pair_geometry"]
    mixed["birth_time_sensitivity"] = mixed_pair_sensitivity(
        nominal_state,
        values,
        uncertainty,
        sample_states,
        nominal_angle_definition=layer["profile"].get("angle_definition"),
    )
    if mixed["birth_time_sensitivity"]["status"] in {"sampled", "partial"}:
        mixed["profile"]["birth_time_contact_sensitivity"] = (
            mixed["birth_time_sensitivity"]["status"] + "_finite_grid"
        )
    if "reference_angle_model" in layer["profile"]:
        layer["solar_arc_analysis"]["profile"]["reference_angle_model"] = layer[
            "profile"
        ]["reference_angle_model"]
    if "angle_definition" in layer["profile"]:
        layer["solar_arc_analysis"]["profile"]["angle_definition"] = layer["profile"][
            "angle_definition"
        ]
        qualify_reference_geometry(
            layer["solar_arc_analysis"], layer["profile"]["angle_definition"]
        )
        mixed = layer["solar_arc_analysis"]["mixed_pair_geometry"]
        qualify_reference_geometry(
            {
                "dials": {
                    key: {
                        "two_factor_contacts": [],
                        "three_factor_contacts": [],
                        "four_factor_contacts": [
                            *dial["arc_dependent_contacts"],
                            *dial["arc_invariant_contacts"],
                        ],
                    }
                    for key, dial in mixed["dials"].items()
                }
            },
            layer["profile"]["angle_definition"],
        )
    layer["solar_arc_analysis"] = layer["solar_arc_analysis"]

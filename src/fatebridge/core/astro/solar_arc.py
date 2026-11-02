"""True solar arc and explicitly labelled natal/directed Hamburg geometry.

The symbolic key is declared: one TT ephemeris day per 365.25 UTC calendar
days. Directed factors are rotations of natal factors, not future observations.
All contacts use exact rational arithmetic on the supplied IEEE coordinates.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from fractions import Fraction
from itertools import combinations
from typing import Any, Dict, Mapping

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
from fatebridge.core.astro.solar_ephemeris import SolarEphemerisBatch
from fatebridge.core.astro.source_pattern import (
    source_pattern_sample,
    source_pattern_summary,
)
from fatebridge.core.astro.witte1925_table import source_table_analysis

RULESET = "hamburg_true_solar_arc_v1"
YEAR_DAYS = 365.25
MAX_KEY_YEARS = 150.0


class SolarArcTimeRangeError(ValueError):
    """A stated symbolic key range, distinct from ephemeris/configuration faults."""

    def __init__(self, key_years: float):
        super().__init__(
            "Solar arc supports target instants 0..150 Julian key years after birth"
        )
        self.key_years = key_years
        self.reason_code = (
            "target_before_birth_time_sample"
            if key_years < 0
            else "target_after_supported_key_range_for_sample"
        )


SOURCES = [
    {
        "id": "bonert_2007_true_solar_arc",
        "author": "Klaus Bonert",
        "title": "Sonnenbogen-Direktionen im Lebenslauf, Chiron 2007, author excerpt",
        "url": "https://www.astro.com/astrologie/in_sonnenbogen_g.htm",
        "sections": ["Der wahre Sonnenbogen", "Die Sonne und der Sonnenbogen"],
        "scope": "Progressed-Sun displacement rotates natal factors; empirical claims and event delineations are not adopted",
    },
    {
        "id": "witte_al319_static_biwheel",
        "author": "Witte-Verlag Hamburg",
        "title": "AstrologicPC Installation, Registrierung und Hinweise, PDF created 2023-01-19",
        "url": "https://witte-verlag.com/pdf/source/AL319_HINWEISE.pdf",
        "sections": ["p.7: static natal/8-degree solar-arc example"],
        "source_sha256": "f319a3590d2214347af1d99bdb5d2d5634133cfb3c0cbc89f16c822f97851692",
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
) -> Dict[str, Any]:
    """Calculate actual tropical solar displacement, with no one-degree shortcut."""
    if _batch is None:
        with SolarEphemerisBatch() as batch:
            result = solar_arc_state(
                birth_utc, birth_jd_tt, analysis_datetime, _batch=batch
            )
        result["sun_ephemeris_source"] = batch.result
        return result
    if birth_utc.utcoffset() is None or analysis_datetime.utcoffset() is None:
        raise ValueError("Solar-arc instants require explicit timezone offsets")
    analysis_datetime = analysis_datetime.astimezone(timezone.utc)
    birth_utc = birth_utc.astimezone(timezone.utc)
    elapsed_days = (analysis_datetime - birth_utc).total_seconds() / 86400
    key_years = elapsed_days / YEAR_DAYS
    if not 0 <= key_years <= MAX_KEY_YEARS:
        raise SolarArcTimeRangeError(key_years)
    progressed_jd = birth_jd_tt + key_years
    observations = [_batch.sun(jd) for jd in (birth_jd_tt, progressed_jd)]
    positions = [row["longitude"] for row in observations]
    models = [row["model"] for row in observations]
    arc = (Fraction(positions[1]) - Fraction(positions[0])) % 360
    return {
        "analysis_utc": analysis_datetime.astimezone(timezone.utc).isoformat(),
        "birth_effective_utc": birth_utc.astimezone(timezone.utc).isoformat(),
        "elapsed_calendar_days": elapsed_days,
        "year_days": YEAR_DAYS,
        "key_years": key_years,
        "birth_julian_day_tt": birth_jd_tt,
        "progressed_julian_day_tt": progressed_jd,
        "julian_day_resolution_seconds": math.ulp(birth_jd_tt) * 86400,
        "natal_tropical_sun": positions[0],
        "progressed_tropical_sun": positions[1],
        "solar_arc_degrees": float(arc),
        "one_degree_per_year_degrees": key_years,
        "difference_from_one_degree_per_year": float(arc) - key_years,
        "sun_ephemeris_models": models,
        "sun_observation_indices": [row["index"] for row in observations],
        "key_policy": "1 TT ephemeris day per 365.25 UTC calendar days; calendar subtraction ignores leap seconds; symbolic convention, not a measured event clock",
    }


def rotate_factors(longitudes: Mapping[str, float], arc: float) -> Dict[str, float]:
    if not math.isfinite(arc):
        raise ValueError("Solar arc must be finite")
    result = {}
    for name, value in longitudes.items():
        if not math.isfinite(value):
            raise ValueError("Natal coordinates must be finite")
        result[name] = _display(Fraction(value) + Fraction(arc))
    return result


def biwheel_geometry(
    longitudes: Mapping[str, float], arc_degrees: float, *, orb_degrees: float = 1.0
) -> Dict[str, Any]:
    """Two/three/four labelled factor references, with full untruncated hit lists.

    Each midpoint has two different factor names. The same named factor at
    different layers is a different reference; zero-arc identities are flagged.
    This is not all possible interleaved natal/directed four-factor equations.
    """
    if (
        not math.isfinite(arc_degrees)
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
    ) -> Dict[str, Any]:
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
        two, three, four = [], [], []
        for a, value in directed.items():
            for b, reference in natal.items():
                delta = _residual(value, reference, period)
                if abs(delta) <= orb:
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
        for point in natal:
            for a, b, axis in axes:
                for point_layer, axis_layer, value, reference in (
                    ("solar_arc", "natal", directed[point], axis),
                    ("natal", "solar_arc", natal[point], (axis + arc) % 180),
                ):
                    delta = _residual(value, reference, period)
                    if abs(delta) <= orb:
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
        for a, b, axis in axes:
            for c, d, reference in axes:
                delta = _residual(axis + arc, reference, period)
                if abs(delta) <= orb:
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
        dials[str(period)] = {
            "period_degrees": period,
            "two_factor_contacts": two,
            "three_factor_contacts": three,
            "four_factor_contacts": four,
        }
        counts[str(period)] = {
            "two_factor": len(two),
            "three_factor": len(three),
            "four_factor": len(four),
            "zero_arc_identities": sum(
                row["zero_arc_identity"] for row in [*two, *three, *four]
            ),
        }
    return {"dials": dials, "contact_counts": counts}


def _reading(values: Mapping[str, float], arc: float) -> Dict[str, Any] | None:
    factors = {k: Fraction(v) for k, v in values.items()}
    factors["Midheaven"] = (factors["Midheaven"] + Fraction(arc)) % 360
    return original_example_reading(
        "Mars", "Jupiter", "Zeus", "Midheaven", factors, axis_orb=Fraction(1)
    )


def enrich_solar_arc(
    payload: Dict[str, Any], birth: AstroBirthInfo, analysis_datetime: datetime | None
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
    sample_states: list[Dict[str, Any] | SolarArcTimeRangeError] = []
    # Collect ephemeris facts under one lock; expensive pure geometry follows
    # outside it. Compare each semantic role across the same birth-time grid,
    # rather than demanding one model across genuinely different epochs.
    with SolarEphemerisBatch() as batch:
        profile = solar_arc_state(
            birth.require_utc_datetime,
            layer["profile"]["julian_day_tt"],
            analysis_datetime,
            _batch=batch,
        )
        natal_index, progressed_index = profile["sun_observation_indices"]
        batch.check_native(layer["profile"]["physical_ephemeris_source"], natal_index)
        cohorts = (PhysicalSourceCohort(), PhysicalSourceCohort())
        for cohort, index in zip(cohorts, (natal_index, progressed_index)):
            cohort.add(batch.source(index))
        target = target_sun_state(analysis_datetime, _batch=batch)
        if uncertainty["status"] == "sampled":
            for sample in uncertainty["samples"]:
                try:
                    computed_state = solar_arc_state(
                        datetime.fromisoformat(sample["effective_utc"]),
                        sample["julian_day_tt"],
                        analysis_datetime,
                        _batch=batch,
                    )
                except SolarArcTimeRangeError as error:
                    # The nominal chart is valid. Keep this confirmed sample
                    # as unknown; do not extrapolate, shorten the interval or
                    # reinterpret a model-range failure as absent geometry.
                    sample_states.append(error)
                    continue
                indices = computed_state["sun_observation_indices"]
                sample_source = uncertainty["physical_ephemeris_sources"][
                    sample["physical_source_index"]
                ]
                batch.check_native(sample_source, indices[0])
                for cohort, index in zip(cohorts, indices):
                    cohort.add(batch.source(index))
                sample_states.append(computed_state)
    profile["sun_ephemeris_source"] = batch.result
    profile["key_source_comparison"] = progression_key_source_comparison()
    values = {f["id"]: f["longitude"] for f in layer["factors"]}
    arc = profile["solar_arc_degrees"]
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
            "solar_arc_degrees": arc,
            "basis_expression": "Mars.natal+Jupiter.natal-Zeus.natal=Midheaven.solar_arc",
            "rule_id": "hamburg.udo1996.directed_mc.v1",
            "reading_zh": "依该书对推移MC占据敏感点的说明，此指定推运时刻满足个人目标与行动成效这一象征主题的几何条件；现实效果尚未验证。",
        }
        interpretations.append(reading)
    day_samples = []
    sensitivity = {
        "status": uncertainty["status"],
        "uncertainty_minutes": uncertainty["uncertainty_minutes"],
        "continuous_interval_proven": False,
        "sample_frequency_is_probability": False,
        "scope": "Directed MC source pattern only; full biwheel contact-set stability not evaluated",
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
        assessments: list[Dict[str, Any] | None] = []
        samples = []
        unavailable = sum(
            isinstance(state, SolarArcTimeRangeError) for state in sample_states
        )
        for sample, state in zip(uncertainty["samples"], sample_states):
            if isinstance(state, SolarArcTimeRangeError):
                assessments.append(None)
                missing = {
                    "offset_seconds": sample["offset_seconds"],
                    "effective_utc": sample["effective_utc"],
                    "status": "unavailable",
                    "reason_code": state.reason_code,
                    "key_years": state.key_years,
                    "supported_key_years": [0.0, MAX_KEY_YEARS],
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
                    "julian_day_tt": state["birth_julian_day_tt"],
                    "progressed_julian_day_tt": state["progressed_julian_day_tt"],
                    "sun_observation_indices": state["sun_observation_indices"],
                    "key_years": state["key_years"],
                    **(
                        {"angle_definition": sample["angle_definition"]}
                        if "angle_definition" in sample
                        else {}
                    ),
                    **day_meridian_coordinates(
                        sample["factor_longitudes"]["Midheaven"],
                        state["natal_tropical_sun"],
                        state["solar_arc_degrees"],
                        target["target_tropical_sun"],
                    ),
                }
            )
            assessment = source_pattern_sample(
                sample["factor_longitudes"],
                sample.get("angle_definition"),
                solar_arc_degrees=state["solar_arc_degrees"],
            )
            assessments.append(assessment)
            samples.append(
                {
                    **({"status": "computed"} if unavailable else {}),
                    "offset_seconds": sample["offset_seconds"],
                    "effective_utc": sample["effective_utc"],
                    "julian_day_tt": sample["julian_day_tt"],
                    "progressed_julian_day_tt": state["progressed_julian_day_tt"],
                    "sun_observation_indices": state["sun_observation_indices"],
                    "sun_ephemeris_models": state["sun_ephemeris_models"],
                    "solar_arc_degrees": state["solar_arc_degrees"],
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
                    "sample_scope_policy": "Keep all confirmed birth-time samples; no extrapolation outside the declared0..150 key-year range",
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
            values, arc, hypothetical_ids=HYPOTHETICAL_BODIES
        ),
        "interpretations": interpretations,
        "birth_time_sensitivity": sensitivity,
        "daily_meridian": build_day_meridian(
            natal_upper_meridian=values["Midheaven"],
            solar_profile=profile,
            target=target,
            uncertainty=uncertainty,
            samples=day_samples,
            native_profile=layer["profile"],
            native_factors=layer["factors"],
            nominal_effective_utc=birth.require_utc_datetime.isoformat(),
            supported_key_years=(0.0, MAX_KEY_YEARS),
        ),
        "original_table_1925": source_table_analysis(),
        "sources": [
            *SOURCES,
            profile["key_source_comparison"]["source"],
            *[
                s
                for s in layer["sources"]
                if s["id"] in ("udo_rudolph_1996_abc_excerpt", "rudolph_1979_17laws")
            ],
        ],
        "rule_trace": [
            {
                "rule_id": "witte1923_constant_source_arithmetic_v1",
                "source_id": "witte1923_progressive_constant",
                "source_sections": ["pp.183-184"],
                "formula": "Audit each printed h/m/s sum or difference in integer time seconds; retain mismatched printed totals",
                "scope": "Historical source comparison only, not the current chart's selected year key or a birth-clock correction",
            },
            {
                "rule_id": "hamburg.solar_arc.true_solar_arc.v1",
                "source_id": "bonert_2007_true_solar_arc",
                "source_sections": ["Der wahre Sonnenbogen"],
                "formula": "arc = tropical Sun(TT_birth + elapsed_UTC_days / 365.25) - tropical Sun(TT_birth), modulo360",
                "scope": "True Sun displacement; the fixed Julian year key and 150-key-year calculation range are FateBridge choices",
            },
            {
                "rule_id": "hamburg.solar_arc.biwheel_geometry.v1",
                "source_id": "rudolph_1979_17laws",
                "source_sections": ["3", "13", "14", "15", "16"],
                "formula": "Apply the natal/directed factor labels before comparing point and midpoint axes modulo90/45",
                "scope": "Point-point, directed-point/natal-axis, natal-point/directed-axis and directed-axis/natal-axis only; no interleaved four-factor catalogue",
            },
            {
                "rule_id": "hamburg.solar_arc.rotation.v1",
                "source_id": "witte_al319_static_biwheel",
                "source_sections": ["p.7"],
                "formula": "directed longitude = natal longitude + same solar arc, modulo360",
                "scope": "22 published static pairs checked by their rounding intervals; no date-to-arc or event validation inferred",
            },
            {
                "rule_id": "hamburg.udo1996.directed_mc.v1",
                "source_id": "udo_rudolph_1996_abc_excerpt",
                "source_sections": ["printed p.14"],
                "formula": "Mars.natal+Jupiter.natal-Zeus.natal = Midheaven.solar_arc, direct full-circle orb<=2degrees",
                "scope": "The source explicitly also discusses occupied sensitive points with directed MC; one attributed symbolic theme only",
            },
        ],
        "limitations": [
            "Symbolic true-solar-arc biwheel, not observed future positions, event forecasts or validated efficacy",
            "365.25-day Julian key is explicit; other year keys and birthday interpolation are not claimed equivalent",
            "Only the named 1924 ecliptic day-meridian equation is in daily_meridian; mixed_pair_geometry adds a declared four-distinct-name uniform-arc reconstruction, not the complete Witte progression system or transits",
            "Only the published Udo p.14 directed-MC symbolic pattern is interpreted; the full rulebook is not accepted",
            "Contact counts and sample counts are not probabilities; different dials are not independent evidence",
        ],
        "original_text_conformance": "not_assessed",
        "real_world_efficacy": "not_tested",
    }
    mixed = layer["solar_arc_analysis"]["mixed_pair_geometry"]
    mixed["birth_time_sensitivity"] = mixed_pair_sensitivity(
        mixed,
        values,
        uncertainty,
        sensitivity.get("samples", []),
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
    layer["limitations"] = [
        (
            "Selected 1923 natal Meridian cusps are in meridian_houses; optional true solar arc and the named 1924 day-meridian subset are in solar_arc_analysis. No complete Witte progression system, actual transit catalogue or validated event forecasts"
            if item.startswith("The selected 1923 natal meridian-house geometry")
            else item
        )
        for item in layer["limitations"]
    ]

"""Finite-grid counterexamples use invented coordinates, not birth estimates."""

import copy
import math
import random
from collections import Counter
from datetime import datetime, timezone
from fractions import Fraction
from itertools import combinations

import pytest

from fatebridge.core.astro.mixed_pairs import mixed_pair_geometry
from fatebridge.core.astro.mixed_sensitivity import mixed_pair_sensitivity
from fatebridge.core.astro.reference_angles import reference_angle_basis
from fatebridge.core.output_midpoints import MixedPairSensitivity
from fatebridge.services.astrology import calculate_germany_chart_analysis

NATAL = {"A": 0.0, "B": 20.0, "C": 10.0, "D": 30.0}
UNRESOLVED = {
    "status": "ecliptic_horizon_numerically_unresolved",
    "retained_ascendant_role": "backend_numeric_convention_only",
    "geometric_ascendant_resolved": False,
}


def inputs(values, arcs, *, rows=None, definitions=None):
    native, solar = [], []
    for i, arc in enumerate(arcs):
        offset = (i - len(arcs) // 2) * 30.0
        native.append(
            {
                "offset_seconds": offset,
                "recorded_utc": f"fictional-recorded-{i}",
                "effective_utc": f"fictional-effective-{i}",
                "julian_day_tt": 2451545.0 + offset / 86400,
                "factor_longitudes": dict(rows[i] if rows else values),
                **({"angle_definition": definitions[i]} if definitions else {}),
            }
        )
        solar.append(
            {
                "offset_seconds": offset,
                "effective_utc": f"fictional-effective-{i}",
                "julian_day_tt": 2451545.0 + offset / 86400,
                **(
                    {"solar_arc_degrees": arc}
                    if arc is not None
                    else {
                        "status": "unavailable",
                        "reason_code": "controlled_outside_arc_domain",
                    }
                ),
            }
        )
    return {
        "status": "sampled",
        "uncertainty_minutes": 1.0,
        "sample_count": len(arcs),
        "samples": native,
    }, solar


def find(result, names=("A", "B", "C", "D"), coefficient=0.5, period="90"):
    return next(
        row
        for row in result["dials"][period]["contacts"]
        if tuple(row[k] for k in ("id_a", "id_b", "id_c", "id_d")) == names
        and row["midpoint_arc_coefficient"] == coefficient
    )


def test_new_sample_only_contact_is_kept_even_when_nominal_contact_is_absent():
    native, solar = inputs(NATAL, [18.5, 17.5, 17.5])
    result = mixed_pair_sensitivity(
        mixed_pair_geometry(NATAL, 17.5), NATAL, native, solar
    )
    row = find(result)
    assert row["nominal_condition"] is False
    assert row["present_sample_indices"] == [0]
    assert row["known_absent_sample_count"] == 2
    assert row["sampled_status"] == "varies_across_samples"
    assert len(result["samples"]) == 3
    assert sum(result["summary"]["90"]["all_group_status_counts"].values()) == 9
    assert (
        MixedPairSensitivity.model_validate(result).model_dump(exclude_unset=True)
        == result
    )


def test_missing_arc_does_not_erase_the_arc_cancelled_natal_relative_geometry():
    values = {"A": 0.0, "B": 40.0, "C": 10.0, "D": 30.0}
    native, solar = inputs(values, [None, 20.0, None])
    result = mixed_pair_sensitivity(
        mixed_pair_geometry(values, 20.0), values, native, solar
    )
    static = find(result, coefficient=0.0)
    assert result["status"] == "partial"
    assert result["unavailable_arc_sample_count"] == 2
    assert static["sampled_status"] == "present_at_every_sample"
    assert static["present_sample_indices"] == [0, 1, 2]
    assert static["unknown_sample_indices"] == []
    assert static["arc_required_for_relative_condition"] is False
    assert [s["solar_arc_degrees"] for s in result["samples"]] == [None, 20.0, None]
    assert (
        result["summary"]["90"]["unlisted_no_observed_hit_counts"]["underdetermined"]
        > 0
    )


def test_arc_invariance_does_not_mean_birth_time_invariance():
    values = {"A": 0.0, "B": 40.0, "C": 10.0, "D": 30.0}
    rows = [{**values, "A": a} for a in [-4.0, 0.0, 4.0]]
    native, solar = inputs(values, [None, 20.0, None], rows=rows)
    result = mixed_pair_sensitivity(
        mixed_pair_geometry(values, 20.0), values, native, solar
    )
    static = find(result, coefficient=0.0)
    assert static["present_sample_indices"] == [1]
    assert static["sampled_status"] == "varies_across_samples"
    assert static["assessment_complete"] is True


def test_backend_hit_at_unresolved_ascendant_remains_physically_unknown():
    values = {"A": 0.0, "B": 40.0, "C": 10.0, "Ascendant": 30.0}
    native, solar = inputs(values, [20.0] * 3, definitions=[{}, UNRESOLVED, {}])
    result = mixed_pair_sensitivity(
        mixed_pair_geometry(values, 20.0),
        values,
        native,
        solar,
        nominal_angle_definition=UNRESOLVED,
    )
    row = find(result, names=("A", "B", "Ascendant", "C"), coefficient=0.0)
    assert row["nominal_backend_condition"] is True
    assert row["nominal_condition"] is None
    assert row["backend_hit_sample_indices"] == [0, 1, 2]
    assert row["present_sample_indices"] == [0, 2]
    assert row["unknown_sample_indices"] == [1]
    assert row["sampled_status"] == "underdetermined"


def test_geographic_pole_meridian_convention_limits_the_midheaven_relation():
    values = {"A": 0.0, "B": 40.0, "C": 10.0, "Midheaven": 30.0}
    pole = {"status": "geographic_pole_meridian_convention"}
    native, solar = inputs(values, [20.0], definitions=[pole])
    result = mixed_pair_sensitivity(
        mixed_pair_geometry(values, 20.0),
        values,
        native,
        solar,
        nominal_angle_definition=pole,
    )
    row = find(result, names=("A", "B", "C", "Midheaven"), coefficient=0.0)
    assert row["nominal_condition"] is None
    assert row["present_sample_indices"] == []
    assert row["unknown_sample_indices"] == [0]
    assert row["backend_hit_sample_indices"] == [0]


def test_proved_variation_is_not_erased_by_an_additional_unknown_sample():
    values = {"A": 0.0, "B": 20.0, "C": 10.0, "Ascendant": 30.0}
    native, solar = inputs(values, [18.5, 17.5, 18.5], definitions=[{}, {}, UNRESOLVED])
    result = mixed_pair_sensitivity(
        mixed_pair_geometry(values, 17.5), values, native, solar
    )
    row = find(result, names=("A", "B", "Ascendant", "C"))
    assert row["sampled_status"] == "varies_across_samples"
    assert row["assessment_complete"] is False
    assert row["unknown_sample_indices"] == [2]


def test_exact_integer_lattice_preserves_inclusive_orb_neighbor_sides():
    arcs = [math.nextafter(18.0, -math.inf), 18.0, math.nextafter(18.0, math.inf)]
    native, solar = inputs(NATAL, arcs)
    result = mixed_pair_sensitivity(
        mixed_pair_geometry(NATAL, 18.0), NATAL, native, solar
    )
    assert find(result)["present_sample_indices"] == [1, 2]
    assert result["exact_lattice_denominator_power"] >= 48


@pytest.mark.parametrize("period", [90, 45])
def test_entire_domain_and_sparse_ledger_match_independent_four_coordinate_enumeration(
    period,
):
    rng = random.Random(84417)
    values = {str(i): rng.randrange(360 * 64) / 64 for i in range(6)}
    samples = [
        {n: v + rng.randrange(-48, 49) / 64 for n, v in values.items()}
        for _ in range(3)
    ]
    arcs = [None, 12.125, 12.25]
    native, solar = inputs(values, arcs, rows=samples)
    result = mixed_pair_sensitivity(
        mixed_pair_geometry(values, arcs[1]), values, native, solar
    )
    expected, counts, unlisted = {}, Counter(), Counter()
    bits_for = {-1: (0, 0, 1, 0), 0: (1, 0, 1, 0), 1: (1, 0, 0, 0)}

    def direct(v, arc, bits, names):
        if arc is None and sum(bits[:2]) != sum(bits[2:]):
            return None
        # Cancellation is used only when the relative condition has no arc.
        if arc is None:
            x = [Fraction(v[n]) for n in names]
        else:
            x = [Fraction(v[n]) + b * Fraction(arc) for n, b in zip(names, bits)]
        z = (x[0] + x[1]) / 2 - (x[2] + x[3]) / 2
        z -= math.floor(z / period + Fraction(1, 2)) * period
        return abs(z) <= 1

    for quartet in combinations(sorted(values), 4):
        a, *rest = quartet
        for b in rest:
            c, d = (n for n in rest if n != b)
            names = (a, b, c, d)
            for numerator, bits in bits_for.items():
                hits = [direct(v, arc, bits, names) for v, arc in zip(samples, arcs)]
                nominal = direct(values, arcs[1], bits, names)
                yes = [i for i, v in enumerate(hits) if v is True]
                unknown = [i for i, v in enumerate(hits) if v is None]
                false = sum(v is False for v in hits)
                if yes and false:
                    state = "varies_across_samples"
                elif unknown:
                    state = "underdetermined"
                elif len(yes) == 3:
                    state = "present_at_every_sample"
                else:
                    state = "absent_at_every_sample"
                counts[state] += 1
                if nominal or yes:
                    expected[(names, numerator / 2)] = (yes, unknown, false, state)
                else:
                    unlisted[state] += 1
    actual = {}
    for row in result["dials"][str(period)]["contacts"]:
        key = (
            tuple(row[k] for k in ("id_a", "id_b", "id_c", "id_d")),
            row["midpoint_arc_coefficient"],
        )
        assert key not in actual
        actual[key] = (
            row["present_sample_indices"],
            row["unknown_sample_indices"],
            row["known_absent_sample_count"],
            row["sampled_status"],
        )
    assert actual == expected
    assert result["summary"][str(period)]["all_group_status_counts"] == dict(counts)
    assert result["summary"][str(period)]["unlisted_no_observed_hit_counts"] == dict(
        unlisted
    )
    assert sum(counts.values()) == math.comb(6, 4) * 9


def test_unknown_interval_stays_unknown_and_explicit_zero_is_evaluated():
    geometry = mixed_pair_geometry(NATAL, 20.0)
    result = mixed_pair_sensitivity(
        geometry, NATAL, {"status": "not_assessed", "uncertainty_minutes": None}, []
    )
    assert result["summary"] is None and result["sample_count"] is None
    native, solar = inputs(NATAL, [20.0])
    native["uncertainty_minutes"] = 0.0
    computed = mixed_pair_sensitivity(geometry, NATAL, native, solar)
    assert computed["sample_count"] == 1 and computed["status"] == "sampled"


def test_corrupted_reference_basis_is_not_promoted_to_a_physical_definition():
    with pytest.raises(ValueError, match="Reference-angle basis"):
        reference_angle_basis(
            {**UNRESOLVED, "retained_ascendant_role": True}, "Ascendant"
        )


@pytest.mark.parametrize(
    "defect",
    [
        "dropped",
        "duplicate",
        "reordered",
        "missing_factor",
        "nan",
        "state",
        "effective_instant",
        "tt_epoch",
    ],
)
def test_corrupted_same_run_samples_fail_without_dropping_or_imputing(defect):
    native, solar = inputs(NATAL, [20.0] * 3)
    if defect == "dropped":
        solar.pop()
    elif defect == "duplicate":
        native["samples"][1]["offset_seconds"] = -30.0
        solar[1]["offset_seconds"] = -30.0
    elif defect == "reordered":
        solar.reverse()
    elif defect == "missing_factor":
        native["samples"][0]["factor_longitudes"].pop("A")
    elif defect == "nan":
        native["samples"][0]["factor_longitudes"]["A"] = math.nan
    elif defect == "effective_instant":
        solar[0]["effective_utc"] = "another-physical-instant"
    elif defect == "tt_epoch":
        solar[0]["julian_day_tt"] += 1
    else:
        solar[0]["status"] = "pretend_computed"
    with pytest.raises(ValueError):
        mixed_pair_sensitivity(mixed_pair_geometry(NATAL, 20.0), NATAL, native, solar)


@pytest.mark.native_engine_fault
def test_misaligned_epoch_is_a_runtime_source_error_not_bad_birth_input(monkeypatch):
    from fatebridge.core.astro import solar_arc

    original = solar_arc.mixed_pair_sensitivity

    def mispaired(geometry, values, uncertainty, solar_samples, **kwargs):
        samples = copy.deepcopy(solar_samples)
        samples[0]["effective_utc"] = "different-physical-instant"
        return original(geometry, values, uncertainty, samples, **kwargs)

    monkeypatch.setattr(solar_arc, "mixed_pair_sensitivity", mispaired)
    result = calculate_germany_chart_analysis(
        name="虚构：样点绑定故障核验",
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=4,
        birth_minute=30,
        birth_timezone="UTC",
        birth_longitude=0.0,
        birth_latitude=0.0,
        birth_time_uncertainty_minutes=0.5,
        analysis_datetime=datetime(2000, 2, 1, tzinfo=timezone.utc),
    )
    assert result["error_code"] == "ephemeris_source_inconsistent"
    assert result["status_code"] == 503
    assert result["retryable"] is False
    assert result["issues"] == [
        {"path": "runtime.ephemeris_data", "code": "mixed_pair_sample_epoch_mismatch"}
    ]

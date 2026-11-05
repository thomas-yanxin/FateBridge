"""Analytic LT geometry, radial projection, units and raw-table contracts."""

import csv
import io
import json
from decimal import Decimal, localcontext
from fractions import Fraction as Q
from pathlib import Path

import pytest

from scripts.astrodice.astrodice_retarded_table import AU_KM, K, compare, parse
from scripts.astrodice.verify_astrodice_retarded_table import independent_relations

FIXTURE = (
    Path(__file__).parents[1]
    / "data/astrodice/reference_sets/fixture-retarded-table-v1"
)
PLAN = {
    "numerical_tube_profiles": {"printing_only": {"extra_binary64_ULPs": 0}},
    "interval_trig_terms": 80,
}


def decimal(value):
    value = Q(value)
    with localcontext() as context:
        context.prec = 80
        return format(Decimal(value.numerator) / Decimal(value.denominator), ".30f")


def analytic(vx="0.000000000000000", vy="0.000000000000000"):
    vector = {
        "printed_state": [
            "1.000000000000000",
            "0.000000000000000",
            "0.000000000000000",
            vx,
            vy,
            "0.000000000000000",
        ],
        "range_AU": "1.000000000000000",
        "range_rate_AU_per_day": vx,
        "light_time_days": decimal(K),
    }
    observer = {
        "range_AU": "1.000000000000000",
        "deldot_km_per_second": decimal(Q(vx) * AU_KM / 86400),
        "light_time_minutes": decimal(K * 1440),
        "astrometric_angles": ["0.000000000", "0.000000000"],
    }
    return vector, observer


def test_stationary_one_au_geometry_has_all_expected_relations():
    vector, observer = analytic()
    result = compare(vector, observer, "printing_only", PLAN)
    for value in result["checks"].values():
        assert all(value) if isinstance(value, list) else value
    assert independent_relations(vector, observer, 0)[3] == result["checks"]
    assert not result["physical_internal_algorithm_or_velocity_derivative_certified"]


def test_range_rate_uses_radial_projection_instead_of_total_speed():
    vector, observer = analytic("0.010000000000000", "0.020000000000000")
    result = compare(vector, observer, "printing_only", PLAN)
    assert result["checks"]["vector_RR_matches_state_projection"]
    assert result["checks"]["observer_RR_matches_vector_RR"]
    lo, hi = map(Q, result["state_projection_AU_per_day"])
    assert lo <= Q(".01") <= hi


def test_au_per_day_cannot_be_compared_directly_with_kilometers_per_second():
    vector, observer = analytic("0.010000000000000")
    observer["deldot_km_per_second"] = "0.010000000000000"
    result = compare(vector, observer, "printing_only", PLAN)
    assert not result["checks"]["observer_RR_matches_vector_RR"]
    assert not result["checks"]["observer_RR_matches_state_projection"]
    assert result["checks"]["vector_RR_matches_state_projection"]


def test_days_and_minutes_are_converted_before_comparing_light_time():
    vector, observer = analytic()
    observer["light_time_minutes"] = vector["light_time_days"]
    result = compare(vector, observer, "printing_only", PLAN)
    assert not result["checks"]["observer_light_time_matches_vector_LT"]
    assert result["checks"]["vector_LT_matches_norm_over_c"]


def test_agreeing_observer_norm_does_not_mask_inconsistent_vector_rg():
    vector, observer = analytic()
    vector["range_AU"] = "2.000000000000000"
    c = compare(vector, observer, "printing_only", PLAN)["checks"]
    assert c["observer_range_matches_vector_position_norm"]
    assert not c["observer_range_matches_vector_RG"]
    assert not c["vector_RG_matches_position_norm"]
    assert not c["vector_LT_matches_RG_over_c"]


def test_zero_length_vector_is_unqualified_instead_of_a_fake_direction():
    vector, observer = analytic()
    vector["printed_state"][:3] = ["0.000000000000000"] * 3
    with pytest.raises(ValueError, match="Nonpositive"):
        compare(vector, observer, "printing_only", PLAN)


@pytest.mark.parametrize(
    "old,new", [("AU-D", "KM-S"), ("LT CORRECTED", "GEOMETRIC"), ("ICRF", "B1950")]
)
def test_actual_table_header_cannot_be_reinterpreted_as_another_unit_or_correction(
    old, new
):
    plan = json.loads((FIXTURE / "plan-before-queries.json").read_text())
    query = plan["queries"][0]
    payload = json.loads((FIXTURE / "responses/A-LT-TT-JD.raw").read_bytes())
    assert old in payload["result"]
    payload["result"] = payload["result"].replace(old, new)
    with pytest.raises(ValueError):
        parse(json.dumps(payload).encode(), query, plan["cohorts"]["A"], plan)


@pytest.mark.parametrize("mutation", ["nonfinite", "missing_row"])
def test_raw_state_contract_retains_nonfinite_and_missing_row_failures(mutation):
    plan = json.loads((FIXTURE / "plan-before-queries.json").read_text())
    query = plan["queries"][0]
    payload = json.loads((FIXTURE / "responses/A-LT-TT-JD.raw").read_bytes())
    prefix, body = payload["result"].split("$$SOE")
    body, suffix = body.split("$$EOE")
    rows = list(csv.reader(body.strip().splitlines()))
    if mutation == "nonfinite":
        rows[0][2] = "NaN"
    else:
        rows.pop()
    out = io.StringIO()
    csv.writer(out).writerows(rows)
    payload["result"] = prefix + "$$SOE\n" + out.getvalue() + "$$EOE" + suffix
    with pytest.raises(ValueError):
        parse(json.dumps(payload).encode(), query, plan["cohorts"]["A"], plan)

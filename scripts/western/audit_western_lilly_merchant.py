"""Retain the complete second printed table, including unknowns and conflicts."""

import argparse
import json
from fractions import Fraction
from pathlib import Path

from fatebridge.core.classical_western import combustion_state
from fatebridge.core.lilly_fortitudes import evaluate_fortitudes
from fatebridge.core.lilly_star_orbs import STELLAR_ORB_DEGREES
from scripts.western.audit_western_lilly_fortitudes import worked_inputs

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/data/astro/lilly_merchant_1647"


def assess_regulus_resolution():
    """Re-evaluate the old diagnosis under the actual corrected stellar rule."""
    original = json.loads(
        (ROOT / "tests/fixtures/western-lilly-fortitudes-1647.json").read_text()
    )
    states, inputs = worked_inputs(original)
    moon = states["Moon"]["longitude"]
    coarse = Fraction(144)
    minute = Fraction(144) + Fraction(34, 60)
    result = []
    for resolution, position in [("coarse", coarse), ("minute", minute)]:
        changed = {
            **inputs,
            "star_longitudes": {**inputs["star_longitudes"], "Regulus": position},
        }
        candidate = evaluate_fortitudes(
            states,
            original["worked_example"]["sect"],
            changed,
            house_system="R",
            zodiac_type="Tropic",
        )
        row = next(
            r for r in candidate["planets"]["Moon"]["rows"] if r["code"] == "F17"
        )
        result.append(
            dict(
                resolution=resolution,
                gap_arcminutes=str((position - moon) * 60),
                current_condition=row["status"] == "satisfied",
                current_orb_degrees=STELLAR_ORB_DEGREES["Regulus"],
                current_moon_balance=candidate["planets"]["Moon"][
                    "literal_table_balance"
                ],
            )
        )
    return dict(
        current_rule_controls=result,
        original_fixture_replaced=False,
        new_independent_original_charts=0,
        source_acceptance_passed=False,
    )


def audit():
    source = json.loads((FIXTURE / "annotation.json").read_text())
    planets = source["planets"]
    states = {
        p: {
            "longitude": Fraction(row["longitude"]),
            "occupied_house": row["occupied_house"],
        }
        for p, row in planets.items()
    }
    # Printed swift/slow labels are expected answers. They do not supply a
    # missing numerical24h displacement or become fabricated physical inputs.
    motion = {p: {"direction": row["motion_direction"]} for p, row in planets.items()}
    result = evaluate_fortitudes(
        states,
        "day",
        {
            "status": "partial_transcribed_original_facts",
            "motion": motion,
            "daily_motion_policy": "numeric_displacements_not_supplied_by_inspected_pages",
        },
        house_system="R",
        zodiac_type="Tropic",
    )
    comparisons = []
    for p, row in planets.items():
        expected = {**row["printed_positive_rows"], **row["printed_negative_rows"]}
        actual = result["planets"][p]
        differences = []
        missing = []
        essential_rows = []
        for observed in actual["rows"]:
            code = observed["code"]
            wanted = expected.get(code, 0)
            if observed["status"] == "unknown":
                missing.append(dict(code=code, printed_contribution=wanted))
            elif observed["contribution"] != wanted:
                differences.append(
                    dict(
                        code=code,
                        printed_contribution=wanted,
                        p115_contribution=observed["contribution"],
                        inputs=observed["inputs"],
                    )
                )
            if code.startswith("E"):
                essential_rows.append(
                    dict(
                        code=code,
                        expected=wanted,
                        actual=observed["contribution"],
                        matched=observed["contribution"] == wanted,
                    )
                )
        positive_sum = sum(row["printed_positive_rows"].values())
        negative_sum = -sum(row["printed_negative_rows"].values())
        comparisons.append(
            dict(
                planet=p,
                printed_arithmetic_correct=(
                    positive_sum == row["fortitude_sum"]
                    and negative_sum == row["debility_sum"]
                    and positive_sum - negative_sum == row["balance"]
                ),
                printed_balance=row["balance"],
                p115_literal_balance=actual["literal_table_balance"],
                known_row_differences=differences,
                unknown_rows=missing,
                essential_rows=essential_rows,
                full_reproduced=not differences
                and not missing
                and actual["literal_table_balance"] == row["balance"],
            )
        )
    fortune = source["fortune"]
    fortune_arithmetic = (
        sum(fortune["positive_rows"].values()) == fortune["fortitude_sum"]
        and -sum(fortune["negative_rows"].values()) == fortune["debility_sum"]
        and fortune["fortitude_sum"] - fortune["debility_sum"] == fortune["balance"]
    )
    venus = next(x for x in comparisons if x["planet"] == "Venus")
    essential = [x for x in venus["essential_rows"] if x["expected"] > 0]
    sun_lon, venus_lon = states["Sun"]["longitude"], states["Venus"]["longitude"]
    return dict(
        source="Lilly1647 pp742-745, second distinct printed figure",
        source_annotation_precedes_candidate_execution=True,
        printed_planet_applications=7,
        printed_fortune_application=1,
        all_eight_printed_arithmetic_sums_match=(
            all(c["printed_arithmetic_correct"] for c in comparisons)
            and fortune_arithmetic
        ),
        comparisons=comparisons,
        fortune=dict(
            printed_balance=fortune["balance"],
            arithmetic_correct=fortune_arithmetic,
            calculated_reproduction=None,
            status="not_reconstructed_from_missing_geometry_and_node_facts",
        ),
        essential_positive_additivity=dict(
            planet="Venus",
            printed_rows=essential,
            printed_sum=sum(x["expected"] for x in essential),
            calculated_sum=sum(x["actual"] for x in essential),
            maximum_only_counterfactual=max(x["actual"] for x in essential),
            global_maximum_only_supported=False,
            sun_leo_omission_resolved=False,
        ),
        printed_cazimi_control=dict(
            sun_longitude_exact=str(sun_lon),
            venus_longitude_exact=str(venus_lon),
            nominal_separation_arcminutes=str((venus_lon - sun_lon) * 60),
            printed_classification="cazimi",
            calculated_classification=combustion_state(venus_lon, sun_lon),
            minute_quantized_source_not_subminute_observational_bound=True,
        ),
        regulus_resolution=assess_regulus_resolution(),
        p115_cross_scope_diagnostic=True,
        p115_method_adopted_as_book3_rule=False,
        numeric_daily_motion_invented=False,
        unknown_rows_converted_to_zero=False,
        original_p177_seven_application_gate_replaced=False,
        full_worked_case_reproduction_passed=False,
        full_original_text_acceptance=False,
        all_three_full_marks_established=False,
        all_four_full_marks_established=False,
        authority_certified=False,
        real_world_observations_added=0,
    )


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {k: v for k, v in result.items() if k != "comparisons"}, ensure_ascii=False
        )
    )
    return 0 if result["full_worked_case_reproduction_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

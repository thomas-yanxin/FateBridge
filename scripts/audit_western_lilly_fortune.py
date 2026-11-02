"""Check sealed Lilly Fortune arithmetic and retain the p180 exception failure."""

import argparse
import hashlib
import json
import zipfile
from fractions import Fraction
from pathlib import Path

from fatebridge.core.lilly_fortune import ROW_SPECS, evaluate_fortune
from fatebridge.core.lilly_house_assignment import assign_cusp_virtue
from fatebridge.core.output_western import LillyFortune

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_SHA256 = "08fdcb25a97ff486eeab20516925bff58b1ad5d96d90c2b71f565ab79a52e4d7"
ARCHIVE_SHA256 = "91893d026edb66109c4b28a19cf2e99a5c82c7a89b5a1922d08b6537708b344f"


def audit():
    path = ROOT / "tests/fixtures/western-lilly-fortune-houses-1647.json"
    archive = path.with_name("western-lilly-fortune-houses-sources.zip")
    assert hashlib.sha256(path.read_bytes()).hexdigest() == FIXTURE_SHA256
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == ARCHIVE_SHA256
    ref = json.loads(path.read_text())
    assert ref["production_imports"] is False
    with zipfile.ZipFile(archive) as z:
        for row in ref["source_receipts"]:
            assert hashlib.sha256(z.read(row["file"])).hexdigest() == row["sha256"]
    assert [
        dict(code=c, points=p, condition=s, page=145) for c, p, s in ROW_SPECS
    ] == ref["rows"]
    cases = []
    for row in ref["printed_formula_examples"]:
        value = evaluate_fortune(
            Fraction(row["asc_arcminutes"], 60),
            {
                "Sun": {"longitude": Fraction(row["sun_arcminutes"], 60)},
                "Moon": {"longitude": Fraction(row["moon_arcminutes"], 60)},
            },
            {},
            house_system="R",
            zodiac_type="Tropic",
        )
        expected = Fraction(row["fortune_arcminutes"], 60)
        cases.append(
            dict(
                id=row["id"],
                expected_longitude=str(expected),
                actual_longitude=value["exact_longitude"],
                passed=Fraction(value["exact_longitude"]) == expected,
            )
        )
    case = ref["house_exception"]
    assignment = assign_cusp_virtue(
        Fraction(case["longitude_arcminutes"], 60),
        case["occupied_house"],
        Fraction(case["lower_cusp_arcminutes"], 60),
        Fraction(case["next_cusp_arcminutes"], 60),
        house_system="R",
        zodiac_type="Tropic",
    )
    old = json.loads(
        (ROOT / "tests/fixtures/western-lilly-fortitudes-1647.json").read_text()
    )
    states = {
        p: {
            "longitude": Fraction(r["longitude_integer_degrees"])
            + Fraction(r["longitude_minutes"], 60)
        }
        for p, r in old["worked_example"]["planets"].items()
    }
    node = old["worked_example"]["north_node"]
    physical = {
        "north_node_longitude": float(
            Fraction(node["longitude_integer_degrees"])
            + Fraction(node["longitude_minutes"], 60)
        ),
        "node_model": "printed_p177_node_not_recomputed",
    }
    physical["star_longitudes"] = {
        p: float(Fraction(v, 60))
        for p, v in ref["printed_star_longitudes_arcminutes"].items()
    }
    physical["star_position_policy"] = (
        "Printed p145 dated controls, not current-star astrometry"
    )
    candidate = evaluate_fortune(
        Fraction(11653, 60),
        states,
        physical,
        house_assignment=assignment,
        house_system="R",
        zodiac_type="Tropic",
    )
    LillyFortune.model_validate(candidate)
    applied = {
        r["code"]: r["contribution"]
        for r in candidate["rows"]
        if r["satisfied"] is True
    }
    printed = case["printed_applied_rows"]
    differences = [
        dict(row=c, printed=printed.get(c, 0), actual=applied.get(c, 0))
        for c in sorted(printed.keys() | applied.keys())
        if printed.get(c, 0) != applied.get(c, 0)
    ]
    full_case = (
        assignment["assigned_house"] == case["printed_assigned_house"]
        and not differences
        and candidate["literal_table_balance"] == case["printed_balance"]
    )
    return dict(
        reference_sha256=FIXTURE_SHA256,
        archive_sha256=ARCHIVE_SHA256,
        source_assets_verified=len(ref["source_receipts"]),
        printed_table_rows_verified=len(ROW_SPECS),
        formula_examples=cases,
        formula_examples_passed=sum(c["passed"] for c in cases),
        p180_printed_assigned_house=case["printed_assigned_house"],
        p33_policy_assigned_house=assignment["assigned_house"],
        p177_next_cusp_gap_degrees=assignment["next_cusp_gap_degrees"],
        p180_printed_balance=case["printed_balance"],
        candidate_literal_balance=candidate["literal_table_balance"],
        p180_row_differences=differences,
        p180_full_application_reproduced=full_case,
        candidate=candidate,
        full_original_text_acceptance=False,
        authority_certified=False,
        all_three_full_marks_established=False,
        all_four_full_marks_established=False,
        real_world_observations_added=0,
        whole_audit_passed=all(c["passed"] for c in cases) and full_case,
        scope="Printed arithmetic and one p180 application; source-transcribed positions, no missing cusps invented, no historical civil-time/ephemeris or actual outcome reconstruction",
    )


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    print(
        json.dumps(
            {k: v for k, v in result.items() if k != "candidate"}, ensure_ascii=False
        )
    )
    return 0 if result["whole_audit_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

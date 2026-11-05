"""Reproduce all printed fortitude rows and retain worked-example conflicts."""

import argparse
import hashlib
import json
import zipfile
from fractions import Fraction
from pathlib import Path

from fatebridge.core.lilly_fortitudes import (
    MEAN_MOTION_ARCSECONDS,
    ROW_SPECS,
    evaluate_fortitudes,
)
from fatebridge.core.output_western import LillyFortitudes

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_SHA256 = "31a64976c3ca8650de975cf53cf76972741788dc81f51021278087f8ef962f6e"
ARCHIVE_SHA256 = "0cea6669b1d9f96e9583772da8002813149282e189be2029165c45c1e153d2cc"
CORRECTION_SHA256 = "2d68237c259f7a502cd58a960ef433588d5c8210784613df7785a0eecda16693"


def worked_inputs(reference):
    case = reference["worked_example"]
    states, motion = {}, {}
    for p, row in case["planets"].items():
        states[p] = {
            "longitude": Fraction(row["longitude_integer_degrees"])
            + Fraction(row["longitude_minutes"], 60),
            "occupied_house": row["occupied_house"],
        }
        daily = Fraction(row["daily_motion_arcminutes"], 60)
        motion[p] = {
            "direction": "retrograde" if daily < 0 else "direct",
            "daily_motion_degrees": float(daily),
            "daily_motion_exact_degrees": str(daily),
        }
    node = case["north_node"]
    inputs = {
        "status": "transcribed_original_facts",
        "motion": motion,
        "north_node_longitude": float(
            Fraction(node["longitude_integer_degrees"])
            + Fraction(node["longitude_minutes"], 60)
        ),
        "node_model": "printed_p177_node_not_a_recomputed_modern_model",
        "star_longitudes": {
            p: float(lon)
            for p, lon in reference["printed_star_longitudes_degrees"].items()
        },
        "star_position_policy": "literal_printed_p115_epoch_controls",
        "daily_motion_policy": "p178 printed24h magnitudes with p178retrograde sign; not reconstructed instantaneous rates",
    }
    return states, inputs


def audit():
    fixture = ROOT / "tests/fixtures/western-lilly-fortitudes-1647.json"
    archive = fixture.with_name("western-lilly-fortitudes-sources.zip")
    assert hashlib.sha256(fixture.read_bytes()).hexdigest() == FIXTURE_SHA256
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == ARCHIVE_SHA256
    reference = json.loads(fixture.read_text())
    assert reference["production_imports"] is False
    sources = []
    with zipfile.ZipFile(archive) as z:
        for row in reference["source_receipts"]:
            assert (
                hashlib.sha256(z.read(f"{row['page']}.{row['type']}")).hexdigest()
                == row["sha256"]
            )
            sources.append({"page": row["page"], "type": row["type"], "passed": True})
    actual_rows = [
        dict(code=c, group=g, points=p, condition=s) for c, g, p, s in ROW_SPECS
    ]
    frozen_rows = [
        {k: r[k] for k in ["code", "group", "points", "condition"]}
        for r in reference["rows"]
    ]
    original_annotation_row_table_matches = actual_rows == frozen_rows
    correction_dir = ROOT / "tests/data/astro/lilly_regulus_orb"
    correction_bytes = (correction_dir / "correction.json").read_bytes()
    assert hashlib.sha256(correction_bytes).hexdigest() == CORRECTION_SHA256
    correction = json.loads(correction_bytes)
    assert set(correction["corrected_rows"]) == {"F17"}
    assert (
        not correction["book_weights_changed"]
        and not correction["printed_totals_changed"]
    )
    for row in frozen_rows:
        if row["code"] == "F17":
            assert row["condition"] == "regulus_within_five_degrees"
            row["condition"] = correction["corrected_rows"]["F17"]["condition"]
    assert actual_rows == frozen_rows and len(actual_rows) == 41
    assert MEAN_MOTION_ARCSECONDS == reference["mean_daily_motion_arcseconds"]
    states, inputs = worked_inputs(reference)
    candidate = evaluate_fortitudes(
        states,
        reference["worked_example"]["sect"],
        inputs,
        house_system="R",
        zodiac_type="Tropic",
    )
    LillyFortitudes.model_validate(candidate)
    comparisons = []
    for p, expected in reference["worked_example"]["planets"].items():
        observed = candidate["planets"][p]
        actual = {
            r["code"]: r["contribution"]
            for r in observed["rows"]
            if r["status"] == "satisfied"
        }
        declared = expected["printed_applied_rows"]
        changes = [
            {
                "row": c,
                "literal_contribution": actual.get(c, 0),
                "printed_contribution": declared.get(c, 0),
            }
            for c in sorted(actual.keys() | declared.keys())
            if actual.get(c, 0) != declared.get(c, 0)
        ]
        comparisons.append(
            dict(
                planet=p,
                printed_balance=expected["printed_balance"],
                literal_table_balance=observed["literal_table_balance"],
                row_differences=changes,
                unknown_rows=observed["unknown_rows"],
                reproduced=observed["literal_table_balance"]
                == expected["printed_balance"]
                and not changes,
            )
        )
    return dict(
        fixture_sha256=FIXTURE_SHA256,
        archive_sha256=ARCHIVE_SHA256,
        frozen_before_candidate_edits=True,
        source_assets_checked=len(sources),
        source_checks=sources,
        printed_rows_transcribed=41,
        row_table_matches=True,
        original_annotation_row_table_matches=original_annotation_row_table_matches,
        original_annotation_preserved=True,
        annotation_correction_sha256=CORRECTION_SHA256,
        annotation_correction="p179 long-s six was initially transcribed as five for Regulus; weights and worked totals unchanged",
        mean_motion_table_matches=True,
        printed_worked_chart_count=1,
        planetary_applications_compared=7,
        planetary_applications_reproduced=sum(c["reproduced"] for c in comparisons),
        comparisons=comparisons,
        candidate=candidate,
        worked_example_reproduction_passed=all(c["reproduced"] for c in comparisons),
        source_conflicts_emended_or_rows_dropped=False,
        full_original_text_acceptance=False,
        all_three_full_marks_established=False,
        all_four_full_marks_established=False,
        authority_certified=False,
        real_world_outcome_observations_added=0,
        scope="One frozen printed chart, seven planetary applications and41 rule rows; no independent modern ephemeris or empirical prediction test. The printed horoscope was not silently interpreted as a modern Gregorian/UTC input. Source discrepancies retain failed worked-case acceptance.",
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
            {
                k: v
                for k, v in result.items()
                if k not in {"candidate", "source_checks"}
            },
            ensure_ascii=False,
        )
    )
    return 0 if result["worked_example_reproduction_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

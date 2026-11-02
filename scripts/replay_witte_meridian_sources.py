"""Replay Witte's printed meridian arithmetic using integer arcminutes only.

This module deliberately imports no FateBridge calculation. It checks the
transcribed operations, not historical ephemeris accuracy or event outcomes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/uranian-witte1923-house-table.json"
FIXTURE_SHA256 = "21621e5ed811d4b702d856c0f6d50f418ca56eef332023458cf11497ae051456"
CIRCLE = 21600


def minutes(parts: list[int], *, zodiac: bool = True) -> int:
    """Read printed sexagesimal values without floating point or sign guessing."""
    size = 3 if zodiac else 2
    if len(parts) != size or any(type(value) is not int for value in parts):
        raise ValueError("Printed coordinates require integer sexagesimal parts")
    if zodiac:
        sign, degree, minute = parts
        if not 0 <= sign < 12 or not 0 <= degree < 30 or not 0 <= minute < 60:
            raise ValueError("Printed zodiac coordinate out of range")
        return sign * 1800 + degree * 60 + minute
    degree, minute = parts
    if degree < 0 or not 0 <= minute < 60:
        raise ValueError("Printed arc out of range")
    return degree * 60 + minute


def replay(fixture: dict) -> dict:
    """Report exact operations and retain separate original comparison residuals."""
    operations = []
    for row in fixture["operations"]:
        difference = (minutes(row["minuend"]) - minutes(row["subtrahend"])) % CIRCLE
        result = (difference + minutes(row["addend"])) % CIRCLE
        item = {
            "id": row["id"],
            "section": row["section"],
            "difference_arcminutes": difference,
            "printed_difference_arcminutes": minutes(
                row["printed_difference_degrees_minutes"], zodiac=False
            ),
            "result_arcminutes": result,
            "printed_result_arcminutes": minutes(row["printed_result"]),
        }
        item["arithmetic_matches_print"] = (
            item["difference_arcminutes"] == item["printed_difference_arcminutes"]
            and result == item["printed_result_arcminutes"]
        )
        if "printed_opposite_result" in row:
            item["opposite_result_arcminutes"] = (result + CIRCLE // 2) % CIRCLE
            item["opposite_matches_print"] = item[
                "opposite_result_arcminutes"
            ] == minutes(row["printed_opposite_result"])
        if "source_compared_sensitive_point" in row:
            item["compared_sensitive_point_arcminutes"] = minutes(
                row["source_compared_sensitive_point"]
            )
            item["signed_comparison_residual_arcminutes"] = (
                result - item["compared_sensitive_point_arcminutes"] + CIRCLE // 2
            ) % CIRCLE - CIRCLE // 2
        operations.append(item)

    table = fixture["table"]
    cusps = {row["house"]: minutes(row["natal_cusp"]) for row in table[:12]}
    oppositions = [
        {
            "houses": [house, house + 6],
            "residual_arcminutes": (cusps[house + 6] - cusps[house]) % CIRCLE
            - CIRCLE // 2,
        }
        for house in range(1, 7)
    ]
    phases = [minutes(row["solar_phase"]) for row in table]
    phase_steps = [(b - a) % CIRCLE for a, b in zip(phases, phases[1:])]
    target = fixture["target_example"]
    reduced_phase = (
        minutes(target["natal_tropical_sun"])
        - minutes(target["solar_arc_degrees_minutes"], zodiac=False)
    ) % CIRCLE
    # The 1924 sum is equivalently an equal ecliptic transport from natal IV.
    # No source birth time, obliquity or event is fitted to obtain this identity.
    target_sun = minutes(target["target_tropical_sun"])
    lower_1924 = (cusps[4] - reduced_phase + target_sun) % CIRCLE
    cusp_equal_transport = (cusps[4] + 4 * 1800) % CIRCLE
    cusp_offset = cusps[8] - cusp_equal_transport
    lower_1923 = operations[0]["result_arcminutes"]
    discrepancy = lower_1923 - lower_1924
    explanation_matches = (
        lower_1924 == minutes(fixture["operations"][0]["compared_1924_lower_meridian"])
        and cusp_offset == discrepancy
        and discrepancy
        == fixture["source_reconciliation"]["expected_difference_from_1924_arcminutes"]
    )
    passed = (
        all(row["arithmetic_matches_print"] for row in operations)
        and operations[0]["opposite_matches_print"]
        and reduced_phase == minutes(target["reduced_solar_phase"])
        and phase_steps == [1795] * 12
        and all(row["residual_arcminutes"] == 0 for row in oppositions)
        and minutes(table[-1]["natal_cusp"]) == cusps[4]
        and explanation_matches
    )
    return {
        "scope": fixture["scope"],
        "source_pdf_sha256": fixture["source_pdf_sha256"],
        "printed_arithmetic_checks_passed": passed,
        "operations": operations,
        "table_rows": len(table),
        "consecutive_phase_steps_arcminutes": phase_steps,
        "printed_cusp_oppositions": oppositions,
        "table_dates_independently_verified": False,
        "reduced_solar_phase_arcminutes": reduced_phase,
        "lower_meridian_1923_arcminutes": lower_1923,
        "lower_meridian_1924_arcminutes": lower_1924,
        "equal_ecliptic_VIII_cusp_arcminutes": cusp_equal_transport,
        "printed_VIII_cusp_arcminutes": cusps[8],
        "cusp_offset_arcminutes": cusp_offset,
        "meridian_difference_arcminutes": discrepancy,
        "difference_explained_by_printed_cusp_offset": explanation_matches,
        "source_disagreement_status": (
            "printed_arithmetic_difference_explained"
            if explanation_matches
            else "printed_arithmetic_difference_not_reproduced"
        ),
        "difference_is_universal_correction": False,
        "all_reported_sensitive_points_exact": all(
            row.get("signed_comparison_residual_arcminutes", 0) == 0
            for row in operations
        ),
        "original_variants_fully_reconciled": False,
        "original_progression_time_key_accepted": False,
        "full_original_numerical_horoscopes_accepted": 0,
        "event_claims_adopted": False,
        "empirical_outcomes": 0,
        "authority_certified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-pdf", type=Path)
    args = parser.parse_args()
    data = FIXTURE.read_bytes()
    if hashlib.sha256(data).hexdigest() != FIXTURE_SHA256:
        raise ValueError("Frozen source transcription checksum mismatch")
    fixture = json.loads(data)
    result = replay(fixture)
    result["fixture_sha256"] = FIXTURE_SHA256
    result["source_pdf_bytes_checked"] = False
    if args.source_pdf:
        actual = hashlib.sha256(args.source_pdf.read_bytes()).hexdigest()
        if actual != fixture["source_pdf_sha256"]:
            raise ValueError("Original source PDF checksum mismatch")
        result["source_pdf_bytes_checked"] = True
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "printed_arithmetic_checks_passed",
                    "meridian_difference_arcminutes",
                    "all_reported_sensitive_points_exact",
                    "original_variants_fully_reconciled",
                )
            }
        )
    )
    return 0 if result["printed_arithmetic_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

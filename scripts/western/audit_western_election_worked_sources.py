"""Replay every published election reading without selecting a source clock."""

import argparse
import json
from pathlib import Path

from fatebridge.core.execution_context import call_clock
from fatebridge.core.planetary_event_order import ordered_contact
from fatebridge.services.western_election import calculate_election

ROOT = Path(__file__).resolve().parents[2]
SIGNS = (
    "Aries",
    "Taurus",
    "Gemini",
    "Cancer",
    "Leo",
    "Virgo",
    "Libra",
    "Scorpio",
    "Sagittarius",
    "Capricorn",
    "Aquarius",
    "Pisces",
)


def audit(
    replay_path: Path | None = None, output_path: Path | None = None
) -> dict[str, object]:
    reference = json.loads(
        (ROOT / "tests/fixtures/western-election-worked-sources.json").read_text(
            encoding="utf-8"
        )
    )
    charts = {chart["id"]: chart for chart in reference["charts"]}
    recorded = (
        {}
        if replay_path is None
        else {
            result["case_id"]: result
            for result in json.loads(replay_path.read_text(encoding="utf-8"))["results"]
        }
    )
    results = []
    receipts = []
    for case in reference["cases"]:
        chart = charts[case["chart"]]
        if replay_path is None:
            with call_clock(as_of=case["as_of"]):
                response = calculate_election(**case["input"])
        else:
            saved = recorded[case["id"]]
            if saved["input"] != case["input"] or saved["as_of"] != case["as_of"]:
                raise ValueError(f"Replay input changed: {case['id']}")
            else:
                response = saved["response"]
        receipts.append(
            {
                "case_id": case["id"],
                "input": case["input"],
                "as_of": case["as_of"],
                "response": response,
            }
        )
        if output_path is not None:
            output_path.write_text(
                json.dumps(
                    {
                        "status": "in_progress",
                        "completed_input_count": len(receipts),
                        "results": receipts,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        else:
            pass
        if "error" in response:
            expected_conditions = {}
            for subject, expected in chart["prose"].items():
                if isinstance(expected, dict):
                    expected_conditions.update(
                        {
                            f"{subject}.{field}": value
                            for field, value in expected.items()
                        }
                    )
                else:
                    expected_conditions[subject] = expected
            expected_conditions.update(
                {
                    field: chart[field]
                    for field in [
                        "lunar_last",
                        "lunar_next",
                        "lunar_next_seven_body_subset",
                    ]
                    if field in chart
                }
            )
            expected_conditions.update(
                {
                    f"lunar_future_prefix.{index}": expected
                    for index, expected in enumerate(
                        chart.get("lunar_future_prefix", [])
                    )
                }
            )
            results.append(
                {
                    "case_id": case["id"],
                    "chart": case["chart"],
                    "input": case["input"],
                    "as_of": case["as_of"],
                    "readings": [
                        {
                            "point": point,
                            "printed": printed,
                            "within_display_unit": None,
                            "within_original_display_unit": None,
                            "reason": response["error"],
                        }
                        for point, printed in chart["points"].items()
                    ],
                    "conditions": [
                        {
                            "field": field,
                            "expected": expected,
                            "actual": None,
                            "matches": None,
                            "reason": response["error"],
                        }
                        for field, expected in expected_conditions.items()
                    ],
                    "response": response,
                    "status": "unavailable",
                }
            )
            continue
        else:
            pass
        election = response["election"]
        readings = []
        for point, printed in chart["points"].items():
            longitude = (
                election["axes"]["ascendant_longitude"]
                if point == "Ascendant"
                else (
                    election["axes"]["midheaven_longitude"]
                    if point == "Midheaven"
                    else election["planets"][point]["longitude"]
                )
            )
            expected = SIGNS.index(printed[0]) * 30 + printed[1] + printed[2] / 60
            residual_arcseconds = (
                None
                if longitude is None
                else abs((longitude - expected + 180) % 360 - 180) * 3600
            )
            original = next(
                (
                    update["original_transcription"]
                    for update in reference["collation_updates"]
                    if update["chart"] == chart["id"] and update["planet"] == point
                ),
                printed,
            )
            original_longitude = (
                SIGNS.index(original[0]) * 30
                + original[1]
                + original[2] / 60
                + (original[3] / 3600 if len(original) == 4 else 0)
            )
            original_residual_arcseconds = (
                None
                if longitude is None
                else abs((longitude - original_longitude + 180) % 360 - 180) * 3600
            )
            original_tolerance_arcseconds = (
                reference["printed_second_tolerance_arcseconds"]
                if len(original) == 4
                else reference["printed_minute_tolerance_arcseconds"]
            )
            readings.append(
                {
                    "point": point,
                    "printed": printed,
                    "longitude_degrees": longitude,
                    "residual_arcseconds": residual_arcseconds,
                    "within_display_unit": (
                        None
                        if residual_arcseconds is None
                        else residual_arcseconds
                        <= reference["printed_minute_tolerance_arcseconds"]
                    ),
                    "original_transcription": original,
                    "original_residual_arcseconds": original_residual_arcseconds,
                    "original_tolerance_arcseconds": original_tolerance_arcseconds,
                    "within_original_display_unit": (
                        None
                        if original_residual_arcseconds is None
                        else original_residual_arcseconds
                        <= original_tolerance_arcseconds
                    ),
                    "unadjudicated_reading": point
                    in chart.get("ambiguous_point_readings", {}),
                }
            )
        conditions = []
        house_roles = {
            row["house"]: row for row in election["marriage_significators"]["houses"]
        }
        for subject, expected in chart["prose"].items():
            if subject in {"first_ruler", "seventh_ruler", "tenth_ruler"}:
                house = {"first_ruler": 1, "seventh_ruler": 7, "tenth_ruler": 10}[
                    subject
                ]
                actual = house_roles[house]["ruler"]
                conditions.append(
                    {
                        "field": subject,
                        "expected": expected,
                        "actual": actual,
                        "matches": None if actual is None else actual == expected,
                    }
                )
            else:
                for field, value in expected.items():
                    actual = election["planets"][subject][field]
                    conditions.append(
                        {
                            "field": f"{subject}.{field}",
                            "expected": value,
                            "actual": actual,
                            "matches": actual == value,
                        }
                    )
        for field, party in [
            ("lunar_last", 0),
            ("lunar_next", 1),
            ("lunar_next_seven_body_subset", 1),
        ]:
            if field in chart:
                expected = chart[field]
                role = election["marriage_significators"]["parties"][party]
                contact = role["contact"]
                actual = {
                    "other": role["lunar_significator"],
                    "aspect": None if contact is None else contact["aspect"],
                }
                conditions.append(
                    {
                        "field": field,
                        "expected": expected,
                        "actual": actual,
                        "matches": (
                            actual == expected
                            if role["contact_order_established"] is True
                            else None
                        ),
                        "reason": (
                            None
                            if role["contact_order_established"] is True
                            else "Adjacent contact order is not established"
                        ),
                        "source_claims_adjacent_seven_body_contact": field
                        != "lunar_next_seven_body_subset",
                    }
                )
            else:
                pass
        history = election["marriage_significators"]["event_history"]
        remaining_events = list(history["events"])
        for index, expected in enumerate(chart.get("lunar_future_prefix", [])):
            contact, order = (
                ordered_contact(
                    remaining_events, history.get("unresolved_intervals", []), "Moon"
                )
                if history["status"] == "computed"
                and history["constant_velocity_projection"] is False
                else (None, None)
            )
            actual = (
                None
                if contact is None or order is not True
                else {
                    "other": next(
                        planet for planet in contact["bodies"] if planet != "Moon"
                    ),
                    "aspect": contact["aspect"],
                }
            )
            conditions.append(
                {
                    "field": f"lunar_future_prefix.{index}",
                    "expected": expected,
                    "actual": actual,
                    "matches": actual == expected if order is True else None,
                    "reason": (
                        None
                        if order is True
                        else "Physical prefix order is not established"
                    ),
                    "scope": "Shared domain order qualification; not independent astronomy or full source application policy",
                }
            )
            if order is True:
                remaining_events.remove(contact)
            else:
                pass
        results.append(
            {
                "status": "computed",
                "case_id": case["id"],
                "chart": case["chart"],
                "input": case["input"],
                "as_of": case["as_of"],
                "source_clock_or_calendar_resolved": case[
                    "source_clock_or_calendar_resolved"
                ],
                "source_framework_confirmed": case["source_framework_confirmed"],
                "readings": readings,
                "conditions": conditions,
                "response": response,
            }
        )
    return {
        "historical_audit": reference["clock_audit"],
        "response_source": (
            "live_service" if replay_path is None else "saved_service_responses"
        ),
        "chart_count": len(charts),
        "input_count": len(results),
        "reading_count": sum(
            len(charts[case["chart"]]["points"]) for case in reference["cases"]
        ),
        "evaluated_reading_count": sum(
            row["within_display_unit"] is not None
            for result in results
            for row in result["readings"]
        ),
        "condition_comparison_count": sum(
            len(result["conditions"]) for result in results
        ),
        "evaluated_condition_count": sum(
            row["matches"] is not None
            for result in results
            for row in result["conditions"]
        ),
        "unevaluated_condition_count": sum(
            row["matches"] is None for result in results for row in result["conditions"]
        ),
        "unavailable_case_count": sum(
            result["status"] == "unavailable" for result in results
        ),
        "current_reading_failures": sum(
            row["within_display_unit"] is False
            for result in results
            for row in result["readings"]
        ),
        "reconstructed_original_transcription_failures": sum(
            row["within_original_display_unit"] is False
            for result in results
            for row in result["readings"]
        ),
        "condition_failures": sum(
            row["matches"] is False
            for result in results
            for row in result["conditions"]
        ),
        "condition_scope": "Prose sign/major-dignity/occupancy and adjacent physical lunar contacts only. Minor dignities and instantaneous aspect policy are not reclassified. This is not the unavailable original v1 condition-row report.",
        "independent_astronomy_cases": 0,
        "full_original_text_acceptance": False,
        "results": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--replay",
        type=Path,
        help="Recheck saved responses with identical inputs and as_of",
    )
    arguments = parser.parse_args()
    report = audit(arguments.replay, arguments.output)
    arguments.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {name: value for name, value in report.items() if name != "results"},
            ensure_ascii=False,
        )
    )

"""Independent JPL solar clocks; boundary tolerance is not a certainty claim."""

import csv
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fatebridge.services.metaphysics import calculate_qimen_analysis
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims


def read_solar_reference(directory: Path) -> list[dict[str, Any]]:
    ref = json.loads((directory / "reference.json").read_text())
    for kind in ("request", "protocol", "response"):
        if (
            hashlib.sha256((directory / ref[f"{kind}_file"]).read_bytes()).hexdigest()
            != ref[f"{kind}_sha256"]
        ):
            raise ValueError("JPL太阳时原件、请求或预先选择协议指纹改变")
    protocol = json.loads((directory / ref["protocol_file"]).read_text())
    request = json.loads((directory / ref["request_file"]).read_text())
    response = json.loads((directory / ref["response_file"]).read_text())
    if (
        request["parameters"]["COMMAND"] != "'10'"
        or request["parameters"]["SITE_COORD"] != "'0,0,0'"
        or request["parameters"]["QUANTITIES"] != "'34,49'"
        or request["parameters"]["TIME_TYPE"] != "'UT'"
        or len(protocol["instants_utc"]) != 12
        or ref["tolerance_seconds"] != 5
        or protocol["tolerance_seconds"] != 5
    ):
        raise ValueError(
            "太阳时参考须保留预定12个实际时刻、Greenwich视太阳钟和DUT1，不放宽容差"
        )
    rows: list[dict[str, Any]] = []
    raw_table = response["result"].split("$$SOE")[1].split("$$EOE")[0].strip()
    for cells in csv.reader(raw_table.splitlines()):
        instant = datetime.strptime(cells[0].strip(), "%Y-%b-%d %H:%M:%S.%f").replace(
            tzinfo=timezone.utc
        )
        apparent, dut1 = float(cells[3]), float(cells[4])
        utc_hours = instant.hour + instant.minute / 60 + instant.second / 3600
        delta = ((apparent - utc_hours + 12) % 24) - 12
        rows.append(
            {
                "instant_utc": instant.isoformat(),
                "apparent_solar_hours": apparent,
                "dut1_seconds": dut1,
                "equation_of_time_minutes": delta * 60 - dut1 / 60,
            }
        )
    if rows != ref["cases"] or {
        datetime.fromisoformat(r["instant_utc"]).strftime("%Y-%m-%d %H:%M:%S")
        for r in rows
    } != set(protocol["instants_utc"]):
        raise ValueError(
            "须保留JPL原始全行，不能改参考值、删掉边界近例或由当前程序生成期望"
        )
    return rows


def expected_solar_label(case: dict[str, Any], longitude: float = 0) -> datetime:
    """Derive a label from the frozen JPL apparent clock, not Swiss output."""
    instant = datetime.fromisoformat(case["instant_utc"])
    hours = instant.hour + instant.minute / 60 + instant.second / 3600
    delta = ((case["apparent_solar_hours"] - hours + 12) % 24) - 12
    return instant.replace(tzinfo=None) + timedelta(hours=delta, minutes=4 * longitude)


def label_classification(label: datetime) -> dict[str, Any]:
    effective_date = label.date() + timedelta(days=int(label.hour == 23))
    return {
        "effective_day": effective_date.isoformat(),
        "hour_branch": "子丑寅卯辰巳午未申酉戌亥"[((label.hour + 1) // 2) % 12],
    }


def audit_solar_clocks(directory: Path) -> dict[str, Any]:
    rows = read_solar_reference(directory)
    observations = []
    errors = []
    for case in rows:
        instant = datetime.fromisoformat(case["instant_utc"])
        result = calculate_qimen_analysis(
            analysis_year=instant.year,
            analysis_month=instant.month,
            analysis_day=instant.day,
            analysis_hour=instant.hour,
            analysis_minute=instant.minute,
            analysis_timezone="UTC",
            analysis_longitude=0.0,
            use_true_solar_time=True,
            qimen_options={"ju_method": "chaibu"},
        )
        if "error" in result:
            errors.append({"instant": case["instant_utc"], "kind": "calculation_error"})
            continue
        receipt = result["qimen"]["calendar_policy"]["solar_time_adjustment"]
        actual = datetime.fromisoformat(receipt["apparent_solar_label"])
        expected = expected_solar_label(case)
        residual = (actual - expected).total_seconds()
        eot_residual = (
            receipt["equation_of_time_minutes"] - case["equation_of_time_minutes"]
        ) * 60
        # Tolerance describes this comparison only. If its interval crosses a
        # day/hour boundary, matching the nominal label cannot certify it.
        low, high = [
            label_classification(expected + timedelta(seconds=sign * 5))
            for sign in (-1, 1)
        ]
        distinguishable = low == high
        nominal = label_classification(actual) == label_classification(expected)
        if (
            abs(residual) > 5
            or abs(eot_residual) > 5
            or (distinguishable and not nominal)
        ):
            errors.append(
                {
                    "instant": case["instant_utc"],
                    "kind": "solar_clock_or_boundary_disagreement",
                }
            )
        observations.append(
            {
                "instant": case["instant_utc"],
                "clock_residual_seconds": residual,
                "eot_residual_seconds": eot_residual,
                "nominal_label_matches": nominal,
                "classification_verifiable_at_reference_tolerance": distinguishable,
                "reference_minus_tolerance": low,
                "reference_plus_tolerance": high,
            }
        )
    return {
        "method_id": "qimen_jpl_solar_clocks_and_boundary_identifiability_v1",
        "reference_instants": len(rows),
        "reference_clock_tolerance_seconds": 5,
        "observations": observations,
        "implementation_disagreements": errors,
        "boundary_cases_not_certified_at_reference_tolerance": [
            r["instant"]
            for r in observations
            if not r["classification_verifiable_at_reference_tolerance"]
        ],
        "maximum_absolute_clock_residual_seconds": max(
            abs(r["clock_residual_seconds"]) for r in observations
        ),
        "hko_calendar_references_added": 0,
        "empirical_prediction_cases": 0,
        "all_boundary_labels_certified": False,
    }


def verify_qimen_solar_time_quotes(
    payload: dict[str, Any], claims: list[CalculationClaim]
) -> dict[str, Any]:
    if not claims or any(
        c.path != "qimen.calendar_policy.solar_time_adjustment" for c in claims
    ):
        return {
            "status": "rejected",
            "reason": "须引用同run整条太阳时修正依据，不能只摘总修正量或方法名",
        }
    result = verify_calculation_claims(payload, claims)
    if result["status"] == "verified_structured_facts":
        result["status"] = "verified_structured_solar_time_quotes"
    return result

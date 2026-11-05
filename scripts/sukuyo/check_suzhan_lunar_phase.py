"""Compare every phase in the five originally frozen USNO annual tables."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fatebridge.core.astro import runtime
from fatebridge.core.astro.geometry import _julian_day
from fatebridge.core.astro.native_coordinates import require_spherical_coordinates
from fatebridge.core.astro.time_scales import tt_from_ut1
from fatebridge.core.suzhan_lunar_phase import lunar_phase_reference

FIXTURE = (
    Path(__file__).resolve().parents[2] / "tests/fixtures/suzhan-usno-phases-2026.json"
)
INDEX = (
    Path(__file__).resolve().parents[2]
    / "tests/fixtures/suzhan-usno-phases-v1/index.json"
)
ORIGINAL_PROTOCOL_SHA256 = (
    "03a5dabf5e849fde1439fc185384a21ccc1a1d316a5735550e76ecbb49ec6b8b"
)
PHASE_ANGLES = {
    "New Moon": 0,
    "First Quarter": 90,
    "Full Moon": 180,
    "Last Quarter": 270,
}


def compare_row(row: dict[str, Any]) -> dict[str, Any]:
    # tzinfo is only a Gregorian JD container. The published clock is UT1,
    # converted directly to TT; it is not fed into a civil UTC conversion.
    hour, minute = map(int, row["time"].split(":"))
    ut1 = _julian_day(
        datetime(
            row["year"], row["month"], row["day"], hour, minute, tzinfo=timezone.utc
        )
    )
    tt = tt_from_ut1(ut1)
    native = runtime.swe
    if native is None:
        raise ImportError("Swiss Ephemeris unavailable")
    states, receipts = {}, {}
    for body in ("Sun", "Moon"):
        values, flags = runtime.ephemeris_call(
            "calc",
            tt,
            getattr(native, body.upper()),
            native.FLG_SWIEPH | native.FLG_SPEED,
        )
        longitude, _, _ = require_spherical_coordinates(values, flags, native=native)
        states[body] = {"longitude": longitude % 360}
        receipts[body] = {
            "ecliptic_model": runtime.ephemeris_model_from_retflag(flags),
            "ecliptic_return_flags": flags,
        }
    result = lunar_phase_reference(
        {
            "states": states,
            "julian_day_tt": tt,
            "julian_day_ut1": ut1,
            "ephemeris_provenance": {"by_body": receipts},
        }
    )
    difference = result["elongation_degrees"] - PHASE_ANGLES[row["phase"]]
    residual = abs((difference + 180) % 360 - 180)
    return {
        "reference": dict(row),
        "julian_day_ut1": ut1,
        "julian_day_tt": tt,
        "absolute_wrapped_elongation_residual_degrees": residual,
        "ephemeris_provenance": result["ephemeris_provenance"],
    }


def compare_available() -> dict[str, Any]:
    """Retain the original one-year fixture as an incomplete-coverage control."""
    data = json.loads(FIXTURE.read_bytes())
    # Bind all copied rows and headers to the extracted publisher response.
    extracted = (json.dumps(data["api_response"], indent=2) + "\n").encode()
    if hashlib.sha256(extracted).hexdigest() != data["extracted_json_sha256"]:
        raise ValueError("USNO copied rows differ from frozen extracted response")
    rows = data["api_response"]["phasedata"]
    if len(rows) != data["api_response"]["numphases"]:
        raise ValueError("USNO phase rows omitted")
    protocol = data["comparison_protocol"]
    _require_original_protocol(protocol)
    results = [compare_row(row) for row in rows]
    tolerance = protocol[
        "uniform_absolute_wrapped_elongation_residual_tolerance_degrees"
    ]
    available_pass = all(
        r["absolute_wrapped_elongation_residual_degrees"] <= tolerance for r in results
    )
    obtained = sorted({row["year"] for row in rows})
    missing = sorted(set(protocol["source_years"]) - set(obtained))
    return {
        "required_years": protocol["source_years"],
        "obtained_years": obtained,
        "missing_years": missing,
        "uniform_tolerance_degrees": tolerance,
        "all_available_rows_checked": len(results),
        "copied_response_matches_frozen_extracted_identity": True,
        "available_rows_within_tolerance": available_pass,
        "full_frozen_five_year_gate_met": available_pass and not missing,
        "strict_holdout": False,
        "real_astrological_samples": 0,
        "results": results,
    }


def _require_original_protocol(protocol: dict[str, Any]) -> None:
    encoded = (json.dumps(protocol, indent=2) + "\n").encode()
    if hashlib.sha256(encoded).hexdigest() != ORIGINAL_PROTOCOL_SHA256:
        raise ValueError(
            "USNO comparison protocol differs from original frozen standard"
        )


def _annual_response(
    content: dict[str, Any], *, year: int, count: int
) -> list[dict[str, Any]]:
    rows = content["phasedata"]
    if (
        type(content.get("year")) is not int
        or content["year"] != year
        or type(content.get("numphases")) is not int
        or content["numphases"] != count
        or not isinstance(rows, list)
        or len(rows) != count
        or count <= 0
    ):
        raise ValueError("USNO annual header or complete row count changed")
    previous_time = None
    previous_angle = None
    phases = set()
    for row in rows:
        if (
            not isinstance(row, dict)
            or any(type(row.get(key)) is not int for key in ("year", "month", "day"))
            or row["year"] != year
            or row.get("phase") not in PHASE_ANGLES
        ):
            raise ValueError("USNO annual phase identity or calendar year changed")
        try:
            hour, minute = map(int, row["time"].split(":"))
            stamp = datetime(year, row["month"], row["day"], hour, minute)
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("USNO annual UT1 minute label invalid") from error
        angle = PHASE_ANGLES[row["phase"]]
        if previous_time is not None and stamp <= previous_time:
            raise ValueError(
                "USNO annual rows duplicated or out of chronological order"
            )
        if previous_angle is not None and (angle - previous_angle) % 360 != 90:
            raise ValueError("USNO annual primary phase sequence incomplete")
        previous_time, previous_angle = stamp, angle
        phases.add(row["phase"])
    if phases != set(PHASE_ANGLES):
        raise ValueError("USNO annual response does not contain all four phases")
    return rows


def compare_frozen_years(index_path: Path | None = None) -> dict[str, Any]:
    """Read all extracted bytes before assessing complete-year residuals.

    The old 2026 fixture stays byte-for-byte intact, and still serves the
    incomplete-coverage test. Missing years never become a passing subset.
    """
    path = INDEX if index_path is None else index_path
    index = json.loads(path.read_bytes())
    protocol = index["comparison_protocol"]
    _require_original_protocol(protocol)
    if index["original_protocol_bytes_sha256"] != ORIGINAL_PROTOCOL_SHA256:
        raise ValueError("USNO source index names a different frozen protocol")
    required = protocol["source_years"]
    records = index["annual_responses"]
    years = [row["year"] for row in records]
    if any(type(year) is not int or year not in required for year in years) or len(
        years
    ) != len(set(years)):
        raise ValueError("USNO annual source identities duplicated or unexpected")
    results = []
    sources = []
    for record in records:
        year = record["year"]
        if record["source_url"] != (
            f"https://aa.usno.navy.mil/api/moon/phases/year?year={year}"
        ):
            raise ValueError("USNO annual source URL or year changed")
        raw = (path.parent / record["fixture"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != record["extracted_bytes_sha256"]:
            raise ValueError("USNO annual extracted source bytes changed")
        content = json.loads(raw)
        if record["format"] == "v51_wrapped_reference":
            _require_original_protocol(content["comparison_protocol"])
            encoded = (json.dumps(content["api_response"], indent=2) + "\n").encode()
            if hashlib.sha256(encoded).hexdigest() != content["extracted_json_sha256"]:
                raise ValueError(
                    "USNO copied rows differ from frozen extracted response"
                )
            content = content["api_response"]
        elif record["format"] != "annual_tool_extracted_json":
            raise ValueError("USNO annual source representation unknown")
        rows = _annual_response(content, year=year, count=record["numphases"])
        year_results = [compare_row(row) for row in rows]
        results.extend(year_results)
        sources.append(
            {
                **record,
                "all_rows_checked": len(year_results),
                "maximum_residual_degrees": max(
                    r["absolute_wrapped_elongation_residual_degrees"]
                    for r in year_results
                ),
            }
        )
    tolerance = protocol[
        "uniform_absolute_wrapped_elongation_residual_tolerance_degrees"
    ]
    within = bool(results) and all(
        row["absolute_wrapped_elongation_residual_degrees"] <= tolerance
        for row in results
    )
    missing = sorted(set(required) - set(years))
    return {
        "required_years": required,
        "obtained_years": sorted(years),
        "missing_years": missing,
        "original_protocol_bytes_sha256": ORIGINAL_PROTOCOL_SHA256,
        "uniform_tolerance_degrees": tolerance,
        "all_available_rows_checked": len(results),
        "all_extracted_source_bytes_and_complete_annual_rows_checked": True,
        "available_rows_within_tolerance": within,
        "full_frozen_five_year_gate_met": within and not missing,
        "annual_sources": sources,
        "strict_holdout": False,
        "real_astrological_samples": 0,
        "ancient_day_boundary_or_rule_priority_established": False,
        "results": results,
    }


if __name__ == "__main__":
    report = compare_frozen_years()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["full_frozen_five_year_gate_met"] else 1)

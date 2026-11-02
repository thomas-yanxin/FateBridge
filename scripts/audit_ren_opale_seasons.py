"""Keep the full PMO gate while diagnosing OPALE event and clock differences.

Expected labels come only from frozen service responses. The later clock
diagnostics do not replace the original UTC/UT1 or documented-TAI-zero tests.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"
EVENTS = {
    "VernalEquinox": "春分",
    "SummerSolstice": "夏至",
    "AutumnalEquinox": "秋分",
    "WinterSolstice": "冬至",
}
FROZEN = {
    "ren_opale_seasons_v1": "86e79fc70465b4a4f13ca09ca584abb34612352728192336b72bd6e0c887e0ed",
    "ren_opale_tt_v1": "07cda4e4e3fcae7e751d581dfa0b7dc0431c865d4e3a1bc907732c63d44cec8f",
    "ren_opale_clock_v1": "518f2751889eb1a792a6120a085c5b2704316e94e7a09d013bc4a00d79de1ba2",
}
TOLERANCE_SECONDS = 1.0  # Engineering comparison, not a source accuracy promise.


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def label(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.tzinfo is not None:
        raise ValueError(
            "Service clock labels must keep their explicit scale separately"
        )
    return result


def julian_day(value: str) -> float:
    return 2451545.0 + (label(value) - datetime(2000, 1, 1, 12)).total_seconds() / 86400


def frozen(corpus: Path, expected_digest: str) -> dict[str, Any]:
    if sha(corpus / "freeze.json") != expected_digest:
        raise ValueError("Original OPALE freeze changed")
    manifest = json.loads((corpus / "freeze.json").read_text())["files"]
    if {p.name for p in corpus.iterdir()} != set(manifest) | {"freeze.json"}:
        raise ValueError("Frozen OPALE inventory changed")
    for name, digest in manifest.items():
        if sha(corpus / name) != digest:
            raise ValueError("Frozen OPALE source changed: " + name)
    pre = json.loads((corpus / "protocol-freeze.json").read_text())["files"]
    if "protocol.json" not in pre or any(
        sha(corpus / name) != digest for name, digest in pre.items()
    ):
        raise ValueError("OPALE prequery protocol changed")
    return {name: json.loads((corpus / name).read_text()) for name in manifest}


def season_cases(
    raw: dict[str, Any], start: int, stop: int, scale: str, name: str
) -> list[dict[str, Any]]:
    req, response = raw["request"], raw["response"]
    if any(
        req[k] != v
        for k, v in dict(
            body=399,
            year=start,
            nbd=stop - start,
            calendar="gregorian",
            timescale=scale,
        ).items()
    ) or any(
        response[k] != v for k, v in dict(calendar="gregorian", timescale=scale).items()
    ):
        raise ValueError("OPALE request/response clock or cohort changed")
    rows = []
    for index, row in enumerate(response["data"]):
        year, event = label(row["date"]).year, row["phenomena"]
        rows.append(
            dict(
                id=f"{year}-{event}",
                year=year,
                term=EVENTS[event],
                phenomena=event,
                published_label=row["date"],
                timescale=scale,
                cohort="historical_ut1" if scale == "UT1" else "modern_utc",
                source_file=name,
                source_row=index,
            )
        )
    if [(r["year"], r["phenomena"]) for r in rows] != [
        (year, event) for year in range(start, stop) for event in EVENTS
    ]:
        raise ValueError("All ordered OPALE years and four seasons are required")
    return rows


def annotated(
    data: dict[str, Any], cases: list[dict[str, Any]], count_key: str = "expected_count"
) -> None:
    if data["cases"] != cases or data[count_key] != len(cases):
        raise ValueError("OPALE annotation differs from the complete raw response")


def reference(fixtures: Path = FIXTURES) -> dict[str, Any]:
    primary, documented, clock = [
        frozen(fixtures / name, digest) for name, digest in FROZEN.items()
    ]
    if (
        primary["protocol.json"]["criteria"]["maximum_absolute_difference_seconds"]
        != TOLERANCE_SECONDS
        or documented["protocol.json"]["maximum_absolute_difference_seconds"]
        != TOLERANCE_SECONDS
        or clock["protocol.json"]["maximum_absolute_difference_seconds"]
        != TOLERANCE_SECONDS
    ):
        raise ValueError("Original one-second engineering criterion changed")
    cases = season_cases(
        primary["historical-ut1.json"], 1900, 1972, "UT1", "historical-ut1.json"
    )
    cases += season_cases(
        primary["modern-utc.json"], 1972, 2026, "UTC", "modern-utc.json"
    )
    annotated(primary["reference.json"], cases)
    raw_doc = season_cases(
        documented["response.json"], 1900, 1961, "UTC", "response.json"
    )
    doc_cases = [
        dict(
            id=r["id"],
            year=r["year"],
            term=r["term"],
            source_row=r["source_row"],
            artificial_utc_label=r["published_label"],
            expected_tt_label=(
                label(r["published_label"]) + timedelta(seconds=32.184)
            ).isoformat(timespec="microseconds"),
            time_scale="TT_from_OPALE_TAI_zero_convention",
        )
        for r in raw_doc
    ]
    annotated(documented["reference.json"], doc_cases, "count")
    request, raw = clock["request.json"], clock["response.json"]
    historical = cases[:288]
    if request["date-set"] != [r["published_label"] for r in historical]:
        raise ValueError("Clock diagnostic must retain all 288 external UT1 labels")
    if raw["request"]["id"] != 10 or any(
        raw["request"][k] != v
        for k, v in request.items()
        if k not in {"body", "date-set"}
    ):
        raise ValueError("OPALE clock request changed")
    response = raw["response"]
    if (
        response["timescale"] != "UT1"
        or response["calendar"] != "gregorian"
        or response["unit"]["TT-UT1"] != "Second"
        or len(response["data"]) != 288
    ):
        raise ValueError("OPALE clock scale, units or full denominator changed")
    clock_cases = []
    for case, row in zip(historical, response["data"]):
        offset = row["TT-UT1"]
        if (
            label(row["date"]) != label(case["published_label"])
            or isinstance(offset, bool)
            or not math.isfinite(offset)
        ):
            raise ValueError("Invalid OPALE clock row")
        clock_cases.append(
            dict(
                id=case["id"],
                year=case["year"],
                term=case["term"],
                source_row=case["source_row"],
                ut1_label=case["published_label"],
                tt_minus_ut1_seconds=offset,
                expected_tt_label=(
                    label(row["date"]) + timedelta(seconds=offset)
                ).isoformat(timespec="microseconds"),
            )
        )
    annotated(clock["reference.json"], clock_cases)
    return dict(seasons=cases, documented_tt=doc_cases, source_clock_tt=clock_cases)


def comparison(
    cases: list[dict[str, Any]],
    actuals: dict[tuple[int, str], dict[str, Any]],
    route: str,
    convert: Callable[[datetime], Any],
) -> dict[str, Any]:
    rows, errors = [], []
    for case in cases:
        try:
            original = actuals[(case["year"], case["term"])]
            moment = datetime.fromisoformat(original["actual"])
            if moment.utcoffset() is None or original["provider"] != "swisseph":
                raise ValueError(
                    "Expected an aware Swiss calculation, without fallback"
                )
            time = convert(moment)
            if any(
                isinstance(value, bool) or value is None or not math.isfinite(value)
                for value in (time.jd_tt, time.jd_ut1)
            ):
                raise ValueError("Nonfinite or unavailable production clock")
            if route == "seasons" and case["timescale"] == "UTC":
                # The production civil label can have +08:00; source labels use UTC.
                expected = label(case["published_label"]).replace(tzinfo=timezone.utc)
                delta = (moment - expected).total_seconds()
            else:
                scale = "jd_ut1" if route == "seasons" else "jd_tt"
                expected_label = (
                    case["published_label"]
                    if route == "seasons"
                    else case["expected_tt_label"]
                )
                delta = (getattr(time, scale) - julian_day(expected_label)) * 86400
            if not math.isfinite(delta):
                raise ValueError("Nonfinite clock difference")
            row = dict(
                **case,
                actual=original["actual"],
                difference_seconds=delta,
                within_criterion=abs(delta) <= TOLERANCE_SECONDS,
                actual_clock_method=time.method,
            )
            if route == "source_clock_tt":
                actual_delta_t = (time.jd_tt - time.jd_ut1) * 86400
                row["actual_tt_minus_ut1_seconds"] = actual_delta_t
                row["clock_model_difference_seconds"] = (
                    actual_delta_t - case["tt_minus_ut1_seconds"]
                )
            rows.append(row)
        except Exception as exc:
            errors.append(
                dict(id=case["id"], error_type=type(exc).__name__, error=str(exc))
            )
    failures = [r for r in rows if not r["within_criterion"]]
    return dict(
        expected_count=len(cases),
        compared_count=len(rows),
        failure_count=len(failures),
        failures=failures,
        calculation_errors=errors,
        comparisons=rows,
        maximum_absolute_difference_seconds=max(
            (abs(r["difference_seconds"]) for r in rows), default=None
        ),
        all_comparisons_passed=len(rows) == len(cases) and not failures and not errors,
    )


def pmo_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "opale_pmo", ROOT / "scripts/audit_ren_calendar_pmo.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assemble(
    pmo: dict[str, Any], ref: dict[str, Any], convert: Callable[[datetime], Any]
) -> dict[str, Any]:
    if (
        pmo["expected_count"] != 3024
        or pmo["minute_criterion"]["max_absolute_difference_seconds"] != 30
    ):
        raise ValueError(
            "The original complete PMO cohort and 30-second gate are required"
        )
    actuals = {(r["year"], r["term"]): r for r in pmo["comparisons"]}
    if len(actuals) != len(pmo["comparisons"]):
        raise ValueError("Duplicate production event labels")
    routes = {key: comparison(ref[key], actuals, key, convert) for key in ref}
    return dict(
        audit_id="ren_opale_seasons_v1",
        criterion_seconds=TOLERANCE_SECONDS,
        criterion_is_source_accuracy_guarantee=False,
        original_pmo=pmo,
        routes=routes,
        source_freeze_sha256=FROZEN,
        unique_astronomical_events_across_all_routes=3024,
        new_unique_astronomical_events=0,
        physical_observations=0,
        initial_source_dynamical_ephemeris_and_frame_verified=False,
        later_clock_request_theory="INPOP19A (clock-quantity endpoint only)",
        all_performed_comparisons_passed=pmo["all_performed_comparisons_passed"]
        and all(r["all_comparisons_passed"] for r in routes.values()),
        full_supported_calendar_domain_certified=False,
        goal_complete=False,
        real_world_prediction_validation="deferred_by_user",
        model_invocations=0,
    )


def audit() -> dict[str, Any]:
    ref = reference()  # Validate all independent labels before production imports.
    pmo_audit = pmo_module()
    names = tuple(pmo_audit.IMPLEMENTATION) + ("scripts/audit_ren_opale_seasons.py",)
    implementation = {n: sha(ROOT / n) for n in names}
    from fatebridge.core.astro.time_scales import ephemeris_time

    report = assemble(pmo_audit.audit(), ref, ephemeris_time)
    report["implementation_sha256"] = implementation
    unchanged = implementation == {n: sha(ROOT / n) for n in names}
    report["implementation_unchanged_during_audit"] = unchanged
    report["all_performed_comparisons_passed"] &= unchanged
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "pmo_failures": report["original_pmo"]["minute_failure_count"],
                "routes": {
                    k: {
                        n: r[n]
                        for n in ("expected_count", "compared_count", "failure_count")
                    }
                    for k, r in report["routes"].items()
                },
                "all_performed_comparisons_passed": report[
                    "all_performed_comparisons_passed"
                ],
            }
        )
    )
    return 0 if report["all_performed_comparisons_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

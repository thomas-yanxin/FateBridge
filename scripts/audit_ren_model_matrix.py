"""Keep original Ren gates and compare named deployment models separately."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/ren_model_matrix_v1"
PROTOCOL_SHA256 = "c87663eb168a41b41948c7d2e2d0e3929c63027489d5a06c98b63b3312dce04b"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def module(name: str, filename: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    assert spec and spec.loader
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def protocol(corpus: Path = CORPUS) -> dict[str, Any]:
    raw = corpus / "protocol.json"
    if (
        sha(raw) != PROTOCOL_SHA256
        or json.loads((corpus / "freeze.json").read_text())["protocol_sha256"]
        != PROTOCOL_SHA256
    ):
        raise ValueError("Declared model-matrix protocol changed")
    result: dict[str, Any] = json.loads(raw.read_text())
    return result


def identity(row: dict[str, Any], selected: dict[str, Any]) -> bool:
    return bool(
        row["provider"] == selected["provider"]
        and row["ephemeris_model"] == selected["model"]
        and row["ephemeris_retflags"] == selected["retflags"]
    )


def compare_route(
    cases: list[dict[str, Any]],
    actuals: dict[tuple[int, str], dict[str, Any]],
    route: str,
    convert: Callable[[datetime], Any],
    julian_day: Callable[[str], float],
    label: Callable[[str], datetime],
    selected: dict[str, Any],
) -> dict[str, Any]:
    """Original one-second arithmetic; actual provider names are never rewritten."""
    rows, errors = [], []
    for case in cases:
        try:
            original = actuals[(case["year"], case["term"])]
            moment = datetime.fromisoformat(original["actual"])
            if moment.utcoffset() is None:
                raise ValueError("Calculation has no physical offset")
            epoch = convert(moment)
            if any(
                isinstance(value, bool) or value is None or not math.isfinite(value)
                for value in (epoch.jd_tt, epoch.jd_ut1)
            ):
                raise ValueError("Nonfinite or unavailable clock")
            if route == "seasons" and case["timescale"] == "UTC":
                expected = label(case["published_label"]).replace(tzinfo=timezone.utc)
                delta = (moment - expected).total_seconds()
            else:
                scale = "jd_ut1" if route == "seasons" else "jd_tt"
                expected = (
                    case["published_label"]
                    if route == "seasons"
                    else case["expected_tt_label"]
                )
                delta = (getattr(epoch, scale) - julian_day(expected)) * 86400
            if not math.isfinite(delta):
                raise ValueError("Nonfinite event difference")
            row = {
                **case,
                "actual": original["actual"],
                "actual_provider": original["provider"],
                "actual_model": original["ephemeris_model"],
                "model_identity_matches_profile": identity(original, selected),
                "difference_seconds": delta,
                "within_original_numeric_criterion": abs(delta) <= 1.0,
                "actual_clock_method": epoch.method,
            }
            if route == "source_clock_tt":
                delta_t = (epoch.jd_tt - epoch.jd_ut1) * 86400
                row["actual_tt_minus_ut1_seconds"] = delta_t
                row["clock_model_difference_seconds"] = (
                    delta_t - case["tt_minus_ut1_seconds"]
                )
            rows.append(row)
        except Exception as error:
            errors.append(
                {"id": case["id"], "type": type(error).__name__, "error": str(error)}
            )
    failures = [r for r in rows if not r["within_original_numeric_criterion"]]
    model_failures = [r for r in rows if not r["model_identity_matches_profile"]]
    return {
        "expected_count": len(cases),
        "compared_count": len(rows),
        "numeric_failure_count": len(failures),
        "numeric_failures": failures,
        "model_identity_failure_count": len(model_failures),
        "calculation_errors": errors,
        "maximum_absolute_difference_seconds": max(
            (abs(r["difference_seconds"]) for r in rows), default=None
        ),
        "comparisons": rows,
        "all_declared_numeric_and_identity_checks_passed": (
            len(rows) == len(cases)
            and not failures
            and not model_failures
            and not errors
        ),
    }


def runtime_manifest() -> dict[str, str]:
    paths = [
        p
        for p in (ROOT / "src/fatebridge").rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    ]
    paths += [
        ROOT / "scripts" / name
        for name in (
            "audit_ren_model_matrix.py",
            "audit_ren_calendar_pmo.py",
            "audit_ren_calendar.py",
            "audit_ren_opale_seasons.py",
        )
    ]
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(paths)}


def audit_profile(name: str, ephe_dir: Path) -> dict[str, Any]:
    declared = protocol()
    selected = declared["profiles"][name]
    if not ephe_dir.is_dir() or (name == "auto_no_files" and any(ephe_dir.iterdir())):
        raise ValueError("Profile requires its declared existing or empty directory")
    # Only this isolated process is configured; unrelated processes are untouched.
    os.environ["SE_EPHE_PATH"] = str(ephe_dir.resolve())
    os.environ["FATEBRIDGE_SOLAR_TERM_MODEL"] = selected["mode"]
    opale = module("ren_matrix_opale", "audit_ren_opale_seasons.py")
    refs = opale.reference()
    pmo = opale.pmo_module()
    before = runtime_manifest()
    native_files = {
        str(p): sha(p)
        for p in sorted(ephe_dir.glob("*"))
        if p.is_file()
        and (p.suffix == ".se1" or p.name in {"swe_deltat.txt", "seleapsec.txt"})
    }
    # Original reference readers and raw provider-dependent results are retained.
    from fatebridge.core.astro.time_scales import ephemeris_time

    old = pmo.audit()
    legacy = opale.assemble(old, refs, ephemeris_time)
    actuals = {(r["year"], r["term"]): r for r in old["comparisons"]}
    if len(actuals) != 3024 or old["boundary_pair_count"] != 4536:
        raise ValueError("Original complete PMO event/boundary cohort incomplete")
    numeric_rows = [
        {
            **row,
            "within_original_numeric_criterion": abs(row["difference_seconds"]) <= 30.0,
            "model_identity_matches_profile": identity(row, selected),
        }
        for row in old["comparisons"]
    ]
    routes = {
        route: compare_route(
            cases,
            actuals,
            route,
            ephemeris_time,
            opale.julian_day,
            opale.label,
            selected,
        )
        for route, cases in refs.items()
    }
    unchanged = before == runtime_manifest() and all(
        sha(Path(filename)) == expected for filename, expected in native_files.items()
    )
    numeric_failures = sum(
        not row["within_original_numeric_criterion"] for row in numeric_rows
    )
    identity_failures = sum(
        not row["model_identity_matches_profile"] for row in numeric_rows
    )
    return {
        "profile": name,
        "selected": selected,
        "protocol_sha256": PROTOCOL_SHA256,
        "legacy_report_with_original_provider_predicates": legacy,
        "pmo_numeric_comparisons": numeric_rows,
        "pmo_numeric_failure_count": numeric_failures,
        "pmo_model_identity_failure_count": identity_failures,
        "named_model_opale_routes": routes,
        "runtime_manifest": before,
        "ephemeris_file_sha256": native_files,
        "implementation_and_selected_files_unchanged": unchanged,
        "all_declared_numeric_and_identity_checks_passed": (
            not numeric_failures
            and not identity_failures
            and not old["calculation_errors"]
            and not old["boundary_pair_failures"]
            and unchanged
            and all(
                r["all_declared_numeric_and_identity_checks_passed"]
                for r in routes.values()
            )
        ),
        "original_thresholds_unchanged": True,
        "new_unique_external_events": 0,
        "model_invocations": 0,
        "full_calendar_domain_certified": False,
        "goal_complete": False,
    }


def lunar_replay() -> dict[str, Any]:
    protocol()
    calendar = module("ren_matrix_hko", "audit_ren_calendar.py")
    calendar.reference()
    before = runtime_manifest()
    root = ROOT / "tests/data/ziwei_independent"
    manifest = json.loads((root / "calendar_manifest.json").read_text())
    from fatebridge.core.almanac import _safe_lunar_date_from_solar

    state, count, supplemented = (1900, 11, False), 0, 0
    failures, missing = [], []
    for source in manifest["sources"]:
        file = root / source["path"]
        if sha(file) != source["sha256"]:
            raise ValueError("Original HKO annual text changed")
        rows, state = calendar.annual_rows(
            file.read_text(encoding="utf-8-sig"), source["year"], state
        )
        for row in rows:
            count += 1
            day = row["date"]
            value = _safe_lunar_date_from_solar(
                datetime(day.year, day.month, day.day, 12), "+08:00"
            )
            expected = [row[k] for k in ("year", "month", "day", "is_leap_month")]
            if value is None:
                missing.append(day.isoformat())
            elif [
                value.year,
                value.month,
                value.day,
                bool(value.isLeapMonth),
            ] != expected:
                failures.append(
                    {
                        "date": day.isoformat(),
                        "expected": expected,
                        "actual": str(value),
                    }
                )
            supplemented += day.isoformat() >= "2100-02-09"
    if count != 73049:
        raise ValueError("Original full 200-year HKO date cohort incomplete")
    return {
        "civil_dates": count,
        "mismatches": failures,
        "unavailable": missing,
        "source_fed_supplement_dates": supplemented,
        "new_independent_oracle": False,
        "scope": "Calendar table fidelity, including a supplement fed from HKO; not independent physical lunar validation or all Ren board-chain acceptance.",
        "runtime_manifest": before,
        "implementation_unchanged": before == runtime_manifest(),
        "all_declared_numeric_and_identity_checks_passed": (
            not failures and not missing and before == runtime_manifest()
        ),
        "full_calendar_domain_certified": False,
        "goal_complete": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        choices=[
            "native_swiss_files",
            "analytic_swiss_clock",
            "auto_no_files",
            "lunar",
        ],
        required=True,
    )
    parser.add_argument("--ephe-dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.profile != "lunar" and args.ephe_dir is None:
        parser.error("--ephe-dir is required for a deployment profile")
    result = (
        lunar_replay()
        if args.profile == "lunar"
        else audit_profile(args.profile, args.ephe_dir)
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k
                in {
                    "profile",
                    "pmo_numeric_failure_count",
                    "pmo_model_identity_failure_count",
                    "civil_dates",
                    "implementation_unchanged",
                    "implementation_and_selected_files_unchanged",
                }
            },
            ensure_ascii=False,
        )
    )
    # Exit status covers the declared finite checks, never the full goal.
    return 0 if result["all_declared_numeric_and_identity_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

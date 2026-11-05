"""Frozen place/clock probes and a single civil timezone for lunar-year age."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone, tzinfo
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/ren_runyear_place_age_v1"
IMPLEMENTATION = (
    "src/fatebridge/core/metaphysics/ren_calendar.py",
    "src/fatebridge/core/metaphysics/liureng.py",
    "src/fatebridge/core/requests/metaphysics.py",
    "src/fatebridge/core/output_ren_clock.py",
    "src/fatebridge/core/output_chinese.py",
    "src/fatebridge/services/metaphysics.py",
    "src/fatebridge/utils/places.py",
    "src/fatebridge/utils/timezones.py",
    "src/fatebridge/data/places/china.json",
    "src/fatebridge/data/places/world.json",
    "scripts/ren/audit_ren_runyear_place_age.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(corpus: Path = CORPUS) -> dict[str, Any]:
    manifest = json.loads((corpus / "freeze.json").read_text())
    names = {
        str(p.relative_to(corpus))
        for p in corpus.rglob("*")
        if p.is_file() and p.name != "freeze.json"
    }
    if names != set(manifest["files"]):
        raise ValueError("Frozen runyear place/age inventory changed")
    for name, digest in manifest["files"].items():
        if sha(corpus / name) != digest:
            raise ValueError(f"Frozen runyear place/age source changed: {name}")
    ref: dict[str, Any] = json.loads((corpus / "reference.json").read_text())
    if [r["id"] for r in ref["cases"]] != [f"P{i:02}" for i in range(1, 29)]:
        raise ValueError("All 28 precommitted cases required")
    # Reconstruct literal UTC -> local labels using the copied database, never
    # the production resolver or service output. This is shared-ancestry data.
    for case in ref["cases"]:
        expected, data = case["expected"], case["input"]
        if "error" in expected:
            continue
        zone = expected["timezone"]
        tz: tzinfo
        if zone == "UTC":
            tz = timezone.utc
        else:
            with (corpus / "tzif" / zone).open("rb") as stream:
                tz = ZoneInfo.from_file(stream, key=zone)
        local = datetime.fromisoformat(expected["birth_instant_utc"]).astimezone(tz)
        if (local.year, local.month, local.day, local.hour, local.minute) != tuple(
            data.get("birth_" + k, 0)
            for k in ("year", "month", "day", "hour", "minute")
        ) or local.fold != expected.get("fold", 0):
            raise ValueError(f"Literal birth UTC differs: {case['id']}")
        if "analysis_in_age_zone" in expected:
            analysis_zone = data["analysis_timezone"]
            atz: tzinfo
            if analysis_zone == "UTC":
                atz = timezone.utc
            else:
                with (corpus / "tzif" / analysis_zone).open("rb") as stream:
                    atz = ZoneInfo.from_file(stream, key=analysis_zone)
            wall = datetime(
                data["analysis_year"],
                data["analysis_month"],
                data["analysis_day"],
                data["analysis_hour"],
                data.get("analysis_minute", 0),
                data.get("analysis_second", 0),
                tzinfo=atz,
            )
            if wall.astimezone(tz).isoformat() != expected["analysis_in_age_zone"]:
                raise ValueError("Literal common-age-zone label differs")
    return ref


def calculate(data: dict[str, Any]) -> dict[str, Any]:
    from fatebridge.services.metaphysics import calculate_liureng_runyear
    from fatebridge.utils.birth_input import PersonInfo

    birth = {k: v for k, v in data.items() if k in PersonInfo.model_fields}
    options = {
        k: v
        for k, v in data.items()
        if k.startswith("analysis_") or k in ("birth_utc_offset", "use_true_solar_time")
    }
    return calculate_liureng_runyear(PersonInfo(**birth), **options)


def audit() -> dict[str, Any]:
    ref = reference()
    before = {n: sha(ROOT / n) for n in IMPLEMENTATION}
    comparisons, errors = [], []
    for case in ref["cases"]:
        expected = case["expected"]
        try:
            result = calculate(case["input"])
            actual: dict[str, Any]
            if "error" in expected:
                actual = {k: result[k] for k in ("error", "error_type") if k in result}
                matched = (
                    expected["error"] in str(result.get("error", ""))
                    and "runyear" not in result
                )
            else:
                run = result.get("runyear", {})
                clock = run.get("birth_civil_clock", {})
                age = run.get("age_calendar", {})
                actual = dict(
                    timezone=clock.get("timezone"),
                    birth_instant_utc=clock.get("instant_utc"),
                    timezone_source=clock.get("timezone_source"),
                    age=run.get("age"),
                    ganzhi=run.get("ganzhi"),
                    assumed=clock.get("timezone_assumed"),
                    fold=clock.get("fold"),
                    birth_lunar_year=run.get("birth_lunar_year"),
                    analysis_lunar_year=age.get("analysis_lunar_year"),
                    analysis_in_age_zone=age.get("analysis_civil_datetime"),
                )
                matched = "error" not in result and all(
                    actual[k] == v and type(actual[k]) is type(v)
                    for k, v in expected.items()
                )
                matched = (
                    matched
                    and age.get("timezone") == clock.get("timezone")
                    and clock.get("timezone_assumed") is expected.get("assumed", False)
                )
            comparisons.append(
                dict(id=case["id"], expected=expected, actual=actual, matched=matched)
            )
        except Exception as exc:
            errors.append(
                dict(id=case["id"], error_type=type(exc).__name__, error=str(exc))
            )
    stable = before == {n: sha(ROOT / n) for n in IMPLEMENTATION}
    return dict(
        audit_id="ren_runyear_place_age_v1",
        expected_count=28,
        compared_count=len(comparisons),
        matched_count=sum(r["matched"] for r in comparisons),
        comparisons=comparisons,
        calculation_errors=errors,
        reference_sha256=sha(CORPUS / "freeze.json"),
        implementation_sha256=before,
        implementation_unchanged_during_audit=stable,
        selected_place_age_checks_passed=stable
        and len(comparisons) == 28
        and not errors
        and all(r["matched"] for r in comparisons),
        scope=ref["scope"],
        age_policy=ref["age_policy"],
        timezone_policy=ref["timezone_policy"],
        full_supported_calendar_domain_certified=False,
        classical_acceptance_passed=False,
        free_text_semantic_acceptance_passed=False,
        model_invocations=0,
        goal_complete=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "expected_count",
                    "compared_count",
                    "matched_count",
                    "calculation_errors",
                    "selected_place_age_checks_passed",
                    "goal_complete",
                )
            },
            ensure_ascii=False,
        )
    )
    return 0 if result["selected_place_age_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

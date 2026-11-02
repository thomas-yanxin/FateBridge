"""Frozen birth/analysis clock probes for Liu Ren runyear chronology."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/ren_runyear_birth_clock_v1"
IMPLEMENTATION = (
    "src/fatebridge/core/almanac.py",
    "src/fatebridge/core/lunar_1900_prefix.py",
    "src/fatebridge/data/lunar_calendar_pmo_1900_prefix.json",
    "src/fatebridge/core/metaphysics/ren_calendar.py",
    "src/fatebridge/core/metaphysics/liureng.py",
    "src/fatebridge/core/requests/metaphysics.py",
    "src/fatebridge/core/output_chinese.py",
    "src/fatebridge/services/metaphysics.py",
    "src/fatebridge/utils/civil_clock.py",
    "src/fatebridge/utils/timezones.py",
    "scripts/audit_ren_runyear_birth_clock.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(corpus: Path = CORPUS) -> dict[str, Any]:
    manifest = json.loads((corpus / "freeze.json").read_text())
    names = {
        str(path.relative_to(corpus))
        for path in corpus.rglob("*")
        if path.is_file() and path != corpus / "freeze.json"
    }
    if names != set(manifest["files"]):
        raise ValueError("Frozen runyear clock inventory changed")
    for name, expected in manifest["files"].items():
        if sha(corpus / name) != expected:
            raise ValueError(f"Frozen runyear clock source changed: {name}")
    ref: dict[str, Any] = json.loads((corpus / "reference.json").read_text())
    if [case["id"] for case in ref["cases"]] != [f"B{i:02}" for i in range(1, 19)]:
        raise ValueError("All eighteen original runyear clock probes are required")
    # Reconstruct only the literal UTC -> local relationship with the copied
    # external database. No production resolver supplies these expectations.
    for case in ref["cases"]:
        data, expected = case["input"], case["expected"]
        for prefix in ("birth", "analysis"):
            key = prefix + "_instant_utc"
            if key not in expected:
                continue
            utc = datetime.fromisoformat(expected[key])
            zone = data[prefix + "_timezone"]
            if zone in ref["zones"]:
                with (corpus / "tzif" / zone).open("rb") as stream:
                    local = utc.astimezone(ZoneInfo.from_file(stream, key=zone))
            elif zone == "UTC":
                local = utc.astimezone(timezone.utc)
            else:
                fixed = datetime.fromisoformat("2000-01-01T00:00:00" + zone).tzinfo
                local = utc.astimezone(fixed)
            wall = datetime(
                *(
                    data[prefix + "_" + field]
                    for field in ("year", "month", "day", "hour", "minute")
                )
            )
            if local.replace(tzinfo=None) != wall:
                raise ValueError(f"Frozen UTC/local clock mismatch: {case['id']}")
            declared = data.get(prefix + "_utc_offset")
            if (
                declared
                and local.utcoffset()
                != datetime.fromisoformat("2000-01-01T00:00:00" + declared).utcoffset()
            ):
                raise ValueError(f"Frozen explicit offset mismatch: {case['id']}")
            if prefix == "birth" and local.fold != expected["birth_fold"]:
                raise ValueError(f"Frozen birth fold mismatch: {case['id']}")
        if "birth_instant_utc" in expected:
            earlier = datetime.fromisoformat(
                expected["analysis_instant_utc"]
            ) < datetime.fromisoformat(expected["birth_instant_utc"])
            if earlier != (expected.get("error") == "早于出生"):
                raise ValueError(f"Frozen chronology differs: {case['id']}")
    return ref


def calculate(data: dict[str, Any]) -> dict[str, Any]:
    from fatebridge.services.metaphysics import calculate_liureng_runyear
    from fatebridge.utils.birth_input import PersonInfo

    birth = {
        key: value for key, value in data.items() if key in PersonInfo.model_fields
    }
    options = {
        key: value
        for key, value in data.items()
        if key.startswith("analysis_")
        or key in ("birth_utc_offset", "use_true_solar_time")
    }
    return calculate_liureng_runyear(PersonInfo(**birth), **options)


def audit() -> dict[str, Any]:
    ref = reference()
    before = {name: sha(ROOT / name) for name in IMPLEMENTATION}
    comparisons, errors = [], []
    for case in ref["cases"]:
        expected = case["expected"]
        try:
            result = calculate(case["input"])
            actual: dict[str, Any]
            if "error" in expected:
                matched = (
                    expected["error"] in str(result.get("error", ""))
                    and "runyear" not in result
                )
                actual = {
                    key: result[key] for key in ("error", "error_type") if key in result
                }
            else:
                clock = result.get("runyear", {}).get("birth_civil_clock", {})
                actual = dict(
                    birth_instant_utc=clock.get("instant_utc"),
                    analysis_instant_utc=result.get("liureng", {})
                    .get("calendar_policy", {})
                    .get("civil_instant_utc"),
                    birth_fold=clock.get("fold"),
                    age=result.get("runyear", {}).get("age"),
                    ganzhi=result.get("runyear", {}).get("ganzhi"),
                )
                matched = "error" not in result and all(
                    actual[key] == expected[key] for key in actual
                )
            comparisons.append(
                dict(id=case["id"], expected=expected, actual=actual, matched=matched)
            )
        except Exception as exc:
            errors.append(
                dict(id=case["id"], error_type=type(exc).__name__, error=str(exc))
            )
    changed = [name for name, value in before.items() if sha(ROOT / name) != value]
    passed = (
        not changed
        and not errors
        and len(comparisons) == 18
        and all(row["matched"] for row in comparisons)
    )
    return dict(
        audit_id="ren_runyear_birth_clock_v1",
        expected_count=18,
        compared_count=len(comparisons),
        matched_count=sum(row["matched"] for row in comparisons),
        comparisons=comparisons,
        calculation_errors=errors,
        implementation_sha256=before,
        implementation_changed_during_audit=changed,
        selected_clock_checks_passed=passed,
        full_supported_calendar_domain_certified=False,
        classical_acceptance_passed=False,
        goal_complete=False,
        source_sha256={
            str((CORPUS / name).relative_to(ROOT)): sha(CORPUS / name)
            for name in ("reference.json", "freeze.json")
        },
        limits=ref["limits"],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit()
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")
    raise SystemExit(0 if report["selected_clock_checks_passed"] else 1)

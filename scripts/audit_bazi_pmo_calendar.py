"""Compare frozen complete PMO cells, HKO cells and a frozen candidate.

Printed-date conformance is distinct from astronomical accuracy, timezone
correctness, classical interpretation and independent reality prediction.
"""

from __future__ import annotations

import argparse
import ast
import gzip
import importlib.metadata
import json
import platform
import re
import sys
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, cast

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_pmo_calendar_v1"
KEYS = ("year", "month", "day", "is_leap_month")


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def frozen_json(path: Path) -> dict[str, Any]:
    if digest(path) != path.with_suffix(".sha256").read_text().strip():
        raise ValueError(f"Frozen JSON changed: {path}")
    result: dict[str, Any] = json.loads(path.read_text())
    return result


def hko_parser() -> Callable[..., list[dict[str, Any]]]:
    """Execute only unchanged literal parser/constant AST, no application imports."""
    path = FIXTURE / "before/scripts/audit_ziwei.py"
    tree = ast.parse(path.read_text())
    wanted = {"MONTHS", "DAYS", "HKO_ROW"}
    selected: list[ast.stmt] = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id in wanted for t in node.targets
        ):
            selected.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name == "hko_rows":
            selected.append(node)
    if len(selected) != 4:
        raise ValueError("Frozen HKO literal parser structure changed")
    namespace = {"date": date, "timedelta": timedelta, "re": re, "Any": Any}
    exec(
        compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"),
        namespace,
    )
    return cast(Callable[..., list[dict[str, Any]]], namespace["hko_rows"])


def audit(candidate: Path, environment_path: Path) -> dict[str, Any]:
    protocol = frozen_json(FIXTURE / "protocol.json")
    reference = frozen_json(FIXTURE / "reference-freeze.json")
    environment = frozen_json(environment_path)
    # This extra binding was sealed after the retained first comparison.
    # It strengthens replays, without retroactively upgrading that first run.
    input_binding = frozen_json(FIXTURE / "comparison-inputs-v2.json")
    for name, wanted in input_binding["files"].items():
        if digest(FIXTURE / name) != wanted:
            raise ValueError(f"Supplemental comparison input changed: {name}")
    for name, wanted in reference["files"].items():
        if digest(FIXTURE / name) != wanted:
            raise ValueError(f"Frozen reference/candidate archive changed: {name}")
    if reference["protocol_sha256"] != digest(FIXTURE / "protocol.json"):
        raise ValueError("Reference protocol changed")
    manifest = json.loads((FIXTURE / "candidate-manifest.json").read_text())
    if (
        digest(FIXTURE / "candidate-manifest.json")
        != protocol["candidate_manifest_sha256"]
    ):
        raise ValueError("Frozen candidate manifest changed")

    def verify_candidate() -> None:
        actual_files = {
            str(p.relative_to(candidate))
            for p in candidate.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
        }
        if actual_files != set(manifest):
            raise ValueError("Frozen candidate file inventory changed")
        for name, wanted in manifest.items():
            if digest(candidate / name) != wanted:
                raise ValueError(f"Frozen candidate changed: {name}")

    verify_candidate()
    sys.path.insert(0, str(candidate / "src"))
    import lunardate

    from fatebridge.core import almanac

    if candidate not in Path(almanac.__file__).resolve().parents:
        raise ValueError("Fresh process must import the declared frozen candidate")
    if digest(Path(lunardate.__file__)) != environment["lunardate_module_sha256"]:
        raise ValueError("Frozen installed lunardate source changed")
    if importlib.metadata.version("lunardate") != environment["lunardate_version"]:
        raise ValueError("Frozen lunardate version changed")
    corpus = json.loads(
        gzip.decompress((FIXTURE / "expected-calendar.json.gz").read_bytes())
    )
    if len(corpus["rows"]) != protocol["expected_source_date_count"]:
        raise ValueError("Complete PMO cohort reduced")
    literal_pmo = {r["solar"]: r for r in corpus["rows"]}

    def convert(solar: date) -> dict[str, Any]:
        lunar = almanac._lunar_date_from_solar(solar)
        return {
            "year": lunar.year,
            "month": lunar.month,
            "day": lunar.day,
            "is_leap_month": lunar.isLeapMonth,
        }

    def matches(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
        return actual == expected and all(
            type(actual[k]) is type(v) for k, v in expected.items()
        )

    pmo_rows, pmo_mismatches = [], []
    periods = {
        "1900-1911": {"rows": 0, "lunar_mismatches": 0, "day_ganzhi_mismatches": 0},
        "1912-1948": {"rows": 0, "lunar_mismatches": 0, "day_ganzhi_mismatches": 0},
        "1949-2025": {"rows": 0, "lunar_mismatches": 0, "day_ganzhi_mismatches": 0},
    }
    for row in corpus["rows"]:
        solar = date.fromisoformat(row["solar"])
        expected = {k: row[k] for k in KEYS}
        try:
            actual = convert(solar)
            lunar_matches = matches(actual, expected)
        except Exception as error:
            actual = {"error_type": type(error).__name__, "message": str(error)}
            lunar_matches = False
        ganzhi: str | dict[str, str]
        try:
            ganzhi = almanac.get_day_ganzhi(solar.year, solar.month, solar.day)
        except Exception as error:
            ganzhi = {"error_type": type(error).__name__, "message": str(error)}
        gz_matches = ganzhi == row["day_ganzhi"]
        output = {
            "solar": row["solar"],
            "source_pdf_page": row["source_pdf_page"],
            "source_literal": row["literal"],
            "expected_lunar": expected,
            "actual_lunar": actual,
            "lunar_matches": lunar_matches,
            "expected_day_ganzhi": row["day_ganzhi"],
            "actual_day_ganzhi": ganzhi,
            "day_ganzhi_matches": gz_matches,
        }
        pmo_rows.append(output)
        if not lunar_matches or not gz_matches:
            pmo_mismatches.append(output)
        period = periods[
            (
                "1900-1911"
                if solar.year <= 1911
                else "1912-1948" if solar.year <= 1948 else "1949-2025"
            )
        ]
        period["rows"] += 1
        period["lunar_mismatches"] += not lunar_matches
        period["day_ganzhi_mismatches"] += not gz_matches

    parser = hko_parser()
    manifest_path = ROOT / "tests/fixtures/ziwei_independent/calendar_manifest.json"
    if digest(manifest_path) != protocol["old_hko_reference_manifest_sha256"]:
        raise ValueError("Old HKO source manifest changed")
    hko_manifest = json.loads(manifest_path.read_text())
    if [s["year"] for s in hko_manifest["sources"]] != list(range(1901, 2101)):
        raise ValueError("Complete old HKO cohort reduced")
    hko_rows, hko_mismatches, cross_mismatches, recovered = [], [], [], []
    complete = partial = full_matches = partial_matches = 0
    last_year = last_month = last_leap = None
    overlap = overlap_full = 0
    union_source_dates = set(literal_pmo)
    for source in hko_manifest["sources"]:
        source_path = manifest_path.parent / source["path"]
        if digest(source_path) != source["sha256"]:
            raise ValueError("HKO literal source changed")
        adjacent = last_year is not None and last_year + 1 == source["year"]
        rows = parser(
            source_path.read_bytes().decode("utf-8-sig"),
            source["year"],
            last_month if adjacent else None,
            last_leap if adjacent else None,
        )
        last_year, last_month, last_leap = (
            source["year"],
            rows[-1]["month"],
            rows[-1]["is_leap"],
        )
        for row in rows:
            solar = row["solar"]
            name = solar.isoformat()
            known = row["month"] is not None
            expected = {"year": row["year"], "day": row["day"]}
            if known:
                expected.update(month=row["month"], is_leap_month=row["is_leap"])
                complete += 1
                union_source_dates.add(name)
            else:
                partial += 1
            try:
                actual = convert(solar)
                compared = {k: actual[k] for k in expected}
                matched = matches(compared, expected)
            except Exception as error:
                actual = {"error_type": type(error).__name__, "message": str(error)}
                matched = False
            full_matches += known and matched
            partial_matches += not known and matched
            output = {
                "solar": name,
                "source": source["path"],
                "known_source_fields": expected,
                "source_full_date": known,
                "actual_lunar": actual,
                "matches_known_fields": matched,
            }
            hko_rows.append(output)
            if not matched:
                hko_mismatches.append(output)
            if name in literal_pmo:
                overlap += 1
                pmo = {k: literal_pmo[name][k] for k in KEYS}
                if known:
                    overlap_full += 1
                if {k: pmo[k] for k in expected} != expected:
                    cross_mismatches.append(
                        {
                            "solar": name,
                            "pmo": pmo,
                            "pmo_pdf_page": literal_pmo[name]["source_pdf_page"],
                            "hko_known_fields": expected,
                            "hko_source": source["path"],
                            "hko_full_date": known,
                        }
                    )
                if not known:
                    recovered.append(
                        {
                            "solar": name,
                            "old_hko_known_fields": expected,
                            "new_pmo_fields": pmo,
                            "original_hko_unknown_fields_not_changed": True,
                            "not_new_independent_credit": True,
                        }
                    )
    verify_candidate()
    if digest(Path(lunardate.__file__)) != environment["lunardate_module_sha256"]:
        raise ValueError("Installed dependency drifted during comparison")
    for source in hko_manifest["sources"]:
        if digest(manifest_path.parent / source["path"]) != source["sha256"]:
            raise ValueError("HKO source drifted during comparison")
    return {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": digest(FIXTURE / "protocol.json"),
        "reference_freeze_sha256": digest(FIXTURE / "reference-freeze.json"),
        "candidate_manifest_sha256": digest(FIXTURE / "candidate-manifest.json"),
        "environment": environment,
        "supplemental_input_binding_sha256": digest(
            FIXTURE / "comparison-inputs-v2.json"
        ),
        "first_comparison_binding_limit": input_binding["first_comparison_limit"],
        "actual_candidate_root": str(candidate),
        "actual_almanac_file": almanac.__file__,
        "python": sys.version,
        "platform": platform.platform(),
        "scope": "Full frozen PMO1900-2025 literal civil dates plus old HKO1901-2100 known fields; normative source conformance and source disagreement, no physical-instant/astronomical/reality score.",
        "pmo": {
            "rows": len(pmo_rows),
            "lunar_matches": sum(r["lunar_matches"] for r in pmo_rows),
            "day_ganzhi_matches": sum(r["day_ganzhi_matches"] for r in pmo_rows),
            "mismatches": pmo_mismatches,
            "periods": periods,
            "all_rows": pmo_rows,
        },
        "hko": {
            "rows": len(hko_rows),
            "full_source_cells": complete,
            "partial_source_cells": partial,
            "matched_full": full_matches,
            "matched_year_day_only": partial_matches,
            "mismatches": hko_mismatches,
            "all_rows": hko_rows,
        },
        "cross_source": {
            "overlapping_date_labels": overlap,
            "overlapping_full_date_labels": overlap_full,
            "different_dates": cross_mismatches,
            "old_unknown_hko19_new_pmo_fields": recovered,
            "union_complete_source_dates": len(union_source_dates),
            "not_summed_as_independent_samples": True,
            "existing_ziwei_TAM_join_already_exposed_the_HKO_prefix": True,
        },
        "source_drift": [],
        "production_changed": False,
        "original_first_reports_or_adoption_gates_changed": False,
        "new_independent_observation_credit": 0,
        "whole_goal_complete": False,
        "reality_prediction_efficacy": "not_tested",
        "overall_score": None,
        "runner_sha256": digest(Path(__file__)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--environment", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Keep all first comparison outputs")
    result = audit(args.candidate_root.resolve(), args.environment)
    encoded = (
        json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode()
    args.output.write_bytes(gzip.compress(encoded, mtime=0))
    args.output.with_suffix(args.output.suffix + ".sha256").write_text(
        digest(args.output) + "\n"
    )
    print(
        json.dumps(
            {
                "pmo_dates": result["pmo"]["rows"],
                "pmo_lunar_mismatches": result["pmo"]["rows"]
                - result["pmo"]["lunar_matches"],
                "pmo_day_ganzhi_mismatches": result["pmo"]["rows"]
                - result["pmo"]["day_ganzhi_matches"],
                "hko_full": result["hko"]["matched_full"],
                "hko_partial": result["hko"]["matched_year_day_only"],
                "cross_source_different_dates": len(
                    result["cross_source"]["different_dates"]
                ),
                "union_complete_source_dates": result["cross_source"][
                    "union_complete_source_dates"
                ],
            }
        )
    )
    return int(
        bool(
            result["pmo"]["mismatches"]
            or result["hko"]["mismatches"]
            or result["cross_source"]["different_dates"]
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())

"""Compare the fixed lunar candidate to every frozen HKO civil-date cell.

Run with the exact optional trial dependency, before adding it to production:
uv run --locked --extra dev --with lunar-python==1.4.8 python scripts/audit_bazi_lunar_extension.py --output /tmp/lunar-extension.json
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import runpy
from datetime import date
from pathlib import Path
from typing import Any

from audit_ziwei import hko_rows

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_lunar_extension_v1"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_frozen() -> dict[str, Any]:
    file = FIXTURE / "protocol.json"
    if digest(file) != file.with_suffix(".sha256").read_text().strip():
        raise ValueError("Extension protocol changed after freeze")
    protocol = json.loads(file.read_text())
    first = ROOT / "docs/validation/bazi-lunar-extension-first-v1.json"
    if first.exists():
        if digest(first) != first.with_suffix(".sha256").read_text().strip():
            raise ValueError("First extension comparison changed after freeze")
        if json.loads(first.read_text())["protocol_sha256"] != digest(file):
            raise ValueError("Extension protocol differs from the frozen first result")
    if digest(FIXTURE / "candidate.py.txt") != protocol["candidate_sha256"]:
        raise ValueError("Extension candidate changed after freeze")
    if importlib.metadata.version("lunar-python") != protocol["lunar_python_version"]:
        raise ValueError("Trial library version differs from the fixed candidate")
    spec = importlib.util.find_spec("lunar_python")
    if spec is None or spec.origin is None:
        raise ValueError("Trial library source unavailable")
    package = Path(spec.origin).parent
    sources = {
        str(p.relative_to(package)): digest(p) for p in sorted(package.rglob("*.py"))
    }
    if sources != protocol["library_source_fingerprints"]:
        raise ValueError("Trial library source changed after freeze")
    if digest(ROOT / protocol["hko_manifest"]) != protocol["hko_manifest_sha256"]:
        raise ValueError("Independent HKO source manifest changed")
    return protocol


def audit() -> dict[str, Any]:
    protocol = load_frozen()
    source = ROOT / protocol["hko_manifest"]
    manifest = json.loads(source.read_text())
    convert = runpy.run_path(str(FIXTURE / "candidate.py.txt"))["convert"]
    begin = date.fromisoformat(protocol["target_extension"]["start"])
    end = date.fromisoformat(protocol["target_extension"]["end"])
    coverage, mismatches, target_rows = [], [], []
    last_year, last_month, last_leap = None, None, None
    for item in manifest["sources"]:
        raw = (source.parent / item["path"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != item["sha256"]:
            raise ValueError(f"HKO source changed: {item['path']}")
        adjacent = last_year is not None and item["year"] == last_year + 1
        rows = hko_rows(
            raw.decode("utf-8-sig"),
            item["year"],
            last_month if adjacent else None,
            last_leap if adjacent else None,
        )
        last_year, last_month, last_leap = (
            item["year"],
            rows[-1]["month"],
            rows[-1]["is_leap"],
        )
        failures = 0
        for row in rows:
            actual = convert(row["solar"])
            expected = {"year": row["year"], "day": row["day"]}
            if row["month"] is not None:
                expected.update(month=row["month"], isLeapMonth=row["is_leap"])
            matched = {k: actual[k] for k in expected} == expected
            if not matched:
                failures += 1
                mismatches.append(
                    {
                        "date": row["solar"].isoformat(),
                        "expected": expected,
                        "candidate": actual,
                    }
                )
            if begin <= row["solar"] <= end:
                target_rows.append(
                    {
                        "date": row["solar"].isoformat(),
                        "expected": expected,
                        "candidate": actual,
                        "matched": matched,
                        "full_source_date": row["month"] is not None,
                    }
                )
        coverage.append(
            {
                "year": item["year"],
                "source_days": len(rows),
                "full_date_cells": sum(r["month"] is not None for r in rows),
                "unknown_prefix_month_cells": sum(r["month"] is None for r in rows),
                "mismatches": failures,
            }
        )
        if item["year"] % 25 == 0:
            print(
                f"Compared through {item['year']}; all mismatches retained", flush=True
            )
    complete_target = len(target_rows) == protocol["target_extension"]["expected_days"]
    if complete_target:
        complete_target = len({r["date"] for r in target_rows}) == len(target_rows)
    target_match = complete_target and all(
        r["matched"] and r["full_source_date"] for r in target_rows
    )
    return {
        "method_id": "bazi_lunar_extension_hko_first_candidate_v1",
        "protocol_sha256": digest(FIXTURE / "protocol.json"),
        "candidate_sha256": protocol["candidate_sha256"],
        "library_version": protocol["lunar_python_version"],
        "hko_manifest_sha256": protocol["hko_manifest_sha256"],
        "classification": protocol["classification"],
        "all_source_days": sum(r["source_days"] for r in coverage),
        "full_source_date_cells": sum(r["full_date_cells"] for r in coverage),
        "unknown_prefix_month_cells": sum(
            r["unknown_prefix_month_cells"] for r in coverage
        ),
        "diagnostic_mismatch_count": len(mismatches),
        "all_diagnostic_mismatches": mismatches,
        "coverage": coverage,
        "target_extension": {
            "start": begin.isoformat(),
            "end": end.isoformat(),
            "days": len(target_rows),
            "complete": complete_target,
            "matched": sum(r["matched"] for r in target_rows),
            "all_target_fields_match": target_match,
            "cases": target_rows,
        },
        "numerical_extension_condition_passed": target_match,
        "production_adopted": False,
        "transport_and_legacy_preservation_verified": False,
        "full_calendar_acceptance": False,
        "scope": protocol["source_clock"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--freeze-first-result", action="store_true")
    args = parser.parse_args()
    first = ROOT / "docs/validation/bazi-lunar-extension-first-v1.json"
    if args.output.resolve() in {
        first.resolve(),
        first.with_suffix(".sha256").resolve(),
    }:
        raise ValueError("First-result path is reserved; use a separate output")
    if args.freeze_first_result and first.exists():
        raise ValueError("Do not overwrite the first candidate comparison")
    result = audit()
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(raw)
    if args.freeze_first_result:
        first.write_bytes(raw)
        first.with_suffix(".sha256").write_text(hashlib.sha256(raw).hexdigest() + "\n")
    print(
        json.dumps(
            {
                "all_source_days": result["all_source_days"],
                "diagnostic_mismatches": result["diagnostic_mismatch_count"],
                "target_days": result["target_extension"]["days"],
                "target_matches": result["target_extension"]["matched"],
                "numerical_condition": result["numerical_extension_condition_passed"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if result["numerical_extension_condition_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

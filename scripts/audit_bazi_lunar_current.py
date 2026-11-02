"""Replay all frozen HKO cells against an explicitly frozen current converter.

HKO was already used for legacy corrections and the2100 supplement. This is
normative conformance replay, never a new independent or blind accuracy trial.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Keep earlier replay outputs")
    if (
        digest(args.protocol)
        != args.protocol.with_suffix(".sha256").read_text().strip()
    ):
        raise ValueError("Protocol changed")
    protocol = json.loads(args.protocol.read_text())
    root = args.candidate_root.resolve()

    def verify_sources() -> None:
        for name, expected in protocol["source_fingerprints"].items():
            if digest(root / name) != expected:
                raise ValueError(f"Frozen candidate or parser changed: {name}")

    verify_sources()
    sys.path[:0] = [str(root / "src"), str(root / "scripts")]
    import lunardate
    from audit_ziwei import hko_rows

    from fatebridge.core import almanac

    if root not in Path(almanac.__file__).resolve().parents:
        raise ValueError("Run in a fresh process; another candidate was imported")
    library_source = Path(lunardate.__file__)
    library_hash = digest(library_source)
    source_manifest = root / protocol["hko_manifest"]
    if digest(source_manifest) != protocol["hko_manifest_sha256"]:
        raise ValueError("Original HKO manifest changed")
    manifest = json.loads(source_manifest.read_text())
    coverage, mismatches = [], []
    last_year = last_month = last_leap = None
    for source in manifest["sources"]:
        file = source_manifest.parent / source["path"]
        if digest(file) != source["sha256"]:
            raise ValueError(f"HKO reply changed: {source['path']}")
        adjacent = last_year is not None and source["year"] == last_year + 1
        rows = hko_rows(
            file.read_bytes().decode("utf-8-sig"),
            source["year"],
            last_month if adjacent else None,
            last_leap if adjacent else None,
        )
        last_year, last_month, last_leap = (
            source["year"],
            rows[-1]["month"],
            rows[-1]["is_leap"],
        )
        complete = partial = complete_matches = partial_matches = 0
        for row in rows:
            expected = {"year": row["year"], "day": row["day"]}
            known = row["month"] is not None
            if known:
                expected.update(month=row["month"], isLeapMonth=row["is_leap"])
                complete += 1
            else:
                partial += 1
            try:
                actual_lunar = almanac._lunar_date_from_solar(row["solar"])
                actual = {key: getattr(actual_lunar, key) for key in expected}
                matched = actual == expected
            except Exception as error:
                actual = {"error_type": type(error).__name__, "message": str(error)}
                matched = False
            if matched and known:
                complete_matches += 1
            elif matched:
                partial_matches += 1
            else:
                mismatches.append(
                    {
                        "solar": row["solar"].isoformat(),
                        "expected_known_fields": expected,
                        "actual": actual,
                        "full_source_date": known,
                    }
                )
        coverage.append(
            {
                "year": source["year"],
                "source_days": len(rows),
                "full_source_cells": complete,
                "partial_source_cells": partial,
                "matched_full": complete_matches,
                "matched_partial": partial_matches,
            }
        )
    verify_sources()
    if digest(library_source) != library_hash:
        raise ValueError("External library source changed during replay")
    result = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "classification": protocol["classification"],
        "protocol": protocol,
        "library": {
            "package": "lunardate",
            "version": importlib.metadata.version("lunardate"),
            "module_sha256": library_hash,
        },
        "source_days": sum(r["source_days"] for r in coverage),
        "full_source_date_cells": sum(r["full_source_cells"] for r in coverage),
        "unknown_month_leap_cells": sum(r["partial_source_cells"] for r in coverage),
        "matched_full_cells": sum(r["matched_full"] for r in coverage),
        "matched_year_day_only": sum(r["matched_partial"] for r in coverage),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "coverage": coverage,
        "source_drift": [],
        "whole_goal_achieved": False,
        "overall_score": None,
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "source_days",
                    "full_source_date_cells",
                    "unknown_month_leap_cells",
                    "matched_full_cells",
                    "matched_year_day_only",
                    "mismatch_count",
                )
            }
        )
    )
    return int(bool(mismatches))


if __name__ == "__main__":
    raise SystemExit(main())

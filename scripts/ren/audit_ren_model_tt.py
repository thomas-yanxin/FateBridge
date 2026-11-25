"""Diagnose supplied TT outcomes against reproducible independent DE440 roots."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict

from pydantic import BaseModel

from scripts.astronomy.solar_term_reference import (
    REFERENCE_SHA256,
    load_solar_term_reference,
)

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "tests/fixtures/ren_model_matrix_v1/de440-followup-protocol.json"
PROTOCOL_SHA256 = "0542c8fb1f39266555a5aa5c052d2c5fd1a43fd3aec1eefe784148440b8839d5"
TERMS = "小寒 大寒 立春 雨水 惊蛰 春分 清明 谷雨 立夏 小满 芒种 夏至 小暑 大暑 立秋 处暑 白露 秋分 寒露 霜降 立冬 小雪 大雪 冬至".split()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TTReference(TypedDict):
    jd_tt: float


class LegacySourceIdentity(TypedDict):
    source_identifier: str
    expected_sha256: str
    historical_sha256: str | None
    historical_identity_matches: bool
    current_path: str
    current_sha256: str | None
    current_identity_matches: bool


class _ComparisonSourcePins(BaseModel):
    source_sha256: dict[str, str]


def reference() -> dict[tuple[int, str], TTReference]:
    """Use the independently reproduced roots under the original comparison gate."""
    if sha(PROTOCOL) != PROTOCOL_SHA256:
        raise ValueError("Follow-up protocol changed")
    else:
        pass
    packet = load_solar_term_reference()
    return {
        (row.year, row.name): {"jd_tt": row.jd_tt}
        for row in packet.rows
        if 1899 <= row.year <= 2101
    }


def legacy_source_status() -> list[LegacySourceIdentity]:
    """Retain old sidecar identity failures separately from the reproduced source."""
    raw = PROTOCOL.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PROTOCOL_SHA256:
        raise ValueError("Follow-up protocol changed")
    else:
        pass
    pins = _ComparisonSourcePins.model_validate_json(raw).source_sha256
    result: list[LegacySourceIdentity] = []
    for filename, expected in pins.items():
        historical = ROOT / filename
        historical_sha = sha(historical) if historical.is_file() else None
        current = ROOT / "tests/data/bazi_all_terms_v1" / Path(filename).name
        actual = sha(current) if current.is_file() else None
        result.append(
            {
                "source_identifier": filename,
                "expected_sha256": expected,
                "historical_sha256": historical_sha,
                "historical_identity_matches": historical_sha == expected,
                "current_path": str(current.relative_to(ROOT)),
                "current_sha256": actual,
                "current_identity_matches": actual == expected,
            }
        )
    return result


def compare(
    matrix_path: Path,
    convert: Any,
    expected: Mapping[tuple[int, str], TTReference],
) -> dict[str, Any]:
    matrix_sha = sha(matrix_path)
    matrix = json.loads(matrix_path.read_text())
    source = matrix["pmo_numeric_comparisons"]
    if len(source) != 3024 or {(r["year"], r["term"]) for r in source} != {
        (year, term) for year in range(1900, 2026) for term in TERMS
    }:
        raise ValueError("All original PMO events are required")
    else:
        pass
    rows, errors = [], []
    for original in source:
        key = (original["year"], original["term"])
        try:
            value = expected[key]["jd_tt"]
            actual = convert(datetime.fromisoformat(original["actual"]))
            printed = convert(datetime.fromisoformat(original["published_moment"]))
            if any(
                isinstance(v, bool) or v is None or not math.isfinite(v)
                for v in (value, actual.jd_tt, printed.jd_tt)
            ):
                raise ValueError("Nonfinite TT reference or clock")
            else:
                pass
            delta = (actual.jd_tt - value) * 86400
            rows.append(
                {
                    "year": key[0],
                    "term": key[1],
                    "reference_jd_tt": value,
                    "actual_jd_tt": actual.jd_tt,
                    "tt_difference_seconds": delta,
                    "within_original_tt_criterion": abs(delta) <= 1.0,
                    "original_pmo_difference_seconds": original["difference_seconds"],
                    "original_pmo_numeric_pass": original[
                        "within_original_numeric_criterion"
                    ],
                    "reference_minus_printed_on_same_clock_seconds": (
                        value - printed.jd_tt
                    )
                    * 86400,
                    "actual_clock_method": actual.method,
                }
            )
        except Exception as error:
            errors.append({"year": key[0], "term": key[1], "error": str(error)})
    if sha(matrix_path) != matrix_sha:
        raise ValueError("First matrix report changed during follow-up")
    else:
        pass
    failures = [r for r in rows if not r["within_original_tt_criterion"]]
    return {
        "profile": matrix["profile"],
        "matrix_report_sha256": matrix_sha,
        "protocol_sha256": PROTOCOL_SHA256,
        "expected_count": 3024,
        "compared_count": len(rows),
        "tt_failure_count": len(failures),
        "tt_failures": failures,
        "maximum_tt_difference_seconds": max(
            (abs(r["tt_difference_seconds"]) for r in rows), default=None
        ),
        "original_pmo_numeric_failures_retained": matrix["pmo_numeric_failure_count"],
        "de440_outside_original_minute_assumption_on_same_clock": sum(
            abs(r["reference_minus_printed_on_same_clock_seconds"]) > 30 for r in rows
        ),
        "calculation_errors": errors,
        "comparisons": rows,
        "scope": "Supplied-matrix TT dynamics comparison; the actual CLI reference source is recorded separately. The same candidate civil converter is used for the time-label decomposition, so it does not independently certify that converter or adjudicate the PMO source's rounding/time convention.",
        "all_declared_tt_comparisons_passed": len(rows) == 3024
        and not failures
        and not errors,
        "new_unique_astronomical_events": 0,
        "old_minute_or_opale_failures_reclassified": False,
        "goal_complete": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--ephe-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    expected = reference()  # Source checks precede production imports.
    os.environ["SE_EPHE_PATH"] = str(args.ephe_dir.resolve())
    matrix = json.loads(args.matrix.read_text())
    for filename, checksum in matrix["runtime_manifest"].items():
        if filename.startswith("src/") and sha(ROOT / filename) != checksum:
            raise ValueError("Follow-up clock differs from the frozen first run")
        else:
            pass
    for filename, checksum in matrix["ephemeris_file_sha256"].items():
        if sha(Path(filename)) != checksum:
            raise ValueError("First run ephemeris file changed")
        else:
            pass
    from fatebridge.core.astro.time_scales import ephemeris_time

    result = compare(args.matrix, ephemeris_time, expected)
    packet = load_solar_term_reference()
    result["reference_source"] = {
        "kind": "independently_reproduced_skyfield153_de440_tt",
        "packet_sha256": REFERENCE_SHA256,
        "kernel_sha256": packet.source.kernel_sha256,
        "producer_sha256": packet.source.producer_sha256,
        "software_versions": packet.source.software_versions,
        "selected_rows": len(expected),
        "original_comparison_protocol_sha256": PROTOCOL_SHA256,
    }
    legacy = legacy_source_status()
    result["legacy_source_identities"] = legacy
    result["legacy_cross_file_pins_passed"] = all(
        row["historical_identity_matches"] for row in legacy
    )
    result["original_detached_provenance_restored"] = any(
        Path(row["source_identifier"]).name == "provenance.json"
        and (row["historical_identity_matches"] or row["current_identity_matches"])
        for row in legacy
    )
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
                    "compared_count",
                    "tt_failure_count",
                    "maximum_tt_difference_seconds",
                    "original_pmo_numeric_failures_retained",
                    "de440_outside_original_minute_assumption_on_same_clock",
                }
            },
            ensure_ascii=False,
        )
    )
    return 0 if result["all_declared_tt_comparisons_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
else:
    pass

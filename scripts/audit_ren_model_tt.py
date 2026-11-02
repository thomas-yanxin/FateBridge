"""Follow-up TT diagnosis against pre-existing independent DE440 references."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "tests/fixtures/ren_model_matrix_v1/de440-followup-protocol.json"
PROTOCOL_SHA256 = "302519e68143dcaabc5cb46cce450b95b896ee5eb7cf5e04a9be89cb4229c284"
TERMS = "小寒 大寒 立春 雨水 惊蛰 春分 清明 谷雨 立夏 小满 芒种 夏至 小暑 大暑 立秋 处暑 白露 秋分 寒露 霜降 立冬 小雪 大雪 冬至".split()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference() -> dict[tuple[int, str], dict[str, Any]]:
    if sha(PROTOCOL) != PROTOCOL_SHA256:
        raise ValueError("Follow-up protocol changed")
    protocol = json.loads(PROTOCOL.read_text())
    for filename, expected in protocol["source_sha256"].items():
        if sha(ROOT / filename) != expected:
            raise ValueError("Independent TT source changed: " + filename)
    folder = ROOT / "tests/fixtures/bazi_all_terms_v1"
    raw = json.loads((folder / "reference.json").read_text())
    if (
        raw["protocol_sha256"] != sha(folder / "protocol.json")
        or raw["collector_sha256"] != sha(folder / "collector.py.txt")
        or len(raw["rows"]) != 4872
        or raw["kernel_published_md5"] != "c9d581bfd84209dbeee8b1583939b148"
    ):
        raise ValueError("Original complete independent TT provenance missing")
    result = {(r["year"], r["name"]): r for r in raw["rows"]}
    if len(result) != 4872:
        raise ValueError("Duplicated independent TT event")
    return result


def compare(
    matrix_path: Path,
    convert: Any,
    expected: dict[tuple[int, str], dict[str, Any]],
) -> dict[str, Any]:
    matrix_sha = sha(matrix_path)
    matrix = json.loads(matrix_path.read_text())
    source = matrix["pmo_numeric_comparisons"]
    if len(source) != 3024 or {(r["year"], r["term"]) for r in source} != {
        (year, term) for year in range(1900, 2026) for term in TERMS
    }:
        raise ValueError("All original PMO events are required")
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
        "scope": "Reused independent TT dynamics comparison. Same candidate civil converter is used for the time-label decomposition, so it does not independently certify that converter or adjudicate the PMO source's rounding/time convention.",
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
    for filename, checksum in matrix["ephemeris_file_sha256"].items():
        if sha(Path(filename)) != checksum:
            raise ValueError("First run ephemeris file changed")
    from fatebridge.core.astro.time_scales import ephemeris_time

    result = compare(args.matrix, ephemeris_time, expected)
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

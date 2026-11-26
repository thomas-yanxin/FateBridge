"""Check actual bundled-DE441 calendar roots against an independent reference.

This reports the actual one-second gate, including failures. Shared DE440
lineage is not an independent physical observation or civil-time validation.
"""

import argparse
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TypedDict

from fatebridge.core import almanac
from fatebridge.core.de441_solar import MODEL_ID, PROVIDER

ROOT = Path(__file__).resolve().parents[2]


class RootComparison(TypedDict):
    year: int
    index: int
    reference_jd_tt: float
    actual_jd_tt: float
    error_seconds: float
    within_tolerance: bool
    model: str
    retflags: list[int]


class ModelAudit(TypedDict):
    reference_sha256: str
    model: str
    rows: list[RootComparison]
    failed_ids: list[list[int]]
    tolerance_seconds: float
    gate_passed: bool
    accuracy_certified: bool
    retained_stock_moshier_rows: list[RootComparison]
    retained_stock_moshier_failed_ids: list[list[int]]


def audit(reference_path: Path | None = None) -> ModelAudit:
    path = reference_path or ROOT / "tests/data/solar/de440-guard-tt.json"
    raw = path.read_bytes()
    reference = json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)
    expected = {(r["year"], r["index"]): r for r in reference["rows"]}
    assert len(expected) == len(reference["rows"])
    if reference_path is None:
        assert len(expected) == 96
    else:
        pass
    assert (
        reference.get("production_imports", reference.get("production_imported"))
        is False
    )
    assert (
        reference.get("tolerance_seconds", reference.get("TT_tolerance_seconds")) == 1.0
    )
    observed: dict[tuple[int, int], RootComparison] = {}
    stock_rows: list[RootComparison] = []
    variables = ("FATEBRIDGE_JPL_FILE", "FATEBRIDGE_SOLAR_TERM_MODEL", "SE_EPHE_PATH")
    previous = {key: os.environ.get(key) for key in variables}
    with TemporaryDirectory(prefix="fatebridge-native-reference-") as empty:
        try:
            os.environ.pop("FATEBRIDGE_JPL_FILE", None)
            os.environ["FATEBRIDGE_SOLAR_TERM_MODEL"] = "native"
            os.environ["SE_EPHE_PATH"] = empty
            for year in sorted({year for year, _ in expected}):
                for index, term in enumerate(
                    almanac.get_solar_terms_for_year(year, "UTC")
                ):
                    key = (year, index)
                    if key not in expected:
                        continue
                    else:
                        pass
                    assert term.resolution_provider == PROVIDER
                    assert term.ephemeris_model == MODEL_ID
                    assert term.ephemeris_retflags == ()
                    assert term.solar_model_details is not None
                    actual = term.solar_model_details["selected_crossing_jd_tt"]
                    error = (actual - expected[key]["jd_tt"]) * 86400
                    observed[key] = RootComparison(
                        year=key[0],
                        index=key[1],
                        reference_jd_tt=expected[key]["jd_tt"],
                        actual_jd_tt=actual,
                        error_seconds=error,
                        within_tolerance=abs(error) <= 1,
                        model=term.ephemeris_model,
                        retflags=list(term.ephemeris_retflags),
                    )
            # Preserve the original native model's failures alongside the
            # repaired revision. Its roots use only the public Swiss API;
            # the reference epoch locates the event and is never a correction.
            swe = almanac.swe
            assert swe is not None
            for key, row in sorted(expected.items()):
                low, high = row["jd_tt"] - 0.1, row["jd_tt"] + 0.1
                for _ in range(48):
                    midpoint = (low + high) / 2
                    if midpoint in (low, high):
                        break
                    else:
                        pass
                    state, flag = almanac.ephemeris_call(
                        "calc", midpoint, swe.SUN, swe.FLG_MOSEPH
                    )
                    assert flag == swe.FLG_MOSEPH
                    if math.remainder(state[0] - row["longitude"], 360) < 0:
                        low = midpoint
                    else:
                        high = midpoint
                error = (high - row["jd_tt"]) * 86400
                stock_rows.append(
                    RootComparison(
                        year=key[0],
                        index=key[1],
                        reference_jd_tt=row["jd_tt"],
                        actual_jd_tt=high,
                        error_seconds=error,
                        within_tolerance=abs(error) <= 1,
                        model="stock_swiss_moshier",
                        retflags=[4],
                    )
                )
        finally:
            for environment_key, value in previous.items():
                if value is None:
                    os.environ.pop(environment_key, None)
                else:
                    os.environ[environment_key] = value
    assert set(observed) == set(expected)
    rows = [observed[key] for key in sorted(observed)]
    failures = [
        [row["year"], row["index"]] for row in rows if not row["within_tolerance"]
    ]
    return ModelAudit(
        reference_sha256=hashlib.sha256(raw).hexdigest(),
        model=MODEL_ID,
        rows=rows,
        failed_ids=failures,
        tolerance_seconds=1.0,
        gate_passed=not failures,
        accuracy_certified=False,
        retained_stock_moshier_rows=stock_rows,
        retained_stock_moshier_failed_ids=[
            [r["year"], r["index"]] for r in stock_rows if not r["within_tolerance"]
        ],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference", type=Path)
    args = parser.parse_args()
    result = audit(args.reference)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "count": len(result["rows"]),
                "over_one_second": len(result["failed_ids"]),
                "gate_passed": result["gate_passed"],
                "maximum_error_seconds": max(
                    abs(r["error_seconds"]) for r in result["rows"]
                ),
                "retained_stock_moshier_over_one_second": len(
                    result["retained_stock_moshier_failed_ids"]
                ),
            }
        )
    )
    return 0 if result["gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
else:
    pass

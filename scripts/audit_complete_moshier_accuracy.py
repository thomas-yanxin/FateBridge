"""Check complete Moshier TT crossings against the unchanged DE440 source cohort.

The full 1784..2204 internal interval is solved, including all public input years
1800..2200. A broad-cohort screen selects additional counterexamples for exact
roots; unsolved outside rows are not an accuracy certification.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path

from fatebridge.core import analytic_solar, moshier_solar

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "tests/data/solar/vsop2013-projection/reference-14904.json.gz"


def audit(output: Path) -> dict[str, object]:
    sources = [
        Path(moshier_solar.__file__),
        Path(analytic_solar.__file__),
        ROOT / "src/fatebridge/data/astronomy/moshier-earth-1996.json",
        ROOT / "src/fatebridge/data/astronomy/analytic-solar-v1.json",
    ]
    before = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sources
    }
    raw = REFERENCE.read_bytes()
    reference = json.loads(gzip.decompress(raw))
    assert reference["production_imported"] is False
    rows = reference["rows"]
    assert len(rows) == 14904
    assert len({(r["year"], r["index"]) for r in rows}) == len(rows)
    internal = [r for r in rows if 1784 <= r["year"] <= 2204]
    assert len(internal) == 10104
    assert sum(1800 <= r["year"] <= 2200 for r in internal) == 9624
    screen = []
    for r in rows:
        angle = math.remainder(
            moshier_solar.solar_longitude(r["jd_tt"]) - r["longitude"], 360
        )
        screen.append(
            {
                "year": r["year"],
                "index": r["index"],
                "longitude_residual_arcseconds": angle * 3600,
                "ranking_estimate_seconds_at_one_degree_per_day": -angle * 86400,
            }
        )
    ranked = {
        (r["year"], r["index"]): abs(
            r["ranking_estimate_seconds_at_one_degree_per_day"]
        )
        for r in screen
    }
    selected = [
        r
        for r in rows
        if 1784 <= r["year"] <= 2204 or ranked[(r["year"], r["index"])] >= 0.9
    ]
    selected.sort(key=lambda r: ranked[(r["year"], r["index"])], reverse=True)
    exact = []
    for number, r in enumerate(selected, 1):

        def residual(epoch: float) -> float:
            return math.remainder(
                moshier_solar.solar_longitude(epoch) - r["longitude"], 360
            )

        low, high = r["jd_tt"] - 60 / 86400, r["jd_tt"] + 60 / 86400
        assert residual(low) < 0 <= residual(high)
        for _ in range(40):
            mid = (low + high) / 2
            if mid in (low, high):
                break
            if residual(mid) < 0:
                low = mid
            else:
                high = mid
        assert residual(low) < 0 <= residual(high)
        error = (high - r["jd_tt"]) * 86400
        exact.append(
            {
                "year": r["year"],
                "index": r["index"],
                "reference_jd_tt": r["jd_tt"],
                "actual_jd_tt": high,
                "error_seconds": error,
                "bracket_seconds": (high - low) * 86400,
                "within_one_second": abs(error) <= 1,
                "internal_scope": 1784 <= r["year"] <= 2204,
                "public_input_scope": 1800 <= r["year"] <= 2200,
            }
        )
        if number % 500 == 0:
            print(
                json.dumps(
                    {"exact_completed": number, "exact_selected": len(selected)}
                ),
                flush=True,
            )
    after = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sources
    }
    scoped = [r for r in exact if r["internal_scope"]]
    public = [r for r in exact if r["public_input_scope"]]
    failures = [r for r in exact if not r["within_one_second"]]
    summary = {
        "reference_rows": len(rows),
        "screened_rows": len(screen),
        "exact_internal_rows": len(scoped),
        "exact_public_rows": len(public),
        "exact_outside_rows": len(exact) - len(scoped),
        "internal_over_one_second": sum(not r["within_one_second"] for r in scoped),
        "public_over_one_second": sum(not r["within_one_second"] for r in public),
        "exact_outside_over_one_second": sum(not r["internal_scope"] for r in failures),
        "internal_max_abs_seconds": max(abs(r["error_seconds"]) for r in scoped),
        "public_max_abs_seconds": max(abs(r["error_seconds"]) for r in public),
        "source_changed_during_audit": before != after,
        "tolerance_seconds": 1.0,
        "accuracy_certified": False,
    }
    result = {
        "summary": summary,
        "model": moshier_solar.model_details(),
        "reference_path": str(REFERENCE.relative_to(ROOT)),
        "reference_original_bytes_sha256": hashlib.sha256(raw).hexdigest(),
        "source_before": before,
        "source_after": after,
        "source_cohort_regenerated": False,
        "independent_physical_observations": False,
        "broader_scope_screen_is_acceptance": False,
        "screen": screen,
        "exact_rows": exact,
        "failed_exact_rows": failures,
    }
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(summary), flush=True)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    summary = audit(parser.parse_args().output)
    return (
        1
        if summary["source_changed_during_audit"]
        or summary["internal_over_one_second"]
        or summary["exact_outside_over_one_second"]
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())

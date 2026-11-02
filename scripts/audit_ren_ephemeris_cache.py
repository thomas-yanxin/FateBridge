"""Reproduce stale solar boundaries across a real data-path change.

The oracle here is a freshly computed result under the same selected path,
not an independent astronomical crossing. No source label or tolerance changes.
Run in a separate process: the selected Swiss path is temporarily changed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
IMPLEMENTATION = (
    "src/fatebridge/core/almanac.py",
    "src/fatebridge/core/solar_term_runtime.py",
    "src/fatebridge/core/ephemeris_runtime.py",
    "src/fatebridge/core/astro_models.py",
    "src/fatebridge/core/ephemeris_installation.py",
    "src/fatebridge/core/metaphysics/ren_calendar.py",
    "scripts/audit_ren_ephemeris_cache.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(year: int = 2026) -> dict[str, Any]:
    before = {name: sha(ROOT / name) for name in IMPLEMENTATION}
    from fatebridge.core import almanac
    from fatebridge.core.ephemeris_runtime import (
        configure_ephemeris_path,
        configured_ephemeris_path,
        ephemeris_call,
        ephemeris_model_from_retflag,
        swe,
    )

    if swe is None:
        raise RuntimeError("The cache-environment audit requires Swiss Ephemeris")
    selected = configured_ephemeris_path()
    clear_year_cache = getattr(almanac.get_solar_terms_for_year, "cache_clear")
    override = os.environ.pop("SE_EPHE_PATH", None)
    try:
        with TemporaryDirectory(prefix="fatebridge-solar-cache-audit-") as empty:
            configure_ephemeris_path(empty)
            clear_year_cache()
            first = almanac.get_solar_terms_for_year(year, "UTC")
            same_environment_reused = (
                almanac.get_solar_terms_for_year(year, "UTC") is first
            )
            _, empty_flags = ephemeris_call("calc", 2461119.5, swe.SUN, swe.FLG_SWIEPH)
            empty_model = ephemeris_model_from_retflag(empty_flags)
            configure_ephemeris_path(selected if selected is not None else "")
            switched = almanac.get_solar_terms_for_year(year, "UTC")
            _, selected_flags = ephemeris_call(
                "calc", 2461119.5, swe.SUN, swe.FLG_SWIEPH
            )
            selected_model = ephemeris_model_from_retflag(selected_flags)
            # A manual clear is used only for this fresh-result comparison.
            # The operation being tested above must work without that clear.
            clear_year_cache()
            fresh = almanac.get_solar_terms_for_year(year, "UTC")
            rows = []
            for old, cached, new in zip(first, switched, fresh):
                rows.append(
                    dict(
                        name=old.name,
                        empty_path_moment=old.moment.isoformat(),
                        switched_path_moment=cached.moment.isoformat(),
                        fresh_selected_path_moment=new.moment.isoformat(),
                        difference_between_models_seconds=(
                            old.moment - new.moment
                        ).total_seconds(),
                        cached_minus_fresh_seconds=(
                            cached.moment - new.moment
                        ).total_seconds(),
                        provider=cached.resolution_provider,
                        empty_path_recorded_model=getattr(old, "ephemeris_model", None),
                        switched_path_recorded_model=getattr(
                            cached, "ephemeris_model", None
                        ),
                        switched_path_retflags=list(
                            getattr(cached, "ephemeris_retflags", ())
                        ),
                        cached_matches_fresh=cached.moment == new.moment,
                    )
                )
            checks = {
                "same_environment_reuses_year": same_environment_reused,
                "path_change_returns_new_year": switched is not first,
                "all_24_switched_boundaries_equal_fresh": len(rows) == 24
                and all(row["cached_matches_fresh"] for row in rows),
                "actual_model_recorded": all(
                    getattr(t, "ephemeris_model", None) == selected_model
                    for t in switched
                ),
            }
    finally:
        if override is not None:
            os.environ["SE_EPHE_PATH"] = override
        configure_ephemeris_path(selected if selected is not None else "")
        clear_year_cache()
    unchanged = before == {name: sha(ROOT / name) for name in IMPLEMENTATION}
    return {
        "audit_id": "ren_solar_ephemeris_cache_isolation_v1",
        "year": year,
        "criterion": "A path switch must not return the prior cached year; all 24 returned boundaries must equal a fresh calculation under the selected path.",
        "empty_path_probed_model": empty_model,
        "selected_path_probed_model": selected_model,
        "checks": checks,
        "comparisons": rows,
        "implementation_sha256": before,
        "implementation_unchanged_during_audit": unchanged,
        "cache_isolation_checks_passed": unchanged and all(checks.values()),
        "independent_astronomical_accuracy_certified": False,
        "classical_acceptance_passed": False,
        "goal_complete": False,
        "scope": "Real numerical-environment regression only. Fresh same-engine values are not independent astronomical or historical labels. This does not replace PMO, HKO, or JPL comparisons.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.year)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report["checks"], ensure_ascii=False))
    return 0 if report["cache_isolation_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Compare all4800 published days and same-dependency reference metadata.

Published-date disagreements remain failures. Metadata correctness is a separate
engineering check and never turns a source disagreement into a passing date.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from scripts.astronomy.build_hko_term_dates import build, encoded

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/ren_hko_dates_v1"
FREEZE_SHA = "3925683153facf0518fa48cef8943ed19b15ee9802e590458a06953d21fe775c"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def reference(folder: Path = CORPUS) -> dict[str, Any]:
    names = {"catalogue.json", "source-manifest.json", "protocol.json"}
    if sha(folder / "freeze.json") != FREEZE_SHA:
        raise ValueError("Frozen HKO dates manifest changed")
    freeze = json.loads((folder / "freeze.json").read_text())
    if set(freeze["files"]) != names or {p.name for p in folder.iterdir()} != names | {
        "freeze.json"
    }:
        raise ValueError("Frozen HKO dates inventory changed")
    if any(sha(folder / n) != h for n, h in freeze["files"].items()):
        raise ValueError("Frozen HKO dates source changed")
    if encoded(build()) != (folder / "catalogue.json").read_bytes():
        raise ValueError(
            "Complete original200 HKO text sources do not reproduce catalogue"
        )
    data: dict[str, Any] = json.loads((folder / "catalogue.json").read_text())
    if len(data["terms"]) != 4800:
        raise ValueError("Complete4800 HKO date denominator required")
    return data


def audit(profile: str, ephe_dir: Path) -> dict[str, Any]:
    if profile not in {
        "auto_empty",
        "auto_swiss",
        "native_swiss_control",
        "analytic_empty",
    }:
        raise ValueError("Unknown frozen profile")
    os.environ["SE_EPHE_PATH"] = str(ephe_dir.resolve())
    os.environ.pop("FATEBRIDGE_JPL_FILE", None)
    os.environ["FATEBRIDGE_SOLAR_TERM_MODEL"] = (
        "native"
        if profile == "native_swiss_control"
        else "analytic" if profile == "analytic_empty" else "auto"
    )
    data = reference()
    paths = [
        p
        for p in (ROOT / "src/fatebridge").rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    ] + [Path(__file__).resolve(), ROOT / "scripts/astronomy/build_hko_term_dates.py"]
    before = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    from fatebridge.core.almanac import get_solar_terms_for_year
    from fatebridge.core.metaphysics.hko_term_dates import published_date_reference
    from fatebridge.core.output_ren_term_dates import RenPublishedDateReference

    rows = []
    errors: list[dict[str, Any]] = []
    metadata_errors = []
    mismatches = []
    for year in range(1901, 2101):
        try:
            terms = get_solar_terms_for_year(year, "Etc/GMT-8")
        except Exception as e:
            errors.extend(
                dict(year=year, term=n.split(":", 1)[1], error=repr(e))
                for n in data["terms"]
                if n.startswith(str(year) + ":")
            )
            continue
        if len(terms) != 24 or {t.name for t in terms} != {
            n.split(":", 1)[1] for n in data["terms"] if n.startswith(str(year) + ":")
        }:
            raise ValueError("Solver did not return all24 original term names")
        for term in terms:
            source = data["terms"][f"{year}:{term.name}"]
            ref = published_date_reference(term.name, term.moment)
            RenPublishedDateReference.model_validate(ref)
            actual_day = (
                term.moment.astimezone(timezone(timedelta(hours=8))).date().isoformat()
            )
            equal = actual_day == source["published_date"]
            ok = (
                ref["published_date"] == source["published_date"]
                and ref["computed_hko_date"] == actual_day
                and ref["dates_equal"] is equal
                and ref["status"] == ("date_match" if equal else "date_mismatch")
                and ref["source_url"] == source["source_url"]
                and ref["source_sha256"] == source["source_sha256"]
                and ref["instant_accuracy_certified"] is False
            )
            row = dict(
                year=year,
                term=term.name,
                computed_moment=term.moment.isoformat(),
                published_date=source["published_date"],
                source_date_equal=equal,
                reference_metadata_correct=ok,
                provider=term.resolution_provider,
                ephemeris_model=term.ephemeris_model,
                reference=ref,
            )
            rows.append(row)
            if not ok:
                metadata_errors.append(row)
            if not equal:
                mismatches.append(row)
    unchanged = before == {str(p.relative_to(ROOT)): sha(p) for p in paths}
    return dict(
        profile=profile,
        ephe_directory=str(ephe_dir.resolve()),
        published_events=4800,
        evaluated_events=len(rows),
        source_date_matches=sum(r["source_date_equal"] for r in rows),
        source_date_mismatches=mismatches,
        calculation_errors=errors,
        reference_metadata_errors=metadata_errors,
        all_published_dates_match=not mismatches and not errors and len(rows) == 4800,
        reference_metadata_checks_passed=not errors
        and not metadata_errors
        and len(rows) == 4800,
        rows=rows,
        source_manifest=before,
        implementation_unchanged=unchanged,
        new_independent_physical_events=0,
        new_empirical_events=0,
        full_supported_calendar_domain_certified=False,
        full_classical_conformance=False,
        goal_complete=False,
    )


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--profile", required=True)
    p.add_argument("--ephe-dir", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    if a.output.exists():
        raise ValueError("Refusing to overwrite HKO audit")
    result = audit(a.profile, a.ephe_dir)
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in ["rows", "source_manifest", "source_date_mismatches"]
            },
            ensure_ascii=False,
        )
    )
    print("source_date_mismatch_count", len(result["source_date_mismatches"]))
    raise SystemExit(
        0
        if result["all_published_dates_match"]
        and result["reference_metadata_checks_passed"]
        and result["implementation_unchanged"]
        and (not result["preservation"] or result["preservation"]["passed"])
        else 1
    )


if __name__ == "__main__":
    main()

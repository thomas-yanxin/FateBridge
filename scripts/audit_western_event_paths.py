"""Audit all seven-planet events against frozen JPL grids; retain every failure."""

import argparse
import hashlib
import json
import zipfile
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from fatebridge.core.astro.ephemeris import _swisseph_planet_state
from fatebridge.core.astro.geometry import angular_separation_fraction
from fatebridge.core.astro.time_scales import ut1_from_tt
from fatebridge.core.horary_events import native_planetary_events

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"


def key(event):
    return (
        event["kind"],
        tuple(event["bodies"]),
        event.get("ray_degrees"),
        event["direction"],
    )


def audit():
    protocol_path = FIXTURES / "western-event-paths-protocol.json"
    reference_path = FIXTURES / "western-event-paths-horizons.json"
    plan = json.loads(protocol_path.read_text())
    reference = json.loads(reference_path.read_text())
    assert (
        reference["protocol_sha256"]
        == hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    )
    with zipfile.ZipFile(FIXTURES / "western-event-paths-raw.zip") as archive:
        for c in reference["cases"]:
            for receipt in c["receipts"].values():
                assert (
                    hashlib.sha256(archive.read(receipt["raw_file"])).hexdigest()
                    == receipt["response_sha256"]
                )
    rows, initial, cases = [], [], []
    longitude_max = 0
    position_count = 0
    for c in reference["cases"]:
        start = c["start_julian_day_tt"]
        native = native_planetary_events(
            SimpleNamespace(julian_day_tt=start + 10.5, zodiac_type="Tropic")
        )
        assert native["status"] == "computed", native
        selected = [
            e for e in native["events"] if start < e["julian_day_tt"] <= start + 21
        ]
        assert Counter(key(e) for e in selected) == Counter(
            key(e) for e in c["expected"]
        )
        for label, expectations, target in (
            ("initial_three_hour", c["expected"], initial),
            ("refined_five_point", c["refined_expected"], rows),
        ):
            for e in expectations:
                same = [s for s in selected if key(s) == key(e)]
                closest = min(
                    same, key=lambda s: abs(s["julian_day_tt"] - e["julian_day_tt"])
                )
                residual = (closest["julian_day_tt"] - e["julian_day_tt"]) * 86400
                tolerance = (
                    plan["station_tolerance_seconds"]
                    if e["kind"] == "station"
                    else plan["contact_and_ingress_tolerance_seconds"]
                )
                target.append(
                    {
                        "case_id": c["case_id"],
                        "kind": e["kind"],
                        "bodies": e["bodies"],
                        "aspect": e.get("aspect"),
                        "reference_julian_day_tt": e["julian_day_tt"],
                        "native_julian_day_tt": closest["julian_day_tt"],
                        "signed_residual_seconds": residual,
                        "tolerance_seconds": tolerance,
                        "passed": abs(residual) <= tolerance,
                        "reference_method": label,
                    }
                )
        for planet, samples in c["samples"].items():
            for tt, longitude, _ in samples:
                state, model = _swisseph_planet_state(
                    planet, ut1_from_tt(tt), julian_day_tt=tt
                )
                error = (
                    float(angular_separation_fraction(longitude, state["longitude"]))
                    * 3600
                )
                longitude_max = max(longitude_max, error)
                position_count += 1
        cases.append(
            {
                "case_id": c["case_id"],
                "event_counts": dict(Counter(e["kind"] for e in selected)),
                "physical_source": native["physical_ephemeris_source"],
                "frame": native["longitude_frame"],
            }
        )
    return {
        "protocol_sha256": reference["protocol_sha256"],
        "reference_sha256": hashlib.sha256(reference_path.read_bytes()).hexdigest(),
        "cases": cases,
        "position_count": position_count,
        "maximum_longitude_residual_arcseconds": longitude_max,
        "longitude_tolerance_arcseconds": plan["longitude_tolerance_arcseconds"],
        "rows": rows,
        "initial_rows_retained": initial,
        "all_event_identities_and_counts_match": True,
        "passed_event_count": sum(r["passed"] for r in rows),
        "event_count": len(rows),
        "all_cases_passed": all(r["passed"] for r in rows)
        and longitude_max <= plan["longitude_tolerance_arcseconds"],
        "remaining_failures": [r for r in rows if not r["passed"]],
        "scope": "Two frozen 21-day windows, all seven traditional planets, same observations reused for station-reference refinement. Initial station failures and revised rows retained. JPL apparent IAU76/80+EOP and default Swiss apparent frame are not identical: attribution of the Saturn station discrepancy awaits independent common-frame validation; no coordinate correction was fitted. No historical-original, complete-interval or outcome certification.",
        "frame_source": "https://www.astro.com/swisseph/swephprg.htm",
        "tolerances_relaxed": False,
        "full_original_text_acceptance": False,
        "authority_certified": False,
        "source_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [
                ROOT / "src/fatebridge/core/horary_events.py",
                ROOT / "src/fatebridge/core/horary_event_paths.py",
            ]
        },
    }


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = audit()
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "event_count",
                    "passed_event_count",
                    "all_cases_passed",
                    "maximum_longitude_residual_arcseconds",
                    "remaining_failures",
                )
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["all_cases_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

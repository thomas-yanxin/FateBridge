"""Reproduce rule-arithmetic references in a separate PyJHora==4.8.7 env.

No FateBridge imports. Supply native Moon coordinates explicitly: this checks
period arithmetic, not independent astronomy, classical completeness or events.
The installed reference module's hash is saved with the output. No third-party
implementation is copied into production.
"""

import argparse
import hashlib
import importlib.metadata
import math
from datetime import datetime, timedelta
from pathlib import Path


def main():
    import json

    from jhora.horoscope.dhasa.graha import vimsottari as reference

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("seeds", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    version = importlib.metadata.version("PyJHora")
    if version != "4.8.7":
        raise ValueError(f"Reference is pinned to 4.8.7, found {version}")
    seeds = json.loads(args.seeds.read_text())
    origin = datetime.fromisoformat(seeds["birth_utc"])
    # Arithmetic day anchor only: this does not claim a UTC->TT conversion.
    anchor = 2451545.0
    names = [
        "Sun",
        "Moon",
        "Mars",
        "Mercury",
        "Jupiter",
        "Venus",
        "Saturn",
        "Rahu",
        "Ketu",
    ]
    original_getter = reference.charts.get_chart_element_longitude
    original_year = reference.year_duration
    rows = []
    try:
        for basis, days in {
            "sidereal_365_25636": 365.25636,
            "tropical_365_2425": 365.2425,
            "savana_360": 360.0,
        }.items():
            reference.year_duration = days
            for sample in seeds["grid"]:
                reference.charts.get_chart_element_longitude = lambda *a, value=sample[
                    "longitude"
                ], **kw: value
                jd = anchor + sample["offset_seconds"] / 86400.0
                majors = reference.vimsottari_mahadasa(jd, None)
                for target in seeds["targets"]:
                    instant = datetime.fromisoformat(target)
                    target_jd = anchor + (instant - origin).total_seconds() / 86400.0
                    cycle = math.floor(
                        (target_jd - next(iter(majors.values()))) / (120 * days)
                    )
                    active = {
                        lord: start + cycle * 120 * days
                        for lord, start in majors.items()
                    }
                    lord = max(
                        (p for p in active if active[p] <= target_jd), key=active.get
                    )
                    subs = reference._vimsottari_bhukti(lord, active[lord])
                    sub = max((p for p in subs if subs[p] <= target_jd), key=subs.get)

                    def label(value):
                        return (origin + timedelta(days=value - anchor)).isoformat()

                    major_end = active[lord] + reference.vimsottari_dict[lord] * days
                    sub_end = (
                        subs[sub]
                        + reference.vimsottari_dict[lord]
                        * reference.vimsottari_dict[sub]
                        / 120
                        * days
                    )
                    rows.append(
                        {
                            "year_basis": basis,
                            "offset_seconds": sample["offset_seconds"],
                            "moon_longitude": sample["longitude"],
                            "analysis": target,
                            "major": names[lord],
                            "sub": names[sub],
                            "major_start": label(active[lord]),
                            "major_end": label(major_end),
                            "sub_start": label(subs[sub]),
                            "sub_end": label(sub_end),
                        }
                    )
    finally:
        reference.charts.get_chart_element_longitude = original_getter
        reference.year_duration = original_year
    result = {
        "reference": "PyJHora",
        "version": version,
        "reference_url": "https://pypi.org/project/PyJHora/4.8.7/",
        "module_sha256": hashlib.sha256(
            Path(reference.__file__).read_bytes()
        ).hexdigest(),
        "seeds_sha256": hashlib.sha256(args.seeds.read_bytes()).hexdigest(),
        "birth_utc": seeds["birth_utc"],
        "boundary_tolerance_seconds": 1.0,
        "scope": "controlled supplied-Moon rule arithmetic, 3 declared year lengths and explicit 120-year cycle composition; native Moon shared, no independent sky or event validation",
        "cases": rows,
    }
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {len(rows)} reference cases")


if __name__ == "__main__":
    main()

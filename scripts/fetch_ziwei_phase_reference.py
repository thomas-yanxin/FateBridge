"""Explicitly refresh NASA raw phase tables; never imports the tested engine."""

import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

TARGET = Path(__file__).resolve().parents[1] / "tests/fixtures/ziwei_independent"


def main() -> None:
    sources = []
    for century in (1801, 1901):
        url = f"https://eclipse.gsfc.nasa.gov/phase/phases{century}.html"
        with urlopen(url, timeout=30) as response:
            data = response.read()
        path = TARGET / f"nasa-phases{century}.html"
        path.write_bytes(data)
        sources.append(
            dict(path=path.name, url=url, sha256=hashlib.sha256(data).hexdigest())
        )
    manifest = {
        "version": "ziwei_nasa_phase_reference_v1",
        "sources": sources,
        "coverage_start": "1900-01-31",
        "coverage_end": "1900-12-31",
        "time_standard_as_published": "Universal Time (UT)",
        "civil_day_offset_hours": 8,
        "checked_field": "lunar_day_only",
        "limits": [
            "Astronomical new moons verify lunar day boundaries, not month numbering, leap months or lunar years",
            "Fixed UTC+8 civil day; historical local civil times and solar-time corrections are outside this comparison",
            "Source times have minute precision; distance to local midnight is reported",
        ],
    }
    (TARGET / "phase_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("Frozen two raw NASA phase tables for the 1900 lunar-day gap")


if __name__ == "__main__":
    main()

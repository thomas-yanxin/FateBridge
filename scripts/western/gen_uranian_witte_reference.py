"""Extract factual reference rows from the publisher's 2026 ephemeris.

Requires pdftotext and the original PDF supplied with --pdf. No FateBridge or
Swiss Ephemeris calculation is used to generate expected answers. Review new
source bytes and extracted glyph mappings before accepting a changed fixture.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

SOURCE = "https://a182559.uranus.1blu.de/data/public/4b5ecc.php?dl=true"
PAGE_URL = "https://witte-verlag.com/"
# Column identities checked visually against the publisher's rendered headers.
PHYSICAL = [
    "Sun",
    "Moon",
    "Mercury",
    "Venus",
    "Mars",
    "Jupiter",
    "Saturn",
    "Uranus",
    "Neptune",
    "Pluto",
]
HYPOTHETICAL = [
    "Cupido",
    "Hades",
    "Zeus",
    "Kronos",
    "Apollon",
    "Admetos",
    "Vulkanus",
    "Poseidon",
]
ROOT = Path(__file__).resolve().parents[2]


def extract(path: Path) -> dict:
    rows = []
    for page in (1, 7, 12):
        text = subprocess.check_output(
            ["pdftotext", "-layout", "-f", str(page), "-l", str(page), str(path), "-"],
            text=True,
        )
        # This font maps zodiac signs to U+00CF..U+00DA. First-of-month
        # entries print the sign explicitly; subsequent rows may omit it.
        first_days = [
            line for line in text.splitlines() if re.match(r"\s*[A-Z][a-z]\s+1\s", line)
        ]
        if len(first_days) != 2:
            raise ValueError(f"Unexpected first-day tables on page {page}")
        tables = [
            re.findall(r"(\d+)ý([Ï-Ú])ý(\d+)(?:\s+(\d+))?[ïñ]", line)
            for line in first_days
        ]
        if [len(table) for table in tables] != [12, 8]:
            raise ValueError(f"Unrecognised PDF glyph layout on page {page}")
        columns = [*tables[0][:10], tables[0][11], *tables[1]]
        positions = {}
        for name, (degree, glyph, minute, second) in zip(
            [*PHYSICAL, "North Node", *HYPOTHETICAL], columns
        ):
            positions[name] = {
                "sign_index": ord(glyph) - ord("Ï"),
                "degree": int(degree),
                "minute": int(minute),
                "second": int(second or 0),
                "tolerance_arcseconds": 2.0 if name in ("Sun", "Moon") else 60.0,
            }
        rows.append(
            {
                "utc": f"2026-{page:02}-01T00:00:00+00:00",
                "pdf_page": page,
                "positions": positions,
            }
        )
    return {
        "source_url": SOURCE,
        "publisher_page": PAGE_URL,
        "publisher": "Witte-Verlag Hamburg / AstrologicPC Terra",
        "edition": "2026 ephemeris, copyright 2026-08-14",
        "source_pdf_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "method": "Independent extraction of published first-of-month rows; glyph/column identities checked visually",
        "time_scale": "Publisher 00:00 UT (~UTC); no subsecond Earth-rotation claim",
        "reference_models": "Publisher states DE442/LE442 for physical bodies; Shudde/Neely elements for hypothetical factors",
        "scope": "Positions and factor identities only; no original-text interpretation or real-world outcome validation",
        "tolerance_policy": "2 arcseconds for second-resolution Sun/Moon, 1 printed arcminute for minute-resolution columns; fixed before comparison",
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "tests/fixtures/uranian-witte-2026.json"
    )
    args = parser.parse_args()
    rendered = json.dumps(extract(args.pdf), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not args.output.exists() or args.output.read_text() != rendered:
            raise SystemExit(
                "Publisher source or extracted fixture changed; manual review required"
            )
        print("Publisher source hash and extracted factual rows match")
    else:
        args.output.write_text(rendered)


if __name__ == "__main__":
    main()

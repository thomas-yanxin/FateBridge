"""Extract explicit additional planet assignments without copying line readings.

The immutable glyph-only catalogue remains unchanged. This bounded grammar is
not a claim to have interpreted every rule in the384line source prose.
"""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "src/fatebridge/data/human_design/additional-polarities-2001.json"
PLANETS = (
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
    "Earth",
)


def extract(pdf: Path) -> dict:
    legacy_path = ROOT / "src/fatebridge/data/human_design/rave-2001-depth.json"
    legacy = json.loads(legacy_path.read_text())
    source_sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    if source_sha != legacy["source"]["pdf_sha256"]:
        raise ValueError("Different source PDF: edition review required")
    pages = subprocess.check_output(
        ["pdftotext", "-layout", str(pdf), "-"], text=True
    ).split("\f")
    pattern = re.compile(
        r"\b(" + "|".join(PLANETS) + r") is also (exalted|in detriment)\."
    )
    facts = []
    scanned = 0
    for gate in range(1, 65):
        page_index = 6 + 2 * (gate - 1)
        text = pages[page_index]
        heads = list(re.finditer(r"(?m)^([1-6])\s", text))
        if [int(m[1]) for m in heads] != [6, 5, 4, 3, 2, 1]:
            raise ValueError(f"Incomplete layout line headings at gate{gate}")
        for index, head in enumerate(heads):
            line = int(head[1])
            block = text[
                head.start() : (
                    heads[index + 1].start() if index + 1 < len(heads) else len(text)
                )
            ]
            flat = " ".join(block.split())
            scanned += 1
            for match in pattern.finditer(flat):
                role = "exaltation" if match[2] == "exalted" else "detriment"
                primary = legacy["gates"][gate - 1]["line_polarities"][line - 1][
                    role + "_planet"
                ]
                if primary is None or primary == match[1]:
                    raise ValueError(
                        "Additional planet has no distinct original marker"
                    )
                facts.append(
                    {
                        "fact_id": f"{gate}.{line}.{role}.{match[1]}",
                        "gate": gate,
                        "line": line,
                        "role": role,
                        "primary_marker_planet": primary,
                        "additional_planet": match[1],
                        "source_pdf_page_one_based": page_index + 1,
                        "source_clause_sha256": hashlib.sha256(
                            match[0].encode()
                        ).hexdigest(),
                    }
                )
    facts.sort(key=lambda r: (r["gate"], r["line"], r["role"], r["additional_planet"]))
    return {
        "source_catalog_id": "human_design_2001_explicit_additional_planets_v1",
        "source": {
            "title": legacy["source"]["title"],
            "author": legacy["source"]["author"],
            "edition_year": 2001,
            "url": legacy["source"]["url"],
            "pdf_sha256": source_sha,
            "glyph_catalog_sha256": hashlib.sha256(
                legacy_path.read_bytes()
            ).hexdigest(),
        },
        "scanned_line_count": scanned,
        "facts": facts,
        "full_line_meanings_accepted": False,
        "publisher_master_authenticated": False,
        "scope": "Only explicitly named additional planet-role clauses in the fixed2001copy. Primary printed glyphs remain unchanged;2extra facts are not a complete384line semantic interpretation, publisher erratum or empirical validation.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    value = json.dumps(extract(args.pdf), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not TARGET.is_file() or TARGET.read_text() != value:
            raise SystemExit("Additional-polarity source facts drifted")
    else:
        TARGET.write_text(value)


if __name__ == "__main__":
    main()

"""Extract exact printed arcs and observed labels without importing the engine.

The original numeric/depth catalogues and official cohorts are never rewritten.
Only numerical facts and short observed labels are emitted, not line prose.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from html.parser import HTMLParser
from pathlib import Path

from build_human_design_reference import DEGREE, RANGE, SIGNS

ROOT = Path(__file__).resolve().parents[1]
DICTIONARY_URL = "https://jovianarchive.com/pages/human-design-dictionary"


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, value):
        self.parts.append(value)


def arcseconds(parts):
    degree, minute, second = map(int, parts)
    return degree * 3600 + minute * 60 + second


def build(pdf: Path, dictionary: Path, cohorts: list[Path]) -> dict:
    pages = subprocess.check_output(
        ["pdftotext", "-raw", str(pdf), "-"], text=True
    ).split("\f")
    layout = subprocess.check_output(
        ["pdftotext", "-layout", str(pdf), "-"], text=True
    ).split("\f")
    lines = []
    for gate in range(1, 65):
        index = 5 + (gate - 1) * 2
        pos = re.search(
            DEGREE + r"\s*(\S)\s*-\s*" + DEGREE + r"\s*(\S)",
            layout[index].split("Astrologic Position")[1],
        )
        if pos is None:
            raise ValueError(f"Missing gate {gate} position")
        start = SIGNS[pos[4]] * 108000 + arcseconds(pos.group(1, 2, 3))
        ranges = list(RANGE.finditer(pages[index + 1]))
        if len(ranges) != 6:
            raise ValueError(f"Expected six line ranges for gate {gate}")
        for line, match in enumerate(reversed(ranges), 1):
            endpoints = [
                (start + (arcseconds(match.group(*group)) - start % 108000) % 108000)
                % 1296000
                for group in ((1, 2, 3), (4, 5, 6))
            ]
            lines.append(
                {
                    "gate": gate,
                    "line": line,
                    "start_arcseconds": endpoints[0],
                    "end_arcseconds": endpoints[1],
                    "pdf_page_one_based": index + 2,
                }
            )
    page = Text()
    page.feed(dictionary.read_text())
    text = " ".join(" ".join(page.parts).split())
    foundation = text.split("Every Line has a binary structure.")[-1].split(
        "Profile Transitions"
    )[0]
    if not all(v in foundation for v in ("56’15”", "48’45”", "07’30”")):
        raise ValueError("Explicit dictionary line arcs absent")
    if "they are always activating the same line" not in text:
        raise ValueError("Paired Sun/Earth line rule absent")
    observations, sources = [], []
    angle_ids = {
        "Right Angle": "right",
        "Left Angle": "left",
        "Juxtaposition": "juxtaposition",
    }
    for cohort in cohorts:
        source = json.loads(cohort.read_text())
        cohort_hash = hashlib.sha256(cohort.read_bytes()).hexdigest()
        sources.append(
            {"fixture": cohort.name, "sha256": cohort_hash, **source["source"]}
        )
        for case in source["cases"]:
            match = re.fullmatch(
                r"(Right Angle|Left Angle|Juxtaposition) Cross of (.+?)\s+"
                r"\((\d+)/(\d+) \| (\d+)/(\d+)\)",
                case["properties"]["Incarnation Cross"],
            )
            if match is None:
                raise ValueError("Unknown frozen cross label format")
            observations.append(
                {
                    "case_id": case["id"],
                    "cohort_sha256": cohort_hash,
                    "pdf_sha256": case["pdf_sha256"],
                    "angle": angle_ids[match[1]],
                    "gates": list(map(int, match.groups()[2:])),
                    "display_name": match[2],
                }
            )
    if len({r["case_id"] for r in observations}) != len(observations):
        raise ValueError("Duplicate observation")
    return {
        "method_id": "human_design_source_variant_facts_v1",
        "printed_source": {
            "author": "Ra Uru Hu",
            "publisher": "Jovian Archive Corporation",
            "edition": "2001 English",
            "url": "https://www.myhumandesign.be/downloads/Rave-I%27Ching.pdf",
            "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
        },
        "dictionary_source": {
            "publisher": "Jovian Archive",
            "url": DICTIONARY_URL,
            "html_sha256": hashlib.sha256(dictionary.read_bytes()).hexdigest(),
            "retrieved_date": "2026-10-22",
            "line_arcseconds": 3375,
            "foundation_arcseconds": 2925,
            "transition_arcseconds": 450,
            "sun_earth_same_line": True,
        },
        "printed_line_arcs": lines,
        "observed_cross_label_sources": sources,
        "observed_cross_labels": observations,
        "scope": "Exact printed angular facts and finite observed official labels; no aliases, erratum, universal modern name catalogue, full line prose or predictive certification.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--dictionary-html", type=Path, required=True)
    parser.add_argument("--cohort", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(
        json.dumps(
            build(args.pdf, args.dictionary_html, args.cohort),
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()

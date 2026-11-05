"""Extract factual identifiers and planetary polarities from the 2001 source.

No calculation engine imports, no line prose or commentary reproduction.
Gate, channel and cross names are source identifiers, not generated readings.
The original numerical fixture is checked and never rewritten by this script.
"""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GLYPHS = dict(
    zip(
        "ÀÁÂÃÄÅÆÇÈÉÍ",
        (
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
        ),
    )
)


def extract(pdf: Path) -> dict:
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    numeric = json.loads(
        (ROOT / "src/fatebridge/data/human_design/rave-2001-reference.json").read_text()
    )
    if digest != numeric["source"]["pdf_sha256"]:
        raise ValueError(
            "PDF differs from the independently frozen 2001 source; review the new edition first"
        )
    pages = subprocess.check_output(
        ["pdftotext", "-raw", str(pdf), "-"], text=True
    ).split("\f")
    rows = []
    for gate in range(1, 65):
        index = 5 + (gate - 1) * 2
        header = pages[index].split("Astrologic Position")[0]
        cross = re.search(
            r"THE RIGHT ANGLE CROSS OF\s+(.+?)THE JUXTAPOSITION CROSS OF\s+(.+?)THE LEFT ANGLE CROSS OF\s+(.+?)\n\d{1,2}\nTHE GATE",
            header,
            re.S,
        )
        if cross is None:
            raise ValueError(f"Missing three cross identifiers for gate {gate}")
        name = re.search(r"THE GATE OF\s+(.+?)\nChannel", header, re.S)[1]
        channel_block = header.split("Channel", 1)[1].split("Harmonic Gate", 1)[0]
        channels = []
        for a, b, title in re.findall(
            r"(?m)^\s*(\d{1,2})-(\d{1,2})\s+([^\n]+)", channel_block
        ):
            title = re.split(r",?\s+A design\b", title)[0].strip()
            channels.append({"gates": sorted((int(a), int(b))), "name": title})
        if (
            sorted(c["gates"] for c in channels)
            != numeric["gates"][gate - 1]["channels"]
        ):
            raise ValueError(
                f"Depth extraction disagrees with frozen channel endpoints for gate {gate}"
            )
        line_page = pages[index + 1]
        heads = [
            m for m in re.finditer(r"(?m)^([1-6])\s+\1\s", line_page) if m.start() > 10
        ]
        if [int(m[1]) for m in heads] != [6, 5, 4, 3, 2, 1]:
            raise ValueError(f"Missing ordered line labels for gate {gate}")
        roles = {line: {"p": [], "s": []} for line in range(1, 7)}
        for marker in re.finditer(r"([\u00c0-\u00ff])\s+([ps])\b", line_page):
            candidates = [
                h
                for h in heads
                if (
                    h.start() > marker.start()
                    if marker[2] == "p"
                    else h.start() < marker.start()
                )
            ]
            if not candidates or marker[1] not in GLYPHS:
                raise ValueError(
                    f"Unrecognized polarity at gate {gate}: {marker.group()}"
                )
            head = candidates[0] if marker[2] == "p" else candidates[-1]
            roles[int(head[1])][marker[2]].append(GLYPHS[marker[1]])
        lines = []
        for line, poles in roles.items():
            if any(len(values) > 1 for values in poles.values()):
                raise ValueError(
                    f"Ambiguous polarity glyph assignment at {gate}.{line}"
                )
            exalted = next(iter(poles["p"]), None)
            detriment = next(iter(poles["s"]), None)
            lines.append(
                {
                    "line": line,
                    "exaltation_planet": exalted,
                    "detriment_planet": detriment,
                    "polarity_kind": (
                        "dual"
                        if exalted and detriment
                        else "unitary" if exalted or detriment else "no_planet_polarity"
                    ),
                }
            )
        rows.append(
            {
                "gate": gate,
                "name": " ".join(name.split()),
                "channel_identifiers": channels,
                "cross_identifiers": {
                    angle: " ".join(cross[i].split())
                    for i, angle in enumerate(("right", "juxtaposition", "left"), 1)
                },
                "line_polarities": lines,
                "pdf_pages_one_based": [index + 1, index + 2],
            }
        )
    dual_count = sum(
        line["polarity_kind"] == "dual"
        for row in rows
        for line in row["line_polarities"]
    )
    if (
        dual_count != 375
        or len({tuple(c["gates"]) for row in rows for c in row["channel_identifiers"]})
        != 36
    ):
        raise ValueError(
            "Incomplete source extraction: expected 375 dual lines and 36 channel pairs"
        )
    return {
        "source": {
            **numeric["source"],
            "scope": "64 gate identifiers, 192 angle-specific cross identifiers, 36 channel identifiers, 384 numeric line/planet-polarity assignments. No line readings or commentary bundled.",
            "extraction": "pdftotext -raw; source font glyphs mapped explicitly; ordered 6-to-1 line headings associated with printed p/s glyphs; 375 dual lines cross-checked against Ra's 1997 newsletter.",
        },
        "gates": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    value = json.dumps(extract(args.pdf), ensure_ascii=False, indent=2) + "\n"
    path = ROOT / "src/fatebridge/data/human_design/rave-2001-depth.json"
    if args.check:
        if not path.is_file() or path.read_text() != value:
            raise SystemExit("Source depth fixture differs from this exact PDF")
    else:
        path.write_bytes(value.encode("utf-8"))
    print(
        "2001 depth catalogue verified"
        if args.check
        else "Saved factual 2001 depth catalogue"
    )


if __name__ == "__main__":
    main()

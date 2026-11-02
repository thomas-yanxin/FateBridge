"""Extract factual tables from Ra Uru Hu's 2001 Complete Rave I'Ching.

No FateBridge calculator is imported. Only angular ranges, center/circuit labels
and channel endpoints are saved. No line readings or commentary are republished.
Requires pdftotext; the PDF is read from an explicit local path.
"""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIGNS = {
    "Q": 0,
    "‚": 1,
    "ƒ": 2,
    "„": 3,
    "…": 4,
    "†": 5,
    "‡": 6,
    "ˆ": 7,
    "‰": 8,
    "Š": 9,
    "‹": 10,
    "Œ": 11,
}
DEGREE = r"(\d{1,2})°\s*(\d{2})'\s*(\d{2})\""
RANGE = re.compile(DEGREE + r"\s*-\s*" + DEGREE)


def angle(values) -> float:
    degree, minute, second = map(int, values)
    return degree + minute / 60 + second / 3600


def extract(pdf: Path) -> dict:
    pages = subprocess.check_output(
        ["pdftotext", "-layout", str(pdf), "-"], text=True
    ).split("\f")
    raw_pages = subprocess.check_output(
        ["pdftotext", "-raw", str(pdf), "-"], text=True
    ).split("\f")
    gates = []
    for gate in range(1, 65):
        index = 5 + (gate - 1) * 2
        page = pages[index]
        header = raw_pages[index].split("Astrologic Position")[0]
        position = re.search(
            DEGREE + r"\s*(\S)\s*-\s*" + DEGREE + r"\s*(\S)",
            page.split("Astrologic Position")[1],
        )
        if not position:
            raise ValueError(f"Missing position for gate {gate}")
        start = SIGNS[position[4]] * 30 + angle(position.group(1, 2, 3))
        end = SIGNS[position[8]] * 30 + angle(position.group(5, 6, 7))
        center = re.search(
            r"Center\s+(Solar Plexus|Head|Ajna|Throat|Heart|G|Spleen|Sacral|Root)\b",
            header,
        )[1]
        circuit = re.search(r"Circuit\s+([^\n]+)", header)[1].strip()
        channels = sorted(
            {
                tuple(sorted(map(int, pair)))
                for pair in re.findall(r"\b(\d{1,2})-(\d{1,2})\b", header)
            }
        )
        lines = []
        ranges = list(RANGE.finditer(raw_pages[index + 1]))
        if len(ranges) != 6:
            raise ValueError(
                f"Expected six line ranges for gate {gate}, got {len(ranges)}"
            )
        for line, match in enumerate(reversed(ranges), 1):
            line_start = (start + (angle(match.group(1, 2, 3)) - start % 30) % 30) % 360
            line_end = (start + (angle(match.group(4, 5, 6)) - start % 30) % 30) % 360
            lines.append(
                {"line": line, "start_longitude": line_start, "end_longitude": line_end}
            )
        gates.append(
            {
                "gate": gate,
                "start_longitude": start,
                "end_longitude": end,
                "center": center,
                "gate_circuit_label": circuit,
                "channels": [list(pair) for pair in channels],
                "lines": lines,
                "pdf_pages_one_based": [index + 1, index + 2],
            }
        )
    if len({tuple(c) for gate in gates for c in gate["channels"]}) != 36:
        raise ValueError("Source did not yield exactly 36 distinct channels")
    return {
        "source": {
            "title": "The Complete Rave I'Ching",
            "author": "Ra Uru Hu",
            "publisher": "Jovian Archive Corporation",
            "edition_year": 2001,
            "url": "https://www.myhumandesign.be/downloads/Rave-I%27Ching.pdf",
            "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
            "scope": "64 gate positions and centers, 36 channel endpoint pairs, 384 line angular ranges; gate circuit labels are not assumed to be identical to channel circuit taxonomy. No copyrighted readings or commentaries included.",
            "extraction": "pdftotext -layout; explicit zodiac font-symbol mapping; no calculator imported",
        },
        "gates": gates,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    args = parser.parse_args()
    data = extract(args.pdf)
    target = ROOT / "src/fatebridge/data/human_design/rave-2001-reference.json"
    target.parent.mkdir(exist_ok=True)
    target.write_bytes(
        (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    print(
        f"Extracted {len(data['gates'])} gates, 384 line ranges and 36 channel pairs to {target}"
    )


if __name__ == "__main__":
    main()

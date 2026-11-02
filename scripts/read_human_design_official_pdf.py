"""Read visible PDF properties independently of the rendered-page transcription.

The activation diagram is an image in these PDFs: this extractor deliberately
does not invent gate.lines from the engine or claim PDF text verifies the SVG.
"""

import argparse
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

LABELS = (
    "Name",
    "Date and Time (Local)",
    "Date and Time (UTC)",
    "Location",
    "Type",
    "Strategy",
    "Signature",
    "Not-Self Theme",
    "Authority",
    "Definition",
    "Incarnation Cross",
    "Profile",
    "Variable",
)
NS = "{http://www.w3.org/1999/xhtml}"


def visible_properties(path):
    xml = subprocess.check_output(
        ["pdftotext", "-bbox-layout", str(path), "-"], text=True
    )
    root = ET.fromstring(xml)
    lines = []
    words = []
    for line in root.iter(NS + "line"):
        tokens = list(line.iter(NS + "word"))
        text = " ".join(t.text or "" for t in tokens)
        lines.append((text, float(line.get("xMin")), float(line.get("yMin"))))
        words.extend(
            (float(w.get("yMin")), float(w.get("xMin")), w.text or "") for w in tokens
        )
    anchors = {}
    for text, x, y in lines:
        if text in LABELS:
            if text in anchors:
                raise ValueError(f"Duplicate visible property label: {text}")
            anchors[text] = (x, y)
    if set(anchors) != set(LABELS):
        raise ValueError(f"Missing visible PDF labels: {set(LABELS) - set(anchors)}")
    result = {}
    for label, (x, y) in anchors.items():
        end = min(
            [ay for ax, ay in anchors.values() if abs(ax - x) < 1 and ay > y] + [y + 65]
        )
        selected = sorted(
            (wy, wx, text)
            for wy, wx, text in words
            if x - 0.1 <= wx < x + 145.67 and y + 15 <= wy < end
        )
        if not selected:
            raise ValueError(f"No value below visible label: {label}")
        result[label] = " ".join(t for _, _, t in selected)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    args = parser.parse_args()
    print(json.dumps(visible_properties(args.pdf), ensure_ascii=False))


if __name__ == "__main__":
    main()

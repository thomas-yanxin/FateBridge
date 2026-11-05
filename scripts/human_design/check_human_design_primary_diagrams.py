"""Verify pinned PDF diagram facts independently of the chart calculator.

Only numbered headings, four gate numbers, the printed page and the proofing
notice are retained. No chapter prose or full copyrighted PDF is distributed.
Requires local public-source copies and pdftotext; never downloads implicitly.
"""

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "src/fatebridge/data/human_design/primary-diagrams-2008-reference.json"
NS = {"x": "http://www.w3.org/1999/xhtml"}


def frozen_observation_check() -> dict:
    path = ROOT / "tests/fixtures/human-design-primary-diagrams-extraction.json"
    raw = path.read_bytes()
    if (
        hashlib.sha256(raw).hexdigest()
        != "085cabac2afdb50a083be78acfc7b2651ab5cd7733d46985a160ededd8bfbdcb"
    ):
        raise ValueError("Independent source extraction changed")
    observed = json.loads(raw)
    reference = json.loads(CATALOG.read_text())
    if observed["catalog_sha256"] != hashlib.sha256(CATALOG.read_bytes()).hexdigest():
        raise ValueError("Diagram catalog changed after the source observation")
    if len(observed["rows"]) != 2 or len(reference["observations"]) != 2:
        raise ValueError("Source observation set incomplete")
    for original, row in zip(observed["rows"], reference["observations"], strict=True):
        if any(original[k] != row[k] for k in original):
            raise ValueError("Independent diagram fact mismatch")
    return {
        "status": "bounded_two_unproofed_diagram_facts_matched",
        "extraction_sha256": hashlib.sha256(raw).hexdigest(),
        "catalog_sha256": observed["catalog_sha256"],
        "diagrams_checked": 2,
        "publisher_master_authenticated": False,
        "publisher_erratum_obtained": False,
        "scope": "Two pinned public-copy diagram facts, independently extracted and visually checked; not publisher-master authentication, proofreading, a16/6erratum, full source prose or closure of any original37criterion.",
    }


def extract_diagram(xml: str, identifier: str) -> dict:
    root = ElementTree.fromstring(xml)
    page = root.find(".//x:page", NS)
    if page is None:
        raise ValueError("Missing PDF page")
    lines = page.findall(".//x:line", NS)
    heading = "The Left Angle Cross of " + identifier
    selected = [
        line
        for line in lines
        if " ".join((w.text or "") for w in line.findall("x:word", NS)).strip()
        == heading
    ]
    if len(selected) != 1:
        raise ValueError("Missing or ambiguous diagram heading")
    anchor = selected[0]
    top, bottom = float(anchor.attrib["yMin"]), float(anchor.attrib["yMax"])
    width = float(page.attrib["width"])
    numbers = [
        w
        for w in page.findall(".//x:word", NS)
        if (w.text or "").isdigit()
        and float(w.attrib["xMin"]) > 0.65 * width
        and top - 5 <= float(w.attrib["yMin"]) <= bottom + 20
    ]
    if len(numbers) != 4:
        raise ValueError("Diagram must have exactly four numerical positions")
    ordered = sorted(
        numbers, key=lambda w: (float(w.attrib["yMin"]), float(w.attrib["xMin"]))
    )
    ys = [float(w.attrib["yMin"]) for w in ordered]
    if not (abs(ys[0] - ys[1]) < 1 and abs(ys[2] - ys[3]) < 1 and ys[2] - ys[1] > 5):
        raise ValueError("Ambiguous diagram row positions")
    gates = [int(ordered[i].text) for i in [0, 2, 1, 3]]
    words = [w.text or "" for w in page.findall(".//x:word", NS)]
    if "This transcription has not been proofed." not in " ".join(words):
        raise ValueError("Missing original unproofed qualification")
    footer = [
        w
        for w in page.findall(".//x:word", NS)
        if (w.text or "").isdigit()
        and float(w.attrib["yMin"]) > 0.94 * float(page.attrib["height"])
    ]
    if len(footer) != 1:
        raise ValueError("Missing or ambiguous printed page number")
    return {
        "display_identifier": identifier,
        "gates": gates,
        "printed_page": int(footer[0].text),
        "transcription_proofed": False,
    }


def verify_sources(directory: Path) -> dict:
    reference = json.loads(CATALOG.read_text())
    rows = []
    for expected in reference["observations"]:
        pdf = directory / f"quarter-{expected['quarter']}.pdf"
        if hashlib.sha256(pdf.read_bytes()).hexdigest() != expected["pdf_sha256"]:
            raise ValueError("Primary PDF bytes changed")
        with tempfile.TemporaryDirectory(prefix="fatebridge-hd-diagram-") as temporary:
            target = Path(temporary) / "page.xml"
            subprocess.run(
                [
                    "pdftotext",
                    "-f",
                    str(expected["pdf_page_one_based"]),
                    "-l",
                    str(expected["pdf_page_one_based"]),
                    "-bbox-layout",
                    str(pdf),
                    str(target),
                ],
                check=True,
                capture_output=True,
            )
            actual = extract_diagram(target.read_text(), expected["display_identifier"])
        if any(actual[k] != expected[k] for k in actual):
            raise ValueError("Source diagram differs from frozen factual transcription")
        rows.append(
            {
                "quarter": expected["quarter"],
                "pdf_sha256": expected["pdf_sha256"],
                "pdf_page_one_based": expected["pdf_page_one_based"],
                **actual,
            }
        )
    return {
        "method_id": "human_design_pinned_transcript_diagram_extraction_v1",
        "status": "two_pinned_diagram_facts_verified",
        "catalog_sha256": hashlib.sha256(CATALOG.read_bytes()).hexdigest(),
        "rows": rows,
        "publisher_master_authenticated": False,
        "publisher_erratum_obtained": False,
        "scope": "Independent PDF text-coordinate extraction of two selected facts. The black/red column roles were also visually inspected. Not an authentication of the public copy, original-source completeness or prose semantics.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify_sources(args.pdf_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

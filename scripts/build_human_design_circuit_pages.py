"""Verify the original scan and frozen visual observations, without engine imports.

This is a builder from image-read factual transcriptions, not an automatic OCR
corrector. It preserves the two observed OCR digit errors and the unresolved
motor-heading discrepancy. It never redistributes source pages or line prose.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OBSERVATION_SHA256 = "84f474f27db707323e17ec397e423f6a2b1028d11bcd3abd27c5eda4de8410c7"


def build(pdf: Path) -> dict:
    observations = ROOT / "tests/fixtures/human-design-circuit-pages-observations.json"
    if hashlib.sha256(observations.read_bytes()).hexdigest() != OBSERVATION_SHA256:
        raise ValueError("Frozen visual observations changed")
    reference = json.loads(observations.read_text())["catalogue"]
    plan_path = ROOT / "tests/fixtures/human-design-circuit-pages-plan.json"
    if hashlib.sha256(plan_path.read_bytes()).hexdigest() != reference["plan_sha256"]:
        raise ValueError("Original observation plan changed")
    if (
        hashlib.sha256(pdf.read_bytes()).hexdigest()
        != reference["source"]["pdf_sha256"]
    ):
        raise ValueError("Original source PDF changed")
    pairs = []
    for topology in reference["topologies"]:
        page = str(topology["pdf_page_one_based"])
        text = subprocess.check_output(
            ["pdftotext", "-layout", "-f", page, "-l", page, str(pdf), "-"], text=True
        )
        raw = [
            [int(m[1]), int(m[2])]
            for line in text.splitlines()
            if (m := re.match(r"^\s*(\d{1,2})\s*[/I|]\s*(\d{1,2})(?=\s|The|$)", line))
        ]
        if raw != topology["ocr_observed_gate_pairs"]:
            raise ValueError("Source text-layer observation changed")
        image_read = topology["image_read_listed_gate_pairs"]
        differences = [
            (i, x, y) for i, (x, y) in enumerate(zip(raw, image_read)) if x != y
        ]
        recorded = [
            (r["index"], r["ocr_pair"], r["image_read_pair"])
            for r in topology["ocr_disagreements"]
        ]
        if len(raw) != len(image_read) or differences != recorded:
            raise ValueError("Unrecorded OCR correction")
        pairs.extend(tuple(sorted(pair)) for pair in image_read)
    if len(pairs) != len(set(pairs)) or len(pairs) != 36:
        raise ValueError("Incomplete or duplicate source channel list")
    reference["observation_fixture_sha256"] = OBSERVATION_SHA256
    return reference


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    reference = build(args.pdf)
    args.output.write_text(json.dumps(reference, ensure_ascii=False, indent=2) + "\n")
    print("Verified all seven source pages and36 visually observed channel assignments")


if __name__ == "__main__":
    main()

"""Extract two structural facts from a pinned publisher preview, without the engine."""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PDF_SHA256 = "5bbc572b33609ee1f23e33ee7a36645ddc565da9f256635a95043295369a33e6"
PDF_URL = "https://cdn.shopify.com/s/files/1/0872/4984/6576/files/Life-Cycles-Analysis-preview.pdf?v=1757008879"
TARGET = ROOT / "src/fatebridge/data/human_design/publisher-natal-2005-reference.json"


def extract_facts(pdf: Path) -> dict:
    if hashlib.sha256(pdf.read_bytes()).hexdigest() != PDF_SHA256:
        raise ValueError("Publisher preview differs from the pinned bytes")
    raw = subprocess.run(
        ["pdftotext", "-f", "10", "-l", "10", "-layout", str(pdf), "-"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return facts_from_page(raw)


def facts_from_page(raw: str) -> dict:
    # Repair only PDF line wrapping, never AM/PM or a source assertion.
    text = re.sub(r"(?<=[A-Za-z])-\s*\n\s*(?=[a-z])", "", raw)
    text = " ".join(text.split())
    heading = re.search(r"The (Single) Definition (Manifestor) Basic Thematic", text)
    note = re.search(
        r"\[Birth Data for this lecture: (May) (12), (1895), "
        r"(12):(25) (PM), (Madanapalle), (India)\]",
        text,
    )
    if (
        heading is None
        or note is None
        or "Krishnamurti" not in text
        or "Copyright 2005 Jovian Archive Corporation" not in text
    ):
        raise ValueError("Required literal publisher facts are absent or changed")
    return {
        "method_id": "human_design_publisher_preview_natal_facts_v1",
        "source": {
            "author": "Ra Uru Hu",
            "title": "Life Cycles Analysis",
            "course_year": 2005,
            "publisher_page": "https://jovianarchive.com/products/life-cycles-analysis",
            "pdf_url": PDF_URL,
            "pdf_sha256": PDF_SHA256,
            "pdf_page_one_based": 10,
            "printed_page": "2",
            "publisher_preview_only": True,
        },
        "example": {
            "id": "krishnamurti-course-2005-published-note",
            "subject": "Krishnamurti",
            "date": "1895-05-12",
            "clock": "12:25 PM",
            "hour_24": int(note[4]),
            "minute": int(note[5]),
            "place": f"{note[7]}, {note[8]}",
            "timezone_printed_in_birth_note": False,
            "expected_structural_fields": {
                "bodygraph.type": heading[2].lower(),
                "bodygraph.definition.kind": heading[1].lower(),
            },
            "independent_structural_fact_count": 2,
            "activation_glyphs_available_in_preview": False,
        },
        "scope": "One publisher example with two structural assertions. The printed birth note supplies no time zone. Hypotheses must remain explicit; matching type/definition cannot authenticate an epoch, all26activations, the whole book or real-world prediction. No unprinted AM input may count as literal conformance.",
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pdf", type=Path, required=True)
    p.add_argument("--output", type=Path, default=TARGET)
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    data = json.dumps(extract_facts(args.pdf), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if args.output.read_text() != data:
            raise SystemExit("Publisher natal reference differs from extraction")
    else:
        args.output.write_text(data)
    print(
        json.dumps(
            {"structural_facts": 2, "sha256": hashlib.sha256(data.encode()).hexdigest()}
        )
    )


if __name__ == "__main__":
    main()

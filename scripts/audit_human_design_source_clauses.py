"""Inventory source clauses without treating text extraction as interpretation.

This audit has no runtime/domain imports and republishes no line prose. A
candidate review checks only planet/polarity clauses in the fixed public copy.
It cannot certify a complete reading, a publisher master, or astronomical truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = "e45ca38d7959efa2f69b512e0d6d97a59dfbc150519d4f54c08b76149e5bb495"
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
NAMED = re.compile(r"\b(" + "|".join(PLANETS) + r")\b", re.IGNORECASE)
EXTRA = re.compile(r"\b(" + "|".join(PLANETS) + r") is also (exalted|in detriment)\.")
MARKERS = {
    "planet_reference": re.compile(r"\bplanets?\b|\bplanetary\b", re.IGNORECASE),
    "polarity_absence": re.compile(
        r"\bno (?:polarity|exaltation|detriment)\b|"
        r"\bneither an exaltation nor a detriment\b",
        re.IGNORECASE,
    ),
    "planet_adjective": re.compile(
        r"\b(?:solar|lunar|mercurial|venusian|martian|jovian|saturnian|"
        r"uranian|neptunian|plutonian)\b",
        re.IGNORECASE,
    ),
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def line_blocks(layout: str) -> list[tuple[int, int, int, str]]:
    """Require all 384 distinct headings; fail before producing a subset report."""
    pages = layout.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    if len(pages) != 133:
        raise ValueError("Expected all 133 source pages")
    blocks = []
    for gate in range(1, 65):
        page_index = 6 + 2 * (gate - 1)
        text = pages[page_index]
        heads = list(re.finditer(r"(?m)^([1-6])\s", text))
        if [int(m[1]) for m in heads] != [6, 5, 4, 3, 2, 1]:
            raise ValueError(f"Incomplete or ambiguous source headings: gate {gate}")
        for index, head in enumerate(heads):
            end = heads[index + 1].start() if index + 1 < len(heads) else len(text)
            blocks.append(
                (gate, int(head[1]), page_index + 1, text[head.start() : end])
            )
    return blocks


def inventory(layout: str, catalog: dict[str, Any]) -> dict[str, Any]:
    canonical = {planet.lower(): planet for planet in PLANETS}
    expected = {(gate, line) for gate in range(1, 65) for line in range(1, 7)}
    assignments = {}
    for gate in catalog["gates"]:
        for row in gate["line_polarities"]:
            key = gate["gate"], row["line"]
            if key in assignments:
                raise ValueError("Duplicate catalogue line")
            assignments[key] = row
    if set(assignments) != expected:
        raise ValueError("Catalogue must retain all 384 line records")
    rows = []
    for gate, line, page, block in line_blocks(layout):
        assignment = assignments[gate, line]
        names = sorted({canonical[m[1].lower()] for m in NAMED.finditer(block)})
        glyphs = {assignment[role + "_planet"] for role in ("exaltation", "detriment")}
        non_glyph = sorted(set(names) - glyphs)
        markers = [key for key, pattern in MARKERS.items() if pattern.search(block)]
        flat = " ".join(block.split())
        extras = [
            {
                "planet": match[1],
                "role": "exaltation" if match[2] == "exalted" else "detriment",
                "clause_sha256": digest(match[0].encode()),
            }
            for match in EXTRA.finditer(flat)
        ]
        rows.append(
            {
                "line_id": f"{gate}.{line}",
                "gate": gate,
                "line": line,
                "pdf_page_one_based": page,
                "source_layout_block_sha256": digest(block.encode()),
                "block_characters": len(block),
                "named_planets": names,
                "catalogue_glyph_assignments": assignment,
                "non_glyph_planet_mentions": non_glyph,
                "candidate_markers": markers,
                "explicit_additional_clauses": extras,
                "requires_clause_review": bool(non_glyph or markers),
                "complete_line_semantics_reviewed": False,
            }
        )
    return {
        "method_id": "human_design_public_source_clause_inventory_v1",
        "source_pdf_sha256": SOURCE_SHA256,
        "source_access": "all_133_pages_and_384_text_blocks_readable",
        "required_line_count": 384,
        "observed_line_count": len(rows),
        "line_rows": rows,
        "candidate_line_ids": [
            r["line_id"] for r in rows if r["requires_clause_review"]
        ],
        "complete_semantic_reviewed_line_count": 0,
        "complete_source_reading_accepted": False,
        "publisher_master_authenticated": False,
        "astronomical_precision_assessed": False,
        "real_world_prediction_assessed": False,
        "scope": "Complete candidate inventory only; neither named-planet extraction nor a polarity-clause review is a complete line-meaning review. Catalogue glyph assignments remain a separately supplied historical reference, not freshly extracted glyph verification.",
    }


def bind_review(report: dict[str, Any], review: dict[str, Any]) -> None:
    """Require every candidate and exact block identity, including rejected leads."""
    if review["source_pdf_sha256"] != report["source_pdf_sha256"]:
        raise ValueError("Review is bound to a different source")
    if review.get("complete_source_reading_accepted") is not False:
        raise ValueError("Clause review cannot certify complete source readings")
    by_id = {row["line_id"]: row for row in report["line_rows"]}
    candidate_ids = set(report["candidate_line_ids"])
    seen = set()
    for row in review["clause_reviews"]:
        key = row["line_id"]
        if key in seen or key not in candidate_ids:
            raise ValueError("Duplicate or substituted candidate review")
        seen.add(key)
        if (
            row["source_layout_block_sha256"]
            != by_id[key]["source_layout_block_sha256"]
        ):
            raise ValueError("Reviewed source block changed")
        if row["review_kind"] != "visual_planet_and_polarity_clause_only":
            raise ValueError("Unsupported clause review scope")
        if row["complete_line_semantics_reviewed"] is not False:
            raise ValueError("Clause review cannot be relabelled as full line review")
        by_id[key]["clause_review"] = row
    if seen != candidate_ids:
        raise ValueError(
            "Candidate reviews omitted; keep every unresolved/rejected lead"
        )
    report["candidate_clause_review_count"] = len(seen)
    report["review_sha256"] = digest(
        json.dumps(review, sort_keys=True, separators=(",", ":")).encode()
    )


def audit(pdf: Path, review: dict[str, Any] | None = None) -> dict[str, Any]:
    if digest(pdf.read_bytes()) != SOURCE_SHA256:
        raise ValueError("Different PDF: edition review required")
    layout = subprocess.check_output(["pdftotext", "-layout", str(pdf), "-"], text=True)
    catalog_path = ROOT / "src/fatebridge/data/human_design/rave-2001-depth.json"
    report = inventory(layout, json.loads(catalog_path.read_text()))
    report["catalogue_sha256"] = digest(catalog_path.read_bytes())
    if review is not None:
        bind_review(report, review)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--review", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-complete-interpretation", action="store_true")
    args = parser.parse_args()
    review = json.loads(args.review.read_text()) if args.review else None
    report = audit(args.pdf, review)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    if (
        args.require_complete_interpretation
        and not report["complete_source_reading_accepted"]
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

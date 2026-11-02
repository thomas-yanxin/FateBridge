"""Verify the paired position notes and exact selected source spans."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if not __package__:
    sys.path.insert(0, str(ROOT / "src"))
from fatebridge.core.sukuyo_calendar_text import calendar_day_evidence
from fatebridge.core.sukuyo_documentary import CLOCK_POSITION
from fatebridge.core.sukuyo_sources import load_source


def main_text(raw: str, after_anchor: str | None = None) -> str:
    """Extract a publisher paragraph; start at the actual anchor if requested."""
    node = ET.fromstring(raw)
    output = []
    active = after_anchor is None

    def visit(element: ET.Element) -> None:
        nonlocal active
        tag = element.tag.rsplit("}", 1)[-1]
        if tag in {"note", "rdg", "mulu"}:
            return
        if element.get("{http://www.w3.org/XML/1998/namespace}id") == after_anchor:
            active = True
        if active and element.text:
            output.append(element.text)
        for child in element:
            visit(child)
            if active and child.tail:
                output.append(child.tail)

    visit(node)
    if not active:
        raise ValueError("Selected position anchor not found")
    return "".join("".join(output).split())


def verify_clock_position(
    xml_path: Path | None = None, symbol_capture: Path | None = None
) -> dict[str, Any]:
    fixture_path = ROOT / "tests/fixtures/sukuyo-clock-transposition-primary.json"
    fixture = json.loads(fixture_path.read_bytes())
    source = load_source(CLOCK_POSITION)
    bundle = source.data
    paragraphs = fixture["raw_selected_xml_paragraphs"]
    special = (
        main_text(paragraphs["pT21p0398b1901"], "nkr_note_orig_0398015")
        + main_text(paragraphs["pT21p0398b2701"])
        + main_text(paragraphs["pT21p0398c0301"])
    )
    clock = main_text(paragraphs["pT21p0399b2301"])
    errors: list[Any] = []
    if [special, clock] != [r["normalized_base_text"] for r in bundle["blocks"]]:
        errors.append("selected_span_text")
    counts = [len(re.findall("[\u3400-\u9fff]", row)) for row in [special, clock]]
    if counts != [248, 93] or counts != [
        r["cjk_character_count"] for r in bundle["blocks"]
    ]:
        errors.append(["selected_span_counts", counts])
    notes = {}
    for number, raw_notes in fixture["raw_selected_note_elements"].items():
        notes[number] = [
            {
                "attributes": dict(ET.fromstring(raw).attrib),
                "text": "".join(ET.fromstring(raw).itertext()),
            }
            for raw in raw_notes
        ]
    if {n: notes[n] for n in ["0398015", "0399016"]} != bundle["paired_apparatus"][
        "note_records"
    ] or notes["0398014"] != bundle["adjacent_variant"]["note_records"]:
        errors.append("selected_apparatus")
    if any("∞" not in row["text"] for n in ["0398015", "0399016"] for row in notes[n]):
        errors.append("position_symbol_missing")
    if (
        bundle["source_sha256"] != fixture["source_sha256"]
        or bundle["source_url"] != fixture["source_url"]
    ):
        errors.append("publisher_provenance")
    if bundle["symbol_reference"] != fixture["symbol_reference"]:
        errors.append("symbol_reference_changed")
    if xml_path:
        raw = xml_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != fixture["source_sha256"]:
            raise ValueError("Full position source bytes changed")
        decoded = raw.decode()
        for fragment in [
            *paragraphs.values(),
            *(
                row
                for rows in fixture["raw_selected_note_elements"].values()
                for row in rows
            ),
        ]:
            if fragment not in decoded:
                errors.append("fragment_missing_from_full_source")
    if symbol_capture:
        raw = symbol_capture.read_bytes()
        if (
            hashlib.sha256(raw).hexdigest()
            != bundle["symbol_reference"]["selected_capture_sha256"]
        ):
            raise ValueError("Selected symbol capture bytes changed")
        capture = json.loads(raw)
        if (
            bundle["symbol_reference"]["selected_explanation"]
            not in capture["selected_text"]
            or capture["full_html_downloaded"]
        ):
            errors.append("selected_legend_scope")
    for day in range(1, 31):
        result = calendar_day_evidence(day)
        reference = result["clock_doctrine"]["textual_position_reference"]
        if (
            result["clock_evaluation_status"] != "not_computed"
            or reference["applied_to_clock_mapping"]
            or reference["applied_to_primary_table"]
            or reference["leap_short_month_priority_established"]
        ):
            errors.append(["position_promoted_to_policy", day])
    return {
        "format": "sukuyo_clock_position_check_v1",
        "source_bundle_sha256": source.sha256,
        "fixture_sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
        "selected_source_paragraphs": 4,
        "paired_position_notes": 2,
        "independent_position_operations": 1,
        "adjacent_single_character_deletion_notes": 1,
        "verified_cjk_counts": counts,
        "full_source_bytes_and_fragments_checked": xml_path is not None,
        "selected_official_legend_capture_checked": symbol_capture is not None,
        "full_symbol_page_HTML_obtained": False,
        "unchanged_runtime_clock_controls": 30,
        "independent_ming_print_or_complete_reconstruction": False,
        "ancient_clock_or_precedence_admitted": False,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xml-path", type=Path)
    parser.add_argument("--symbol-capture", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify_clock_position(args.xml_path, args.symbol_capture)
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")
    return bool(report["errors"])


if __name__ == "__main__":
    raise SystemExit(main())

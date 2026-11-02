"""Check selected comparative time texts without adopting a clock conversion."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if not __package__:
    sys.path.insert(0, str(ROOT / "src"))

from fatebridge.core.sukuyo_calendar_text import (
    COMPARATIVE_TIME_SOURCE,
    calendar_day_evidence,
)
from fatebridge.core.sukuyo_sources import load_source

FIXTURE = ROOT / "tests/fixtures/sukuyo-comparative-time-primary.json"


def selected_tei_lines(
    path: Path, start: str, end: str
) -> tuple[str, dict[str, list[str]]]:
    """Read publisher main text, keeping inline notes separate from apparatus."""
    root = ET.fromstring(path.read_bytes())
    main: dict[str, str] = {}
    notes: dict[str, list[str]] = {}
    current: str | None = None

    def visit(node: ET.Element) -> None:
        nonlocal current
        tag = node.tag.rsplit("}", 1)[-1]
        if tag in {"teiHeader", "back", "rdg"}:
            return
        if tag == "lb":
            if node.get("ed") == "T":
                current = node.get("n")
                if current is not None:
                    main.setdefault(current, "")
            return
        if tag == "note":
            if node.get("place") == "inline" and current is not None:
                notes.setdefault(current, []).append("".join(node.itertext()).strip())
            return
        if node.text and current is not None:
            main[current] += node.text.replace("\n", "")
        for child in node:
            visit(child)
            if child.tail and current is not None:
                main[current] += child.tail.replace("\n", "")

    visit(root)
    selected = [key for key in main if start <= key <= end]
    if not selected or selected[0] != start or selected[-1] != end:
        raise ValueError("Comparative source line range is incomplete")
    return "".join(main[key] for key in selected), {
        key: notes[key] for key in selected if key in notes
    }


def verify_time_primary(capture_dir: Path | None = None) -> dict[str, Any]:
    fixture = json.loads(FIXTURE.read_bytes())
    source = load_source(COMPARATIVE_TIME_SOURCE)
    bundle = source.data
    witnesses = {row["id"]: row for row in bundle["witnesses"]}
    errors = []
    if set(witnesses) != set(fixture["expected_main_excerpts"]):
        raise ValueError("Comparative witnesses changed; revalidate original sources")
    checked_files = []
    for identifier, witness in witnesses.items():
        if witness["source_excerpt"] != fixture["expected_main_excerpts"][identifier]:
            errors.append([identifier, "selected_main_excerpt"])
        if witness["inline_notes"] != fixture["expected_inline_notes"][identifier]:
            errors.append([identifier, "inline_notes"])
        file = identifier + ".xml"
        expected = fixture["source_files"][file]
        if (
            witness["source_sha256"] != expected["sha256"]
            or witness["source_url"] != expected["url"]
            or witness["publisher_commit"] != fixture["publisher_commit"]
        ):
            errors.append([identifier, "publisher_provenance"])
        if capture_dir is not None:
            path = capture_dir / file
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected["sha256"]:
                raise ValueError("Comparative source bytes changed")
            authors = [
                "".join(row.itertext()).strip()
                for row in ET.fromstring(path.read_bytes()).findall(
                    ".//{http://www.tei-c.org/ns/1.0}titleStmt/"
                    "{http://www.tei-c.org/ns/1.0}author"
                )
            ]
            if witness["source_header_author_literal"] not in authors:
                errors.append([identifier, "source_header_author_literal"])
            text, notes = selected_tei_lines(
                path, *fixture["selected_line_ranges"][file]
            )
            if witness["source_excerpt"] not in text:
                errors.append([identifier, "main_text_not_in_captured_source"])
            for row in witness["inline_notes"]:
                line = row["locator"].rsplit("_p", 1)[1]
                if row["text"] not in notes.get(line, []):
                    errors.append([identifier, "inline_note_not_in_captured_source"])
            checked_files.append(file)
    for day in range(1, 31):
        result = calendar_day_evidence(day)
        doctrine = result["clock_doctrine"]
        comparative = doctrine["comparative_time_systems"]
        if (
            result["clock_evaluation_status"] != "not_computed"
            or doctrine["day_parts"] != 8
            or doctrine["night_parts"] != 8
            or doctrine["physical_clock_mapping_status"] != "not_established"
            or comparative["applied_to_runtime_clock"]
            or comparative["modern_clock_conversion_established"]
            or comparative["hinoo_half_mapping_established"]
        ):
            errors.append(["runtime_clock_promoted", day])
    return {
        "format": "sukuyo_comparative_time_primary_check_v1",
        "source_bundle_sha256": source.sha256,
        "fixture_sha256": hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
        "selected_witnesses": len(witnesses),
        "inline_notes": sum(len(row["inline_notes"]) for row in witnesses.values()),
        "full_source_files_checked": checked_files,
        "unchanged_runtime_day_controls_checked": 30,
        "errors": errors,
        "whole_source_apparatus_or_manuscript_collation": False,
        "independent_human_transcription": False,
        "modern_clock_admission": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify_time_primary(args.capture_dir)
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")
    return bool(report["errors"])


if __name__ == "__main__":
    raise SystemExit(main())

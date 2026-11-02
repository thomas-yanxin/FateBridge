"""Reproduce bounded Robbins terms checks using the frozen manual reference.

Source acquisition is separate: --source-directory holds the downloaded HTML
and inspected page images. No network call, oracle generation or golden rewrite.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

from fatebridge.core.astrology_tables import SIGNS
from fatebridge.core.ptolemy_terms import terms_at

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "tests/fixtures/western-ptolemy-terms-robbins-1940.json"
GLYPHS = {"♃": "Jupiter", "♀": "Venus", "☿": "Mercury", "♂": "Mars", "♄": "Saturn"}


class Rows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.cells = []
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.cells = []
        if tag in {"td", "th"}:
            self.cell = ""

    def handle_data(self, data):
        if self.cell is not None:
            self.cell += data

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self.cell is not None:
            self.cells.append(" ".join(self.cell.split()))
            self.cell = None
        if tag == "tr" and self.cells:
            self.rows.append(self.cells)


def source_checks(ref, directory):
    html = (directory / "robbins-1b.html").read_bytes()
    assert hashlib.sha256(html).hexdigest() == ref["html_sha256"]
    for page, expected in ref["scan_image_sha256"].items():
        data = (directory / f"scan-pdf-{page}.jpg").read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected
    tables = []
    for markup in re.findall(r"<TABLE\b[^>]*>.*?</TABLE>", html.decode(), re.I | re.S):
        parser = Rows()
        parser.feed(markup)
        if len(parser.rows) == 12 and parser.rows[0][0] == "Aries":
            tables.append(parser.rows)
    assert len(tables) == 2
    differences = []
    for system, rows in zip(("egyptian", "ptolemaic"), tables):
        for index, row in enumerate(rows):
            for position, cell in enumerate(row[1:]):
                glyph, count = cell.split()
                value = [GLYPHS[glyph], int(count)]
                printed = ref[system][index][position + 1]
                if value != printed:
                    differences.append(
                        {
                            "system": system,
                            "sign": SIGNS[index],
                            "position": position + 1,
                            "html": value,
                            "printed": printed,
                        }
                    )
    assert differences == [
        {
            "system": "ptolemaic",
            "sign": "Libra",
            "position": 5,
            "html": ["Saturn", 6],
            "printed": ["Mars", 6],
        }
    ]
    return differences


def check_terms(ref, calculator=terms_at):
    counts = {"interior_and_integer_probes": 0, "boundary_probes": 0}

    def row_for(system, index, sect):
        if system == "chaldaean":
            return list(
                zip(
                    ref["chaldaean_order_by_triangle"][sect][index % 4],
                    ref["chaldaean_lengths"],
                )
            )
        row = ref[system][index]
        assert row[0] == SIGNS[index]
        return row[1:]

    for sect in ("day", "night"):
        for system in ("egyptian", "chaldaean", "ptolemaic"):
            totals = Counter()
            for index in range(12):
                row = row_for(system, index, sect)
                assert len(row) == 5 and len({lord for lord, _ in row}) == 5
                assert sum(n for _, n in row) == 30
                start = 0
                for position, (lord, n) in enumerate(row):
                    end = start + n
                    totals[lord] += n
                    for degree in range(start, end):
                        for fraction in (0, 0.5):
                            term = calculator(30 * index + degree + fraction, sect)[
                                system
                            ]
                            assert (
                                term["lord"],
                                term["start_degree"],
                                term["end_degree"],
                            ) == (lord, start, end)
                            counts["interior_and_integer_probes"] += 1
                    boundary = 30 * index + start
                    previous = (
                        row[position - 1][0]
                        if position
                        else row_for(system, (index - 1) % 12, sect)[-1][0]
                    )
                    for value, expected in (
                        (math.nextafter(boundary, -math.inf), previous),
                        (boundary, lord),
                        (math.nextafter(boundary, math.inf), lord),
                    ):
                        assert calculator(value, sect)[system]["lord"] == expected
                        counts["boundary_probes"] += 1
                    start = end
            if system == "chaldaean":
                assert totals == ref["chaldaean_totals"][sect]
            else:
                # The printed tables have equal aggregate totals; this alone
                # cannot authenticate any cell, so every segment is also tested.
                assert totals == {
                    "Saturn": 57,
                    "Jupiter": 79,
                    "Mars": 66,
                    "Venus": 82,
                    "Mercury": 76,
                }
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    ref = json.loads(REFERENCE.read_text())
    differences = source_checks(ref, args.source_directory)
    probes = check_terms(ref)

    # A regression to the known online typo must fail the same audit.
    def wrong_libra(value, sect):
        result = terms_at(value, sect)
        if 204 <= value < 210:
            result["ptolemaic"]["lord"] = "Saturn"
        return result

    rejected = False
    try:
        check_terms(ref, wrong_libra)
    except AssertionError:
        rejected = True
    assert rejected
    report = {
        "status": "bounded_printed_edition_checks_passed",
        "reference_sha256": hashlib.sha256(REFERENCE.read_bytes()).hexdigest(),
        "source_differences": differences,
        "source_scan_hashes_verified": len(ref["scan_image_sha256"]),
        **probes,
        "known_html_typo_negative_control_rejected": rejected,
        "full_textual_criticism_verified": False,
        "full_professional_system_verified": False,
        "limitations": [
            "Manual transcription and manual scan inspection, not independent expert review",
            "Printed main tables only; apparatus variants remain unresolved",
            "No life-event judgement or empirical predictive validation",
            "Probe counts reuse the same finite tables; they are not independent observations",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()

"""Verify selected SAT quotations; optionally recheck the private full HTML.

The default offline check never treats selected quotations as full source bytes.
Full publisher HTML is not redistributed with FateBridge.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/sukuyo-t2465-downloaded-primary.json"


class SATQuotationParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.line: str | None = None
        self.lines: dict[str, list[str]] = {}
        self.notes: dict[str, list[str]] = {}
        self.button_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "a" and re.fullmatch(r"\d{4}[abc]\d\d", attributes.get("name") or ""):
            self.line = attributes["name"]
            assert self.line is not None
            if self.line in self.lines:
                raise ValueError(f"Duplicate primary text line: {self.line}")
            self.lines[self.line] = []
        if tag == "button":
            if self.line:
                self.notes.setdefault(self.line, []).append(
                    attributes.get("title") or ""
                )
            self.button_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "button":
            self.button_depth -= 1
        if tag == "a":
            self.line = None

    def handle_data(self, data: str) -> None:
        if self.line and not self.button_depth:
            self.lines[self.line].append(data)


def verify_primary(publisher_html: Path | None = None) -> dict[str, Any]:
    fixture = json.loads(FIXTURE.read_bytes())
    parser = SATQuotationParser()
    for row in fixture["selected_html_quotations"]:
        parser.feed(row["html"])
    if set(parser.lines) != {"0024a04", *[f"0030c{i:02}" for i in range(13, 27)]}:
        raise ValueError("Selected primary quotation line set is incomplete")
    calendar_text = "".join(
        "".join(parser.lines[f"0030c{i:02}"]) for i in range(13, 27)
    )
    calendar_text = re.sub(r"[\s\u200b]+", "", calendar_text)
    first = calendar_text[
        calendar_text.index("若有閏月時。") : calendar_text.index("取小月闕")
    ]
    second = calendar_text[calendar_text.index("取小月闕") :]
    profiles = json.loads(
        (ROOT / "src/fatebridge/data/sukuyo_t1299_calendar_profiles.json").read_bytes()
    )
    cached = profiles["hinoo_addendum"]["cached_primary_excerpt"]
    # The prior manual quotation supplied a terminal full stop where the live
    # HTML has a closing quote mark. Preserve both witnesses and this finding;
    # do not silently change the old fixture or report byte-identical text.
    if first != cached["windows"][0]["text"] or second != (
        cached["windows"][1]["text"].removesuffix("。") + "｣"
    ):
        raise ValueError(
            "Primary quotation differs beyond the recorded terminal punctuation finding"
        )
    if publisher_html is not None:
        raw = publisher_html.read_bytes()
        if hashlib.sha256(raw).hexdigest() != fixture["publisher_html_response_sha256"]:
            raise ValueError("Private publisher response fingerprint changed")
        if len(raw) != fixture["publisher_html_response_bytes"]:
            raise ValueError("Private publisher response byte count changed")
        text = raw.decode("utf-8")
        if any(row["html"] not in text for row in fixture["selected_html_quotations"]):
            raise ValueError(
                "A selected quotation is absent from the publisher response"
            )
        keys = sorted(set(re.findall(r'<a name="(\d{4}[abc]\d\d)"', text)))
        if (len(keys), keys[0], keys[-1]) != (
            fixture["html_line_anchor_count"],
            fixture["html_line_anchor_first"],
            fixture["html_line_anchor_last"],
        ):
            raise ValueError("Publisher response line extent changed")
    return {
        "format": "sukuyo_t2465_primary_quotation_check_v1",
        "publisher_html_response_sha256": fixture["publisher_html_response_sha256"],
        "publisher_html_response_bytes": fixture["publisher_html_response_bytes"],
        "publisher_response_line_anchor_count": fixture["html_line_anchor_count"],
        "publisher_response_line_extent": [
            fixture["html_line_anchor_first"],
            fixture["html_line_anchor_last"],
        ],
        "full_publisher_response_bytes_rechecked": publisher_html is not None,
        "selected_quotation_lines_checked": len(parser.lines),
        "cached_calendar_windows_exactly_match_downloaded_quotations": False,
        "cached_quotation_discrepancies": [
            {
                "locator": "T2465_.78.0030c26",
                "cached_terminal_text": "眞宿無改代也。",
                "downloaded_terminal_text": "眞宿無改代也｣",
                "meaning_changed": False,
                "old_cached_fixture_modified": False,
            }
        ],
        "downloaded_calendar_windows": [
            {"locator": cached["windows"][0]["locator"], "text": first},
            {"locator": cached["windows"][1]["locator"], "text": second},
        ],
        "edition_witness_note_html": parser.notes["0024a04"][0],
        "calendar_apparatus": [
            {"line": key, "notes_html": notes}
            for key, notes in parser.notes.items()
            if key != "0024a04"
        ],
        "calendar_window_sha256": [
            hashlib.sha256(text.encode()).hexdigest() for text in [first, second]
        ],
        "full_publisher_response_redistributed": False,
        "embedded_images_fetched": False,
        "facsimile_collation_complete": False,
        "independent_scholarly_acceptance": False,
        "scope": "Two calendar passages and five apparatus entries checked against a direct publisher response. A complete HTML response is not a manuscript, a facsimile collation or an independent resolution of half-clock and precedence questions.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publisher-html", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify_primary(args.publisher_html)
    data = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(data)
    else:
        print(data, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

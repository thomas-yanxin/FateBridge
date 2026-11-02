"""Extract compact circuit-group facts from captured official public pages.

No FateBridge imports or network access. Keep memberships and source hashes,
not complete teaching passages or claims about real people.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DICTIONARY_URL = "https://jovianarchive.com/pages/human-design-dictionary"
OVERVIEW_URL = "https://jovianarchive.com/pages/what-is-circuitry-in-human-design"


class Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.heading: str | None = None
        self.parts: list[str] = []
        self.key: str | None = None
        self.entries: dict[str, list[str]] = {}
        self.content: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "h4":
            self.heading, self.parts, self.key = tag, [], None

    def handle_data(self, text: str) -> None:
        self.content.append(text)
        if self.heading:
            self.parts.append(text)
        elif self.key:
            self.entries[self.key].append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag == self.heading:
            self.key = " ".join("".join(self.parts).split())
            if self.key in self.entries:
                raise ValueError("Duplicate glossary heading")
            self.entries[self.key] = []
            self.heading = None

    def entry(self, key: str) -> str:
        if key not in self.entries:
            raise ValueError("Required glossary heading absent: " + key)
        return " ".join(" ".join(self.entries[key]).split())


def build(dictionary_html: Path, overview_html: Path) -> dict[str, Any]:
    dictionary, overview = Page(), Page()
    dictionary.feed(dictionary_html.read_text())
    overview.feed(overview_html.read_text())
    individual = dictionary.entry("Individual")
    # These source anchors are independent of the implementation's mapping.
    if not all(
        token in individual
        for token in ("Knowing Circuit", "Centering Circuit", "Integration Channels")
    ):
        raise ValueError("Individual membership source anchors absent")
    collective = dictionary.entry("Collective")
    groups = dictionary.entry("Circuit Group")
    if not all(
        token in collective for token in ("Understanding Circuit", "Sensing Circuit")
    ):
        raise ValueError("Collective membership source anchors absent")
    if "Tribal (Tribal and Defense)" not in groups or not (
        "Tribal Ego Circuit" in dictionary.entry("Ego Circuit")
        and "minor Tribal Circuit" in dictionary.entry("Defense Circuit")
    ):
        raise ValueError("Tribal membership source anchors absent")
    overview_text = " ".join(" ".join(overview.content).split())
    start = overview_text.index("Individual Circuit Group (Empowerment)")
    end = overview_text.index("Collective Circuit Group (Sharing)", start)
    if "plus the Integration Channel" not in overview_text[start:end]:
        raise ValueError("Independent overview Integration anchor absent")
    return {
        "method_id": "jovian_public_circuit_group_membership_2026_v1",
        "publisher": "Jovian Archive",
        "author": "Jovian Archive public glossary and circuitry overview",
        "sources": {
            "dictionary": {
                "url": DICTIONARY_URL,
                "capture_sha256": hashlib.sha256(
                    dictionary_html.read_bytes()
                ).hexdigest(),
                "headings": [
                    "Individual",
                    "Collective",
                    "Circuit Group",
                    "Ego Circuit",
                    "Defense Circuit",
                ],
            },
            "overview": {
                "url": OVERVIEW_URL,
                "capture_sha256": hashlib.sha256(
                    overview_html.read_bytes()
                ).hexdigest(),
                "section": "Individual Circuit Group (Empowerment)",
            },
        },
        "groups": {
            "individual": ["individual_knowing", "individual_centering", "integration"],
            "collective": ["collective_understanding", "collective_sensing"],
            "tribal": ["tribal_ego", "tribal_defense"],
        },
        "integration_group": "individual",
        "integration_is_separately_reported_subset": True,
        "scope": "Group membership facts only. Integration has separate topology while included in Individual group totals. This does not independently verify all36 channel-to-circuit assignments, full teachings or predictive/psychological claims.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dictionary_html", type=Path)
    parser.add_argument("overview_html", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = (
        json.dumps(
            build(args.dictionary_html, args.overview_html),
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    target = ROOT / "src/fatebridge/data/human_design/circuit-group-2026-reference.json"
    if args.check:
        if target.read_text() != text:
            raise SystemExit("Circuit-group source facts changed")
    else:
        target.write_text(text)
    print(
        json.dumps(
            {"groups": 3, "integration_group": "individual", "checked": args.check}
        )
    )


if __name__ == "__main__":
    main()

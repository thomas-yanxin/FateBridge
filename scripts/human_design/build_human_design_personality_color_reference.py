"""Extract12ordered category labels and their actual Color dependencies.

No engine imports, psychological measurements or complete prose reproduction.
"""

import argparse
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
URLS = {
    "motivation": "https://jovianarchive.com/pages/the-gift-of-awareness-understanding-motivation-in-human-design",
    "view": "https://jovianarchive.com/pages/seeing-through-your-unique-perspective-understanding-view-in-human-design",
}


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.content = []
        self.strong = False
        self.parts = []
        self.labels = []

    def handle_starttag(self, tag, attrs):
        if tag == "strong":
            self.strong = True
            self.parts = []

    def handle_data(self, data):
        self.content.append(data)
        if self.strong:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == "strong" and self.strong:
            self.labels.append(" ".join("".join(self.parts).split()))
            self.strong = False


def build(motivation: Path, view: Path):
    sources = {}
    categories = {}
    for key, path in [("motivation", motivation), ("view", view)]:
        p = Page()
        p.feed(path.read_text())
        text = " ".join(" ".join(p.content).split())
        anchor = (
            "Motivation is determined by the Color of your Personality Sun"
            if key == "motivation"
            else "Color of your Personality Nodes"
        )
        if anchor not in text:
            raise ValueError("Missing original dependency anchor")
        labels = [
            m.groups()
            for s in p.labels
            if (m := re.fullmatch(r"([1-6])\. ([A-Za-z]+)", s))
        ]
        if [int(x[0]) for x in labels] != list(range(1, 7)):
            raise ValueError("Missing, duplicate or unordered category labels")
        categories[key] = [{"color": int(n), "source_term": name} for n, name in labels]
        sources[key] = {
            "url": URLS[key],
            "html_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "dependency": (
                "personality_sun_color"
                if key == "motivation"
                else "personality_nodes_color"
            ),
            "attribution": "Jovian Archive current public learning page, attributed to Ra Uru Hu; not a dated source manuscript",
        }
    return {
        "source_catalog_id": "human_design_public_personality_color_facts_v1",
        "publisher": "Jovian Archive",
        "sources": sources,
        "categories": categories,
        "scope": "Twelve category labels and two explicitly stated Color dependencies only. No clinical, cognitive or personality measurement, observed transference/distraction state, complete original teaching or empirical forecast is accepted.",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("motivation", type=Path)
    p.add_argument("view", type=Path)
    p.add_argument("--check", action="store_true")
    a = p.parse_args()
    value = json.dumps(build(a.motivation, a.view), ensure_ascii=False, indent=2) + "\n"
    target = ROOT / "src/fatebridge/data/human_design/personality-color-reference.json"
    if a.check:
        if not target.is_file() or target.read_text() != value:
            raise SystemExit("Personality Color reference drifted")
    else:
        target.write_text(value)


if __name__ == "__main__":
    main()

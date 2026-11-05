"""Extract factual profile/line metadata from independently captured public pages.

No FateBridge imports. This keeps headings, classifications and cycle markers,
not lecture transcripts, the384 gate-line readings or empirical assertions.
Explicit maintenance only; tests use the frozen compact facts offline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROFILE_URL = "https://jovianarchive.com/pages/understanding-profile-in-human-design"
LINES_URL = "https://jovianarchive.com/blogs/chart-interpretations-components/the-six-lines-of-the-hexagram"


class Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.heading: str | None = None
        self.parts: list[str] = []
        self.headings: list[tuple[str, str]] = []
        self.content: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in {"h2", "h3"}:
            self.heading, self.parts = tag, []

    def handle_data(self, data):
        self.content.append(data)
        if self.heading:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == self.heading:
            self.headings.append((tag, " ".join("".join(self.parts).split())))
            self.heading = None


def build(profile_html: Path, lines_html: Path) -> dict:
    profile_page, line_page = Page(), Page()
    profile_page.feed(profile_html.read_text())
    line_page.feed(lines_html.read_text())
    profiles, roles = [], {}
    angle = None
    for tag, text in profile_page.headings:
        if tag == "h2":
            angle = next(
                (
                    a
                    for title, a in [
                        ("Right Angle Profiles:", "right"),
                        ("Juxtaposition Profile:", "juxtaposition"),
                        ("Left Angle Profiles:", "left"),
                    ]
                    if text.startswith(title)
                ),
                None,
            )
        if tag != "h3" or not (
            m := re.fullmatch(r"([1-6])/([1-6]) \(([^/]+)/([^/]+)\)", text)
        ):
            continue
        if angle is None:
            raise ValueError("Profile has no independent angle heading")
        p, d = map(int, m.group(1, 2))
        profiles.append(
            {
                "profile": f"{p}/{d}",
                "personality_line": p,
                "design_line": d,
                "angle": angle,
            }
        )
        for line, role in [(p, m[3]), (d, m[4])]:
            if line in roles and roles[line] != role:
                raise ValueError("Conflicting archetype labels in source")
            roles[line] = role
    if (
        len(profiles) != 12
        or len({r["profile"] for r in profiles}) != 12
        or set(roles) != set(range(1, 7))
    ):
        raise ValueError("Incomplete independent profile headers")
    text = " ".join(" ".join(line_page.content).split())
    if (
        "completion of the lower trigram" not in text
        or "When we move to the upper trigram" not in text
    ):
        raise ValueError("Line trigram source anchors absent")
    saturn = re.search(r"Saturn cycle of approximately (\d+)[–—-](\d+) years", text)
    kiron = re.search(r"Kiron return between (\d+) and (\d+)", text)
    if not saturn or not kiron:
        raise ValueError("Approximate teaching-cycle source markers absent")
    return {
        "method_id": "jovian_public_profile_facts_2026_v1",
        "publisher": "Jovian Archive",
        "author": "Ra Uru Hu (publicly attributed teaching pages)",
        "sources": {
            "profile": {
                "url": PROFILE_URL,
                "capture_sha256": hashlib.sha256(profile_html.read_bytes()).hexdigest(),
                "facts": "12 profile headers, six archetype labels and their enclosing angle headings",
            },
            "six_lines": {
                "url": LINES_URL,
                "capture_sha256": hashlib.sha256(lines_html.read_bytes()).hexdigest(),
                "facts": "Lower/upper line groups and approximate Saturn/Kiron transition markers; only these compact facts adopted",
            },
        },
        "profiles": profiles,
        "line_archetypes": {str(k): roles[k] for k in sorted(roles)},
        "trigram_lines": {"lower": [1, 2, 3], "upper": [4, 5, 6]},
        "sixth_line_cycle_markers": {
            "saturn_return": {
                "approximate_teaching_age_years": list(map(int, saturn.group(1, 2)))
            },
            "kiron_return": {
                "approximate_teaching_age_years": list(map(int, kiron.group(1, 2)))
            },
            "event_dates_computed": False,
        },
        "scope": "Public header/factual metadata only. No complete lectures or384 line prose reproduced; no psychological measurements, fate certainty, accidents, biology, health, lifespan or event predictions adopted. Approximate teaching ages are not computed return dates.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile_html", type=Path)
    parser.add_argument("lines_html", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "src/fatebridge/data/human_design/profile-2026-reference.json",
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = build(args.profile_html, args.lines_html)
    if args.check:
        if json.loads(args.output.read_text()) != result:
            raise SystemExit("Frozen profile reference differs from source captures")
    else:
        args.output.write_bytes(
            (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
        )
    print(
        json.dumps(
            {
                "profiles": len(result["profiles"]),
                "lines": len(result["line_archetypes"]),
                "checked": args.check,
            }
        )
    )


if __name__ == "__main__":
    main()

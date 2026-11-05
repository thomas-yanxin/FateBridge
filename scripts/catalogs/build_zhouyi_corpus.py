"""Freeze and extract the public-domain Zhouyi transcription without an LLM.

Default: rebuild from frozen wikitext. --fetch explicitly refreshes source
revisions over the network; --check checks the installed corpus for drift.
The transcription is not a critical edition or a prediction benchmark.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests/fixtures/zhouyi-wikisource.json"
OUTPUT = ROOT / "src/fatebridge/data/classical/zhouyi.json"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def serialize(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def fetch(page: str) -> dict:
    query = urllib.parse.urlencode(
        {"action": "parse", "page": page, "prop": "wikitext|revid", "format": "json"}
    )
    request = urllib.request.Request(
        "https://zh.wikisource.org/w/api.php?" + query,
        headers={"User-Agent": "FateBridge/0.1 source-verification"},
    )
    with urllib.request.urlopen(request, timeout=40) as response:
        parsed = json.load(response)["parse"]
    raw = parsed["wikitext"]["*"]
    return {
        "title": parsed["title"],
        "revision": parsed["revid"],
        "source_url": "https://zh.wikisource.org/w/index.php?"
        + urllib.parse.urlencode({"title": parsed["title"], "oldid": parsed["revid"]}),
        "wikitext_sha256": sha(raw),
        "wikitext": raw,
    }


def fetch_chapters(names: list[str]) -> list[dict]:
    """Use two bulk revision requests instead of scraping 64 pages."""
    pages = {}
    for start in range(0, len(names), 32):
        query = urllib.parse.urlencode(
            {
                "action": "query",
                "prop": "revisions",
                "rvprop": "ids|content",
                "rvslots": "main",
                "format": "json",
                "titles": "|".join(names[start : start + 32]),
            }
        )
        request = urllib.request.Request(
            "https://zh.wikisource.org/w/api.php?" + query,
            headers={"User-Agent": "FateBridge/0.1 source-verification"},
        )
        with urllib.request.urlopen(request, timeout=40) as response:
            result = json.load(response)
        for page in result["query"]["pages"].values():
            revision = page["revisions"][0]
            raw = revision["slots"]["main"]["*"]
            pages[page["title"]] = {
                "title": page["title"],
                "revision": revision["revid"],
                "source_url": "https://zh.wikisource.org/w/index.php?"
                + urllib.parse.urlencode(
                    {"title": page["title"], "oldid": revision["revid"]}
                ),
                "wikitext_sha256": sha(raw),
                "wikitext": raw,
            }
    return [pages[name] for name in names]


def plain(raw: str) -> str:
    text = re.sub(r"<[^>]+>", "", raw)
    text = re.sub(r"-\{([^{}]+)\}-", r"\1", text)
    text = re.sub(r"\{\{\*\|([^{}]+)\}\}", r"〈\1〉", text)
    text = re.sub(r"\[\[(?:[^]|]+\|)?([^]]+)\]\]", r"\1", text)
    return html.unescape(text.replace("'''", "").replace("''", "")).strip()


def extract(page: dict, number: int) -> dict:
    raw = page["wikitext"]
    if sha(raw) != page["wikitext_sha256"]:
        raise ValueError(f"Source hash changed: {page['title']}")
    # Span tags may wrap across lines. Preserve wikitext list markers.
    text = re.sub(r"<[^>]+>", "", raw)
    sections = re.split(r"^\*'+彖曰[：:]'+", text, maxsplit=1, flags=re.M)
    if len(sections) != 2:
        raise ValueError(f"Missing 彖曰 delimiter: {page['title']}")
    scripture = sections[0]
    verses = [plain(x) for x in re.findall(r"^\*#(.*)$", scripture, re.M)]
    if len(verses) != (7 if number in (1, 2) else 6):
        raise ValueError(f"Wrong line count: {page['title']}: {verses}")
    lines = []
    for position, verse in enumerate(verses[:6], 1):
        match = re.fullmatch(r"(初[九六]|[九六][二三四五]|上[九六])[：:，](.+)", verse)
        if not match:
            raise ValueError(f"Unparsed line: {page['title']}: {verse}")
        label, content = match.groups()
        expected = {1: "初", 2: "二", 3: "三", 4: "四", 5: "五", 6: "上"}[position]
        if expected not in label:
            raise ValueError(f"Wrong line position: {verse}")
        lines.append({"position": position, "label": label, "text": content})
    guaci = "".join(
        plain(x) for x in re.findall(r"^\*{2,3}([^*#].*)$", scripture, re.M)
    )
    image_section = re.split(r"^\*'+象曰[：:]'+", sections[1], maxsplit=1, flags=re.M)[
        1
    ]
    image = plain(re.search(r"^\*\*([^*#].*)$", image_section, re.M).group(1))
    code = "".join("1" if "九" in line["label"] else "0" for line in lines)
    if not guaci or not image or any("{{" in s or "-{" in s for s in [guaci, image]):
        raise ValueError(f"Unparsed text: {page['title']}")
    special = None
    if len(verses) == 7:
        label, content = verses[6].split("：", 1)
        special = {"label": label, "text": content}
    return {
        "number": number,
        "name": page["title"].split("/", 1)[1],
        "code": code,
        "guaci": guaci,
        "daxiang": image,
        "yaoci": lines,
        "special": special,
        "source_url": page["source_url"],
        "source_revision": page["revision"],
        "source_wikitext_sha256": page["wikitext_sha256"],
    }


def build(source: dict) -> dict:
    chapters = []
    for number, page in enumerate(source["chapters"], 1):
        chapters.append(extract(page, number))
    if len(chapters) != 64 or len({c["code"] for c in chapters}) != 64:
        raise ValueError("Expected exactly 64 distinct six-line hexagrams")
    return {
        "corpus_id": "zhouyi_wikisource_v1",
        "title": "《周易》经文与《象传》大象，维基文库转录本",
        "source_kind": "public_domain_transcription",
        "edition_status": "转录本；未作影印底本逐字校勘，不声称校勘定本",
        "license": "Public-domain ancient text; Wikisource transcription attribution retained",
        "line_order": "初爻至上爻",
        "chapters": chapters,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.fetch:
        if args.check:
            parser.error("--fetch and --check cannot be combined")
        index = fetch("周易")
        # Unicode hexagram symbols identify King Wen order independently of
        # FateBridge's hexagram table or any production calculation.
        pairs = re.findall(r"([\u4dc0-\u4dff])\s*\[\[/([^]|]+)\|", index["wikitext"])
        names = {ord(symbol) - 0x4DC0 + 1: name for symbol, name in pairs}
        if set(names) != set(range(1, 65)):
            raise ValueError("Index must identify all 64 chapters")
        chapters = fetch_chapters(["周易/" + names[n] for n in range(1, 65)])
        source = {"index": index, "chapters": chapters}
        # Preserve fetched revision bytes even if a new transcription format
        # needs a parser repair; never replace the runtime corpus on failure.
        SOURCE.write_text(serialize(source), encoding="utf-8")
    corpus = build(json.loads(SOURCE.read_text(encoding="utf-8")))
    rendered = serialize(corpus)
    if args.check:
        if OUTPUT.read_text(encoding="utf-8") != rendered:
            raise SystemExit(
                "Zhouyi corpus drift; run scripts/catalogs/build_zhouyi_corpus.py"
            )
    else:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(rendered, encoding="utf-8")
    print("Zhouyi: 64 hexagrams, 384 line texts, 2 special texts; extraction verified")


if __name__ == "__main__":
    main()

"""Check maintained Markdown links, heading anchors, fences and JSON offline.

Run from any directory with the repository's Python interpreter. This checks
inline and reference Markdown links and HTML href/src attributes.
Remote URLs and prose claims are not checked.
Runtime examples and generated contracts have their own validation commands.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\[((?:[^\[\]\n]|!?\[[^\]\n]*\]\([^\n)]*\))*)\]\(([^\n]*?)\)")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
HEADING = re.compile(r"^ {0,3}#{1,6}\s+(.+?)(?:\s+#+)?\s*$")
REFERENCE = re.compile(r"!?\[([^\]\n]+)\]\[([^\]\n]*)\]")
DEFINITION = re.compile(r"^ {0,3}\[([^]]+)\]:\s*(<[^>]+>|\S+)")


class HtmlLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[int, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name in {"href", "src"} and value:
                self.links.append((self.getpos()[0], value))


@dataclass
class Document:
    anchors: set[str] = field(default_factory=set)
    links: list[tuple[int, str]] = field(default_factory=list)
    json_blocks: int = 0
    errors: list[str] = field(default_factory=list)


def inspect_markdown(text: str) -> Document:
    document = Document()
    html = HtmlLinks()
    definitions: dict[str, str] = {}
    references: list[tuple[int, str]] = []
    fence = ""
    language = ""
    opened_at = 0
    body: list[str] = []
    for number, line in enumerate(text.splitlines(), 1):
        marker = FENCE.match(line)
        if fence:
            html.feed("\n")
            if (
                marker
                and marker[1][0] == fence[0]
                and len(marker[1]) >= len(fence)
                and not marker[2].strip()
            ):
                if language == "json":
                    document.json_blocks += 1
                    try:
                        json.loads("\n".join(body))
                    except ValueError as error:
                        document.errors.append(f"{opened_at}: invalid JSON: {error}")
                fence = ""
            else:
                body.append(line)
            continue
        if marker:
            html.feed("\n")
            fence, language = marker[1], marker[2].strip().lower()
            opened_at, body = number, []
            continue
        heading = HEADING.match(line)
        if heading:
            title = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", heading[1])
            slug = re.sub(r"[^\w -]", "", title.lower()).replace(" ", "-")
            anchor, suffix = slug, 0
            while anchor in document.anchors:
                suffix += 1
                anchor = f"{slug}-{suffix}"
            document.anchors.add(anchor)
        # Code spans are literal even when they contain Markdown-like text.
        prose = re.sub(r"(`+).*?\1", "", line)
        html.feed(prose + "\n")
        definition = DEFINITION.match(prose)
        if definition:
            key = " ".join(definition[1].lower().split())
            definitions.setdefault(key, definition[2].strip("<>"))
            continue
        for match in REFERENCE.finditer(prose):
            key = " ".join((match[2] or match[1]).lower().split())
            references.append((number, key))
        for match in LINK.finditer(prose):
            target = match[2].strip()
            if target.startswith("<") and ">" in target:
                target = target[1 : target.index(">")]
            else:
                target = target.split(maxsplit=1)[0] if target else ""
            document.links.append((number, target))
    html.close()
    document.links.extend(html.links)
    for number, key in references:
        if key in definitions:
            document.links.append((number, definitions[key]))
        else:
            document.errors.append(f"{number}: undefined link reference: {key}")
    if fence:
        document.errors.append(f"{opened_at}: unclosed code fence")
    return document


def markdown_paths() -> list[Path]:
    paths = set(ROOT.glob("*.md")) | set((ROOT / "skills").rglob("*.md"))
    paths.update(
        path
        for path in (ROOT / "scripts/README.md", ROOT / "tests/README.md")
        if path.is_file()
    )
    for current, directories, files in os.walk(ROOT / "docs", followlinks=False):
        directories[:] = [
            name
            for name in directories
            if name != "reviews"
            and name != "validation"
            and not (Path(current) / name).is_symlink()
        ]
        paths.update(Path(current) / name for name in files if name.endswith(".md"))
    return sorted(paths)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    paths = markdown_paths()
    documents = {
        path.resolve(): inspect_markdown(path.read_text(encoding="utf-8"))
        for path in paths
    }
    errors = []
    checked_links = 0
    for path, document in documents.items():
        label = path.relative_to(ROOT)
        errors.extend(f"{label}:{error}" for error in document.errors)
        for number, target in document.links:
            url = urlsplit(target)
            if url.scheme or url.netloc:
                continue
            checked_links += 1
            destination = (
                (path.parent / unquote(url.path)).resolve() if url.path else path
            )
            if not destination.exists():
                errors.append(f"{label}:{number}: missing local target: {target}")
            elif url.fragment and destination.suffix == ".md":
                linked = documents.get(destination)
                if linked is None:
                    linked = inspect_markdown(destination.read_text(encoding="utf-8"))
                if unquote(url.fragment) not in linked.anchors:
                    errors.append(f"{label}:{number}: missing heading anchor: {target}")
    json_paths = sorted((ROOT / "docs" / "examples").rglob("*.json")) + sorted(
        (ROOT / "examples").rglob("*.json")
    )
    for path in json_paths:
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except ValueError as error:
            errors.append(f"{path.relative_to(ROOT)}: invalid JSON: {error}")
    if errors:
        print("\n".join(errors))
        return 1
    blocks = sum(document.json_blocks for document in documents.values())
    print(
        f"OK: {len(documents)} Markdown files, {checked_links} local links, "
        f"{blocks} JSON blocks, {len(json_paths)} JSON example files"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Check maintained Markdown links, heading anchors, fences and JSON offline.

Run from any directory with the repository's Python interpreter. This checks
inline Markdown links (including badge links), not remote URLs or prose claims.
Runtime examples and generated contracts have their own validation commands.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\[((?:[^\[\]\n]|!?\[[^\]\n]*\]\([^\n)]*\))*)\]\(([^\n]*?)\)")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
HEADING = re.compile(r"^ {0,3}#{1,6}\s+(.+?)(?:\s+#+)?\s*$")


@dataclass
class Document:
    anchors: set[str] = field(default_factory=set)
    links: list[tuple[int, str]] = field(default_factory=list)
    json_blocks: int = 0
    errors: list[str] = field(default_factory=list)


def inspect_markdown(text: str) -> Document:
    document = Document()
    fence = ""
    language = ""
    opened_at = 0
    body: list[str] = []
    for number, line in enumerate(text.splitlines(), 1):
        marker = FENCE.match(line)
        if fence:
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
        for match in LINK.finditer(prose):
            target = match[2].strip()
            if target.startswith("<") and ">" in target:
                target = target[1 : target.index(">")]
            else:
                target = target.split(maxsplit=1)[0] if target else ""
            document.links.append((number, target))
    if fence:
        document.errors.append(f"{opened_at}: unclosed code fence")
    return document


def main() -> int:
    paths = sorted(
        set(ROOT.glob("*.md"))
        | {
            path
            for path in (ROOT / "docs").rglob("*.md")
            if "reviews" not in path.parts
        }
        | set((ROOT / "skills").rglob("*.md"))
    )
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
    json_paths = sorted((ROOT / "docs" / "examples").glob("*.json")) + sorted(
        (ROOT / "examples").glob("*.json")
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

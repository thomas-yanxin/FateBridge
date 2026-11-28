"""Check local links, heading anchors, fences and JSON in maintained Markdown."""

from __future__ import annotations

import argparse
import json
import os
import re
import types
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Annotated, Any, Union, get_args, get_origin
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\[((?:[^\[\]\n]|!?\[[^\]\n]*\]\([^\n)]*\))*)\]\(([^\n]*?)\)")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
HEADING = re.compile(r"^ {0,3}#{1,6}\s+(.+?)(?:\s+#+)?\s*$")
REFERENCE = re.compile(r"!?\[([^\]\n]+)\]\[([^\]\n]*)\]")
DEFINITION = re.compile(r"^ {0,3}\[([^]]+)\]:\s*(<[^>]+>|\S+)")


class HtmlLinks(HTMLParser):
    """Collect href/src links and element id anchors from inline HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[int, str]] = []
        self.anchors: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name in {"href", "src"} and value:
                self.links.append((self.getpos()[0], value))
            elif name == "id" and value:
                self.anchors.add(value)


@dataclass
class Document:
    """Parsed anchors, links, JSON block count and syntax errors for one file."""

    anchors: set[str] = field(default_factory=set)
    links: list[tuple[int, str]] = field(default_factory=list)
    json_blocks: int = 0
    errors: list[str] = field(default_factory=list)


def inspect_markdown(text: str) -> Document:
    """Extract headings, links, fences and JSON block validity from Markdown text."""
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
                    except json.JSONDecodeError as error:
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
    document.anchors.update(html.anchors)
    document.links.extend(html.links)
    for number, key in references:
        if key in definitions:
            document.links.append((number, definitions[key]))
        else:
            document.errors.append(f"{number}: undefined link reference: {key}")
    if fence:
        document.errors.append(f"{opened_at}: unclosed code fence")
    return document


_QIMEN_STALE_ROOTS = frozenset({"evidence", "qualification", "rulesets", "rule_trace"})
_INDEX_SUFFIX_RE = re.compile(r"\[(?:[a-zA-Z_*]|\d*)\]$")
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")


def _extract_inline_code_tokens(text: str) -> list[tuple[int, str]]:
    """Extract (line_number, inline_code_text) outside fenced code blocks."""
    tokens: list[tuple[int, str]] = []
    fence = ""
    for number, line in enumerate(text.splitlines(), 1):
        marker = FENCE.match(line)
        if fence:
            if (
                marker
                and marker[1][0] == fence[0]
                and len(marker[1]) >= len(fence)
                and not marker[2].strip()
            ):
                fence = ""
            continue
        if marker:
            fence = marker[1]
            continue
        for match in _INLINE_CODE_RE.finditer(line):
            tokens.append((number, match[1].strip()))
    return tokens


def _unwrap_model_or_open(annotation: Any) -> tuple[type[Any] | None, bool]:
    """Return (BaseModel subclass if concrete, is_open_container) from a type annotation."""
    from pydantic import BaseModel

    if annotation is None or annotation is type(None):
        return None, False
    origin = get_origin(annotation)
    if origin is Annotated:
        return _unwrap_model_or_open(get_args(annotation)[0])
    if origin in (Union, types.UnionType):
        models: list[type[Any]] = []
        open_container = False
        for arg in get_args(annotation):
            if arg is type(None):
                continue
            sub_model, sub_open = _unwrap_model_or_open(arg)
            if sub_model is not None:
                models.append(sub_model)
            if sub_open:
                open_container = True
        if len(models) == 1 and not open_container:
            return models[0], False
        return (models[0] if len(models) == 1 else None), open_container or len(
            models
        ) > 1
    if origin in (list, tuple, set, frozenset):
        args = get_args(annotation)
        return _unwrap_model_or_open(args[0]) if args else (None, True)
    if origin is dict:
        return None, True
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation, False
    if annotation is dict:
        return None, True
    return None, False


def _validate_model_path(model_cls: type[Any], segments: list[str]) -> str | None:
    """Validate dotted segments against Pydantic BaseModel fields; return error detail or None."""
    current: type[Any] | None = model_cls
    for idx, raw_seg in enumerate(segments):
        seg = _INDEX_SUFFIX_RE.sub("", raw_seg)
        if not seg or not seg.isidentifier():
            return None
        if current is None:
            return None
        fields = current.model_fields
        if seg not in fields:
            prefix = ".".join(segments[:idx]) if idx else current.__name__
            return f"unknown schema field `{seg}` under `{prefix}`"
        next_model, is_open = _unwrap_model_or_open(fields[seg].annotation)
        if idx == len(segments) - 1:
            return None
        if next_model is not None:
            current = next_model
        elif is_open:
            return None
        else:
            return f"field `{seg}` has no child schema attributes for `{'.'.join(segments[idx + 1:])}`"
    return None


def check_interpretation_schema_paths(root: Path = ROOT) -> list[str]:
    """Validate documented JSON schema paths in docs/interpretation against live models."""
    interp_dir = root / "docs" / "interpretation"
    if not interp_dir.is_dir():
        return []
    from fatebridge.core.contracts.qimen import Qimen, QimenPalace
    from fatebridge.core.response_models import output_model_for

    qimen_output = output_model_for("qimen")
    unambiguous_roots = {
        "liuyao_evidence": output_model_for("liuyao"),
        "bazi_birth": output_model_for("bazi_birth_chart"),
        "runyear": output_model_for("liuren_yearly_timing"),
        "jinkou": output_model_for("jinkou"),
    }
    errors: list[str] = []
    for md_path in sorted(interp_dir.rglob("*.md")):
        rel = md_path.relative_to(root).as_posix()
        is_qimen_doc = rel == "docs/interpretation/zhanbu/qimen-evidence.md"
        tokens = _extract_inline_code_tokens(md_path.read_text(encoding="utf-8"))
        for line_no, token in tokens:
            if (
                "." not in token
                or any(
                    ch in token
                    for ch in (" ", "=", "(", ")", "/", "<", ">", "{", "}", "*", ":")
                )
                or token.startswith(".")
                or token.endswith(".")
            ):
                continue
            segments = token.split(".")
            first = _INDEX_SUFFIX_RE.sub("", segments[0])
            if not first.isidentifier():
                continue
            if is_qimen_doc:
                if first in _QIMEN_STALE_ROOTS:
                    errors.append(
                        f"{rel}:{line_no}: retired/nonexistent qimen schema path `{token}`"
                    )
                    continue
                if first == "qimen":
                    msg = _validate_model_path(qimen_output, segments)
                    if msg:
                        errors.append(f"{rel}:{line_no}: {msg} (`{token}`)")
                    continue
                if first in {"palaces", "palace"}:
                    msg = _validate_model_path(QimenPalace, segments[1:])
                    if msg:
                        errors.append(f"{rel}:{line_no}: {msg} (`{token}`)")
                    continue
                if first in Qimen.model_fields:
                    msg = _validate_model_path(Qimen, segments)
                    if msg:
                        errors.append(f"{rel}:{line_no}: {msg} (`{token}`)")
                    continue
            if first in unambiguous_roots:
                msg = _validate_model_path(unambiguous_roots[first], segments)
                if msg:
                    errors.append(f"{rel}:{line_no}: {msg} (`{token}`)")
    return errors


def markdown_paths() -> list[Path]:
    """Return sorted maintained Markdown files checked by the documentation linter."""
    paths = set(ROOT.glob("*.md"))
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
    """Validate links, anchors, fences and example JSON across maintained docs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    paths = markdown_paths()
    documents = {
        path.resolve(): inspect_markdown(path.read_text(encoding="utf-8"))
        for path in paths
    }
    errors: list[str] = []
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
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            errors.append(f"{path.relative_to(ROOT)}: invalid JSON: {error}")
    blocks = sum(document.json_blocks for document in documents.values())
    errors.extend(check_interpretation_schema_paths(ROOT))
    if errors:
        print("\n".join(errors))
        return 1
    print(
        f"OK: {len(documents)} Markdown files, {checked_links} local links, "
        f"{blocks} JSON blocks, {len(json_paths)} JSON example files"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

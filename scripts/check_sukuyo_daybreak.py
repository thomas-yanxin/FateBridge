"""Verify all selected dawn quotations and linked apparatus from four captures."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as E

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/data/sukuyo-daybreak-before-production-v75.json"
SOURCE = ROOT / "src/fatebridge/data/sukuyo_daybreak_sources.json"
R1_SHA256 = "49bfe3aa0b1e5187f06e5abec3b03530768423385422d53634228a584b6fc5af"
R2_SHA256 = "08ff13f9f24581ca2432a250c2e1611217edbe0126df88a0c3b15df8a8f6093d"
R3_SHA256 = "d32827a09183c03822f00daa99782f0afc0d8029d9b0fcee0b0432196155c9e8"
NS = "{http://www.tei-c.org/ns/1.0}"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main_lines(tree: E.Element, edition: str) -> dict[str, Any]:
    body = tree.find(".//" + NS + "body")
    if body is None:
        raise ValueError("缺少TEI正文")
    lines: dict[str, Any] = {}
    current: str | None = None

    def visit(node: E.Element) -> None:
        nonlocal current
        if node.tag == NS + "lb" and node.get("ed") == edition:
            current = node.attrib["n"]
            lines.setdefault(current, {"main": "", "inline": []})
        if node.text and current is not None:
            lines[current]["main"] += node.text
        for child in node:
            if child.tag == NS + "note":
                if child.get("place") == "inline" and current is not None:
                    lines[current]["inline"].append(
                        "".join("".join(child.itertext()).split())
                    )
            else:
                visit(child)
            if child.tail and current is not None:
                lines[current]["main"] += child.tail

    visit(body)
    return {
        k: {"main": "".join(v["main"].split()), "inline": v["inline"]}
        for k, v in lines.items()
    }


def anchor_lines(tree: E.Element, edition: str) -> tuple[dict[str, str], int]:
    body = tree.find(".//" + NS + "body")
    if body is None:
        raise ValueError("缺少TEI正文")
    anchors: dict[str, str] = {}
    current = ""
    unaddressable = 0
    for node in body.iter():
        if node.tag == NS + "lb" and node.get("ed") == edition:
            current = node.attrib["n"]
        if node.tag == NS + "anchor" and current:
            identity = node.get(XML_ID)
            if identity is None:
                unaddressable += 1
            else:
                anchors[identity] = current
    return anchors, unaddressable


def verify(
    captures: dict[str, Path], apparatus_reference: Path, header_reference: Path
) -> dict[str, Any]:
    raw, supplement = FIXTURE.read_bytes(), apparatus_reference.read_bytes()
    if sha(raw) != R1_SHA256 or sha(supplement) != R2_SHA256:
        raise ValueError("生产前来源参考或校勘补充改变")
    reference = json.loads(raw)
    apparatus = json.loads(supplement)["selected_apparatus"]
    header_raw = header_reference.read_bytes()
    if sha(header_raw) != R3_SHA256:
        raise ValueError("题头署名的生产前参考改变")
    header = json.loads(header_raw)["header_attribution"]
    package = json.loads(SOURCE.read_bytes())
    if package != {
        "source_data": reference["source_bundle"],
        "selected_apparatus": apparatus,
        "header_attribution": header,
    }:
        raise ValueError("运行资料不等于两个改码前来源参考")
    sources = reference["source_bundle"]["sources"]
    if set(captures) != {r["capture_file"] for r in sources}:
        raise ValueError("须核验全部四份具名捕获，不接受通过子集")
    records = []
    unaddressable_anchors = {}
    for src in sources:
        captured = captures[src["capture_file"]].read_bytes()
        if sha(captured) != src["sha256"] or len(captured) != src["bytes"]:
            raise ValueError("捕获身份改变：" + src["id"])
        tree = E.fromstring(captured)
        actual_authors = [
            "".join(node.itertext()).strip()
            for node in tree.findall(".//" + NS + "titleStmt/" + NS + "author")
        ]
        claimed_header = next(
            row for row in header["sources"] if row["source_id"] == src["id"]
        )
        if actual_authors != claimed_header["title_stmt_author_literals"]:
            raise ValueError("题头撰译署名不符")
        body_bylines = {
            "".join(node.itertext()).strip()
            for node in tree.findall(".//" + NS + "body//" + NS + "byline")
        }
        if not set(claimed_header["selected_body_bylines"]) <= body_bylines:
            raise ValueError("正文所选署名不在原文")
        lines = main_lines(tree, src["id"][0])
        ranges = []
        for window in src["windows"].values():
            first, last = window["locator"].split("_", 1)[1].split("-")
            ranges.append((first, last))
            selected = {n: v for n, v in sorted(lines.items()) if first <= n <= last}
            if (
                "".join(v["main"] for v in selected.values()) != window["main_literal"]
                or {n: v["inline"] for n, v in selected.items() if v["inline"]}
                != window["inline_notes"]
            ):
                raise ValueError("正文或inline层不符：" + window["locator"])
        body, back = tree.find(".//" + NS + "body"), tree.find(".//" + NS + "back")
        if body is None or back is None:
            raise ValueError("缺少正文或校勘层")
        anchors, unaddressable = anchor_lines(tree, src["id"][0])
        unaddressable_anchors[src["id"]] = unaddressable
        for node in back.iter():
            if node.tag not in {NS + "note", NS + "app"}:
                continue
            targets = (node.get("target") or node.get("from") or "").split()
            positions = [
                anchors[t.lstrip("#")] for t in targets if t.lstrip("#") in anchors
            ]
            if any(a <= n <= b for n in positions for a, b in ranges):
                records.append(
                    {
                        "source_id": src["id"],
                        "body_anchor_lines": positions,
                        "kind": node.tag.rsplit("}", 1)[-1],
                        "attributes": dict(node.attrib),
                        "text_with_inline_content": "".join(
                            "".join(node.itertext()).split()
                        ),
                        "xml_element": E.tostring(node, encoding="unicode"),
                        "scope": "Actual back-matter record linked to selected body window, not independently acquired printed witness.",
                    }
                )
    if records != apparatus["records"]:
        raise ValueError("全部所选后置记录不符，不得折叠原注、改注或读法层")
    return {
        "all_four_captures_verified": True,
        "selected_windows": 5,
        "all_linked_postposed_records_verified": len(records),
        "unaddressable_anchor_counts": unaddressable_anchors,
        "R1_sha256": R1_SHA256,
        "R2_sha256": R2_SHA256,
        "R3_sha256": R3_SHA256,
        "source_bundle_sha256": sha(SOURCE.read_bytes()),
        "new_independent_measurements": 0,
        "ancient_clock_or_half_or_priority_established": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", action="append", required=True)
    parser.add_argument("--apparatus-reference", type=Path, required=True)
    parser.add_argument("--header-reference", type=Path, required=True)
    args = parser.parse_args()
    captures = {}
    for pair in args.capture:
        name, path = pair.split("=", 1)
        if name in captures:
            raise ValueError("重复捕获")
        captures[name] = Path(path)
    print(
        json.dumps(
            verify(captures, args.apparatus_reference, args.header_reference),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

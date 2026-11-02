"""Verify source identities and frozen electronic passages without emending editions."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sanskrit_editions import (
    ADJUDICATION_SHA256,
    REFERENCE_SHA256,
    sanskrit_edition_reference,
)

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "tests/fixtures/sukuyo-sanskrit-before-production-v80.json"


class TextReader(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in {"script", "style"}:
            self.skip += 1
        if tag in {"br", "p", "div"} and not self.skip:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self.skip -= 1

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.parts.append(data)


def parse_titus(raw: bytes) -> dict[str, Any]:
    decoded = raw.decode("utf-8", errors="surrogateescape")
    invalid = []
    for index, char in enumerate(decoded):
        if 0xDC80 <= ord(char) <= 0xDCFF:
            invalid.append(
                {
                    "byte_offset": len(
                        decoded[:index].encode("utf-8", errors="surrogateescape")
                    ),
                    "hex": format(ord(char) - 0xDC00, "02x"),
                }
            )
    decoded = "".join(
        (
            "[BYTE-" + format(ord(c) - 0xDC00, "02X") + "]"
            if 0xDC80 <= ord(c) <= 0xDCFF
            else c
        )
        for c in decoded
    )
    reader = TextReader()
    reader.feed(decoded)
    records = []
    occurrences: dict[tuple[str, int], int] = {}
    part = ""
    paragraph = 0
    for line in "".join(reader.parts).splitlines():
        sub = re.fullmatch(r"Subchapter: (I|II)\s*", line)
        if sub:
            part = sub[1]
        heading = re.match(r"Paragraph: (\d+)", line)
        if heading:
            paragraph = int(heading[1])
            key = part, paragraph
            occurrences[key] = occurrences.get(key, 0) + 1
        verse = re.match(r"Verse: ([^\s]+)\s+(.*)", line)
        if verse and part and paragraph:
            records.append(
                {
                    "part": part,
                    "paragraph": paragraph,
                    "paragraph_occurrence": occurrences[(part, paragraph)],
                    "verse": verse[1],
                    "text": verse[2],
                }
            )
    return {"records": records, "invalid_utf8_bytes": invalid}


def verify(captures: dict[str, Path]) -> dict[str, Any]:
    raw = REFERENCE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != REFERENCE_SHA256:
        raise ValueError("生产前来源参考改变")
    first = json.loads(raw)
    if set(captures) != {r["id"] for r in first["captures"]}:
        raise ValueError("须核验全部四份捕获，不接受通过子集")
    adjudication_raw = (
        REFERENCE.parent / "sukuyo-sanskrit-adjudication-before-c-v80.json"
    ).read_bytes()
    if hashlib.sha256(adjudication_raw).hexdigest() != ADJUDICATION_SHA256:
        raise ValueError("独立核读后的修正参考改变")
    adjudication = json.loads(adjudication_raw)
    current = sanskrit_edition_reference()
    if (
        current["source_data"] != adjudication["facts"]
        or current["captures"] != first["captures"]
    ):
        raise ValueError("运行来源与独立冻结参考不符")
    if current["conditional_products"] != adjudication["expected_products"]:
        raise ValueError("版本条件乘积不符")
    anomalies = {}
    for row in first["captures"]:
        source = captures[row["id"]].read_bytes()
        if (
            len(source) != row["bytes"]
            or hashlib.sha256(source).hexdigest() != row["sha256"]
        ):
            raise ValueError("捕获身份改变：" + row["id"])
        if row["id"].endswith(".html"):
            parsed = parse_titus(source)
            anomalies[row["id"]] = parsed["invalid_utf8_bytes"]
            if row["id"] == "titus-1954-roman.html":
                expected = first["titus_selected_records"]
                keys = {
                    (r["part"], r["paragraph"], r["paragraph_occurrence"])
                    for r in expected
                }
                selected = [
                    r
                    for r in parsed["records"]
                    if (r["part"], r["paragraph"], r["paragraph_occurrence"]) in keys
                ]
                if selected != expected:
                    raise ValueError("全部所选电子原文及重复编号次序不符")
    return {
        "all_four_capture_identities_verified": True,
        "all_frozen_roman_records_verified": len(first["titus_selected_records"]),
        "raw_invalid_utf8_bytes_preserved_and_reported": anomalies,
        "reference_sha256": REFERENCE_SHA256,
        "adjudication_sha256": ADJUDICATION_SHA256,
        "source_bundle_sha256": current["source_bundle_sha256"],
        "conditional_products": current["conditional_products"],
        "automatic_pdf_transcription_or_full_collation_verified": False,
        "clock_half_priority_or_real_world_efficacy_established": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", action="append", required=True)
    args = parser.parse_args()
    captures = {}
    for arg in args.capture:
        name, path = arg.split("=", 1)
        if name in captures:
            raise ValueError("重复来源名")
        captures[name] = Path(path)
    print(json.dumps(verify(captures), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

"""Verify selected T1299 Taibai quotations and optional private full captures."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if not __package__:
    sys.path.insert(0, str(ROOT))

from scripts.audit_sukuyo_t2465_primary import SATQuotationParser

FIXTURE = ROOT / "tests/data/sukuyo-taibai-primary.json"
NS = {"t": "http://www.tei-c.org/ns/1.0"}
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"


def _fragment(text: str) -> ET.Element:
    wrapper = '<root xmlns="http://www.tei-c.org/ns/1.0" xmlns:cb="http://www.cbeta.org/ns/1.0">'
    return ET.fromstring(wrapper + text + "</root>")[0]


def _render(node: ET.Element, apps: list[ET.Element], ming: bool) -> str:
    parts: list[str] = []
    anchors: dict[str, int] = {}

    def walk(current: ET.Element) -> None:
        if current.tag.endswith("}anchor"):
            anchors[current.attrib[XML_ID]] = sum(map(len, parts))
        if current.text:
            parts.append(current.text)
        for child in current:
            walk(child)
            if child.tail:
                parts.append(child.tail)

    walk(node)
    text = "".join(parts)
    edits = []
    if ming:
        for app in apps:
            begin, end = app.attrib["from"].lstrip("#"), app.attrib["to"].lstrip("#")
            if begin in anchors and end in anchors:
                reading = next(
                    r
                    for r in app.findall("t:rdg", NS)
                    if "#wit1" in r.attrib.get("wit", "").split()
                )
                edits.append(
                    (anchors[begin], anchors[end], "".join(reading.itertext()))
                )
        for begin_offset, end_offset, replacement in sorted(edits, reverse=True):
            text = text[:begin_offset] + replacement + text[end_offset:]
    return re.sub(r"\s+", "", text)


def verify_primary(
    source_xml: Path | None = None, publisher_html: Path | None = None
) -> dict[str, Any]:
    fixture = json.loads(FIXTURE.read_bytes())
    apps = [_fragment(text) for text in fixture["selected_apparatus_xml"]]
    if len(apps) != 13:
        raise ValueError("Taibai apparatus is incomplete")
    for app, expected in zip(apps, fixture["selected_apparatus"]):
        lemma = app.find("t:lem", NS)
        reading = next(
            r
            for r in app.findall("t:rdg", NS)
            if "#wit1" in r.attrib.get("wit", "").split()
        )
        if (
            lemma is None
            or {
                "begin": app.attrib["from"].lstrip("#"),
                "end": app.attrib["to"].lstrip("#"),
                "corresp": app.get("corresp"),
                "taisho_text": _render(lemma, [], False),
                "ming_text": _render(reading, [], False),
            }
            != expected
        ):
            raise ValueError("Apparatus metadata differs from its raw XML")
    paragraphs = [_fragment(text) for text in fixture["selected_xml_fragments"]]
    if len(paragraphs) != 12:
        raise ValueError("Taibai source paragraph selection changed")
    for paragraph, expected in zip(paragraphs, fixture["selected_xml_paragraphs"]):
        if (
            paragraph.attrib[XML_ID] != expected["xml_id"]
            or _render(paragraph, apps, False) != expected["taisho_text"]
            or _render(paragraph, apps, True) != expected["ming_apparatus_reading"]
        ):
            raise ValueError("Taibai paragraph/apparatus reconstruction differs")
    parser = SATQuotationParser()
    for row in fixture["selected_html_quotations"]:
        parser.feed(row["html"])
    expected_lines = {"0399b29", *[f"0399c{n:02}" for n in range(1, 19)]}
    if set(parser.lines) != expected_lines:
        raise ValueError("SAT Taibai quotation line set changed")
    source = json.loads(
        (ROOT / "src/fatebridge/data/sukuyo_t1299_taibai.json").read_bytes()
    )
    if source["source_sha256"] != fixture["source_sha256"] or len(source["rows"]) != 10:
        raise ValueError("Taibai source/table identity differs")
    for row, primary in zip(source["rows"], fixture["selected_xml_paragraphs"][1:11]):
        if (
            row["taisho_text"] != primary["taisho_text"]
            or row["ming_apparatus_text"] != primary["ming_apparatus_reading"]
        ):
            raise ValueError("Runtime Taibai table differs from the printed row")
        sat = re.sub(
            r"[\s＊]+", "", "".join(parser.lines[primary["locator"].split("_")[-1][1:]])
        )
        if sat != row["taisho_text"]:
            raise ValueError("SAT and CBETA Taibai table rows differ")
    if (
        source["apparatus"] != fixture["selected_apparatus"]
        or source["publisher_primary"]["known_apparatus_literal_differences"]
        != fixture["publisher_apparatus_literal_findings"]
    ):
        raise ValueError("Source apparatus or recorded literal differences changed")
    doctrine = fixture["selected_xml_paragraphs"][-1]
    if (
        source["doctrine"]["taisho_text"] != doctrine["taisho_text"]
        or source["doctrine"]["ming_apparatus_reading"]
        != doctrine["ming_apparatus_reading"]
    ):
        raise ValueError("Taibai doctrine does not retain both selected readings")
    if (
        source["publisher_primary"]["response_sha256"]
        != fixture["publisher_html_response_sha256"]
        or source["publisher_primary"]["response_bytes"]
        != fixture["publisher_html_response_bytes"]
    ):
        raise ValueError("Runtime publisher reference fingerprint differs")
    deletion = next(a for a in apps if a.attrib["from"] == "#beg0399022")
    deletion_lemma = deletion.find("t:lem", NS)
    if (
        deletion_lemma is None
        or "".join(deletion_lemma.itertext()).strip() == ""
        or _render(paragraphs[10], apps, True) != ""
    ):
        raise ValueError("Ming sky-row deletion was lost")
    if (
        "年疫死後多虚消耗" not in parser.notes["0399c13"][0]
        or "巳來" not in parser.notes["0399c13"][0]
    ):
        raise ValueError("SAT literal apparatus findings were normalized away")
    if source_xml:
        raw = source_xml.read_bytes()
        if hashlib.sha256(raw).hexdigest() != fixture["source_sha256"] or any(
            text not in raw.decode("utf-8")
            for text in [
                *fixture["selected_xml_fragments"],
                *fixture["selected_apparatus_xml"],
            ]
        ):
            raise ValueError("Private full XML differs from its selected source bytes")
    if publisher_html:
        raw = publisher_html.read_bytes()
        if (
            hashlib.sha256(raw).hexdigest() != fixture["publisher_html_response_sha256"]
            or len(raw) != fixture["publisher_html_response_bytes"]
            or any(
                row["html"] not in raw.decode("utf-8")
                for row in fixture["selected_html_quotations"]
            )
        ):
            raise ValueError(
                "Private full SAT response differs from selected quotations"
            )
        if (
            len(set(re.findall(r'<a name="(\d{4}[abc]\d\d)"', raw.decode("utf-8"))))
            != fixture["publisher_html_line_anchor_count"]
        ):
            raise ValueError("SAT response line extent changed")
    return {
        "format": "sukuyo_taibai_primary_check_v1",
        "source_xml_sha256": fixture["source_sha256"],
        "full_source_xml_bytes_rechecked": source_xml is not None,
        "publisher_html_response_sha256": fixture["publisher_html_response_sha256"],
        "publisher_html_response_bytes": fixture["publisher_html_response_bytes"],
        "publisher_response_text_extent": fixture["publisher_html_line_anchor_extent"],
        "complete_t1299_text_response": False,
        "full_publisher_response_bytes_rechecked": publisher_html is not None,
        "selected_xml_paragraphs": len(paragraphs),
        "selected_sat_quotation_lines": len(parser.lines),
        "selected_apparatus_records": len(apps),
        "main_table_rows_agree_after_annotation_and_space_removal": True,
        "exact_cross_database_apparatus_identity": False,
        "retained_apparatus_literal_findings": fixture[
            "publisher_apparatus_literal_findings"
        ],
        "ming_missing_days": fixture["ming_missing_days"],
        "independent_ming_edition_or_facsimile_collation": False,
        "movement_alignment_definition_established": False,
        "scope": "Selected electronic primary table and apparatus only. Raw quotations and known apparatus differences remain distinct; no physical Venus, historical daybreak or movement-alignment acceptance.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-xml", type=Path)
    parser.add_argument("--publisher-html", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify_primary(args.source_xml, args.publisher_html)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()

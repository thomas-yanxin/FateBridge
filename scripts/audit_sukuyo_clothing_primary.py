"""Verify selected clothing main text and three apparatus records, offline."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if not __package__:
    sys.path.insert(0, str(ROOT))

from scripts.audit_sukuyo_t2465_primary import SATQuotationParser
from scripts.audit_sukuyo_taibai_primary import NS, XML_ID, _fragment, _render

FIXTURE = ROOT / "tests/fixtures/sukuyo-clothing-primary.json"
DATA = ROOT / "src/fatebridge/data/sukuyo_t1299_clothing.json"


def _compact(text: str) -> str:
    return re.sub(r"[\s，。、：；（）＊]", "", text)


def verify_primary(capture_dir: Path | None = None) -> dict[str, Any]:
    fixture = json.loads(FIXTURE.read_bytes())
    source = json.loads(DATA.read_bytes())
    apps = [_fragment(raw) for raw in fixture["selected_apparatus_xml"]]
    if len(apps) != 3:
        raise ValueError("Clothing apparatus selection changed")
    for app, expected in zip(apps, fixture["selected_apparatus"]):
        lemma, reading = app.find("t:lem", NS), app.find("t:rdg", NS)
        if lemma is None or reading is None:
            raise ValueError("Clothing apparatus is missing a selected reading")
        actual = {
            "from": app.attrib["from"],
            "to": app.attrib["to"],
            "taisho": _render(lemma, [], False),
            "ming": _render(reading, [], False),
        }
        if actual != expected:
            raise ValueError("Clothing apparatus does not match raw source")
    records = {}
    for raw, expected in zip(
        fixture["selected_xml_fragments"], fixture["selected_xml_records"]
    ):
        node = _fragment(raw)
        actual = {
            "xml_id": node.attrib[XML_ID],
            "taisho_text": _render(node, apps, False),
            "ming_chapter_apparatus_reading": _render(node, apps, True),
        }
        if actual != expected or actual["xml_id"] in records:
            raise ValueError("Clothing source paragraph or ID changed")
        records[actual["xml_id"]] = actual
    if len(records) != 56:
        raise ValueError("Selected clothing source paragraph count changed")
    parser = SATQuotationParser()
    for row in fixture["selected_html_quotations"]:
        parser.feed(row["html"])
    if set(parser.lines) != {f"0397b{n:02}" for n in range(16, 28)}:
        raise ValueError("Clothing SAT chapter is incomplete")
    verse = records["lgT21p0397b1701"]["taisho_text"]
    if len(source["verse_rows"]) != 27 or source["verse_rows"] != fixture["verse_rows"]:
        raise ValueError("Runtime clothing verses differ from transcribed facts")
    if _compact(verse) != "".join(row["taisho_text"] for row in fixture["verse_rows"]):
        raise ValueError("Clothing verse does not preserve all 27 literal clauses")

    # Explicitly reported orthographic comparison; never normalize 并 to 井.
    def equivalent(text: str) -> str:
        return _compact(text).translate(str.maketrans("虚増", "虛增"))

    sat_verse = "".join("".join(parser.lines[f"0397b{n:02}"]) for n in range(17, 26))
    summary = records["pT21p0397b2601"]
    sat_summary = "".join("".join(parser.lines[f"0397b{n:02}"]) for n in (26, 27))
    if equivalent(sat_verse) != equivalent(verse) or equivalent(
        sat_summary
    ) != equivalent(summary["taisho_text"]):
        raise ValueError("SAT and CBETA main text differ beyond declared orthography")
    if (
        source["summary_taisho"] != summary["taisho_text"]
        or source["summary_ming_apparatus"] != summary["ming_chapter_apparatus_reading"]
        or source["primary_positive_mansions"] != fixture["primary_positive_mansions"]
        or source["ming_literal_list"] != fixture["ming_literal_list"]
        or source["ming_unresolved_tokens"] != ["并"]
        or source["ming_complement_assessment"] is not None
    ):
        raise ValueError("Clothing membership or missing Ming complement was rewritten")
    aliases = str.maketrans("參畢軫張虛婁", "参毕轸张虚娄")
    literal_primary_names = _compact(summary["taisho_text"]).split("此以上", 1)[0]
    literal_ming_names = _compact(summary["ming_chapter_apparatus_reading"]).split(
        "此以上", 1
    )[0]
    if (
        [name.translate(aliases) for name in literal_primary_names]
        != source["primary_positive_mansions"]
        or [name.translate(aliases) for name in literal_ming_names if name != "并"]
        != source["ming_recognized_positive_mansions"]
        or source["verse_and_literal_forecasts_applied_to_aggregate"]
    ):
        raise ValueError(
            "Literal membership characters or unscored forecast policy changed"
        )
    if (
        len(source["rules"]) != 38
        or len({row["rule_id"] for row in source["rules"]}) != 38
    ):
        raise ValueError("Clothing rule inventory changed")
    for rule in source["rules"]:
        paragraph = records["pT21p" + rule["locator"].split("_p")[-1] + "01"][
            "taisho_text"
        ]
        if any(
            _compact(quote) not in _compact(paragraph)
            for quote in rule["source_excerpts"]
        ):
            raise ValueError("Clothing activity quotation is not source-bound")
    for row in source["upper_literal_cutting_statements"]:
        paragraph = records[row["xml_id"]]["taisho_text"]
        if row["source_excerpt"] not in paragraph:
            raise ValueError("Upper clothing literal statement differs")
        if row["mansion"] == "壁" and not (
            paragraph.startswith("璧圖。壁二星")
            and row["literal_heading_mansion"] == "璧"
        ):
            raise ValueError("Explicit 壁 identification and 璧 heading were lost")
    checked = []
    if capture_dir is not None:
        for name, meta in fixture["source_metadata"].items():
            raw = (capture_dir / name).read_bytes()
            if (
                hashlib.sha256(raw).hexdigest() != meta["sha256"]
                or len(raw) != meta["bytes"]
            ):
                raise ValueError("Private clothing primary capture changed")
            checked.append(name)
        xml = (capture_dir / "cbeta.xml").read_text()
        if any(
            fragment not in xml
            for fragment in [
                *fixture["selected_xml_fragments"],
                *fixture["selected_apparatus_xml"],
            ]
        ):
            raise ValueError("Selected fragments are not literal captured source bytes")
        html = (capture_dir / "sat-clothing.html").read_text()
        if any(row["html"] not in html for row in fixture["selected_html_quotations"]):
            raise ValueError("SAT clothing quotation is not in its full capture")
    return {
        "format": "sukuyo_clothing_primary_check_v1",
        "source_xml_sha256": fixture["source_sha256"],
        "selected_xml_fragments": len(records),
        "selected_sat_lines": len(parser.lines),
        "apparatus_records": 3,
        "verse_clauses": 27,
        "taisho_positive_mansions": 14,
        "taisho_complement_mansions": 13,
        "ming_recognized_positive_mansions": 13,
        "ming_unresolved_tokens": ["并"],
        "ming_unlisted_complement_assessment": None,
        "action_rules_with_literal_source_quotes": 38,
        "sat_cbeta_comparison_orthographic_map": {"虚": "虛", "増": "增"},
        "upper_heading_璧_and_explicit_壁_identification_preserved": True,
        "full_private_captures_hash_checked": checked,
        "independent_ming_print_collation": False,
        "manual_action_annotation_independently_accepted": False,
        "scope": "Literal selected-source conformance only. Predicate mapping is manual annotation; literal forecasts remain unscored. No whole-work or independent scholarly acceptance.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify_primary(args.capture_dir)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

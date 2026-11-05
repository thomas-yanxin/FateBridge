"""Recheck a named Xuanying entry and actual source bytes, without choosing a clock."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/fatebridge/data/sukuyo_xuanying_source_chain.json"
FIXTURE = ROOT / "tests/data/sukuyo-xuanying-before-production-v65.json"


def verify_primary(captures: dict[str, Path] | None = None) -> dict:
    raw = SOURCE.read_bytes()
    data = json.loads(raw)
    expected = json.loads(FIXTURE.read_bytes())
    if hashlib.sha256(raw).hexdigest() != expected["source_bundle_sha256"]:
        raise ValueError("玄应来源与事前读录指纹不一致")
    if data["selected_literal"] != expected["selected_literal"]:
        raise ValueError("玄应所选条目与事前读录不一致")
    actual = []
    for name, path in (captures or {}).items():
        keys = {
            "C1163": "C1163_capture_sha256",
            "T2216": "T2216_capture_sha256",
            "SINICA_PDF": "sinica_pdf_sha256",
        }
        if name not in keys:
            raise ValueError("未登记玄应来源")
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != expected[keys[name]]:
            raise ValueError("玄应原始来源字节指纹不一致")
        if name == "C1163":
            tree = ElementTree.fromstring(content)
            ns = "{http://www.tei-c.org/ns/1.0}"
            entries = [
                entry
                for entry in tree.findall(".//" + ns + "entry")
                if entry.find(ns + "form") is not None
                and "".join(entry.find(ns + "form").itertext())
                == data["selected_entry"]
            ]
            if len(entries) != 1:
                raise ValueError("玄应沸星条须完整且唯一")
            literal = re.sub(r"\s+", "", "".join(entries[0].itertext()))
            if literal != data["selected_literal"]:
                raise ValueError("玄应实际条目与所选全文不同")
        actual.append(name)
    return {
        "source_bundle_sha256": hashlib.sha256(raw).hexdigest(),
        "actual_captures_rechecked": actual,
        "selected_literal": data["selected_literal"],
        "facsimile_glyph_uniquely_accepted": False,
        "T2216_cited_exemplar_identified": False,
        "historical_clock_or_hinoo_priority_established": False,
        "scope": "Byte and selected-entry checks; not automated facsimile collation or historical-clock certification.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", action="append", default=[], metavar="ID=PATH")
    args = parser.parse_args()
    captures = {}
    for arg in args.capture:
        name, path = arg.split("=", 1)
        if name in captures:
            raise ValueError("重复玄应来源")
        captures[name] = Path(path)
    print(json.dumps(verify_primary(captures), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

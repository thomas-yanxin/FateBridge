"""Check the complete selected literal table against its frozen source record."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src/fatebridge/data/sukuyo_rizang_comparison.json"
FIXTURE = ROOT / "tests/fixtures/sukuyo-rizang-before-production-v66.json"


def verify_primary(capture: Path | None = None) -> dict[str, Any]:
    raw = DATA.read_bytes()
    data = json.loads(raw)
    frozen = json.loads(FIXTURE.read_bytes())
    if hashlib.sha256(raw).hexdigest() != frozen["source_bundle_sha256"]:
        raise ValueError("日藏来源包与修改前冻结记录不一致")
    if data["literal_slots"] != frozen["all330_literal_slots"]:
        raise ValueError("日藏完整字面表槽与修改前记录不同")
    if capture is not None:
        captured = capture.read_bytes()
        if hashlib.sha256(captured).hexdigest() != data["source_sha256"]:
            raise ValueError("日藏实际来源字节指纹不一致")
        tree = ET.fromstring(captured)
        ns = {
            "t": "http://www.tei-c.org/ns/1.0",
            "xml": "http://www.w3.org/XML/1998/namespace",
        }
        for paragraph in data["explicit_fortnight_paragraphs"]:
            query = f".//t:body//t:p[@xml:id='{paragraph['paragraph_id']}']"
            found = tree.findall(query, ns)
            if len(found) != 1:
                raise ValueError("具名日藏原段落未唯一定位")
            text = re.sub(r"\s+", "", "".join(found[0].itertext()))
            if text != paragraph["literal"]:
                raise ValueError("具名日藏原段落与冻结读录不同")
    return {
        "source_bundle_sha256": hashlib.sha256(raw).hexdigest(),
        "literal_slots_checked": len(data["literal_slots"]),
        "paragraphs_checked_against_actual_source": 22 if capture else 0,
        "actual_source_bytes_rechecked": capture is not None,
        "cited_exemplar_identified": False,
        "citation_reconciled": False,
        "historical_clock_or_hinoo_priority_established": False,
        "scope": "Literal selected table only; no full-book collation, missing-cell reconstruction or prediction certification.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify_primary(args.capture), ensure_ascii=False, indent=2))

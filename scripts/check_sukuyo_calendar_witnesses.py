"""Bind all selected apparatus readings to fixed source bytes and frozen facts."""

from __future__ import annotations

import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src/fatebridge/data/sukuyo_calendar_witnesses.json"
FIXTURE = ROOT / "tests/fixtures/sukuyo-calendar-witnesses-before-production-v70.json"
NS = {"t": "http://www.tei-c.org/ns/1.0"}


def verify_primary(captures: dict[str, Path] | None = None) -> dict[str, Any]:
    raw = DATA.read_bytes()
    data = json.loads(raw)
    before = json.loads(FIXTURE.read_bytes())
    if (
        hashlib.sha256(raw).hexdigest() != before["source_bundle_sha256"]
        or data != before["expected_data"]
    ):
        raise ValueError("历日校勘记录与修改前来源不一致")
    checked = []
    for name, path in (captures or {}).items():
        captured = path.read_bytes()
        expected = (
            data["new_SAT_T1644_capture"]
            if name == "T1644-SAT.html"
            else data["actual_sources"][name]
        )
        if hashlib.sha256(captured).hexdigest() != expected["sha256"]:
            raise ValueError("历日校勘实际来源字节指纹不一致")
        if name.endswith(".xml"):
            tree = ET.fromstring(captured)
            for paragraph in data["all_five_selected_paragraphs"]:
                if paragraph["source_file"] != name:
                    continue
                for row in paragraph["apparatus_entries"]:
                    found = [
                        a
                        for a in tree.findall(".//t:back//t:app", NS)
                        if a.get("from") == "#" + row["from_anchor"]
                        and a.get("to") == "#" + row["to_anchor"]
                    ]
                    if (
                        len(found) != 1
                        or dict(found[0].attrib) != row["app_attributes"]
                    ):
                        raise ValueError("历日校勘锚点或属性不一致")
                    readings = [
                        ET.tostring(n, encoding="unicode").strip() for n in found[0]
                    ]
                    if readings != [r["serialized_xml"] for r in row["readings"]]:
                        raise ValueError("历日校勘实际所报读法不一致")
        checked.append(name)
    return {
        "source_bundle_sha256": hashlib.sha256(raw).hexdigest(),
        "apparatus_entries": sum(
            len(p["apparatus_entries"]) for p in data["all_five_selected_paragraphs"]
        ),
        "actual_source_files_rechecked": checked,
        "independent_manuscript_or_day_boundary_acceptance": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", action="append", default=[])
    args = parser.parse_args()
    print(
        json.dumps(
            verify_primary(
                {n: Path(p) for n, p in (v.split("=", 1) for v in args.capture)}
            ),
            ensure_ascii=False,
            indent=2,
        )
    )

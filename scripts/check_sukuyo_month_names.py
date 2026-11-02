"""Check the complete fixed month-name reference and optional acquired bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src/fatebridge/data/sukuyo_month_names.json"
FIXTURE = ROOT / "tests/fixtures/sukuyo-month-names-before-production-v67.json"


def verify_primary(captures: dict[str, Path] | None = None) -> dict[str, Any]:
    raw = DATA.read_bytes()
    data = json.loads(raw)
    before = json.loads(FIXTURE.read_bytes())
    if hashlib.sha256(raw).hexdigest() != before["source_bundle_sha256"]:
        raise ValueError("月名来源包与修改前冻结指纹不一致")
    if data["all330_fixed_projection_rows"] != before["all330_fixed_projection_rows"]:
        raise ValueError("月名全槽对照与修改前参考不一致")
    if data["Tang_named_month_annotations"] != before["all12_Tang_named_months"]:
        raise ValueError("十二项月名原注与修改前读录不一致")
    checked = []
    for name, path in (captures or {}).items():
        captured = path.read_bytes()
        if hashlib.sha256(captured).hexdigest() != data["source_files_sha256"][name]:
            raise ValueError("月名实际源文件字节指纹不一致")
        if name == "T21n1299.xml":
            tree = ET.fromstring(captured)
            ns = {
                "t": "http://www.tei-c.org/ns/1.0",
                "xml": "http://www.w3.org/XML/1998/namespace",
            }
            for row in data["T1299_selected_passages"]:
                found = tree.findall(
                    f".//t:body//t:p[@xml:id='{row['paragraph_id']}']", ns
                )
                if (
                    len(found) != 1
                    or re.sub(r"\s+", "", "".join(found[0].itertext()))
                    != row["literal"]
                ):
                    raise ValueError("T1299月名原段与修改前读录不一致")
        checked.append(name)
    return {
        "source_bundle_sha256": hashlib.sha256(raw).hexdigest(),
        "all_named_months_checked": 12,
        "all_projection_slots_checked": 330,
        "literal_same": data["projection_literal_equal"],
        "literal_different": data["projection_literal_different"],
        "actual_source_files_rechecked": checked,
        "actual_date_conversion_or_cited_exemplar_certified": False,
        "scope": "Textual named-month and diagnostic method comparison; not independent physical dates, whole-book collation, source priority or efficacy.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", action="append", default=[])
    args = parser.parse_args()
    print(
        json.dumps(
            verify_primary(
                {n: Path(p) for n, p in (x.split("=", 1) for x in args.capture)}
            ),
            ensure_ascii=False,
            indent=2,
        )
    )

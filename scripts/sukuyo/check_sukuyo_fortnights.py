"""Check the before-production full declared arithmetic and exact source rows."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_fortnights import declared_fortnight_ordinal

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "src/fatebridge/data/sukuyo_fortnights.json"
FIXTURE = ROOT / "tests/data/sukuyo-fortnight-before-production-v69.json"


def verify_primary(captures: dict[str, Path] | None = None) -> dict[str, Any]:
    raw = DATA.read_bytes()
    data = json.loads(raw)
    before = json.loads(FIXTURE.read_bytes())
    if hashlib.sha256(raw).hexdigest() != before["source_bundle_sha256"]:
        raise ValueError("黑白分来源包与修改前指纹不一致")
    if data["selected_paragraphs"] != before["selected_paragraphs"]:
        raise ValueError("黑白分所选原段与修改前参考不一致")
    valid = invalid = 0
    for row in before["all68_declared_ordinal_cases"]:
        try:
            value = declared_fortnight_ordinal(
                **{k: row[k] for k in ("half", "day", "black_length", "white_length")}
            )
        except ValueError:
            if row["valid"]:
                raise ValueError("声明有效的编号被拒绝")
            invalid += 1
        else:
            if not row["valid"] or value != row["ordinal"]:
                raise ValueError("编号与修改前参考不一致")
            valid += 1
    checked = []
    ns = {
        "t": "http://www.tei-c.org/ns/1.0",
        "xml": "http://www.w3.org/XML/1998/namespace",
    }
    for name, path in (captures or {}).items():
        captured = path.read_bytes()
        if (
            hashlib.sha256(captured).hexdigest()
            != before["actual_sources"][name]["sha256"]
        ):
            raise ValueError("黑白分实际源文件字节指纹不一致")
        if name.endswith(".xml"):
            tree = ET.fromstring(captured)
            for row in before["selected_paragraphs"]:
                if row["source_file"] != name:
                    continue
                found = tree.findall(
                    f".//t:body//t:p[@xml:id='{row['paragraph_id']}']", ns
                )
                if (
                    len(found) != 1
                    or re.sub(r"\s+", "", "".join(found[0].itertext()))
                    != row["literal_with_inline_notes"]
                ):
                    raise ValueError("黑白分实际原段与修改前参考不一致")
        checked.append(name)
    return {
        "source_bundle_sha256": hashlib.sha256(raw).hexdigest(),
        "declared_ordinal_cases": valid + invalid,
        "valid_ordinal_cases": valid,
        "invalid_ordinal_cases_rejected": invalid,
        "actual_source_files_rechecked": checked,
        "actual_date_or_leap_precedence_admitted": False,
        "scope": "All68 declared numbering cases and selected named source paragraphs, not a physical calendar, ancient epoch, whole-book collation or reality evidence.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", action="append", default=[])
    args = parser.parse_args()
    print(
        json.dumps(
            verify_primary(
                {n: Path(p) for n, p in (s.split("=", 1) for s in args.capture)}
            ),
            ensure_ascii=False,
            indent=2,
        )
    )

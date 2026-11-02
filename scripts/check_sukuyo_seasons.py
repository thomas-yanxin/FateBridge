"""Verify all twelve source-specific season rows and optional actual captures."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src/fatebridge/data/sukuyo_seasons.json"
FIXTURE = ROOT / "tests/fixtures/sukuyo-season-before-production-v68.json"


def verify_primary(captures: dict[str, Path] | None = None) -> dict[str, Any]:
    raw = DATA.read_bytes()
    data = json.loads(raw)
    before = json.loads(FIXTURE.read_bytes())
    if hashlib.sha256(raw).hexdigest() != before["source_bundle_sha256"]:
        raise ValueError("季节来源包与修改前冻结指纹不一致")
    if data["all12_season_rows"] != before["all12_season_rows"]:
        raise ValueError("十二月季节原录与修改前参考不一致")
    if [r["textual_month"] for r in data["all12_season_rows"]] != list(range(1, 13)):
        raise ValueError("十二月季节原录缺失或重复")
    checked = []
    ns = {
        "t": "http://www.tei-c.org/ns/1.0",
        "xml": "http://www.w3.org/XML/1998/namespace",
    }
    for name, path in (captures or {}).items():
        captured = path.read_bytes()
        if hashlib.sha256(captured).hexdigest() != before["source_files_sha256"][name]:
            raise ValueError("季节实际源文件字节指纹不一致")
        if name == "T13n0397.xml":
            tree = ET.fromstring(captured)
            for row in [*data["all12_season_rows"], data["rizang_unit_context"]]:
                found = tree.findall(
                    f".//t:body//t:p[@xml:id='{row['paragraph_id']}']", ns
                )
                if (
                    len(found) != 1
                    or re.sub(r"\s+", "", "".join(found[0].itertext()))
                    != row["literal"]
                ):
                    raise ValueError("日藏季节实际原段与修改前参考不一致")
        elif name == "T25n1509.xml":
            from scripts.check_sukuyo_time_units import selected_tei_lines

            text, _ = selected_tei_lines(path, "0409b25", "0409b29")
            if re.sub(r"\s+", "", text) != data["T1509_season_context"]["main_literal"]:
                raise ValueError("大智度论实际原段与修改前参考不一致")
        checked.append(name)
    return {
        "source_bundle_sha256": hashlib.sha256(raw).hexdigest(),
        "all_seasonal_month_rows_checked": 12,
        "all12_sums_equal30": all(
            r["day_count"] + r["night_count"] == 30 for r in data["all12_season_rows"]
        ),
        "actual_source_files_rechecked": checked,
        "physical_clock_or_uniform_calendar_conversion_certified": False,
        "scope": "Selected named textual counts and original shadow strings, not independent observations or physical dates, modern minutes, latitude, leap precedence or efficacy.",
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

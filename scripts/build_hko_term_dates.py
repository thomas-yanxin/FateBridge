"""Derive published term dates from all pinned HKO1901–2100 text tables.

No FateBridge computation supplies a label. The old source manifest and all
200 source byte hashes are checked before a date is read.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_SHA = "62e919e2d4fbf59c643d4cca429d67cb8958fe3705abd33044a378b86f2bcabc"
TERMS = "小寒 大寒 立春 雨水 惊蛰 春分 清明 谷雨 立夏 小满 芒种 夏至 小暑 大暑 立秋 处暑 白露 秋分 寒露 霜降 立冬 小雪 大雪 冬至".split()
SPELLING = {
    "驚蟄": "惊蛰",
    "穀雨": "谷雨",
    "小滿": "小满",
    "芒種": "芒种",
    "處暑": "处暑",
}


def build(source_root: Path | None = None) -> dict[str, Any]:
    folder = source_root or ROOT / "tests/fixtures/ziwei_independent"
    raw = (folder / "calendar_manifest.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA:
        raise ValueError("Frozen HKO source manifest changed")
    sources = json.loads(raw)["sources"]
    if len(sources) != 200 or {s["year"] for s in sources} != set(range(1901, 2101)):
        raise ValueError("All200 HKO annual sources required")
    rows = {}
    for source in sources:
        year = source["year"]
        raw = (folder / source["path"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != source["sha256"]:
            raise ValueError("Frozen HKO annual source changed")
        found = {}
        for line in raw.decode("utf-8-sig").splitlines():
            match = re.match(r"^(\d{4})年(\d{1,2})月(\d{1,2})日\s+", line)
            if not match:
                continue
            tokens = line.split()
            name = SPELLING.get(tokens[-1], tokens[-1])
            if name not in TERMS:
                continue
            d = date(*map(int, match.groups()))
            if d.year != year or name in found:
                raise ValueError("Duplicate or cross-year HKO term")
            found[name] = d.isoformat()
        if set(found) != set(TERMS):
            raise ValueError("All24 HKO annual terms required")
        for name in TERMS:
            rows[f"{year}:{name}"] = dict(
                published_date=found[name],
                source_url=source["url"],
                source_sha256=source["sha256"],
            )
    return dict(
        schema_version="hko_published_term_dates_v1",
        publisher="Hong Kong Observatory",
        clock="fixed UTC+08:00; published dates, no crossing instants",
        start_year=1901,
        end_year=2100,
        source_manifest_sha256=MANIFEST_SHA,
        source_url="https://www.hko.gov.hk/tc/gts/time/conversion.htm",
        terms=rows,
        source_event_count=4800,
        independent_new_observations=0,
        scope="Reuses previously exposed HKO annual dates. Historical publication conventions and future near-midnight uncertainty are retained. Date equality never certifies the crossing instant, a full calendar, or predictive efficacy.",
    )


def encoded(data: dict[str, Any]) -> bytes:
    return (
        json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    raw = encoded(build())
    if args.check:
        if args.output.read_bytes() != raw:
            raise ValueError("Published HKO term data drifted")
    else:
        if args.output.exists():
            raise ValueError("Refusing to overwrite HKO term catalogue")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(raw)
    print(hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()

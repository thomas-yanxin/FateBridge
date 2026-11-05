"""Freeze independent HKO calendar tables; never derive expected dates from FateBridge.

Run deliberately to refresh source bytes, then review every manifest diff.
Offline tests and the audit script do not download or rewrite these files.
"""

from __future__ import annotations

import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "tests/data/ziwei_independent"
YEARS = tuple(range(1901, 2101))


def fetch(year: int) -> dict:
    url = f"https://www.hko.gov.hk/tc/gts/time/calendar/text/files/T{year}c.txt"
    with urlopen(url, timeout=30) as response:
        data = response.read()
    text = data.decode("utf-8-sig")
    if not re.search(rf"{year}年0?1月0?1日", text) or f"{year}年12月31日" not in text:
        raise ValueError(f"Incomplete HKO table for {year}")
    name = f"hko/T{year}c.txt"
    dest = TARGET / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return {
        "path": name,
        "url": url,
        "sha256": hashlib.sha256(data).hexdigest(),
        "year": year,
    }


def main() -> None:
    with ThreadPoolExecutor(max_workers=4) as pool:
        sources = list(pool.map(fetch, YEARS))
    manifest = {
        "schema_version": "ziwei_hko_calendar_v1",
        "publisher": "Hong Kong Observatory",
        "retrieved_on": datetime.now(timezone.utc).date().isoformat(),
        "clock": "HKO published civil dates, UTC+08:00; no apparent-solar correction",
        "selection": "All HKO annual text tables, 1901-2100; no outcome-based year selection",
        "engine_supported_solar_start": "1900-01-31",
        "engine_supported_solar_end": "2100-02-08",
        "future_uncertainty_source": "https://www.hko.gov.hk/tc/gts/time/conversion.htm",
        "sources": sources,
    }
    (TARGET / "calendar_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Frozen {len(sources)} independent HKO annual tables")


if __name__ == "__main__":
    main()

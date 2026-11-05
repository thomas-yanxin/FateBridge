"""Capture complete historical-reference inputs, without admitting a backend.

Requires --download. Existing valid captures are resumed, never overwritten.
NAOJ returns at most 400-day spans; one overlapping span per lunar year
collects all month starts. HuTime's 28-day grid independently samples every
full month; the two-day Meiji reform month is queried explicitly at the end.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from itertools import zip_longest
from pathlib import Path
from typing import Any

FIRST = date(1, 1, 1)
LAST = date(1872, 12, 31)
NAOJ = "https://eco.mtk.nao.ac.jp/cgi-bin/koyomi/caldb.cgi"
HUTIME = "https://ap.hutime.org/cal/"


def jobs() -> list[tuple[str, str, dict[str, str]]]:
    values = [FIRST + timedelta(days=n) for n in range(0, (LAST - FIRST).days + 1, 28)]
    if values[-1] != LAST:
        values.append(LAST)
    hutime = [
        (
            f"hutime-{batch:03}",
            HUTIME,
            {
                "ical": "2.1",
                "itype": "date",
                "ival": "\r\n".join(d.isoformat() for d in values[start : start + 100]),
                "method": "conv",
                "ep": "b",
                "ocal": "1001.1",
                "otype": "month",
                "oprop": "text;jdBegin;jdEnd;uri;isLeap",
                "oform": "yW|MMM",
                "out": "json",
            },
        )
        for batch, start in enumerate(range(0, len(values), 100))
    ]
    naoj = [
        (
            f"naoj-{year:04}",
            NAOJ,
            {
                "type": "2",
                "gengo": "a000",
                "year": str(year),
                "month": "1",
                "day": "1",
                "jg": "1",
                "div": "1",
                "divu": "3",
                "len": "400",
                "lenu": "3",
                "gen": "1",
                "csv": "CSV",
            },
        )
        for year in range(0, 1873)
    ]
    return [
        item for pair in zip_longest(hutime, naoj) for item in pair if item is not None
    ]


def validate_response(name: str, params: dict[str, str], raw: bytes) -> int:
    if name.startswith("hutime-"):
        rows = json.loads(raw)
        if not isinstance(rows, list) or len(rows) != len(params["ival"].splitlines()):
            raise ValueError("HuTime response count changed")
        # Nulls and contradictory source periods must remain available to the
        # admission audit; transport validation never deletes them.
        return len(rows)
    rows = list(csv.reader(io.StringIO(raw.decode("cp932"))))
    if not rows or rows[0] != [
        "西暦",
        "和暦",
        "神武紀元",
        "年の干支",
        "月の干支",
        "日の干支",
    ]:
        raise ValueError("NAOJ source header or encoding changed")
    if not 1 <= len(rows) - 1 <= 15 or any(len(row) != 6 for row in rows[1:]):
        raise ValueError("NAOJ month-start response shape changed")
    return len(rows) - 1


def acquire(directory: Path, job: tuple[str, str, dict[str, str]]) -> dict[str, Any]:
    name, endpoint, params = job
    request_raw = urllib.parse.urlencode(params).encode("ascii")
    request_path = directory / (name + ".request.txt")
    response_path = directory / (name + ".response.bin")
    metadata_path = directory / (name + ".metadata.json")
    if request_path.exists() and request_path.read_bytes() != request_raw:
        raise ValueError(f"Existing request differs: {name}")
    request_path.write_bytes(request_raw)
    if response_path.exists():
        raw = response_path.read_bytes()
        rows = validate_response(name, params, raw)
    else:
        request = urllib.request.Request(
            endpoint,
            data=request_raw,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "FateBridge historical calendar source verification",
            },
        )
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=45) as response:
                    raw = response.read()
                    rows = validate_response(name, params, raw)
                    metadata = {
                        "endpoint": endpoint,
                        "effective_url": response.url,
                        "status": response.status,
                        "response_headers": dict(response.headers),
                        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
                    }
                response_path.write_bytes(raw)
                metadata_path.write_text(
                    json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
                )
                break
            except Exception as error:
                if attempt == 2:
                    raise RuntimeError(
                        f"Capture failed after three attempts: {name}"
                    ) from error
                time.sleep(2 * (attempt + 1))
        time.sleep(0.5)
    if not metadata_path.exists():
        raise ValueError(f"Response metadata missing: {name}")
    return {
        "id": name,
        "endpoint": endpoint,
        "rows": rows,
        "request_file": request_path.name,
        "response_file": response_path.name,
        "metadata_file": metadata_path.name,
        "request_sha256": hashlib.sha256(request_raw).hexdigest(),
        "response_sha256": hashlib.sha256(raw).hexdigest(),
        "metadata_sha256": hashlib.sha256(metadata_path.read_bytes()).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    if not args.download:
        parser.error("Network acquisition requires explicit --download")
    args.directory.mkdir(parents=True, exist_ok=True)
    planned = jobs()
    records = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        for record in pool.map(lambda job: acquire(args.directory, job), planned):
            records.append(record)
            if len(records) % 25 == 0 or len(records) == len(planned):
                print(
                    json.dumps(
                        {
                            "completed": len(records),
                            "total": len(planned),
                            "last": record["id"],
                        }
                    ),
                    flush=True,
                )
    manifest = {
        "format": "sukuyo_historical_calendar_acquisition_v1",
        "gregorian_domain_inclusive": [FIRST.isoformat(), LAST.isoformat()],
        "naoj_lunar_year_queries_inclusive": [0, 1872],
        "hutime_calendar_id": "1001.1",
        "hutime_query_spacing_days": 28,
        "requests": records,
        "scope": "Source acquisition only; nulls, overlaps, discrepancies and early reconstructed chronology remain subject to admission. Not a runtime calendar or historical authority certification.",
    }
    (args.directory / "acquisition.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps({"complete": True, "requests": len(records)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

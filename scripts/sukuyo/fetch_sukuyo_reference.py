"""Freeze official HKO source bytes and derive the scoped calendar corrections.

Fetch only with --download. Otherwise rebuild from the frozen ZIP without a
network call. Expected days come from the published text, never FateBridge.
The Chinese 2069 table independently fills a missing English row.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from lunardate import LunarDate

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/data/sukuyo_hko_v1"
BUNDLE = ROOT / "src/fatebridge/data/sukuyo_calendar_corrections.json"
PREFIX = "https://www.hko.gov.hk/en/gts/time/calendar/text/files/"
SUPPLEMENT = "https://www.hko.gov.hk/tc/gts/time/calendar/text/files/T2069c.txt"


def decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("big5")


def published_rows(sources: dict[str, bytes]) -> list[list]:
    rows = []
    for year in range(1901, 2100):
        for line in decode(sources[f"T{year}e.txt"]).splitlines():
            m = re.match(r"\s*(\d{4})/(\d{1,2})/(\d{1,2})\s+(.+?)\s{2,}", line)
            if not m:
                continue
            civil = date(*map(int, m.group(1, 2, 3)))
            label = m[4].strip()
            month = re.fullmatch(r"(\d+)(?:st|nd|rd|th) Lunar [Mm]onth", label)
            if not month and not label.isdigit():
                raise ValueError(f"Unrecognized source label: {line}")
            rows.append(
                [civil, int(month[1]) if month else None, 1 if month else int(label)]
            )
    # Do not silently invent the missing English record by interpolation.
    chinese = decode(sources["T2069c.txt"])
    if not re.search(r"2069年12月30日\s+十七\s+星期一", chinese):
        raise ValueError("Chinese supplement for 2069-12-30 changed")
    if any(row[0] == date(2069, 12, 30) for row in rows):
        raise ValueError("English table gap changed: review source reconciliation")
    rows.append([date(2069, 12, 30), None, 17])
    rows.sort()
    expected_count = (date(2100, 1, 1) - date(1901, 1, 1)).days
    if len(rows) != expected_count or any(
        b[0] - a[0] != timedelta(days=1) for a, b in zip(rows, rows[1:])
    ):
        raise ValueError(
            "Official source dates must cover the declared range exactly once"
        )
    # First upcoming new month provides the preceding month's number. No call
    # to the production calendar is used to seed the reference chronology.
    first = next(row for row in rows if row[1] is not None)
    month, lunar_year, leap = first[1] - 1 or 12, 1900, False
    result = []
    for civil, new_month, day in rows:
        if new_month is not None:
            leap = new_month == month
            if new_month == 1:
                lunar_year = civil.year
            month = new_month
        result.append([civil.isoformat(), lunar_year, month, day, leap])
    return result


def read_sources() -> dict[str, bytes]:
    with ZipFile(FIXTURE / "official_texts.zip") as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def render(sources: dict[str, bytes]) -> tuple[str, str]:
    rows = published_rows(sources)
    corrections = {}
    for civil, year, month, day, leap in rows:
        moment = date.fromisoformat(civil)
        lunar = LunarDate.fromSolarDate(moment.year, moment.month, moment.day)
        expected = [year, month, day, leap]
        if [lunar.year, lunar.month, lunar.day, bool(lunar.isLeapMonth)] != expected:
            corrections[civil] = expected
    bundle = {
        "id": "sukuyo_hko_corrections_v1",
        "source": "https://www.hko.gov.hk/en/gts/time/conversion.htm",
        "range": ["1901-01-01", "2099-12-31"],
        "reference_days": len(rows),
        "corrections": corrections,
        "scope": "Modern Chinese calendar, fixed UTC+08; not a reconstruction of historical calendars",
    }
    manifest = {
        "source_date": "2026-10-22",
        "reference_days": len(rows),
        "english_days": len(rows) - 1,
        "supplemented_date": "2069-12-30",
        "correction_count": len(corrections),
        "annotation_method": "Parse official daily labels; repeated month number means leap month; do not use production output as expected values.",
        "sources": [
            {
                "file": name,
                "url": SUPPLEMENT if name.endswith("c.txt") else PREFIX + name,
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
            for name, raw in sorted(sources.items())
        ],
    }
    return tuple(
        json.dumps(x, ensure_ascii=False, indent=2) + "\n" for x in (bundle, manifest)
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true")
    parser.add_argument(
        "--source-dir", type=Path, help="Existing official downloads to freeze"
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.download or args.source_dir:
        names = [f"T{year}e.txt" for year in range(1901, 2100)] + ["T2069c.txt"]

        def fetch(name):
            if args.source_dir:
                return name, (args.source_dir / name).read_bytes()
            url = SUPPLEMENT if name.endswith("c.txt") else PREFIX + name
            return name, urlopen(url, timeout=30).read()

        with ThreadPoolExecutor(max_workers=8) as pool:
            sources = dict(pool.map(fetch, names))
        FIXTURE.mkdir(parents=True, exist_ok=True)
        with ZipFile(FIXTURE / "official_texts.zip", "w", ZIP_DEFLATED) as archive:
            for name, raw in sorted(sources.items()):
                info = ZipInfo(name, date_time=(2026, 10, 22, 0, 0, 0))
                info.compress_type = ZIP_DEFLATED
                archive.writestr(info, raw)
    else:
        sources = read_sources()
    bundle, manifest = render(sources)
    for path, content in [(BUNDLE, bundle), (FIXTURE / "manifest.json", manifest)]:
        if args.check:
            if path.read_text() != content:
                raise SystemExit(f"Reference drift: {path}")
        else:
            path.write_text(content)
    print(
        json.dumps(
            {
                "reference_days": json.loads(manifest)["reference_days"],
                "corrections": len(json.loads(bundle)["corrections"]),
            }
        )
    )


if __name__ == "__main__":
    main()

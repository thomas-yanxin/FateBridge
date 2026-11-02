"""Freeze existing raw captures only; never generate production calendar data.

The source directory contains 000..021 request/response pairs and the named
version/day/NAOJ probes. Reacquisition is deliberately a separate operation:
changed provider bytes must remain reviewable, rather than replace a baseline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]


def freeze(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    files = {}
    batches = []
    for index in range(22):
        names = {
            "request": f"{index:03}.request.txt",
            "response": f"{index:03}.response.json",
        }
        for name in names.values():
            files[name] = (source / "hutime-months-v1" / name).read_bytes()
        batches.append(names)
    probes = {}
    for key, stem, suffix in [
        ("version_probe", "hutime-version-probe", "json"),
        ("day_probe", "hutime-overlap-days", "json"),
        ("naoj_control", "naoj-1872", "txt"),
    ]:
        names = {
            "request": stem + ".request.txt",
            "response": stem + ".response." + suffix,
        }
        for name in names.values():
            files[name] = (source / name).read_bytes()
        probes[key] = names
    archive = destination / "captures.zip"
    with ZipFile(archive, "x", ZIP_DEFLATED) as bundle:
        for name, raw in sorted(files.items()):
            info = ZipInfo(name, (2026, 10, 22, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            bundle.writestr(info, raw)
    manifest = {
        "format": "sukuyo_japanese_candidate_capture_v1",
        "retrieved_on": "2026-10-22",
        "provider": "HuTime / Tatsuki Sekino",
        "api_endpoint": "https://ap.hutime.org/cal/",
        "calendar_id_used": "1002.1",
        "calendar_id_listed_on_lod_page": "1002.2",
        "calendar_list_url": "https://datetime.hutime.org/calendar/",
        "api_documentation": "https://ap.hutime.org/cal/index_en.html",
        "format_documentation": "https://www.hutime.jp/basicdata/calendar/calendars/JapaneseFormat.html",
        "calendar_methodology": "https://www.hutime.jp/basicdata/calendar/calendars/OldJapanese.html",
        "naoj_endpoint": "https://eco.mtk.nao.ac.jp/cgi-bin/koyomi/caldb.cgi",
        "naoj_csv_encoding": "cp932",
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "files_sha256": {
            n: hashlib.sha256(raw).hexdigest() for n, raw in sorted(files.items())
        },
        "month_batches": batches,
        **probes,
        "source_provenance": [
            {
                "years": "1872-1909",
                "basis": "Published almanac old-calendar entries; 1872 is pre-reform.",
            },
            {
                "years": "1910-1946",
                "basis": "Provider reconstruction from published new moons and solar terms; 1923-1944 uses Nichiyo Benran for missing terms.",
            },
            {
                "years": "1947-2014",
                "basis": "Provider follows Jingu almanacs. 1947 retains printed leap third month; 1969 corrects a large-almanac leap-seventh typo using the small almanac.",
            },
            {
                "years": "2015 onward",
                "basis": "Reference projections from Rekijitsu Taikan; provider describes later Jingu comparison as planned, not completed.",
            },
        ],
        "scope": "Research facts and raw API/CSV responses; no whole Jingu edition, no historical time-standard reconstruction, no scholarly acceptance or runtime admission.",
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "tests/fixtures/sukuyo_hutime_v1"
    )
    args = parser.parse_args()
    freeze(args.source_dir, args.output_dir)


if __name__ == "__main__":
    main()

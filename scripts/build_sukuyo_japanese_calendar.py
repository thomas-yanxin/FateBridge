"""Build a Japanese reference calendar from complete, frozen daily responses.

No production calendar supplies expected fields. Old monthly responses remain
rejected; one endpoint discrepancy is retained and reconciled by daily facts.
The LOD domain and the longer methodology-page claim are separate ranges.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import parse_qs
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
FIRST = date(1872, 2, 9)
ADVERTISED_END = date(2033, 1, 30)
PROPERTIES = "text;jdBegin;jdEnd;uri;isLeap;ofMonth.isLeap;ofMonth.uri"
PREFIX = "http://datetime.hutime.org/calendar/1002.1/"


def parse_day(row: dict, civil: date) -> tuple[int, int, int, bool]:
    if not isinstance(row, dict) or set(row) != set(PROPERTIES.split(";")):
        raise ValueError("Daily response property set changed")
    match = re.fullmatch(
        r"(\d{4})\|(閏)?([1-9]|1[0-2])\|([1-9]|[12][0-9]|30)", row["text"]
    )
    if not match:
        raise ValueError("Daily response must use printed yW|MMM|d")
    year, month, day, leap = int(match[1]), int(match[3]), int(match[4]), bool(match[2])
    jd = 2451544.5 + (civil - date(2000, 1, 1)).days
    if (
        type(row["jdBegin"]) not in (float, int)
        or type(row["jdEnd"]) not in (float, int)
        or (row["jdBegin"], row["jdEnd"]) != (jd, jd + 1)
    ):
        raise ValueError("Daily JD does not identify the requested calendar date")
    # CalendarDate.isLeap describes the day period, not its enclosing month.
    if row["isLeap"] != "False" or row["ofMonth.isLeap"] != (
        "True" if leap else "False"
    ):
        raise ValueError("Printed month and enclosing-month flag disagree")
    if (
        row["uri"] != PREFIX + f"date/{jd:.1f}"
        or row["ofMonth.uri"] != PREFIX + f"month/{jd - day + 1:.1f}"
    ):
        raise ValueError("Daily/month URI contradicts the printed date")
    return year, month, day, leap


def normalize(files: dict[str, bytes], manifest: dict) -> tuple[dict, dict]:
    directory = files["calendar-index.html"].decode("utf-8")
    if not re.search(
        r'<a href="http://datetime.hutime.org/calendar/1002\.1" property="dcterms:identifier">1002\.2</a>',
        directory,
    ):
        raise ValueError(
            "Calendar-directory label/link discrepancy changed; review source"
        )
    lod = json.loads(files["calendar-metadata.json"])[PREFIX.rstrip("/")]
    begin = lod["http://resource.hutime.org/ontology/supportedBegin"][0]["value"]
    finish = lod["http://resource.hutime.org/ontology/supportedEnd"][0]["value"]

    def civil_from_resource(uri: str) -> date:
        if not uri.startswith(PREFIX + "date/"):
            raise ValueError("LOD boundary is not a date of the selected calendar")
        jd = float(uri.rsplit("/", 1)[1])
        if jd % 1 != 0.5:
            raise ValueError("LOD boundary must be a calendar-date period index")
        return date(2000, 1, 1) + timedelta(days=jd - 2451544.5)

    first, last = civil_from_resource(begin), civil_from_resource(finish)
    if first != FIRST or last != date(2031, 1, 22):
        raise ValueError("Provider's LOD domain changed: review it explicitly")
    expected_civil = FIRST
    months, nulls = [], []
    previous = None
    checked = 0
    early_control = {}
    for batch in manifest["daily_batches"]:
        request = parse_qs(files[batch["request"]].decode("ascii"), strict_parsing=True)
        fixed = {
            "ical": "2.1",
            "itype": "date",
            "method": "conv",
            "ep": "b",
            "ocal": "1002.1",
            "otype": "date",
            "oprop": PROPERTIES,
            "oform": "yW|MMM|d",
            "out": "json",
        }
        if (
            set(request) != {*fixed, "ival"}
            or any(request[k] != [v] for k, v in fixed.items())
            or len(request["ival"]) != 1
        ):
            raise ValueError("Daily request calendar or format changed")
        values = request["ival"][0].splitlines()
        rows = json.loads(files[batch["response"]])
        if not isinstance(rows, list) or len(rows) != len(values):
            raise ValueError("Daily source row counts disagree")
        for value, row in zip(values, rows):
            civil = date.fromisoformat(value)
            if civil != expected_civil:
                raise ValueError(
                    "Daily source grid must cover the entire advertised range once"
                )
            expected_civil += timedelta(days=1)
            if row is None:
                nulls.append(value)
                if first <= civil <= last:
                    raise ValueError(
                        "Missing daily source inside the LOD supported domain"
                    )
                continue
            if not first <= civil <= last:
                raise ValueError(
                    "Response outside LOD domain requires explicit source review"
                )
            year, month, day, leap = parse_day(row, civil)
            if day == 1:
                if previous is not None:
                    py, pm, pd, pl = previous
                    expected = (py + 1, 1) if pm == 12 else (py, pm + 1)
                    if (
                        pd not in (29, 30)
                        or (leap and (pl or (year, month) != (py, pm)))
                        or (not leap and (year, month) != expected)
                    ):
                        raise ValueError(
                            "Daily source has an invalid month/year/leap sequence"
                        )
                months.append([value, year, month, leap, 0])
            elif previous is None or (year, month, day, leap) != (
                previous[0],
                previous[1],
                previous[2] + 1,
                previous[3],
            ):
                raise ValueError("Daily source skips or repeats a printed lunar date")
            months[-1][4] += 1
            previous = (year, month, day, leap)
            if civil.year == 1872:
                early_control[civil] = (year, month, day, leap)
            checked += 1
    if expected_civil != ADVERTISED_END + timedelta(days=1):
        raise ValueError(
            "Advertised range has been trimmed or acquisition is incomplete"
        )
    if not months or any(m[4] not in (29, 30) for m in months):
        raise ValueError("Observed source must contain complete 29/30-day months")
    if checked != (last - first).days + 1 or len(nulls) != (ADVERTISED_END - last).days:
        raise ValueError("Source grid coverage disagrees with the declared domains")
    old_manifest = json.loads(
        (ROOT / "tests/fixtures/sukuyo_hutime_v1/manifest.json").read_bytes()
    )
    old_path = ROOT / "tests/fixtures/sukuyo_hutime_v1/captures.zip"
    if (
        hashlib.sha256(old_path.read_bytes()).hexdigest()
        != old_manifest["archive_sha256"]
    ):
        raise ValueError("Earlier monthly capture archive changed")
    monthly = {}
    with ZipFile(old_path) as archive:
        for batch in old_manifest["month_batches"]:
            raw = archive.read(batch["response"])
            if (
                hashlib.sha256(raw).hexdigest()
                != old_manifest["files_sha256"][batch["response"]]
            ):
                raise ValueError("Earlier monthly response hash changed")
            for row in json.loads(raw):
                if row is not None:
                    monthly[row["jdBegin"]] = row
        control_name = old_manifest["naoj_control"]["response"]
        control_raw = archive.read(control_name)
        if (
            hashlib.sha256(control_raw).hexdigest()
            != old_manifest["files_sha256"][control_name]
        ):
            raise ValueError("Independent NAOJ control bytes changed")
        controls = list(csv.reader(io.StringIO(control_raw.decode("cp932"))))
        control_dates = []
        for row in controls[1:]:
            if not row:
                continue
            match = re.fullmatch(r"明治05年(閏)?(\d{2})月(\d{2})日", row[1])
            if not match:
                raise ValueError("Independent control contains an unexpected date")
            civil = date.fromisoformat(row[0].replace("/", "-"))
            expected = (1872, int(match[2]), int(match[3]), bool(match[1]))
            if early_control.get(civil) != expected:
                raise ValueError(
                    "Daily reference disagrees with independent NAOJ control"
                )
            control_dates.append(civil)
        if control_dates != [FIRST + timedelta(days=n) for n in range(327)]:
            raise ValueError(
                "Independent control must cover all 327 declared days once"
            )
    reconciled = []
    for start, year, month, leap, length in months:
        civil = date.fromisoformat(start)
        jd = 2451544.5 + (civil - date(2000, 1, 1)).days
        row = monthly.pop(jd)
        if row["text"] != f"{year}|{'閏' if leap else ''}{month}" or row["isLeap"] != (
            "True" if leap else "False"
        ):
            raise ValueError("Daily and monthly printed year/month/leap disagree")
        if row["jdEnd"] != jd + length:
            reconciled.append(
                {
                    "month_start": start,
                    "monthly_response_end_jd": row["jdEnd"],
                    "daily_derived_end_jd": jd + length,
                    "daily_count": length,
                    "basis": "All daily responses, adjacent month start and provider methodology's explicit 1989-01-08..02-05 example; earlier raw monthly bytes remain unchanged.",
                }
            )
    if monthly or [
        (r["month_start"], r["monthly_response_end_jd"], r["daily_derived_end_jd"])
        for r in reconciled
    ] != [("1989-01-08", 2447564.5, 2447563.5)]:
        raise ValueError(
            "Monthly discrepancy set changed; do not silently correct new conflicts"
        )
    provenance = old_manifest["source_provenance"]
    report = {
        "format": "sukuyo_japanese_daily_admission_v1",
        "daily_rows_checked": checked,
        "lod_range_inclusive": [first.isoformat(), last.isoformat()],
        "methodology_range_inclusive": [FIRST.isoformat(), ADVERTISED_END.isoformat()],
        "null_dates_outside_lod_domain": nulls,
        "complete_in_lod_domain": True,
        "complete_methodology_advertised_range": False,
        "source_months": len(months),
        "reconciled_monthly_discrepancies": reconciled,
        "earlier_monthly_source_admission_still_rejected": True,
        "directory_label": "1002.2",
        "directory_link_and_entity_identifier": "1002.1",
        "independent_whole_range_verification": False,
        "independent_control": {
            "provider": "NAOJ",
            "dates": 327,
            "range_inclusive": ["1872-02-09", "1872-12-31"],
            "mismatches": [],
        },
        "historical_calendar_acceptance": False,
        "authority_certified": False,
    }
    bundle = {
        "id": "hutime_japanese_daily_reference_20261022_v1",
        "provider_calendar_id": "1002.1",
        "source_url": "https://ap.hutime.org/cal/",
        "calendar_metadata_url": "https://datetime.hutime.org/calendar/1002.1",
        "source_archive_sha256": manifest["archive_sha256"],
        "supported_range_inclusive": report["lod_range_inclusive"],
        "methodology_advertised_range_inclusive": report["methodology_range_inclusive"],
        "reference_day_count": checked,
        "source_provenance": provenance,
        "monthly_endpoint_reconciliation": reconciled,
        "source_discrepancies_retained": [
            "Methodology page ends 2033-01-30, LOD entity ends 2031-01-22; the longer range is not accepted.",
            "Calendar directory label 1002.2 links to entity 1002.1; no distinct API 1002.2 data are claimed.",
            "Daily isLeap is a day-period flag; enclosing ofMonth.isLeap and printed 閏 identify leap months.",
            "2015 onward is the provider's reference projection, not a verified whole Jingu edition.",
        ],
        "scope": "Frozen HuTime daily reference facts. UTC+09 is an explicit modern reference-date convention, not historical Japanese local time, a complete Tenpo/Tang reconstruction or a full Jingu facsimile collation.",
        "historical_calendar_acceptance": False,
        "independent_whole_range_verification": False,
        "months": months,
    }
    return bundle, report


def read_fixture(folder: Path) -> tuple[dict[str, bytes], dict]:
    manifest = json.loads((folder / "manifest.json").read_bytes())
    raw = (folder / "captures.zip").read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["archive_sha256"]:
        raise ValueError("Daily source archive hash mismatch")
    with ZipFile(folder / "captures.zip") as archive:
        if len(archive.namelist()) != len(set(archive.namelist())) or set(
            archive.namelist()
        ) != set(manifest["files_sha256"]):
            raise ValueError("Daily source capture inventory changed")
        files = {n: archive.read(n) for n in archive.namelist()}
    if any(
        hashlib.sha256(raw).hexdigest() != manifest["files_sha256"][n]
        for n, raw in files.items()
    ):
        raise ValueError("Daily source capture file hash changed")
    return files, manifest


def freeze(source: Path, metadata: Path, destination: Path) -> None:
    acquisition = json.loads((source / "acquisition.json").read_bytes())
    files, batches = {}, []
    for batch in acquisition["batches"]:
        pair = {"request": batch["request_file"], "response": batch["response_file"]}
        for key in pair:
            raw = (source / pair[key]).read_bytes()
            if hashlib.sha256(raw).hexdigest() != batch[key + "_sha256"]:
                raise ValueError("Acquisition bytes changed before freezing")
            files[pair[key]] = raw
        batches.append(pair)
    for name in ["calendar-index.html", "calendar-metadata.json"]:
        files[name] = (metadata / name).read_bytes()
    destination.mkdir(parents=True, exist_ok=False)
    with ZipFile(destination / "captures.zip", "x", ZIP_DEFLATED) as archive:
        for name, raw in sorted(files.items()):
            info = ZipInfo(name, (2026, 10, 22, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, raw)
    manifest = {
        "format": "sukuyo_hutime_daily_capture_v1",
        "retrieved_on": "2026-10-22",
        "source": "https://ap.hutime.org/cal/",
        "archive_sha256": hashlib.sha256(
            (destination / "captures.zip").read_bytes()
        ).hexdigest(),
        "files_sha256": {
            n: hashlib.sha256(raw).hexdigest() for n, raw in sorted(files.items())
        },
        "daily_batches": batches,
        "scope": "Complete advertised date grid; raw nulls and metadata disagreements retained. Factual API responses, not a whole almanac facsimile.",
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--metadata-dir", type=Path)
    parser.add_argument(
        "--fixture", type=Path, default=ROOT / "tests/fixtures/sukuyo_hutime_daily_v1"
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.source_dir:
        if args.check or args.metadata_dir is None:
            parser.error("Freezing needs --metadata-dir and cannot use --check")
        freeze(args.source_dir, args.metadata_dir, args.fixture)
    files, manifest = read_fixture(args.fixture)
    bundle, report = normalize(files, manifest)
    for path, data in [
        (ROOT / "src/fatebridge/data/sukuyo_japanese_daily_v1.json", bundle),
        (ROOT / "docs/validation/sukuyo-japanese-daily-admission.json", report),
    ]:
        text = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.check:
            if path.read_text() != text:
                raise SystemExit(f"Daily reference drift: {path}")
        else:
            path.write_text(text)
    print(
        json.dumps(
            {
                k: report[k]
                for k in [
                    "daily_rows_checked",
                    "source_months",
                    "complete_in_lod_domain",
                    "complete_methodology_advertised_range",
                ]
            }
        )
    )


if __name__ == "__main__":
    main()

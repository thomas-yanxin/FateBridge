"""Freeze/rebuild the complete historical candidate; never download implicitly."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from fatebridge.validation.sukuyo_historical_sources import normalize

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = ROOT / "tests/fixtures/sukuyo_historical_calendar_v1"
DATA = ROOT / "src/fatebridge/data/sukuyo_japanese_historical_v1.json"
REPORT = ROOT / "docs/validation/sukuyo-historical-calendar-source-admission.json"


def freeze(capture: Path, target: Path) -> None:
    if target.exists():
        raise ValueError("Refusing to overwrite an existing historical fixture")
    acquisition = json.loads((capture / "acquisition.json").read_bytes())
    names = {"acquisition.json", "source-documents.json"}
    for record in acquisition["requests"]:
        names.update(
            record[key] for key in ("request_file", "response_file", "metadata_file")
        )
    documents = json.loads((capture / "source-documents.json").read_bytes())
    names.update(row["file"] for row in documents)
    payloads = {name: (capture / name).read_bytes() for name in sorted(names)}
    for row in documents:
        if hashlib.sha256(payloads[row["file"]]).hexdigest() != row["sha256"]:
            raise ValueError("Primary methodology document changed before freezing")
    # Validate the complete declared request set before creating the fixture.
    normalize(payloads, {"archive_sha256": "pending_archive_construction"})
    target.mkdir(parents=True)
    archive = target / "captures.zip"
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as bundle:
        for name, raw in payloads.items():
            info = ZipInfo(name, (2026, 10, 22, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            bundle.writestr(info, raw)
    manifest = {
        "format": "sukuyo_historical_calendar_frozen_capture_v1",
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "files_sha256": {
            name: hashlib.sha256(raw).hexdigest() for name, raw in payloads.items()
        },
        "source_documents": documents,
        "scope": "Complete declared requests and every raw response, including year zero, source discrepancies and legal reform truncation. No production calendar supplies expected facts.",
    }
    (target / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )


def read_fixture(directory: Path) -> tuple[dict[str, bytes], dict]:
    manifest = json.loads((directory / "manifest.json").read_bytes())
    raw = (directory / "captures.zip").read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["archive_sha256"]:
        raise ValueError("Historical source archive fingerprint changed")
    with ZipFile(directory / "captures.zip") as bundle:
        if len(bundle.namelist()) != len(set(bundle.namelist())):
            raise ValueError("Historical source archive has duplicate member names")
        files = {name: bundle.read(name) for name in bundle.namelist()}
    if {
        name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()
    } != manifest["files_sha256"]:
        raise ValueError("Historical source members differ from their manifest")
    return files, manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", type=Path)
    parser.add_argument("--fixture-dir", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.capture_dir:
        if args.check:
            parser.error("--check cannot freeze a new source capture")
        freeze(args.capture_dir, args.fixture_dir)
    files, manifest = read_fixture(args.fixture_dir)
    data, report = normalize(files, manifest)
    report_text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if not report["naoj_reference_import_eligible"]:
        if not args.check:
            REPORT.write_text(report_text)
        raise SystemExit(
            "NAOJ reference admission failed; retained findings cannot be hidden by writing a runtime table"
        )
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if DATA.read_text() != text or REPORT.read_text() != report_text:
            raise SystemExit("Historical reference table/report is stale")
    else:
        DATA.write_text(text)
        REPORT.write_text(report_text)
    print(
        json.dumps(
            {
                "reference_months": len(data["months"]),
                "reference_days": data["reference_day_count"],
                "cross_source_disagreement_days": report[
                    "cross_source_disagreement_dates"
                ],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

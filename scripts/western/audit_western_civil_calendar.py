"""Verify sealed date controls; no historical-clock or original-chart certificate."""

import argparse
import hashlib
import json
import zipfile
from datetime import date
from pathlib import Path

from fatebridge.core.civil_calendar import gregorian_date

ROOT = Path(__file__).resolve().parents[2]
REFERENCE_SHA256 = "d45a9da2daea6cd32945f2b7a4cf0827306da1dab58f16b5364a144deef7806b"
ARCHIVE_SHA256 = "62f45992910b5d603efaa87ea57a3d57ac9bff7e201279f00412fe68bb12dc5e"


def audit():
    p = ROOT / "tests/fixtures/western-civil-calendar-reference.json"
    z = p.with_name("western-civil-calendar-sources.zip")
    assert hashlib.sha256(p.read_bytes()).hexdigest() == REFERENCE_SHA256
    assert hashlib.sha256(z.read_bytes()).hexdigest() == ARCHIVE_SHA256
    ref = json.loads(p.read_text())
    assert ref["production_imports"] is False
    with zipfile.ZipFile(z) as archive:
        for source in ref["source_receipts"]:
            assert (
                hashlib.sha256(archive.read(source["file"])).hexdigest()
                == source["sha256"]
            )
    for row in ref["manual_conversion_controls"]:
        actual = gregorian_date(*row["date"], calendar=row["calendar"])
        assert [actual.year, actual.month, actual.day] == row["gregorian"]
        if "midnight_jd" in row:
            assert actual.toordinal() + 1721424.5 == row["midnight_jd"]
    supported, rejected = 0, 0
    for row in ref["supplementary_swiss_implementation_vectors"]:
        if not row["target_datetime_representable"]:
            try:
                gregorian_date(*row["date"], calendar=row["calendar"])
            except ValueError:
                rejected += 1
            else:
                raise AssertionError("Out-of-range target was silently normalized")
        else:
            actual = gregorian_date(*row["date"], calendar=row["calendar"])
            assert actual == date(*row["gregorian"])
            assert actual.toordinal() + 1721424.5 == row["midnight_jd"]
            supported += 1
    return dict(
        reference_sha256=REFERENCE_SHA256,
        archive_sha256=ARCHIVE_SHA256,
        source_assets_verified=len(ref["source_receipts"]),
        primary_numeric_examples=ref["primary_numeric_examples"],
        manual_conversion_controls=len(ref["manual_conversion_controls"]),
        supplementary_implementation_vectors=len(
            ref["supplementary_swiss_implementation_vectors"]
        ),
        supported_supplementary_vectors_reproduced=supported,
        unrepresentable_targets_rejected=rejected,
        bounded_date_conversion_passed=True,
        historical_clock_reconstruction_accepted=False,
        lilly_complete_chart_reproduced=False,
        full_original_text_acceptance=False,
        all_three_full_marks_established=False,
        all_four_full_marks_established=False,
        real_world_observations_added=0,
        scope=ref["scope"],
    )


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = audit()
    args.output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(value, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

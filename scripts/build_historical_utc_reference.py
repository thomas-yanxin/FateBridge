"""Extract IERS' historical UTC coefficients without importing the calculator."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "src/fatebridge/data/knowledge/western-historical-utc.json"


def extract(source: Path) -> dict:
    text = source.read_text(encoding="ascii")
    months = {
        "Jan.": 1,
        "Feb.": 2,
        "March": 3,
        "April": 4,
        "Jul.": 7,
        "Aug.": 8,
        "Sept.": 9,
        "Nov.": 11,
    }
    pattern = re.compile(
        r"^\s*(?:(\d{4})\s+)?(Jan\.|Feb\.|March|April|Jul\.|Aug\.|Sept\.|Nov\.)\s+1\s+-(.*)$",
        re.M,
    )
    year = reference = rate = None
    entries = []
    for match in pattern.finditer(text):
        if match[1]:
            year = int(match[1])
        if year is None:
            raise ValueError("IERS row has no inherited year")
        if year >= 1972:
            break
        offset = re.search(r"(\d)\.(\d[\d ]*)s\s*\+", match[3])
        if offset is None:
            raise ValueError("IERS row has no affine offset")
        drift = re.search(r"\(MJD\s*-\s*([\d ]+)\)\s*x\s*([\d. ]+)s", match[3])
        if drift:
            reference = int(drift[1].replace(" ", ""))
            rate = float(drift[2].replace(" ", ""))
        if reference is None or rate is None:
            raise ValueError("IERS row has no inherited MJD/drift")
        entries.append(
            {
                "effective_date": f"{year:04d}-{months[match[2]]:02d}-01",
                "offset_seconds": float(offset[1] + "." + offset[2].replace(" ", "")),
                "reference_mjd": reference,
                "rate_seconds_per_day": rate,
            }
        )
    dates = [row["effective_date"] for row in entries]
    if (
        len(entries) != 13
        or dates != sorted(set(dates))
        or dates[0] != "1961-01-01"
        or dates[-1] != "1968-02-01"
    ):
        raise ValueError("IERS historical coefficient table is incomplete")
    return {
        "source_url": "https://hpiers.obspm.fr/eoppc/bul/bulc/UTC-TAI.history",
        "source_title": "IERS Earth Orientation Centre: relationship between TAI and UTC",
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "scope": "Factual affine TAI-UTC coefficients for 1961-01-01 through 1971-12-31. Earlier epochs are outside this IERS table. Fractional clock adjustments are not integer leap seconds.",
        "formula": "TAI-UTC seconds = offset_seconds + (MJD_UTC - reference_mjd) * rate_seconds_per_day",
        "valid_until": "1972-01-01",
        "entries": entries,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source",
        nargs="?",
        type=Path,
        default=ROOT / "tests/fixtures/historical-utc-iers.txt",
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = extract(args.source)
    if args.check:
        if json.loads(TARGET.read_text(encoding="utf-8")) != data:
            raise SystemExit(
                "Historical UTC coefficients differ from the frozen IERS source"
            )
        print("Historical UTC reference matches IERS source")
    else:
        TARGET.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print("Extracted 13 IERS historical UTC coefficient rows")


if __name__ == "__main__":
    main()

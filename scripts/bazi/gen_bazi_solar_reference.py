"""Freeze independent JPL solar-clock references without importing FateBridge.

Protocol fixed before collection: eight whole years, the fifteenth of each
month at 12 UT, Greenwich equator, airless, five-second tolerance. 2000/2026
are development years; six other years are reserved for the frozen candidate.
The reserved values must not be used to tune coefficients or tolerance.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

YEARS = (1900, 1950, 1984, 2000, 2025, 2026, 2050, 2100)
DEVELOPMENT = (2000, 2026)
URL = "https://ssd.jpl.nasa.gov/api/horizons.api"


def fetch(year: int) -> dict:
    dates = [f"{year}-{month:02d}-15 12:00:00" for month in range(1, 13)]
    parameters = {
        "format": "json",
        "COMMAND": "'10'",
        "OBJ_DATA": "'NO'",
        "MAKE_EPHEM": "'YES'",
        "EPHEM_TYPE": "'OBSERVER'",
        "CENTER": "'coord@399'",
        "COORD_TYPE": "'GEODETIC'",
        "SITE_COORD": "'0,0,0'",
        "TLIST": " ".join(f"'{date}'" for date in dates),
        "TLIST_TYPE": "'CAL'",
        "TIME_TYPE": "'UT'",
        "QUANTITIES": "'34,49'",
        "CSV_FORMAT": "'YES'",
        "EXTRA_PREC": "'YES'",
        "CAL_TYPE": "'GREGORIAN'",
        "ANG_FORMAT": "'DEG'",
        "TIME_DIGITS": "'FRACSEC'",
        "APPARENT": "'AIRLESS'",
    }
    url = URL + "?" + urlencode(parameters)
    raw = subprocess.check_output(
        [
            "curl",
            "--fail",
            "--silent",
            "--show-error",
            "--max-time",
            "45",
            "--retry",
            "2",
            "--retry-delay",
            "1",
            url,
        ]
    )
    response = json.loads(raw)
    if "error" in response:
        raise ValueError(response["error"])
    text = response["result"]
    table = text.split("$$SOE\n", 1)[1].split("$$EOE", 1)[0]
    rows = []
    for row in csv.reader(io.StringIO(table)):
        moment = datetime.strptime(row[0].strip(), "%Y-%b-%d %H:%M:%S.%f")
        apparent_hours = float(row[3])
        dut1 = None if row[4].strip() == "n.a." else float(row[4])
        # Horizons UT is UTC after 1962, UT1 before it. Subtract the
        # reported DUT1 from LAT-UTC to isolate LAT-LMT, not LAT-UTC.
        difference_hours = (apparent_hours - 12 + 12) % 24 - 12
        equation = difference_hours * 60 - (dut1 or 0) / 60
        rows.append(
            {
                "instant": moment.replace(tzinfo=timezone.utc).isoformat(),
                "apparent_solar_hours": apparent_hours,
                "dut1_seconds": dut1,
                "equation_of_time_minutes": equation,
            }
        )
    if len(rows) != 12:
        raise ValueError(f"Expected all twelve months: {year}")
    return {
        "year": year,
        "split": "development" if year in DEVELOPMENT else "reserved",
        "request_url": url,
        "parameters": parameters,
        "response": response,
        "response_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Never overwrite frozen references; choose a new version")
    result = {
        "protocol_id": "jpl_solar_equation_96_v1",
        "source": URL,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "tolerance_seconds": 5,
        "development_years": list(DEVELOPMENT),
        "reserved_years": [year for year in YEARS if year not in DEVELOPMENT],
        "selection": "12 UT on the fifteenth of every month; eight preselected complete years",
        "scope": "Greenwich equatorial topocentric airless apparent solar clock minus UT1 mean clock; finite astronomy comparison, not life-event prediction",
        "collector_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "references": [fetch(year) for year in YEARS],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    args.output.with_suffix(".sha256").write_text(
        hashlib.sha256(args.output.read_bytes()).hexdigest() + "\n"
    )
    print(
        "Frozen 96 reference instants; 24 development, 72 reserved; tolerance fixed at 5 seconds"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

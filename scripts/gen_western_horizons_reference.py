"""Collect independent NASA/JPL observations, without importing FateBridge.

The 2 arcsecond tolerance and 12 UTC epochs are declared before collection.
Ordinary tests use the frozen responses, never a live network or our engine
as an oracle. Replay URLs, complete responses and SHA-256 remain in the file.
"""

import csv
import hashlib
import io
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
DATES = [
    "1900-01-01 00:00:00",
    "1950-06-21 12:00:00",
    "1969-07-20 20:17:00",
    "1972-01-01 00:00:00",
    "1985-12-31 05:15:00",
    "1990-04-06 01:33:00",
    "1999-12-31 23:59:00",
    "2000-02-29 18:15:00",
    "2024-03-20 06:30:00",
    "2026-10-22 00:00:00",
    "2050-12-21 12:00:00",
    "2099-12-31 23:59:00",
]
BODIES = dict(
    Sun=10,
    Moon=301,
    Mercury=199,
    Venus=299,
    Mars=499,
    Jupiter=599,
    Saturn=699,
    Uranus=799,
    Neptune=899,
    Pluto=999,
)


def fetch(body):
    name, number = body
    parameters = {
        "format": "json",
        "COMMAND": f"'{number}'",
        "OBJ_DATA": "'NO'",
        "MAKE_EPHEM": "'YES'",
        "EPHEM_TYPE": "'OBSERVER'",
        "CENTER": "'500@399'",
        "TLIST": " ".join(f"'{date}'" for date in DATES),
        "TLIST_TYPE": "'CAL'",
        "TIME_TYPE": "'UT'",
        "QUANTITIES": "'31,49'",
        "CSV_FORMAT": "'YES'",
        "EXTRA_PREC": "'YES'",
        "CAL_TYPE": "'GREGORIAN'",
        "ANG_FORMAT": "'DEG'",
    }
    url = URL + "?" + urlencode(parameters)
    response = json.loads(
        subprocess.check_output(
            [
                "curl",
                "--fail",
                "--silent",
                "--show-error",
                "--max-time",
                "45",
                "--retry",
                "3",
                "--retry-delay",
                "1",
                url,
            ]
        )
    )
    if "error" in response:
        raise RuntimeError(response["error"])
    text = response["result"]
    table = text.split("$$SOE\n", 1)[1].split("$$EOE", 1)[0]
    rows = []
    for row in csv.reader(io.StringIO(table)):
        moment = datetime.strptime(row[0].strip(), "%Y-%b-%d %H:%M:%S.%f")
        rows.append(
            {
                "utc": moment.replace(tzinfo=timezone.utc).isoformat(),
                "apparent_ecliptic_longitude": float(row[3]),
                "apparent_ecliptic_latitude": float(row[4]),
                "dut1_seconds": (None if row[5].strip() == "n.a." else float(row[5])),
            }
        )
    if len(rows) != len(DATES):
        raise ValueError(f"Incomplete Horizons data for {name}")
    return {
        "body": name,
        "parameters": parameters,
        "request_url": url,
        "response": response,
        "response_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "rows": rows,
    }


def main():
    with ThreadPoolExecutor(max_workers=4) as pool:
        references = list(pool.map(fetch, BODIES.items()))
    path = Path(__file__).resolve().parents[1] / "tests/fixtures/western-horizons.json"
    path.write_text(
        json.dumps(
            {
                "source": URL,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "scope": "Ten physical bodies, geocentric apparent IAU76/80 ecliptic of date; twelve UTC epochs, 1900-2099. Does not validate nodes, houses, classical rules or life-event predictions.",
                "tolerance_arcseconds": 2.0,
                "references": references,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Saved {len(references) * len(DATES)} independent observations to {path}")


if __name__ == "__main__":
    main()

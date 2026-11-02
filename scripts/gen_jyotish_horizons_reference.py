"""Freeze NASA/JPL reference data without importing FateBridge or Swiss Ephemeris.

Requires curl with a trusted system CA store. Ordinary tests read the frozen
fixture and never need network access. Expected angular tolerance is 2 arcsec
(Moshier vs DE441 and different precession/nutation models), chosen before
collecting the data; this is a bounded comparison, not an accuracy guarantee.
"""

import csv
import hashlib
import io
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
DATES = ["1985-12-31 05:15:00", "1990-04-06 01:33:00", "2000-02-29 18:15:00"]
BODIES = dict(
    Sun=10, Moon=301, Mercury=199, Venus=299, Mars=499, Jupiter=599, Saturn=699
)


def main():
    references = []
    for name, number in BODIES.items():
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
        raw = subprocess.check_output(
            ["curl", "--fail", "--silent", "--show-error", "--max-time", "30", url]
        )
        response = json.loads(raw)
        if "error" in response:
            raise RuntimeError(response["error"])
        text = response["result"]
        table = text.split("$$SOE\n", 1)[1].split("$$EOE", 1)[0]
        rows = []
        for row in csv.reader(io.StringIO(table)):
            when = datetime.strptime(row[0].strip(), "%Y-%b-%d %H:%M:%S.%f")
            rows.append(
                {
                    "utc": when.replace(tzinfo=timezone.utc).isoformat(),
                    "apparent_ecliptic_longitude": float(row[3]),
                    "dut1_seconds": float(row[5]),
                }
            )
        references.append(
            {
                "body": name,
                "parameters": parameters,
                "response": response,
                "response_sha256": hashlib.sha256(
                    response["result"].encode()
                ).hexdigest(),
                "rows": rows,
            }
        )
        print(f"Fetched {name}: {len(rows)} independent positions")
    path = Path(__file__).resolve().parents[1] / "tests/fixtures/jyotish-horizons.json"
    path.write_text(
        json.dumps(
            {
                "source": URL,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "scope": "Geocentric apparent IAU76/80 ecliptic-of-date; seven physical bodies, three UTC instants. Lahiri offset, nodes and ascendant are not independently validated by this dataset.",
                "tolerance_arcseconds": 2.0,
                "references": references,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

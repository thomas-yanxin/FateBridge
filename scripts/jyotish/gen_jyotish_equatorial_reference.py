"""NASA/JPL apparent equatorial-of-date checks, no production/SWE imports.

Predeclared tolerance2arcsec for Moshier vs DE441 and frame models. Ordinary
tests use the frozen response and never query the network.
"""

import argparse
import csv
import hashlib
import importlib.metadata
import io
import json
import math
import subprocess
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from urllib.parse import urlencode

URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
DATES = ["1985-12-31 05:15:00", "1990-04-06 01:33:00", "2000-02-29 18:15:00"]
BODIES = dict(
    Sun=10, Moon=301, Mercury=199, Venus=299, Mars=499, Jupiter=599, Saturn=699
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--from-frozen-ecliptic",
        action="store_true",
        help="Derive from previously fetched JPL quantity31 with independent ERFA IAU76/80 true obliquity; requires isolated pyerfa2.0.1.5, no Swiss/FateBridge",
    )
    if parser.parse_args().from_frozen_ecliptic:
        derive_frozen()
        return
    references = []
    for name, number in BODIES.items():
        parameters = {
            "format": "json",
            "COMMAND": f"'{number}'",
            "OBJ_DATA": "'NO'",
            "MAKE_EPHEM": "'YES'",
            "EPHEM_TYPE": "'OBSERVER'",
            "CENTER": "'500@399'",
            "TLIST": " ".join(f"'{day}'" for day in DATES),
            "TLIST_TYPE": "'CAL'",
            "TIME_TYPE": "'UT'",
            "QUANTITIES": "'2,49'",
            "CSV_FORMAT": "'YES'",
            "EXTRA_PREC": "'YES'",
            "CAL_TYPE": "'GREGORIAN'",
            "ANG_FORMAT": "'DEG'",
            "APPARENT": "'AIRLESS'",
        }
        raw = subprocess.check_output(
            [
                "curl",
                "--fail",
                "--silent",
                "--show-error",
                "--max-time",
                "30",
                URL + "?" + urlencode(parameters),
            ]
        )
        response = json.loads(raw)
        if "error" in response:
            raise RuntimeError(response["error"])
        text = response["result"]
        table = text.split("$$SOE\n", 1)[1].split("$$EOE", 1)[0]
        rows = []
        for row in csv.reader(io.StringIO(table)):
            instant = datetime.strptime(row[0].strip(), "%Y-%b-%d %H:%M:%S.%f").replace(
                tzinfo=timezone.utc
            )
            rows.append(
                {
                    "utc": instant.isoformat(),
                    "right_ascension": float(row[3]),
                    "declination": float(row[4]),
                    "dut1_seconds": float(row[5]),
                }
            )
        references.append(
            {
                "body": name,
                "parameters": parameters,
                "response": response,
                "response_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "rows": rows,
            }
        )
        print(name, len(rows))
    target = (
        Path(__file__).resolve().parents[2]
        / "tests/fixtures/jyotish-equatorial-horizons.json"
    )
    target.write_text(
        json.dumps(
            {
                "source": URL,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "scope": "Geocentric airless apparent equatorial-of-date positions. Does not independently validate traditional Ayana coefficient or prediction.",
                "tolerance_arcseconds": 2.0,
                "references": references,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )


def derive_frozen():
    import erfa

    assert importlib.metadata.version("pyerfa") == "2.0.1.5"
    root = Path(__file__).resolve().parents[2]
    original = root / "tests/fixtures/jyotish-horizons.json"
    data = json.loads(original.read_text())
    primary_time = json.loads(
        (root / "tests/fixtures/jyotish-time-reference.json").read_text()
    )
    offsets = []
    for line in primary_time["source_text"].splitlines():
        fields = line.split()
        if not fields or fields[0].startswith("#"):
            continue
        _, day, month, year, offset = fields
        offsets.append(
            (
                datetime(int(year), int(month), int(day), tzinfo=timezone.utc),
                int(offset),
            )
        )
    references = []
    for ref in data["references"]:
        table = ref["response"]["result"].split("$$SOE\n", 1)[1].split("$$EOE", 1)[0]
        rows = []
        for raw in csv.reader(io.StringIO(table)):
            stamp = datetime.strptime(raw[0].strip(), "%Y-%b-%d %H:%M:%S.%f").replace(
                tzinfo=timezone.utc
            )
            offset = next(value for when, value in reversed(offsets) if stamp >= when)
            elapsed = stamp - datetime(1970, 1, 1, tzinfo=timezone.utc)
            tt = float(
                Fraction(4881175, 2)
                + (
                    Fraction(elapsed.days * 86400 + elapsed.seconds)
                    + Fraction(offset)
                    + Fraction(32184, 1000)
                )
                / 86400
            )
            epsilon = float(erfa.obl80(tt, 0) + erfa.nut80(tt, 0)[1])
            lon, lat = map(math.radians, (float(raw[3]), float(raw[4])))
            x = math.cos(lat) * math.cos(lon)
            y = math.cos(lat) * math.sin(lon) * math.cos(epsilon) - math.sin(
                lat
            ) * math.sin(epsilon)
            z = math.cos(lat) * math.sin(lon) * math.sin(epsilon) + math.sin(
                lat
            ) * math.cos(epsilon)
            rows.append(
                {
                    "utc": stamp.isoformat(),
                    "right_ascension": math.degrees(math.atan2(y, x)) % 360,
                    "declination": math.degrees(math.asin(z)),
                    "ecliptic_longitude": float(raw[3]),
                    "ecliptic_latitude": float(raw[4]),
                    "true_obliquity_radians": epsilon,
                }
            )
        references.append(
            {
                "body": ref["body"],
                "original_response_sha256": ref["response_sha256"],
                "rows": rows,
            }
        )
    result = {
        "source": URL,
        "scope": "Derived equatorial-of-date from existing JPL apparent ecliptic quantity31 using ERFA IAU76/80 true obliquity; not a fresh quantity2 retrieval and not Swiss/production-generated. Same original21 reference positions, not additional epochs.",
        "tolerance_arcseconds": 2.0,
        "derivation": {
            "software": "pyerfa",
            "version": "2.0.1.5",
            "erfa_version": erfa.version.erfa_version,
            "model": "obl80+nut80[1]",
            "source_sha256": hashlib.sha256(original.read_bytes()).hexdigest(),
            "iers_source_sha256": hashlib.sha256(
                (root / "tests/fixtures/jyotish-time-reference.json").read_bytes()
            ).hexdigest(),
        },
        "references": references,
    }
    target = root / "tests/fixtures/jyotish-equatorial-horizons.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(target)


if __name__ == "__main__":
    main()

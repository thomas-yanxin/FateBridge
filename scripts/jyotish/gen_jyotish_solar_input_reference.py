"""Independent labels: frozen NASA Sun RA/DUT1 + primary IERS + ERFA GST06A.
No FateBridge imports, no production solar converter, no outcome cases.
"""

import hashlib
import importlib.metadata
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import erfa

assert (
    importlib.metadata.version("pyerfa") == "2.0.1.5"
), "Reference requires pyerfa==2.0.1.5"
root = Path(sys.argv[1])
out = Path(sys.argv[2])
files = {
    n: root / "tests/fixtures" / n
    for n in [
        "jyotish-equatorial-horizons.json",
        "jyotish-horizons.json",
        "jyotish-time-reference.json",
    ]
}
equ = json.loads(files["jyotish-equatorial-horizons.json"].read_text())
horizons = json.loads(files["jyotish-horizons.json"].read_text())
iers = json.loads(files["jyotish-time-reference.json"].read_text())
offsets = []
for line in iers["source_text"].splitlines():
    fields = line.split()
    if fields and not fields[0].startswith("#"):
        _, d, m, y, seconds = fields
        offsets.append(
            (datetime(int(y), int(m), int(d), tzinfo=timezone.utc), int(seconds))
        )
rows = []
for sun in next(r["rows"] for r in equ["references"] if r["body"] == "Sun"):
    stamp = sun["utc"]
    moment = datetime.fromisoformat(stamp)
    utc_jd = (
        moment.toordinal()
        + 1721424.5
        + (moment.hour * 3600 + moment.minute * 60 + moment.second) / 86400
    )
    dut1 = next(
        r["dut1_seconds"]
        for r in horizons["references"][0]["rows"]
        if r["utc"] == stamp
    )
    jd_ut1 = utc_jd + dut1 / 86400
    offset = next(n for start, n in reversed(offsets) if start <= moment)
    jd_tt = utc_jd + (offset + 32.184) / 86400
    gast = math.degrees(
        erfa.gst06a(2400000.5, jd_ut1 - 2400000.5, 2400000.5, jd_tt - 2400000.5)
    )
    day_fraction = (jd_ut1 + 0.5) % 1
    eot = (
        (gast - sun["right_ascension"] - 360 * day_fraction - 180 + 180) % 360 - 180
    ) * 240
    for longitude in [-180, -73.98765, 0, 10, 121.4667, 180]:
        for basis in ["local_mean_solar", "local_apparent_solar"]:
            seconds = (
                longitude * 240 + dut1 + (eot if basis == "local_apparent_solar" else 0)
            )
            label = moment.replace(tzinfo=None) + timedelta(seconds=seconds)
            rows.append(
                {
                    "utc": stamp,
                    "longitude": longitude,
                    "basis": basis,
                    "input_wall_datetime": label.isoformat(),
                    "dut1_seconds": dut1,
                    "sun_ra_degrees": sun["right_ascension"],
                    "gast_degrees": gast,
                    "eot_seconds": eot,
                }
            )
result = {
    "reference": "Frozen NASA/JPL equatorial Sun from ecliptic quantity31/ERFA obliquity, observed JPL DUT1, primary IERS TAI offsets, independent ERFA gst06a",
    "source_hashes": {
        k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in files.items()
    },
    "software": {
        "pyerfa": importlib.metadata.version("pyerfa"),
        "erfa": erfa.version.erfa_version,
    },
    "unique_epochs": 3,
    "longitudes": [-180, -73.98765, 0, 10, 121.4667, 180],
    "scope": "36 clock labels reuse3 previously used development epochs. Frame and modeled-vs-observed UT1 differences bounded by fixed1s UTC and2arcsec sky gates; not36 independent astronomical epochs, no reality predictions",
    "utc_tolerance_seconds": 1.0,
    "sky_tolerance_arcseconds": 2.0,
    "cases": rows,
}
out.write_text(json.dumps(result, indent=2) + "\n")
print("Wrote", len(rows), "labels,3 unique epochs")

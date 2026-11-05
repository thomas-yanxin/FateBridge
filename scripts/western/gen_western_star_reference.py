"""Generate an ERFA apparent-place reference, with no FateBridge/Swiss imports.

Use an explicit ERFA environment, e.g. uv run --with pyerfa==2.0.1.5.
Shared inputs are the frozen SIMBAD observations, not production sky positions.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

import erfa
import numpy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalogue", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = json.loads(args.catalogue.read_text())
    protocol = json.loads(args.protocol.read_text())
    assert source["catalogue_sha256"] == protocol["catalogue_sha256"]
    rows = []
    for epoch in protocol["epochs_tt"]:
        year, month, day = (int(x) for x in epoch[:10].split("-"))
        hour, minute, second = (int(x) for x in epoch[11:].split(":"))
        tt1, tt2 = erfa.dtf2d("TT", year, month, day, hour, minute, second)
        _, deps = erfa.nut06a(tt1, tt2)
        epsilon = erfa.obl06(tt1, tt2) + deps
        for star in source["stars"]:
            rh, rm, rs, dd, dm, ds, pmra, pmdec, rv, px = star["record"]
            ra = math.radians(15 * (rh + rm / 60 + rs / 3600))
            dec = math.radians(math.copysign(abs(dd) + dm / 60 + ds / 3600, dd))
            # SIMBAD is mu_alpha*cos(delta); ERFA expects d(alpha)/dt.
            ri, di, eo = erfa.atci13(
                ra,
                dec,
                math.radians(pmra / 3600000) / math.cos(dec),
                math.radians(pmdec / 3600000),
                px / 1000,
                rv,
                tt1,
                tt2,
            )
            equinox_ra = ri - eo
            x = math.cos(di) * math.cos(equinox_ra)
            y = math.cos(epsilon) * math.cos(di) * math.sin(equinox_ra) + math.sin(
                epsilon
            ) * math.sin(di)
            z = -math.sin(epsilon) * math.cos(di) * math.sin(equinox_ra) + math.cos(
                epsilon
            ) * math.sin(di)
            longitude = math.degrees(math.atan2(y, x)) % 360
            latitude = math.degrees(math.atan2(z, math.hypot(x, y)))
            rows.append(
                {
                    "epoch_tt": epoch,
                    "julian_day_tt": float(tt1 + tt2),
                    "star": star["name"],
                    "longitude": longitude,
                    "latitude": latitude,
                }
            )
    report = {
        "generator": "ERFA atci13 + nut06a/obl06; CIRS converted to equinox apparent RA with equation of origins, then true ecliptic of date",
        "erfa_version": erfa.__version__,
        "numpy_version": numpy.__version__,
        "source_sha256": hashlib.sha256(args.catalogue.read_bytes()).hexdigest(),
        "protocol_sha256": hashlib.sha256(args.protocol.read_bytes()).hexdigest(),
        "time_argument": "TT supplied as TDB approximation for atci13; periodic TT-TDB difference not explicitly converted",
        "earth_model": "ERFA epv00 analytic Earth; no production Earth states used",
        "scope": "Independent numerical library, shared catalogue observations; no covariance/binary orbit validation or ancient epoch precision certification",
        "rows": rows,
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"rows": len(rows), "erfa": erfa.__version__}))


if __name__ == "__main__":
    main()

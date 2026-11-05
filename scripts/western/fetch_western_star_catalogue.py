"""Acquire twenty identified stars from CDS SIMBAD; never generate sky oracles.

Explicit refresh only. Raw public responses are saved outside the repository;
review the selected ICRS astrometry before accepting generated catalogue data.
"""

import argparse
import concurrent.futures
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

STARS = [
    ("Algol", "beta Per"),
    ("Alcyone", "eta Tau"),
    ("Aldebaran", "alpha Tau"),
    ("Rigel", "beta Ori"),
    ("Capella", "alpha Aur"),
    ("Betelgeuse", "alpha Ori"),
    ("Sirius", "alpha CMa"),
    ("Pollux", "beta Gem"),
    ("Procyon", "alpha CMi"),
    ("Regulus", "alpha Leo"),
    ("Denebola", "beta Leo"),
    ("Algorab", "delta Crv"),
    ("Spica", "alpha Vir"),
    ("Arcturus", "alpha Boo"),
    ("Alphecca", "alpha CrB"),
    ("Antares", "alpha Sco"),
    ("Vega", "alpha Lyr"),
    ("Deneb Algedi", "delta Cap"),
    ("Fomalhaut", "alpha PsA"),
    ("Markab", "alpha Peg"),
]


def fetch(pair, raw_directory):
    name, identifier = pair
    url = "https://simbad.cds.unistra.fr/simbad/sim-id?" + urlencode(
        {"Ident": identifier, "output.format": "ASCII"}
    )
    raw = urlopen(
        Request(url, headers={"User-Agent": "FateBridge source audit"}), timeout=30
    ).read()
    (raw_directory / (name.replace(" ", "-") + ".txt")).write_bytes(raw)
    text = raw.decode()
    position = re.search(
        r"Coordinates\(ICRS,ep=J2000,eq=2000\):\s+(\d+)\s+(\d+)\s+([\d.]+)\s+([+-]\d+)\s+(\d+)\s+([\d.]+)([^\n]*)",
        text,
    )
    pm = re.search(r"Proper motions:\s+([\d.+-]+)\s+([\d.+-]+)([^\n]*)", text)
    px = re.search(r"Parallax:\s+([\d.+-]+)([^\n]*)", text)
    rv = re.search(r"Radial Velocity:\s+([\d.+-]+)([^\n]*)", text)
    if not all((position, pm, px, rv)):
        raise ValueError(
            f"Incomplete SIMBAD astrometry for {identifier}; no zero defaults"
        )
    record = [float(v) for v in position.groups()[:6]] + [
        float(pm[1]),
        float(pm[2]),
        float(rv[1]),
        float(px[1]),
    ]
    if not all(math.isfinite(v) for v in record) or record[-1] <= 0:
        raise ValueError(f"Invalid astrometry for {identifier}")
    return {
        "name": name,
        "identifier": identifier,
        "source_url": url,
        "response_sha256": hashlib.sha256(raw).hexdigest(),
        "record": record,
        "coordinate_reference": position[7].strip(),
        "proper_motion_reference": pm[3].strip(),
        "radial_velocity_reference": rv[2].strip(),
        "parallax_reference": px[2].strip(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-directory", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    args.raw_directory.mkdir(parents=True, exist_ok=True)
    args.output_directory.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(lambda pair: fetch(pair, args.raw_directory), STARS))
    lines = [
        "# FateBridge twenty-star catalogue: selected numerical facts from CDS SIMBAD.",
        "# ICRS epoch J2000; pmRA*cos(dec), pmDec and parallax in mas; RV km/s.",
        "# Identifications, source references and receipts are in sources.json.",
    ]
    for index, row in enumerate(rows):
        row["catalogue_key"] = f"FBW{index:02}"
        lines.append(
            f"FBW{index:02},FBW{index:02},ICRS,"
            + ",".join(str(v) for v in row["record"])
            + ",0"
        )
    data = ("\n".join(lines) + "\n").encode()
    (args.output_directory / "sefstars.txt").write_bytes(data)
    receipt = {
        "catalogue_id": "fatebridge_simbad_western_twenty_20261022",
        "acquired_at": datetime.now(timezone.utc).isoformat(),
        "frame": "ICRS",
        "epoch": "J2000.0",
        "record_fields": [
            "ra_h",
            "ra_m",
            "ra_s",
            "dec_signed_d",
            "dec_m",
            "dec_s",
            "pm_ra_cosdec_mas_yr",
            "pm_dec_mas_yr",
            "radial_velocity_km_s",
            "parallax_mas",
        ],
        "catalogue_sha256": hashlib.sha256(data).hexdigest(),
        "scope": "Twenty explicitly identified objects; current astrometry, not an ancient observational reconstruction. Linear space motion does not model binary orbits or catalogue covariance.",
        "stars": rows,
    }
    (args.output_directory / "sources.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {"stars": len(rows), "catalogue_sha256": receipt["catalogue_sha256"]}
        )
    )


if __name__ == "__main__":
    main()

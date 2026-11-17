"""Cross-check the type-21 Chiron adapter against Horizons observer quantity31."""

import csv
import hashlib
import io
import json
import subprocess
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "tests/fixtures/human-design-cycles-reference.json"
OUTPUT = ROOT / "tests/fixtures/human-design-cycles-horizons.json"


def main() -> None:
    reference = json.loads(REFERENCE.read_text())
    anchors = []
    for row in reference["records"]:
        if row["body"] == "Chiron":
            anchors.extend(
                [
                    {
                        "jd_tt": row["birth"]["jd_tt"],
                        "longitude": row["natal_longitude"],
                    },
                    {k: row["contacts"][-1][k] for k in ("jd_tt", "longitude")},
                ]
            )
    parameters = {
        "format": "json",
        "COMMAND": "'2060;'",
        "OBJ_DATA": "'NO'",
        "MAKE_EPHEM": "'YES'",
        "EPHEM_TYPE": "'OBSERVER'",
        "CENTER": "'500@399'",
        "TLIST": " ".join(f"'{r['jd_tt']:.12f}'" for r in anchors),
        "TLIST_TYPE": "'JD'",
        "TIME_TYPE": "'TT'",
        "TIME_DIGITS": "'FRACSEC'",
        "CAL_FORMAT": "'JD'",
        "QUANTITIES": "'31'",
        "CSV_FORMAT": "'YES'",
        "EXTRA_PREC": "'YES'",
        "CAL_TYPE": "'GREGORIAN'",
        "ANG_FORMAT": "'DEG'",
    }
    url = "https://ssd.jpl.nasa.gov/api/horizons.api?" + urlencode(parameters)
    raw = subprocess.check_output(
        ["curl", "--fail", "--silent", "--show-error", "--max-time", "45", url]
    )
    response = json.loads(raw)
    if "error" in response:
        raise ValueError(response["error"])
    table = response["result"].split("$$SOE", 1)[1].split("$$EOE", 1)[0].strip()
    comparisons = []
    for cells in csv.reader(io.StringIO(table)):
        jd, longitude = float(cells[0]), float(cells[3])
        anchor = min(anchors, key=lambda row: abs(row["jd_tt"] - jd))
        if abs(anchor["jd_tt"] - jd) * 86400 > 0.001:
            raise ValueError("Unmatched Horizons TT")
        comparisons.append(
            {
                "jd_tt": jd,
                "longitude": longitude,
                "independent_longitude": anchor["longitude"],
                "error_arcseconds": abs(
                    (longitude - anchor["longitude"] + 180) % 360 - 180
                )
                * 3600,
            }
        )
    if len(comparisons) != len(anchors):
        raise ValueError("Incomplete Horizons cross-check")
    result = {
        "reference_sha256": hashlib.sha256(REFERENCE.read_bytes()).hexdigest(),
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "parameters": parameters,
        "url": url,
        "raw_response_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_response_utf8": raw.decode(),
        "rows": comparisons,
        "tolerance_arcseconds": 2.0,
        "scope": "Six predetermined birth/last-contact TT anchors, geocentric apparent ecliptic-of-date. Confirms selected SPK21/Skyfield pipeline positions; not all dates or event timing.",
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "anchors": len(comparisons),
                "maximum_error_arcseconds": max(
                    r["error_arcseconds"] for r in comparisons
                ),
            }
        )
    )


if __name__ == "__main__":
    main()

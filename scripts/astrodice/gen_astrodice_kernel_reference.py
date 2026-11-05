"""Freeze geocentric geometric ICRF vectors from NASA/JPL, not our engine.

Use a frozen protocol with tolerances chosen before collecting comparisons.
Preserve an unavailable requested endpoint as missing evidence; never replace
it with the supplementary epoch or count it as a successful comparison.
"""

import argparse
import csv
import hashlib
import io
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

URL = "https://ssd.jpl.nasa.gov/api/horizons.api"


def jd_tt(date):
    value = datetime.fromisoformat(date)
    seconds = value.hour * 3600 + value.minute * 60 + value.second
    return value.toordinal() + 1721424.5 + seconds / 86400


def request(number, dates):
    parameters = {
        "format": "json",
        "COMMAND": f"'{number}'",
        "OBJ_DATA": "'NO'",
        "MAKE_EPHEM": "'YES'",
        "EPHEM_TYPE": "'VECTORS'",
        "CENTER": "'500@399'",
        "TLIST": "'" + " ".join(format(jd_tt(d), ".17g") for d in dates) + "'",
        "TLIST_TYPE": "'JD'",
        "TIME_TYPE": "'TT'",
        "VEC_CORR": "'NONE'",
        "REF_SYSTEM": "'ICRF'",
        "REF_PLANE": "'FRAME'",
        "VEC_TABLE": "'2'",
        "OUT_UNITS": "'AU-D'",
        "CSV_FORMAT": "'YES'",
        "CAL_TYPE": "'GREGORIAN'",
    }
    url = URL + "?" + urlencode(parameters)
    raw = subprocess.check_output(
        ["curl", "--fail", "--silent", "--show-error", "--max-time", "45", url]
    )
    response = json.loads(raw)
    return {
        "parameters": parameters,
        "request_url": url,
        "response": response,
        "raw_response_sha256": hashlib.sha256(raw).hexdigest(),
        "result_sha256": hashlib.sha256(
            response.get("result", "").encode()
        ).hexdigest(),
        "raw_response_utf8": raw.decode(),
    }


def fetch(item, protocol):
    name, number = item
    dates = protocol["dates_tt"] + protocol["supplemental_dates_tt"]
    original_request = request(number, dates)
    text = original_request["response"].get("result", "")
    unavailable = []
    failed_request = None
    if "$$SOE" not in text:
        error = original_request["response"].get("error", text)
        # This exact endpoint restriction was observed before collection. Do
        # not turn an arbitrary server/error response into a partial reference.
        if "No ephemeris" not in error or "9999-DEC-30" not in error:
            raise RuntimeError(error)
        failed_request = original_request
        last = "9999-12-31T12:00:00"
        assert last in dates
        dates = [d for d in dates if d != last]
        unavailable.append({"date_tt": last, "jd_tt": jd_tt(last), "reason": error})
        original_request = request(number, dates)
        text = original_request["response"].get("result", "")
    assert all(
        value in text
        for value in (
            "Reference frame : ICRF",
            "GEOMETRIC cartesian",
            "JDTT",
            "$$SOE",
            "Center body name: Earth (399)",
            "Output units    : AU-D",
        )
    ), text
    rows = []
    table = text.split("$$SOE\n", 1)[1].split("$$EOE", 1)[0]
    for date, row in zip(dates, csv.reader(io.StringIO(table)), strict=True):
        epoch = float(row[0])
        assert abs(epoch - jd_tt(date)) <= 1e-9
        rows.append(
            {
                "date_tt": date,
                "jd_tt": epoch,
                "position_au": list(map(float, row[2:5])),
                "velocity_au_per_day": list(map(float, row[5:8])),
            }
        )
    return {
        "body": name,
        "target_id": number,
        **original_request,
        "rows": rows,
        "unavailable_requested_epochs": unavailable,
        "failed_original_request": failed_request,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert not any(n.startswith(("fatebridge", "swisseph")) for n in sys.modules)
    protocol = json.loads(args.protocol.read_text())
    with ThreadPoolExecutor(max_workers=2) as pool:
        references = list(
            pool.map(lambda item: fetch(item, protocol), protocol["targets"].items())
        )
    result = {
        "source": URL,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": hashlib.sha256(args.protocol.read_bytes()).hexdigest(),
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "references": references,
        "scope": protocol["scope"],
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "available": sum(len(r["rows"]) for r in references),
                "unavailable_requested": sum(
                    len(r["unavailable_requested_epochs"]) for r in references
                ),
            }
        )
    )


if __name__ == "__main__":
    main()

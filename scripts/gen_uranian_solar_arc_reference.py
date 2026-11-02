"""Freeze NASA/JPL Sun epochs independently of FateBridge and Swiss Ephemeris.

The position/arc tolerances (2/4 arcseconds) are fixed before comparison.
New network epochs are in 2000/2001; --from-recorded preserves the original
epochs and retrieval date. Ordinary tests never call the network.
"""

import argparse
import csv
import hashlib
import io
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
CASES = [
    ("2000-01-01", 100),
    ("2000-07-01", 100),
    ("2000-03-10", 30),
    ("2000-12-30", 30),
]


def from_recorded(path):
    original = json.loads(path.read_text())
    text = original["response"]["result"]
    # That older collector hashes raw HTTP JSON bytes, but saves only decoded
    # JSON. Its transport digest cannot be reverified from a reserialization.
    # Preserve it under its original meaning, and pin the exact source fixture
    # plus the decoded ephemeris text that can actually be reverified here.
    table = text.split("$$SOE\n", 1)[1].split("$$EOE", 1)[0]
    rows = []
    for row in csv.reader(io.StringIO(table)):
        moment = datetime.strptime(row[0].strip(), "%Y-%b-%d %H:%M:%S.%f").replace(
            tzinfo=timezone.utc
        )
        rows.append(
            {"utc": moment.isoformat(), "apparent_ecliptic_longitude": float(row[3])}
        )
    available = {r["utc"] for r in rows}
    previously_parsed = {
        datetime.fromisoformat(r["utc"]).isoformat(): r["sun_longitude"]
        for r in original["rows"]
    }
    if {r["utc"]: r["apparent_ecliptic_longitude"] for r in rows} != previously_parsed:
        raise ValueError("Saved parsed positions disagree with the recorded NASA table")
    cases = []
    for pair in original["pairs"]:
        start = datetime.fromisoformat(pair["design_candidate_utc"])
        end = datetime.fromisoformat(pair["birth_utc"])
        assert start.isoformat() in available and end.isoformat() in available
        elapsed = end - start
        cases.append(
            {
                "birth_utc": start.isoformat(),
                "analysis_utc": (start + elapsed * 365.25).isoformat(),
                "progressed_utc": end.isoformat(),
                "key_years": elapsed.total_seconds() / 86400,
            }
        )
    return {
        "source": URL,
        "retrieved_at": original["retrieved_at"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "collection_mode": "Reparse existing independently fetched NASA/JPL response; no fresh network retrieval",
        "source_fixture": str(path),
        "source_fixture_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "epoch_selection_scope": original["scope"],
        "scope": "Eight existing NASA apparent Sun observations and four derived symbolic-key pairs. Epochs were selected for a different engine study; positions are independently from the raw NASA response. No independent choice of Design epoch, original rulebook or outcome validation.",
        "position_tolerance_arcseconds": 2.0,
        "arc_tolerance_arcseconds": 4.0,
        "year_days": 365.25,
        "cases": cases,
        "request_url": original["source_url"],
        "response": original["response"],
        "response_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "response_hash_policy": "SHA256 of decoded result UTF8 text",
        "original_http_json_bytes_sha256": original["response_sha256"],
        "original_http_json_bytes_preserved": False,
        "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--from-recorded",
        type=Path,
        help="Explicitly reparse an existing full NASA response; record its original retrieval time and source hash",
    )
    args = parser.parse_args()
    if args.from_recorded is not None:
        result = from_recorded(args.from_recorded)
        target = (
            Path(__file__).resolve().parents[1]
            / "tests/fixtures/uranian-solar-arc-horizons.json"
        )
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(
            f"Reparsed {len(result['rows'])} NASA Sun positions and {len(result['cases'])} symbolic-key pairs from recorded response"
        )
        return
    cases, dates = [], []
    for birth, years in CASES:
        start = datetime.fromisoformat(birth).replace(tzinfo=timezone.utc)
        progressed = start + timedelta(days=years)
        dates.extend(
            [
                start.strftime("%Y-%m-%d %H:%M:%S"),
                progressed.strftime("%Y-%m-%d %H:%M:%S"),
            ]
        )
        cases.append(
            {
                "birth_utc": start.isoformat(),
                "analysis_utc": (start + timedelta(days=365.25 * years)).isoformat(),
                "progressed_utc": progressed.isoformat(),
                "key_years": years,
            }
        )
    parameters = {
        "format": "json",
        "COMMAND": "'10'",
        "OBJ_DATA": "'NO'",
        "MAKE_EPHEM": "'YES'",
        "EPHEM_TYPE": "'OBSERVER'",
        "CENTER": "'500@399'",
        "TLIST": " ".join(f"'{d}'" for d in dates),
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
        [
            "curl",
            "--fail",
            "--silent",
            "--show-error",
            "--connect-timeout",
            "10",
            "--max-time",
            "45",
            "--retry",
            "2",
            "--retry-all-errors",
            "--retry-delay",
            "1",
            url,
        ]
    )
    response = json.loads(raw)
    if "error" in response:
        raise RuntimeError(response["error"])
    text = response["result"]
    table = text.split("$$SOE\n", 1)[1].split("$$EOE", 1)[0]
    rows = []
    for row in csv.reader(io.StringIO(table)):
        moment = datetime.strptime(row[0].strip(), "%Y-%b-%d %H:%M:%S.%f").replace(
            tzinfo=timezone.utc
        )
        rows.append(
            {
                "utc": moment.isoformat(),
                "apparent_ecliptic_longitude": float(row[3]),
                "dut1_seconds": None if row[5].strip() == "n.a." else float(row[5]),
            }
        )
    assert len(rows) == len(dates)
    result = {
        "source": URL,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Eight geocentric apparent Sun positions and four differences. No hypothetical-body, original-rulebook or outcome validation.",
        "position_tolerance_arcseconds": 2.0,
        "arc_tolerance_arcseconds": 4.0,
        "year_days": 365.25,
        "cases": cases,
        "parameters": parameters,
        "request_url": url,
        "response": response,
        "response_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "response_hash_policy": "SHA256 of decoded result UTF8 text",
        "http_json_text": raw.decode("utf-8"),
        "http_json_bytes_sha256": hashlib.sha256(raw).hexdigest(),
        "original_http_json_bytes_sha256": hashlib.sha256(raw).hexdigest(),
        "original_http_json_bytes_preserved": True,
        "collection_mode": "Fresh NASA/JPL HTTP retrieval",
        "rows": rows,
    }
    target = (
        Path(__file__).resolve().parents[1]
        / "tests/fixtures/uranian-solar-arc-horizons.json"
    )
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        f"Saved {len(rows)} independent Sun positions and {len(cases)} symbolic-key pairs"
    )


if __name__ == "__main__":
    main()

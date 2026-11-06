"""Freeze independent JPL-derived solar/lunar returns, without project imports.

Declared before collection: 120 seconds solar / 15 seconds lunar tolerances
(the natal and return longitudes each carry the ephemeris comparison error).
The oracle uses only NASA longitudes: fixed scans plus secant refinement.
"""

import csv
import hashlib
import io
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
CASES = [
    ("leap_birth", "2000-02-29T18:15:00+00:00", "2024-03-01T00:00:00+00:00"),
    ("civil_year_boundary", "1985-12-31T05:15:00+00:00", "2026-01-01T00:00:00+00:00"),
    ("future_time_scales", "1990-04-06T01:33:00+00:00", "2099-12-31T23:59:00+00:00"),
]


def fetch(body, *, times=None, start=None, end=None, step=None):
    params = {
        "format": "json",
        "COMMAND": f"'{body}'",
        "OBJ_DATA": "'NO'",
        "MAKE_EPHEM": "'YES'",
        "EPHEM_TYPE": "'OBSERVER'",
        "CENTER": "'500@399'",
        "TIME_TYPE": "'UT'",
        "QUANTITIES": "'31'",
        "CSV_FORMAT": "'YES'",
        "EXTRA_PREC": "'YES'",
        "CAL_TYPE": "'GREGORIAN'",
        "ANG_FORMAT": "'DEG'",
        "TIME_DIGITS": "'FRACSEC'",
    }

    def fmt(moment):
        return moment.strftime("%Y-%m-%d %H:%M:%S.%f")

    if times is not None:
        params.update(
            TLIST=" ".join(f"'{fmt(moment)}'" for moment in times), TLIST_TYPE="'CAL'"
        )
    else:
        params.update(
            START_TIME=f"'{fmt(start)}'",
            STOP_TIME=f"'{fmt(end)}'",
            STEP_SIZE=f"'{step}d'",
        )
    raw = subprocess.check_output(
        [
            "curl",
            "--fail",
            "--silent",
            "--show-error",
            "--retry",
            "3",
            "--retry-delay",
            "1",
            "--max-time",
            "45",
            URL + "?" + urlencode(params),
        ]
    )
    response = json.loads(raw)
    if "error" in response:
        raise ValueError(response["error"])
    result = response["result"]
    table = result.split("$$SOE\n", 1)[1].split("$$EOE", 1)[0]
    rows = []
    for row in csv.reader(io.StringIO(table)):
        label = row[0].strip()
        # Range tables can use minute precision for minute-aligned scans even
        # with TIME_DIGITS set. Refinement TLIST rows must retain seconds.
        pattern = "%Y-%b-%d %H:%M:%S.%f" if "." in label else "%Y-%b-%d %H:%M"
        if times is not None and pattern.endswith("%M"):
            raise ValueError("NASA refinement lost sub-minute timestamp precision")
        moment = datetime.strptime(label, pattern).replace(tzinfo=timezone.utc)
        rows.append((moment, float(row[3])))
    return rows, {
        "parameters": params,
        "response": response,
        "response_sha256": hashlib.sha256(result.encode()).hexdigest(),
    }


def offset(value, target):
    return (value - target + 180) % 360 - 180


def collect(planet, body, lookback, step):
    recordings = []
    birth_rows, record = fetch(
        body, times=[datetime.fromisoformat(case[1]) for case in CASES]
    )
    recordings.append(record)
    births = {moment: longitude for moment, longitude in birth_rows}
    pending = []
    for key, birth, analysis in CASES:
        born, until = datetime.fromisoformat(birth), datetime.fromisoformat(analysis)
        target = births[born]
        rows, record = fetch(
            body, start=until - timedelta(days=lookback), end=until, step=step
        )
        recordings.append(record)
        brackets = [
            (left, right)
            for left, right in zip(rows, rows[1:])
            if offset(left[1], target) <= 0 <= offset(right[1], target)
            and offset(right[1], target) - offset(left[1], target) < 180
        ]
        if not brackets:
            raise ValueError(f"No NASA return bracket for {key}/{planet}")
        (low, lo_lon), (high, hi_lon) = brackets[-1]
        pending.append(
            dict(
                case_id=key,
                planet=planet,
                birth_utc=birth,
                analysis_utc=analysis,
                natal_longitude=target,
                low=low,
                high=high,
                low_offset=offset(lo_lon, target),
                high_offset=offset(hi_lon, target),
            )
        )
    # Each iteration evaluates all independent cases in a single NASA query.
    for _ in range(6):
        guesses = [
            item["low"]
            + (item["high"] - item["low"])
            * (-item["low_offset"])
            / (item["high_offset"] - item["low_offset"])
            for item in pending
        ]
        rows, record = fetch(body, times=guesses)
        recordings.append(record)
        for item, guess in zip(pending, guesses):
            # Horizons rounds requested timestamps to milliseconds in its table.
            when, lon = min(rows, key=lambda row: abs((row[0] - guess).total_seconds()))
            error = offset(lon, item["natal_longitude"])
            item["expected_return_utc"] = when.isoformat()
            item["oracle_residual_arcseconds"] = abs(error) * 3600
            if error < 0:
                item["low"], item["low_offset"] = when, error
            else:
                item["high"], item["high_offset"] = when, error
        if all(item["oracle_residual_arcseconds"] < 0.002 for item in pending):
            break
    if any(item["oracle_residual_arcseconds"] >= 0.002 for item in pending):
        raise ValueError("NASA refinement did not converge; no reference file written")
    for item in pending:
        for key in ("low", "high", "low_offset", "high_offset"):
            item.pop(key)
    print(f"Collected {len(pending)} independent {planet} returns")
    return pending, recordings


def main():
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [
            pool.submit(collect, "Sun", 10, 370, 10),
            pool.submit(collect, "Moon", 301, 32, 1),
        ]
        data = [job.result() for job in jobs]
    path = (
        Path(__file__).resolve().parents[2]
        / "tests/fixtures/western-returns-horizons.json"
    )
    path.write_text(
        json.dumps(
            {
                "source": URL,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "scope": "Geocentric tropical apparent longitudes, independent natal target and latest preceding return; UTC and Horizons' last-known-leap assumption.",
                "tolerances_seconds": {"Sun": 120, "Moon": 15},
                "cases": [case for group, _ in data for case in group],
                "recordings": [record for _, records in data for record in records],
            },
            indent=2,
        )
        + "\n"
    )
    print(path)


if __name__ == "__main__":
    main()

"""Independent fractional-calendar lunar direction probes for a frozen plan.

Maintenance only: isolated pyerfa2.0.1.5/numpy2.5.4. All requests, including
failures, are journalled; no FateBridge/Swiss import or residual selection.
"""

import argparse
import csv
import hashlib
import importlib.metadata
import io
import json
import math
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

from gen_astrodice_apparent_reference import (
    MONTHS,
    direction_and_rate,
    julian_day_tt,
    project_motion,
)

URL = "https://ssd.jpl.nasa.gov/api/horizons.api"


def fetch(dates, protocol, archive, label):
    month_names = {number: name for name, number in MONTHS.items()}

    def calendar_label(date):
        value = datetime.fromisoformat(date)
        # Horizons requires an AD marker for calendar years below100.
        fraction = f".{value.microsecond:06d}" if value.microsecond else ""
        return f"{value.year}ad-{month_names[value.month]}-{value.day:02} {value.hour:02}:{value.minute:02}:{value.second:02}{fraction}"

    parameters = {
        **protocol["reference_parameters"],
        "TLIST": " ".join(f"'{calendar_label(date)}'" for date in dates),
    }
    url = URL + "?" + urlencode(parameters)
    raw = subprocess.check_output(
        ["curl", "--fail", "--silent", "--show-error", "--max-time", "45", url]
    )
    response = json.loads(raw)
    record = {
        "parameters": parameters,
        "request_url": url,
        "raw_response_utf8": raw.decode(),
        "raw_response_sha256": hashlib.sha256(raw).hexdigest(),
        "response": response,
        "result_sha256": hashlib.sha256(
            response.get("result", "").encode()
        ).hexdigest(),
    }
    (archive / f"{label}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n"
    )
    if "$$SOE\n" not in response.get("result", ""):
        return {
            **record,
            "rows": [],
            "error": response.get("error", response.get("result", "")),
        }
    rows = []
    for raw in csv.reader(
        io.StringIO(response["result"].split("$$SOE\n", 1)[1].split("$$EOE", 1)[0])
    ):
        match = re.fullmatch(
            r"\s*(\d{1,4})-(\w{3})-(\d{2}) (\d{2}):(\d{2}):(\d{2})\.(\d+)\s*", raw[0]
        )
        if match is None:
            raise ValueError("Unexpected lunar reference epoch format")
        year, month, day, hour, minute, second, fraction = match.groups()
        if len(fraction) > 6 and any(c != "0" for c in fraction[6:]):
            raise ValueError("Sub-microsecond reference label cannot be represented")
        date = datetime(
            int(year),
            MONTHS[month],
            int(day),
            int(hour),
            int(minute),
            int(second),
            int(fraction[:6].ljust(6, "0")),
        ).isoformat()
        ra, dec = map(float, raw[3:5])
        if not math.isfinite(ra) or not math.isfinite(dec):
            raise ValueError("Nonfinite lunar reference position")
        rows.append(
            {
                "date_tt": date,
                "ra_degrees": ra,
                "dec_degrees": dec,
                "printed_values": [v.strip() for v in raw[3:5]],
                "icrf_unit_direction": direction_and_rate(ra, dec, 0, 0)[0],
            }
        )
    if len(rows) != len(dates) or {r["date_tt"] for r in rows} != set(dates):
        raise ValueError("Lunar request epoch coverage mismatch")
    return {**record, "rows": rows}

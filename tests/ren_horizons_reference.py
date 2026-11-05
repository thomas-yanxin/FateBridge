"""Independent Horizons TT parsing and IAU frame arithmetic, with no production imports."""

import csv
import io
import json
import math
from datetime import datetime

import erfa
import numpy as np

J2000 = datetime(2000, 1, 1, 12)


def parse(path, expected):
    data = json.loads(path.read_text())
    if data.get("error"):
        raise ValueError(data["error"])
    if data.get("signature", {}).get("source") != "NASA/JPL Horizons API":
        raise ValueError("Unexpected remote source")
    before, table = data["result"].split("$$SOE", 1)
    table = table.split("$$EOE", 1)[0]
    for token in (
        "Target body name: Sun (10)",
        "Center body name: Earth (399)",
        "Center-site name: GEOCENTRIC",
        "{source: DE441}",
        "NO (AIRLESS)",
        "Calendar mode   : Gregorian",
    ):
        if token not in before:
            raise ValueError("Different query geometry: " + token)
    header = next((line for line in before.splitlines() if "Date__(TT)" in line))
    names = [s.strip() for s in next(csv.reader([header]))]
    keys = ("ObsEcLon", "ObsEcLat", "RA_(ICRF-a-app)", "DEC_(ICRF-a-app)")
    indexes = {key: names.index(key) for key in keys}
    rows = []
    for fields in csv.reader(io.StringIO(table.strip())):
        dt = datetime.strptime(fields[0].strip(), "%Y-%b-%d %H:%M:%S.%f")
        row = {"tt_label": dt.isoformat(sep=" ", timespec="milliseconds")}
        row.update({key: float(fields[i]) for key, i in indexes.items()})
        if not all((math.isfinite(row[k]) for k in keys)):
            raise ValueError("Non-finite remote angle")
        if (
            not 0 <= row["RA_(ICRF-a-app)"] < 360
            or not -90 <= row["DEC_(ICRF-a-app)"] <= 90
        ):
            raise ValueError("Remote inertial angle out of range")
        rows.append(row)
    if [row["tt_label"] for row in rows] != expected:
        raise ValueError("Returned TT cohort differs from submitted labels")
    return rows


def transform(row):
    offset = (datetime.fromisoformat(row["tt_label"]) - J2000).total_seconds() / 86400
    ra, dec = map(math.radians, (row["RA_(ICRF-a-app)"], row["DEC_(ICRF-a-app)"]))
    vector = np.array(
        [math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec)]
    )
    dp, de = erfa.nut06a(2451545.0, offset)
    matrix = erfa.ecm06(2451545.0, offset)
    mean = matrix @ vector
    lon = (math.atan2(mean[1], mean[0]) + dp) % (2 * math.pi)
    true_equator = erfa.pnm06a(2451545.0, offset) @ vector
    ob = erfa.obl06(2451545.0, offset) + de
    x, y, z = true_equator
    route2 = math.atan2(math.cos(ob) * y + math.sin(ob) * z, x)
    difference = abs(math.remainder(lon - route2, 2 * math.pi)) * 180 / math.pi * 3600
    if difference > 1e-07:
        raise ValueError("Independent transform route mismatch")
    if (
        np.max(np.abs(matrix @ matrix.T - np.eye(3))) > 2e-14
        or abs(np.linalg.det(matrix) - 1) > 2e-14
    ):
        raise ValueError("Invalid proper rotation")
    return row | {
        "iau2006_longitude": math.degrees(lon),
        "route_difference_arcseconds": difference,
    }


def crossing(rows, target):
    residuals = [math.remainder(row["iau2006_longitude"] - target, 360) for row in rows]
    if not all((a < b for a, b in zip(residuals, residuals[1:]))):
        raise ValueError("Non-monotonic Sun probes")
    indices = [i for i in range(len(rows) - 1) if residuals[i] <= 0 <= residuals[i + 1]]
    if len(indices) != 1:
        raise ValueError("No unique TT bracket")
    i = indices[0]
    lo, hi = [datetime.fromisoformat(r["tt_label"]) for r in rows[i : i + 2]]
    fraction = -residuals[i] / (residuals[i + 1] - residuals[i])
    return lo + (hi - lo) * fraction

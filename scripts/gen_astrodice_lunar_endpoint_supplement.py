"""Collect a separate NASA supplement for the two original missing lunar centers.

Exact BC/AD calendar labels avoid the AD1 Python-calendar boundary. The AD9999
source endpoint, original complete stencil and every remote failure are retained.
No native ephemeris or FateBridge calculation is imported.
"""

import argparse
import csv
import hashlib
import io
import json
import math
import re
import ssl
import sys
import urllib.request
from datetime import datetime, timezone
from fractions import Fraction as Q
from pathlib import Path
from urllib.parse import urlencode

import certifi

MONTHS = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]


def calendar_label(epoch):
    j = Q(epoch) + Q(1, 2)
    whole = j.numerator // j.denominator
    seconds = int((j - whole) * 86400)
    a = whole + 32044
    b = (4 * a + 3) // 146097
    c = a - (146097 * b) // 4
    d = (4 * c + 3) // 1461
    e = c - (1461 * d) // 4
    m = (5 * e + 2) // 153
    day = e - (153 * m + 2) // 5 + 1
    month = m + 3 - 12 * (m // 10)
    year = 100 * b + d - 4800 + m // 10
    return f"{year if year>0 else 1-year}{'ad' if year>0 else 'bc'}-{MONTHS[month-1]}-{day:02} {seconds//3600:02}:{seconds%3600//60:02}:{seconds%60:02}"


def collect(directory):
    D = directory
    p = json.loads((D / "protocol.json").read_text())
    if any(
        name == "fatebridge" or name.startswith("fatebridge.") or name == "swisseph"
        for name in sys.modules
    ):
        raise ValueError("Independent collection cannot import the candidate")
    if (D / "reference.json").exists() or (D / "raw").exists():
        raise ValueError("Use a fresh directory containing only the declared protocol")
    (D / "raw").mkdir()
    requests = []
    samples = {}

    def get(name, epochs):
        params = {
            **p["reference_parameters"],
            "TLIST": " ".join(f"'{calendar_label(jd)}'" for jd in epochs),
        }
        url = p["source_url"] + "?" + urlencode(params)
        at = datetime.now(timezone.utc).isoformat()
        rawfile = D / "raw" / (name + ".json")
        with urllib.request.urlopen(
            url, context=ssl.create_default_context(cafile=certifi.where()), timeout=45
        ) as response:
            raw = response.read()
            http = {"status": response.status, "headers": dict(response.headers)}
        received = datetime.now(timezone.utc).isoformat()
        rawfile = D / "raw" / (name + ".json")
        rawfile.write_bytes(raw)
        decoded = json.loads(raw)
        text = decoded.get("result", "")
        record = {
            "id": name,
            "requested_at_utc": at,
            "received_at_utc": received,
            "parameters": params,
            "numeric_jd_tt": [str(j) for j in epochs],
            "calendar_labels": [calendar_label(j) for j in epochs],
            "raw_path": str(rawfile.relative_to(D)),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "request_url": url,
            "http": http,
            "rows": [],
        }
        requests.append(record)
        save()
        if "$$SOE\n" not in text:
            record["error"] = decoded.get("error", text)
            save()
            return False
        if not all(
            x in text for x in ["Moon (301)", "Earth (399)", "ICRF", "Date__(TT)"]
        ):
            raise ValueError("Changed source semantics")
        cols = list(
            csv.reader(io.StringIO(text.split("$$SOE\n", 1)[1].split("$$EOE", 1)[0]))
        )
        if len(cols) != len(epochs):
            raise ValueError("Source table count differs")
        for epoch, row in zip(epochs, cols):
            # Explicitly verify response BC/AD date, rather than labeling returned rows by order alone.
            expected = calendar_label(epoch)
            m = re.fullmatch(r"(\d+)(ad|bc)-(\w+)-(\d+) (.*)", expected)
            yr, era, mon, day, clock = m.groups()
            actual = row[0].strip()
            wanted_prefix = f"{int(yr):04}-{mon}-{int(day):02} {clock}"
            if era == "bc":
                if (
                    not actual.startswith("b" + wanted_prefix)
                    and not actual.startswith("B.C. " + wanted_prefix)
                    and not actual.startswith(wanted_prefix)
                ):
                    raise ValueError(("Unexpected BC row", actual, expected))
            elif not actual.startswith(wanted_prefix):
                raise ValueError(("Unexpected AD row", actual, expected))
            ra, dec = map(float, row[3:5])
            a, d = map(math.radians, [ra, dec])
            u = [math.cos(d) * math.cos(a), math.cos(d) * math.sin(a), math.sin(d)]
            if not all(math.isfinite(v) for v in u):
                raise ValueError("Nonfinite source")
            item = {
                "jd_tt": str(epoch),
                "calendar_label": expected,
                "returned_calendar_label": row[0],
                "ra_degrees": ra,
                "dec_degrees": dec,
                "printed_values": [v.strip() for v in row[3:5]],
                "icrf_unit_direction": u,
            }
            record["rows"].append(item)
            samples[str(epoch)] = u
        save()
        return True

    def save():
        (D / "reference.partial.json").write_text(
            json.dumps(
                {
                    "protocol_sha256": hashlib.sha256(
                        (D / "protocol.json").read_bytes()
                    ).hexdigest(),
                    "candidate_imported": False,
                    "candidate_compared": False,
                    "requests": requests,
                },
                indent=2,
            )
            + "\n"
        )

    for index, center in enumerate(p["centers"]):
        epoch = Q(center["jd_tt"])
        epochs = sorted(epoch + Q(o, 86400) for o in [0, *p["offsets_seconds"]])
        if not get(f"center-{index}-full-stencil", epochs):
            if index == 1:
                get(
                    "center-1-supported-prefix",
                    [jd for jd in epochs if jd <= epoch + Q(3, 4)],
                )
                get("center-1-first-original-missing", [epoch + 1])
                get("center-1-final-required-probe", [epoch + 3])
            else:
                for k, jd in enumerate(epochs):
                    get(f"center-{index}-probe-{k:02}", [jd])
        print(
            index, "collected", len(samples), "unique available directions", flush=True
        )
    weights = {
        k: float(
            Q((-1) ** (k + 1), k)
            * Q(math.factorial(6) ** 2, math.factorial(6 - k) * math.factorial(6 + k))
        )
        for k in range(1, 7)
    }
    rows = []
    for center in p["centers"]:
        epoch = Q(center["jd_tt"])
        missing = [
            {
                "offset_seconds": o,
                "jd_tt": str(epoch + Q(o, 86400)),
                "calendar_label": calendar_label(epoch + Q(o, 86400)),
            }
            for o in [0, *p["offsets_seconds"]]
            if str(epoch + Q(o, 86400)) not in samples
        ]
        row = {
            **{k: center[k] for k in ["date_tt", "jd_tt", "cohort"]},
            "status": "incomplete" if missing else "available",
            "missing_probes": missing,
        }
        if not missing:
            derivatives = {
                str(h): [
                    math.fsum(
                        weights[k]
                        * (
                            samples[str(epoch + Q(k * h, 86400))][axis]
                            - samples[str(epoch - Q(k * h, 86400))][axis]
                        )
                        for k in range(1, 7)
                    )
                    * 86400
                    / h
                    for axis in range(3)
                ]
                for h in p["steps_seconds"]
            }
            row.update(
                derivatives=derivatives,
                icrf_unit_direction=samples[str(epoch)],
                icrf_direction_derivative_per_day=derivatives[
                    str(p["chosen_step_seconds"])
                ],
                step_difference_arcsec_per_day=math.degrees(
                    math.dist(*derivatives.values())
                )
                * 3600,
            )
        rows.append(row)
    result = {
        "protocol_sha256": hashlib.sha256(
            (D / "protocol.json").read_bytes()
        ).hexdigest(),
        "candidate_imported": False,
        "candidate_compared": False,
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "requests": requests,
        "rows": rows,
        "all_original_offsets_preserved": True,
        "old_reference_modified": False,
    }
    (D / "reference.json").write_text(json.dumps(result, indent=2) + "\n")
    (D / "reference.partial.json").unlink()
    print(
        [
            (x["date_tt"], x["status"], x.get("step_difference_arcsec_per_day"))
            for x in rows
        ]
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    collect(args.directory)


if __name__ == "__main__":
    main()

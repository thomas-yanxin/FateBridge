"""Compare three encodings of frozen, identical TT epochs without moving them.

This is an input-path diagnostic, not a replacement for a failed reference.
Every raw response and every rejected label is retained. No candidate import.
"""

import argparse
import csv
import hashlib
import io
import json
import ssl
import sys
import urllib.parse
import urllib.request
from decimal import Decimal, localcontext
from fractions import Fraction as Q
from pathlib import Path

from scripts.gen_astrodice_horizons_wide import calendar_label, julian_day


def epoch_label(tick, encoding):
    if encoding == "CAL":
        return calendar_label(tick)
    if encoding not in {"JD", "MJD"}:
        raise ValueError("Undeclared epoch encoding")
    value = julian_day(tick)
    if encoding == "MJD":
        value -= Q(4800001, 2)
    with localcontext() as context:
        context.prec = 60
        return str(Decimal(value.numerator) / Decimal(value.denominator))


def requests_for(plan):
    if (
        plan["encodings"] != ["JD", "MJD", "CAL"]
        or plan["fixed_epoch_budget_days"] != "1/1000000000"
        or len(plan["wire_ticks"]) > plan["maximum_labels_per_batch"]
        or [str(julian_day(t)) for t in plan["wire_ticks"]]
        != plan["exact_JD_fractions"]
        or [calendar_label(t) for t in plan["wire_ticks"]]
        != plan["exact_calendar_labels"]
    ):
        raise ValueError("Frozen exact epochs or diagnostic plan changed")
    return {
        encoding: {
            **plan["reference_parameters"],
            "COMMAND": f"'{plan['target']}'",
            "TLIST_TYPE": f"'{encoding}'",
            "TLIST": "\n".join(
                f"'{epoch_label(t, encoding)}'" for t in plan["wire_ticks"]
            ),
        }
        for encoding in plan["encodings"]
    }


def assess(raw, plan):
    response = json.loads(raw)
    text = response.get("result", "")
    if response.get("error") or "$$SOE" not in text or "$$EOE" not in text:
        return {"status": "response_unavailable", "error": response.get("error")}
    if (
        f"({plan['target']})" not in text.split("Center body name:")[0]
        or "Center body name: Earth (399)" not in text
        or "RA_(ICRF-a-app)" not in text
    ):
        raise ValueError("Diagnostic source or coordinate identity changed")
    rows = []
    for row in csv.reader(io.StringIO(text.split("$$SOE")[1].split("$$EOE")[0])):
        if not row or not row[0].strip():
            continue
        returned = Q(row[1].strip())
        closest = min(plan["wire_ticks"], key=lambda t: abs(julian_day(t) - returned))
        delta = returned - julian_day(closest)
        rows.append(
            {
                "requested_tick": closest,
                "requested_jd_fraction": str(julian_day(closest)),
                "returned_jd_string": row[1].strip(),
                "delta_microseconds_fraction": str(delta * 86400000000),
                "epoch_within_original_budget": abs(delta) <= Q(1, 1000000000),
                "printed_angles": [row[4].strip(), row[5].strip()],
            }
        )
    if len(rows) != len(plan["wire_ticks"]) or {
        r["requested_tick"] for r in rows
    } != set(plan["wire_ticks"]):
        raise ValueError("Diagnostic returned duplicate or missing epochs")
    return {
        "status": "diagnostic_only",
        "rows": rows,
        "labels_within_original_budget": sum(
            row["epoch_within_original_budget"] for row in rows
        ),
        "candidate_accuracy_passes": 0,
        "failed_reference_replaced": False,
    }


def run(plan_path, output):
    import certifi

    plan = json.loads(plan_path.read_text())
    queries = requests_for(plan)
    output.mkdir(exist_ok=False)
    results = {}
    context = ssl.create_default_context(cafile=certifi.where())
    for encoding, parameters in queries.items():
        url = "https://ssd.jpl.nasa.gov/api/horizons.api?" + urllib.parse.urlencode(
            parameters
        )
        if len(url.encode()) > plan["maximum_url_bytes"]:
            raise ValueError("Frozen URL byte budget exceeded")
        receipt = {"parameters": parameters, "verification_disabled": False}
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "FateBridge independent epoch diagnostic"}
            )
            from scripts.astrodice_horizons_transport import open_horizons

            with open_horizons(
                request, context=context, timeout=40, receipt=receipt
            ) as response:
                raw = response.read()
                receipt["http_status"] = response.status
            with (output / (encoding + "-raw.json")).open("xb") as f:
                f.write(raw)
            receipt["raw_sha256"] = hashlib.sha256(raw).hexdigest()
            receipt["assessment"] = assess(raw, plan)
        except Exception as error:
            receipt.update(error_type=type(error).__name__, message=str(error))
        with (output / (encoding + "-receipt.json")).open("x") as f:
            json.dump(receipt, f, indent=2)
            f.write("\n")
        results[encoding] = receipt
        print(
            encoding,
            receipt.get("assessment", {}).get("labels_within_original_budget"),
            flush=True,
        )
    if any(
        n == "swisseph" or n == "fatebridge" or n.startswith("fatebridge.")
        for n in sys.modules
    ):
        raise ValueError("Independent diagnostic imported candidate")
    with (output / "index.json").open("x") as f:
        json.dump(
            {
                "plan_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
                "results": results,
                "full_goal_complete": False,
                "candidate_accuracy_passes": 0,
            },
            f,
            indent=2,
        )
        f.write("\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    run(args.plan, args.output)

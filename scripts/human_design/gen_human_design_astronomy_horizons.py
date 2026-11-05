"""Cross-check predeclared DE440 reference anchors against live JPL Horizons.

No FateBridge or Swiss import. Explicit maintenance only; tests use frozen raw
responses. Fixed anchor indices/targets/tolerance are read from the original
plan, not chosen after observing either backend's agreement.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "tests/fixtures/human-design-astronomy-plan.json"
REFERENCE = ROOT / "tests/fixtures/human-design-astronomy-de440.json"
OUTPUT = ROOT / "tests/fixtures/human-design-astronomy-horizons.json"
URL = "https://ssd.jpl.nasa.gov/api/horizons.api"


def main() -> None:
    plan = json.loads(PLAN.read_text())
    reference = json.loads(REFERENCE.read_text())
    anchors = [
        {
            "label": reference["pairs"][i]["label"],
            "side": side,
            **reference["pairs"][i][side],
        }
        for i in plan["horizons_crosscheck"]["birth_indices"]
        for side in ("personality", "design")
    ]

    def fetch(body):
        parameters = {
            "format": "json",
            "COMMAND": f"'{plan['bodies'][body]}'",
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
        url = URL + "?" + urlencode(parameters)
        raw = subprocess.check_output(
            [
                "curl",
                "--fail",
                "--silent",
                "--show-error",
                "--max-time",
                "45",
                "--retry",
                "2",
                url,
            ]
        )
        payload = json.loads(raw)
        if "error" in payload:
            raise ValueError(payload["error"])
        result = payload["result"]
        table = result.split("$$SOE", 1)[1].split("$$EOE", 1)[0].strip()
        rows = []
        # Horizons sorts the time list. Match by the printed physical JD,
        # never by input order (Design precedes its birth).
        for cells in csv.reader(io.StringIO(table)):
            jd = float(cells[0].strip())
            original = min(anchors, key=lambda r: abs(r["jd_tt"] - jd))
            if abs(original["jd_tt"] - jd) * 86400 > 0.001:
                raise ValueError("Unmatched Horizons TT epoch")
            longitude = float(cells[3])
            expected = original["positions"][body]["longitude"]
            rows.append(
                {
                    "label": original["label"],
                    "side": original["side"],
                    "jd_tt": jd,
                    "longitude": longitude,
                    "latitude": float(cells[4]),
                    "skyfield_longitude": expected,
                    "error_arcseconds": abs((longitude - expected + 180) % 360 - 180)
                    * 3600,
                }
            )
        if len(rows) != len(anchors):
            raise ValueError("Incomplete Horizons anchor response")
        return {
            "body": body,
            "target_id": plan["bodies"][body],
            "parameters": parameters,
            "request_url": url,
            "response": payload,
            "raw_response_utf8": raw.decode(),
            "raw_response_sha256": hashlib.sha256(raw).hexdigest(),
            "rows": rows,
        }

    with ThreadPoolExecutor(max_workers=3) as pool:
        records = list(pool.map(fetch, plan["horizons_crosscheck"]["bodies"]))
    report = {
        "source": URL,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "plan_sha256": hashlib.sha256(PLAN.read_bytes()).hexdigest(),
        "de440_reference_sha256": hashlib.sha256(REFERENCE.read_bytes()).hexdigest(),
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "tolerance_arcseconds": plan["horizons_crosscheck"]["tolerance_arcseconds"],
        "scope": "18 fixed Sun/Moon/Pluto anchors at birth and independently solved Design TT, compared against Horizons apparent IAU76/80 ecliptic-of-date quantity31. This tests selected reference-pipeline conventions, not all 2440 positions, source doctrine or prediction.",
        "records": records,
    }
    OUTPUT.write_bytes(
        (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode()
    )
    print(
        json.dumps(
            {
                "observations": sum(len(r["rows"]) for r in records),
                "max_error_arcseconds": max(
                    v["error_arcseconds"] for r in records for v in r["rows"]
                ),
            }
        )
    )


if __name__ == "__main__":
    main()

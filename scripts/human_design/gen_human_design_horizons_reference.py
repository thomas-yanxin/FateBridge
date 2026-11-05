"""Freeze JPL Sun observations at birth and candidate Design epochs.

FateBridge selects observation times, never expected positions. This is an
astronomical solar-arc check, not an official Human Design chart comparison.
Run explicitly to retrieve or replace the frozen reference; tests are offline.
"""

import hashlib
import json
import subprocess
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from fatebridge.core.human_design import design_epoch

ROOT = Path(__file__).resolve().parents[2]
BIRTHS = [
    "1990-04-06T01:33:00+00:00",
    "2000-01-01T12:00:00+00:00",
    "2024-03-20T06:30:00+00:00",
    "2026-10-22T00:00:00+00:00",
]


def main() -> None:
    pairs = []
    epochs = []
    for value in BIRTHS:
        birth = datetime.fromisoformat(value)
        design, _ = design_epoch(birth)
        pair = {
            "birth_utc": birth.isoformat(timespec="milliseconds"),
            "design_candidate_utc": design.isoformat(timespec="milliseconds"),
        }
        pairs.append(pair)
        epochs.extend([birth, design])
    params = {
        "format": "json",
        "COMMAND": "'10'",
        "OBJ_DATA": "'NO'",
        "MAKE_EPHEM": "'YES'",
        "EPHEM_TYPE": "'OBSERVER'",
        "CENTER": "'500@399'",
        "TLIST": " ".join(
            "'" + m.strftime("%Y-%m-%d %H:%M:%S.") + f"{m.microsecond // 1000:03d}'"
            for m in epochs
        ),
        "TLIST_TYPE": "'CAL'",
        "TIME_TYPE": "'UT'",
        "QUANTITIES": "'31'",
        "CSV_FORMAT": "'YES'",
        "EXTRA_PREC": "'YES'",
        "CAL_TYPE": "'GREGORIAN'",
        "ANG_FORMAT": "'DEG'",
    }
    url = "https://ssd.jpl.nasa.gov/api/horizons.api?" + urllib.parse.urlencode(params)
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
    response = json.loads(raw)
    text = response["result"]
    rows = []
    for line in text.split("$$SOE")[1].split("$$EOE")[0].strip().splitlines():
        cells = [c.strip() for c in line.split(",")]
        moment = datetime.strptime(cells[0], "%Y-%b-%d %H:%M:%S.%f").replace(
            tzinfo=timezone.utc
        )
        rows.append(
            {
                "utc": moment.isoformat(timespec="milliseconds"),
                "sun_longitude": float(cells[3]),
            }
        )
    output = {
        "source": "NASA/JPL Horizons DE441",
        "source_url": url,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Independent apparent geocentric solar longitude at engine-selected test epochs; not an independent official BodyGraph or independent choice of Design time.",
        "tolerance_arcseconds": 2.0,
        "pairs": pairs,
        "rows": rows,
        "response": response,
        "response_sha256": hashlib.sha256(raw).hexdigest(),
    }
    target = ROOT / "tests/fixtures/human-design-horizons.json"
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(f"Saved {len(rows)} independent JPL observations to {target}")


if __name__ == "__main__":
    main()

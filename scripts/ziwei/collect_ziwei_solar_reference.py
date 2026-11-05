"""Fetch a predeclared JPL observer corpus without importing FateBridge."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode


def collect(directory: Path) -> None:
    protocol_raw = (directory / "protocol.json").read_bytes()
    protocol_hash = hashlib.sha256(protocol_raw).hexdigest()
    if protocol_hash != (directory / "protocol.sha256").read_text().strip():
        raise ValueError("Protocol checksum mismatch")
    protocol = json.loads(protocol_raw)
    manifest_path = directory / "manifest.json"
    if manifest_path.exists():
        raise FileExistsError("Frozen manifest exists; use a new corpus")
    records = []
    for site in protocol["sites"]:
        for batch_start in range(0, len(site["instants"]), 12):
            instants = site["instants"][batch_start : batch_start + 12]
            params = {
                "format": "json",
                "COMMAND": "'10'",
                "OBJ_DATA": "'NO'",
                "MAKE_EPHEM": "'YES'",
                "EPHEM_TYPE": "'OBSERVER'",
                "CENTER": "'coord@399'",
                "COORD_TYPE": "'GEODETIC'",
                "SITE_COORD": f"'{site['longitude']},{site['latitude']},0'",
                "TLIST": " ".join(
                    "'" + datetime.fromisoformat(s).strftime("%Y-%m-%d %H:%M:%S") + "'"
                    for s in instants
                ),
                "TLIST_TYPE": "'CAL'",
                "TIME_TYPE": "'UT'",
                "QUANTITIES": "'34,42,49'",
                "CSV_FORMAT": "'YES'",
                "EXTRA_PREC": "'YES'",
                "CAL_TYPE": "'GREGORIAN'",
                "ANG_FORMAT": "'DEG'",
                "TIME_DIGITS": "'FRACSEC'",
                "APPARENT": "'AIRLESS'",
            }
            url = protocol["source_url"] + "?" + urlencode(params)
            path = directory / (site["id"] + f"-{batch_start // 12:02d}.json")
            # Complete replies can be resumed, never replaced silently.
            if not path.exists():
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
                if "error" in response or "$$SOE" not in response.get("result", ""):
                    raise ValueError(response.get("error", "No ephemeris table"))
                path.write_bytes(raw)
            records.append(
                dict(
                    site_id=site["id"],
                    instants=instants,
                    path=path.name,
                    request_parameters=params,
                    request_url=url,
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                )
            )
            print("Frozen " + path.name, flush=True)
    if (directory / "protocol.json").read_bytes() != protocol_raw:
        raise ValueError("Protocol changed during collection")
    manifest = dict(
        method_id=protocol["method_id"],
        protocol_sha256=protocol_hash,
        collected_at=datetime.now(timezone.utc).isoformat(),
        replies=records,
    )
    manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    manifest_path.write_text(manifest_text)
    (directory / "manifest.sha256").write_text(
        hashlib.sha256(manifest_text.encode()).hexdigest() + "\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    collect(args.directory)

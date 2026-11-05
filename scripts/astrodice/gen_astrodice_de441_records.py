"""Collect bounded original DE441 record windows, preserving every response.

Only source metadata and frozen calendar conditions select byte ranges. No
candidate ephemeris or numeric comparison is imported. Excerpts are diagnostic
fixtures with limited coverage, never complete DE441 installations.
"""

import argparse
import hashlib
import json
import re
import ssl
import struct
import sys
import urllib.request
from datetime import datetime, timezone
from fractions import Fraction as F
from pathlib import Path

from scripts.astrodice.astrodice_de441_records import (
    METHOD,
    RECORD_BYTES,
    calendar_jd_tdb,
    geometric_states,
    header,
    mini_kernel,
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect(run):
    import certifi

    plan = json.loads((run / "design-before-source.json").read_text())
    source = json.loads((run / "header-response.json").read_text())
    original_header = (run / "header.bin").read_bytes()
    if hashlib.sha256(original_header).hexdigest() != source["sha256"]:
        raise ValueError("Original header response changed")
    metadata = header(original_header)
    etag = source["headers"]["ETag"]
    total = int(source["headers"]["Content-Range"].split("/")[1])
    expected_size = (
        int((metadata["end_jd_tdb"] - metadata["start_jd_tdb"]) / 32) + 2
    ) * RECORD_BYTES
    if total != expected_size:
        raise ValueError("Original record extent does not match remote object size")
    raw_dir = run / "record-responses"
    raw_dir.mkdir()
    journal = (raw_dir / "requests.jsonl").open("x")
    context = ssl.create_default_context(cafile=certifi.where())

    def request(name, start, size):
        if size > 3 * RECORD_BYTES:
            raise ValueError("Unplanned record request size")
        end = start + size - 1
        req = urllib.request.Request(
            plan["source_url"],
            headers={
                "Range": f"bytes={start}-{end}",
                "If-Match": etag,
                "User-Agent": "FateBridge independent DE441 record diagnostic",
            },
        )
        record = {"name": name, "start": start, "end": end, "expected_etag": etag}
        try:
            with urllib.request.urlopen(req, context=context, timeout=40) as response:
                data = response.read(size + 1)
                record.update(status=response.status, headers=dict(response.headers))
            path = raw_dir / (name + ".bin")
            with path.open("xb") as file:
                file.write(data)
            record.update(bytes=len(data), sha256=digest(path), file=path.name)
            if (
                record["status"] != 206
                or record["headers"].get("Content-Range")
                != f"bytes {start}-{end}/{total}"
                or record["headers"].get("ETag") != etag
                or len(data) != size
            ):
                raise ValueError("Original byte range/source identity mismatch")
            return data
        except Exception as error:
            record.update(error_type=type(error).__name__, error=str(error))
            raise
        finally:
            journal.write(json.dumps(record) + "\n")
            journal.flush()

    rows = []
    kernels = run / "diagnostic-kernels"
    kernels.mkdir()
    try:
        constants = request("constants", RECORD_BYTES, RECORD_BYTES)
        for index, label in enumerate(plan["conditions"]):
            epoch = calendar_jd_tdb(label)
            record_index = int((epoch - F(metadata["start_jd_tdb"])) // 32)
            first = record_index - 1
            data = request(
                f"case-{index:02}", (first + 2) * RECORD_BYTES, 3 * RECORD_BYTES
            )
            records = [
                data[k : k + RECORD_BYTES] for k in range(0, len(data), RECORD_BYTES)
            ]
            expected_start = metadata["start_jd_tdb"] + first * 32
            if struct.unpack_from("<d", data)[0] != expected_start:
                raise ValueError("Original coefficient record labels changed")
            states = geometric_states(metadata, records[1], epoch)
            collapsed = F(float(epoch))
            argument_states = geometric_states(metadata, records[1], collapsed)
            kernel_path = kernels / f"case-{index:02}.eph"
            with kernel_path.open("xb") as file:
                file.write(mini_kernel(original_header, constants, records))
            row = {
                "id": f"de441-geometric-{index:02}",
                "date_tdb": label,
                "role": (
                    "known_diagnostic_control"
                    if index < 3
                    else "frozen_geometric_holdout"
                ),
                "epoch_jd_tdb_exact": str(epoch),
                "native_numeric_argument": float(epoch),
                "argument_rounding_seconds": str((collapsed - epoch) * 86400),
                "original_record_index": record_index,
                "original_window_first_record_index": first,
                "source_record_file": f"record-responses/case-{index:02}.bin",
                "kernel_path": f"diagnostic-kernels/case-{index:02}.eph",
                "kernel_sha256": digest(kernel_path),
                "states_at_exact_tdb_au_and_au_per_day": {
                    name: list(map(str, value)) for name, value in states.items()
                },
                "states_at_binary64_argument_au_and_au_per_day": {
                    name: list(map(str, value))
                    for name, value in argument_states.items()
                },
                "coefficients_modified": False,
                "excerpt_header_modified_byte_ranges": [[0, 251], [2652, 2667]],
            }
            rows.append(row)
            print(row["id"], label, "source reference computed", flush=True)
    finally:
        journal.close()
    forbidden = [
        name for name in sys.modules if re.match(r"^(swisseph|fatebridge)(\.|$)", name)
    ]
    if forbidden:
        raise ValueError(
            "Independent source collector imported candidate: " + str(forbidden)
        )
    result = {
        "method_id": METHOD,
        "at_utc": datetime.now(timezone.utc).isoformat(),
        "design_sha256": digest(run / "design-before-source.json"),
        "collector_sha256": digest(Path(__file__)),
        "source_metadata": metadata,
        "rows": rows,
        "candidate_imported": False,
        "full_kernel_sha256_verified": False,
        "source_identity_scope": "HTTPS original record ranges, checked length/Content-Range/ETag and actual record labels; not a full-file SHA-256 proof.",
        "time_contract": "Exact TDB calendar targets plus separate binary64 argument control. No TT/UTC conversion or apparent corrections.",
        "scope": "Independent exact geometric evaluation of shared DE441 coefficients; not independent observations or full astrodice numerical acceptance.",
    }
    with (run / "geometric-reference.json").open("x") as file:
        file.write(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    collect(parser.parse_args().run)

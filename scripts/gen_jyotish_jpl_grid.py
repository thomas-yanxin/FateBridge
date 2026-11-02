"""Collect a frozen geometric Horizons grid, independently reduced with ERFA.

No FateBridge or Swiss imports. Raw responses, headers, vectors and complete
target/epoch coverage are checked before writing a reference file.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import ssl
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any, cast

import erfa  # type: ignore[import-untyped]  # pyerfa lacks typing metadata.
import numpy as np
import truststore

PROTOCOL_SHA256 = "8bc70e8c3796696c889572197b4da02833dd84f9e32fffbebb40cfa11bbb694a"
ENDPOINT = "https://ssd.jpl.nasa.gov/api/horizons.api"


def load_protocol(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PROTOCOL_SHA256:
        raise ValueError("Frozen geometry protocol changed")
    return cast(dict[str, Any], json.loads(raw))


def reduce_response(
    protocol: dict[str, Any], body: str, raw: bytes
) -> list[dict[str, Any]]:
    """Validate the actual returned contract, not just request parameters."""
    data = json.loads(raw)
    result = data.get("result", "")
    target = protocol["targets"][body]
    lines = result.splitlines()
    target_header = next((s for s in lines if s.startswith("Target body name:")), "")
    center_header = next((s for s in lines if s.startswith("Center body name:")), "")
    if (
        "error" in data
        or f"({protocol['returned_target_ids'][body]})" not in target_header
        or body not in target_header
        or "{source: DE441}" not in target_header
        or "Earth (399)" not in center_header
        or "{source: DE441}" not in center_header
        or "Reference frame : ICRF" not in result
        or "Output units    : AU-D" not in result
        or "Output type     : GEOMETRIC cartesian states" not in result
        or "JDTT" not in result
        or "$$SOE\n" not in result
        or "$$EOE" not in result
    ):
        raise ValueError(f"{body}: Horizons returned a different physical contract")
    table = list(csv.reader(io.StringIO(result.split("$$SOE\n")[1].split("$$EOE")[0])))
    wanted = [row["jd_tt"] for row in protocol["epochs"]]
    if len(table) != len(wanted):
        raise ValueError(f"{body}: incomplete reference coverage")
    rotation = erfa.rx(erfa.obl80(2451545.0, 0.0), erfa.bp00(2451545.0, 0.0)[0])
    rows = []
    for columns, epoch in zip(table, protocol["epochs"]):
        jd = float(columns[0])
        # Horizons prints nine decimal places for JD; this only checks that
        # request/response rounding differs by at most one double ULP here.
        if abs(jd - epoch["jd_tt"]) > math.ulp(epoch["jd_tt"]):
            raise ValueError(f"{body}: returned epoch changed")
        vector = np.array([float(v) for v in columns[2:5]])
        velocity = [float(v) for v in columns[5:8]]
        if not all(math.isfinite(v) for v in [*vector, *velocity]):
            raise ValueError(f"{body}: nonfinite reference vector")
        norm = float(np.linalg.norm(vector))
        if norm <= 0:
            raise ValueError(f"{body}: undefined reference direction")
        direction = rotation @ vector / norm
        delta = float(erfa.dtdb(2451545.0, epoch["jd_tt"] - 2451545.0, 0, 0, 0, 0))
        rows.append(
            {
                "body": body,
                "target_id": target,
                **epoch,
                "returned_printed_jd_tt": columns[0].strip(),
                "icrf_position_au": vector.tolist(),
                "icrf_velocity_au_per_day": velocity,
                "ecliptic_unit_vector": direction.tolist(),
                "geocentric_tdb_minus_tt_seconds": delta,
                "reference_raw_sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--raw-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    protocol = load_protocol(args.protocol)
    if args.output.exists() or args.output.resolve() == args.protocol.resolve():
        parser.error("output must be new and must not overwrite the protocol")
    args.raw_dir.mkdir(parents=True, exist_ok=True)
    references, rows = [], []
    for body, target in protocol["targets"].items():
        params = {
            **protocol["reference_parameters"],
            "COMMAND": f"'{target}'",
            "TLIST": "'"
            + " ".join(format(r["jd_tt"], ".17g") for r in protocol["epochs"])
            + "'",
        }
        raw_path = args.raw_dir / f"{body}.json"
        if raw_path.exists():
            raw = raw_path.read_bytes()
        else:
            request = urllib.request.Request(
                ENDPOINT + "?" + urllib.parse.urlencode(params),
                headers={"User-Agent": "FateBridge-independent-geometry-audit/1"},
            )
            # Use the operating system trust store, including managed roots;
            # certificate and hostname verification remain enabled.
            context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            with urllib.request.urlopen(
                request, timeout=45, context=context
            ) as response:
                raw = response.read()
            # Keep failed raw responses, too; never replace them on a rerun.
            with raw_path.open("xb") as stream:
                stream.write(raw)
        body_rows = reduce_response(protocol, body, raw)
        rows.extend(body_rows)
        references.append(
            {
                "body": body,
                "parameters": params,
                "raw_response_utf8": raw.decode(),
                "raw_sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
        print(f"{body}: validated {len(body_rows)} raw reference rows", flush=True)
    if any(n == "swisseph" or n.startswith("fatebridge") for n in sys.modules):
        raise ValueError("Reference isolation violated")
    if len(rows) != protocol["expected_rows"]:
        raise ValueError("Incomplete frozen cohort")
    output = {
        "protocol_sha256": PROTOCOL_SHA256,
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "packages": {"pyerfa": version("pyerfa"), "numpy": version("numpy")},
        "references": references,
        "rows": rows,
        "scope": protocol["scope"],
        "forbidden_candidate_imports": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        stream.write(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()

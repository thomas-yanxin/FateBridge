"""Find every repeated local clock in the frozen whole solar-term cohort."""

from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import io
import json
import sys
import tarfile
import types
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Protocol, Tuple, cast
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_term_offset_v1"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inputs() -> (
    tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, ZoneInfo]]
):
    protocol = json.loads((FIXTURE / "protocol.json").read_text())
    if (
        digest(FIXTURE / "protocol.json")
        != (FIXTURE / "protocol.sha256").read_text().strip()
    ):
        raise ValueError("Frozen protocol changed")
    for name, expected in protocol["input_sha256"].items():
        if digest(FIXTURE / name) != expected:
            raise ValueError("Frozen input changed: " + name)
    archive = json.loads(
        gzip.decompress((FIXTURE / "exposed-term-inputs.json.gz").read_bytes())
    )
    manifest = json.loads((FIXTURE / "timezone-manifest.json").read_text())
    baseline = json.loads((FIXTURE / "before-manifest.json").read_text())
    zones = {}
    with tarfile.open(FIXTURE / "tzif.tar.gz", "r:gz") as tar:
        if {m.name for m in tar.getmembers()} != set(manifest["zones"]):
            raise ValueError("Pinned zone inventory differs")
        for member in tar.getmembers():
            handle = tar.extractfile(member)
            if handle is None:
                raise ValueError("Zone is not a file: " + member.name)
            raw = handle.read()
            if hashlib.sha256(raw).hexdigest() != manifest["zones"][member.name]:
                raise ValueError("Pinned zone changed: " + member.name)
            zones[member.name] = ZoneInfo.from_file(io.BytesIO(raw), key=member.name)
    expected = {(y, i) for y in range(1899, 2102) for i in range(24)}
    if {(r["year"], r["index"]) for r in archive["rows"]} != expected or len(
        archive["rows"]
    ) != len(expected):
        raise ValueError("Complete original term cohort changed")
    return protocol, archive, {"zones": manifest, "baseline": baseline}, zones


class SerializedTerm(Protocol):
    def __init__(
        self,
        name: str,
        moment: datetime,
        date_key: str,
        day_ganzhi: str,
        resolution_provider: str = "unknown",
        ephemeris_model: str = "unknown",
        ephemeris_retflags: Tuple[int, ...] = (),
        ephemeris_library_version: Optional[str] = None,
        solar_model_details: Optional[Dict[str, Any]] = None,
    ) -> None: ...

    def as_dict(self) -> dict[str, Any]: ...


def baseline_class() -> tuple[type[SerializedTerm], dict[str, Any]]:
    manifest = json.loads((FIXTURE / "before-manifest.json").read_text())
    name = "src/fatebridge/core/almanac.py"
    with tarfile.open(FIXTURE / "before-package.tar.gz", "r:gz") as tar:
        handle = tar.extractfile(name)
        if handle is None:
            raise ValueError("Baseline almanac is missing")
        raw = handle.read()
    if hashlib.sha256(raw).hexdigest() != manifest["files"][name]:
        raise ValueError("Baseline almanac differs from its manifest")
    tree = ast.parse(raw.decode())
    node = next(
        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "SolarTerm"
    )
    module = types.ModuleType("_frozen_bazi_solar_term")
    module.__dict__.update(
        dataclass=dataclass,
        field=field,
        datetime=datetime,
        Any=Any,
        Dict=Dict,
        Optional=Optional,
        Tuple=Tuple,
        deepcopy=deepcopy,
    )
    sys.modules[module.__name__] = module
    exec(
        compile(ast.Module(body=[node], type_ignores=[]), "frozen_almanac.py", "exec"),
        module.__dict__,
    )
    return cast(type[SerializedTerm], module.__dict__["SolarTerm"]), {
        n.name: ast.dump(n, include_attributes=False)
        for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def discover() -> dict[str, Any]:
    protocol, archive, metadata, zones = inputs()
    baseline = metadata["baseline"]
    almanac_path = ROOT / "src/fatebridge/core/almanac.py"
    SolarTerm, original_functions = baseline_class()
    from fatebridge.core.almanac import get_day_ganzhi

    def check_numerical_functions() -> None:
        tree = ast.parse(almanac_path.read_text())
        actual = {
            n.name: ast.dump(n, include_attributes=False)
            for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        # This replay consumes the sealed timestamps and original SolarTerm
        # serializer. The only live calendar function it calls is day-ganzhi.
        # The complete original almanac remains hash-checked in baseline_class.
        if actual["get_day_ganzhi"] != original_functions["get_day_ganzhi"]:
            raise ValueError("Calendar function used by the historical replay changed")

    check_numerical_functions()

    scanned = 0
    rows = []
    stream = hashlib.sha256()
    for record in archive["rows"]:
        instant = datetime.fromisoformat(record["public_civil_datetime"]).astimezone(
            timezone.utc
        )
        for name, zone in zones.items():
            local = instant.astimezone(zone)
            other = local.replace(fold=1 - local.fold)
            ambiguous = other.utcoffset() != local.utcoffset()
            scanned += 1
            stream.update(
                f"{record['year']}|{record['index']}|{name}|{local.isoformat()}|{local.fold}|{int(ambiguous)}\n".encode()
            )
            if not ambiguous:
                continue
            if other.astimezone(timezone.utc).astimezone(zone).replace(
                tzinfo=None
            ) != local.replace(tzinfo=None):
                raise ValueError("Other fold is not a valid duplicate local clock")
            term = SolarTerm(
                record["name"],
                local,
                local.strftime("%Y%m%d"),
                get_day_ganzhi(local.year, local.month, local.day),
                record["actual_provider"],
                record["actual_model"],
                solar_model_details=record["details"],
            )
            serialized = term.as_dict()
            reconstructed = (
                datetime.fromisoformat(serialized["datetime"])
                .replace(tzinfo=zone)
                .astimezone(timezone.utc)
            )
            seconds = (reconstructed - instant).total_seconds()
            rows.append(
                {
                    "year": record["year"],
                    "index": record["index"],
                    "name": record["name"],
                    "zone": name,
                    "tzif_sha256": metadata["zones"]["zones"][name],
                    "source_civil_offset_label": instant.isoformat(),
                    "actual_local_datetime": local.isoformat(),
                    "actual_fold": local.fold,
                    "other_valid_local_datetime": other.isoformat(),
                    "legacy_record": serialized,
                    "legacy_default_reconstruction": reconstructed.isoformat(),
                    "legacy_reconstruction_error_seconds": seconds,
                    "legacy_lossless": seconds == 0,
                }
            )
    if scanned != protocol["cohort"]["cartesian_pairs"]:
        raise ValueError("A term/zone pair escaped the complete scan")
    check_numerical_functions()
    rows.sort(key=lambda r: (r["source_civil_offset_label"], r["zone"]))
    eligible = [r for r in rows if 1900 <= r["year"] <= 2100 and r["actual_fold"] == 1]
    representative = eligible[0] if eligible else None
    return {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": digest(FIXTURE / "protocol.json"),
        "term_input_sha256": digest(FIXTURE / "exposed-term-inputs.json.gz"),
        "baseline_almanac_sha256": baseline["files"]["src/fatebridge/core/almanac.py"],
        "cohort": protocol["cohort"],
        "scanned_pairs": scanned,
        "all_pair_transform_stream_sha256": stream.hexdigest(),
        "ambiguous_rows": len(rows),
        "distinct_term_events": len({(r["year"], r["index"]) for r in rows}),
        "distinct_event_zone_rule_pairs": len(
            {(r["year"], r["index"], r["tzif_sha256"]) for r in rows}
        ),
        "legacy_reconstruction_failures": sum(not r["legacy_lossless"] for r in rows),
        "maximum_legacy_error_seconds": max(
            (abs(r["legacy_reconstruction_error_seconds"]) for r in rows), default=0
        ),
        "representative": representative,
        "rows": rows,
        "scope": "Exposed actual model timestamps transformed with pinned TZif. Aliases retained, not independent trials, absolute UTC observations, future timezone laws or new astronomical accuracy credit.",
        "lossless_delivery_requirement_passed": False,
        "original_moshier_failures_superseded": False,
        "new_model_executions": 0,
        "real_world_predictive_validity": "not_tested",
        "full_goal_complete": False,
        "overall_score": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    checksum = Path(str(output) + ".sha256")
    if output.exists() or checksum.exists():
        raise SystemExit("Output exists; preserve first results")
    result = discover()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(
        gzip.compress(
            (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode(), mtime=0
        )
    )
    checksum.write_text(digest(output) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "scanned_pairs",
                    "ambiguous_rows",
                    "distinct_term_events",
                    "legacy_reconstruction_failures",
                    "maximum_legacy_error_seconds",
                )
            },
            ensure_ascii=False,
        )
    )
    if result["representative"]:
        r = result["representative"]
        print(
            json.dumps(
                {
                    k: r[k]
                    for k in (
                        "year",
                        "index",
                        "name",
                        "zone",
                        "actual_local_datetime",
                        "actual_fold",
                        "legacy_reconstruction_error_seconds",
                    )
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()

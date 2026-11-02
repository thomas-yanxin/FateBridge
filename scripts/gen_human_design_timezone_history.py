"""Freeze official primary/backzone clocks with independent installed C tools.

No FateBridge, Swiss or production timezone reader imports. Historical source
conformance is not certification of actual past clocks or astronomical time.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "docs/validation/human-design-timezone-history-v1"
E = BASE / "evidence"
PLAN_SHA = "cdf888ac36f936745904997803d6f055ff5fe48166dafb282ad7139d4ce8420d"
FILES = (
    "africa",
    "antarctica",
    "asia",
    "australasia",
    "europe",
    "northamerica",
    "southamerica",
    "etcetera",
    "factory",
    "backward",
)
MONTHS = {
    name: i
    for i, name in enumerate(
        "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1
    )
}
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> Any:
    data = path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix == ".gz" else data)


def write(path: Path, value: Any) -> None:
    data = (
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode()
    with path.open("xb") as output:
        output.write(gzip.compress(data, mtime=0) if path.suffix == ".gz" else data)


def seconds(moment: datetime) -> int:
    delta = moment - EPOCH
    return delta.days * 86400 + delta.seconds


def calendar(text: str) -> datetime:
    fields = text.split()
    if len(fields) != 5 or fields[1] not in MONTHS:
        raise ValueError("Unexpected C calendar: " + text)
    hour, minute, second = map(int, fields[3].split(":"))
    return datetime(
        int(fields[4]),
        MONTHS[fields[1]],
        int(fields[2]),
        hour,
        minute,
        second,
        tzinfo=timezone.utc,
    )


def compact_initial(text: str) -> dict[str, Any]:
    rows = [line.split("\t") for line in text.splitlines() if line.startswith("-\t-\t")]
    if len(rows) != 1:
        raise ValueError("Missing or duplicate C initial interval")
    fields = rows[0]
    offset_text = fields[2]
    if not re.fullmatch(r"[+-](?:\d{2}|\d{4}|\d{6})", offset_text):
        raise ValueError("Unexpected compact C offset")
    padded = offset_text[1:].ljust(6, "0")
    offset = (int(padded[:2]) * 3600 + int(padded[2:4]) * 60 + int(padded[4:])) * (
        -1 if offset_text[0] == "-" else 1
    )
    rest = fields[3:]
    abbreviation = offset_text
    if rest and not re.fullmatch(r"-?\d+", rest[0]):
        abbreviation = (
            json.loads(rest.pop(0)) if rest[0].startswith('"') else rest.pop(0)
        )
    dst = int(rest.pop(0)) if rest else 0
    if rest:
        raise ValueError("Extra initial C fields")
    return {"offset_seconds": offset, "abbreviation": abbreviation, "isdst": dst}


def transition_rows(text: str, path: Path) -> list[list[Any]]:
    result: list[list[Any]] = []
    for line in text.splitlines():
        if not line.startswith(str(path)):
            raise ValueError("C reference zone identity changed")
        match = re.fullmatch(
            r"\s*(.*?) UT = (.*?) (\S+) isdst=(-?\d+) gmtoff=(-?\d+)",
            line[len(str(path)) :],
        )
        if match is None:
            raise ValueError("Unexpected C transition: " + line)
        ut, local, abbreviation, dst, offset = match.groups()
        utc_moment, local_moment = calendar(ut), calendar(local)
        if seconds(local_moment) - seconds(utc_moment) != int(offset):
            raise ValueError("C offset contradicts its literal calendars")
        result.append(
            [
                seconds(utc_moment),
                int(offset),
                abbreviation,
                int(dst),
                local_moment.replace(tzinfo=None).isoformat(),
            ]
        )
    if len(result) % 2:
        raise ValueError("Unpaired C transition observations")
    for left, right in zip(result[::2], result[1::2], strict=True):
        if right[0] - left[0] != 1:
            raise ValueError(
                "C transition does not retain adjacent before/after seconds"
            )
    return result


def build(output: Path) -> None:
    if output.exists():
        raise FileExistsError(output)
    if sha(E / "plan.json") != PLAN_SHA:
        raise ValueError("Frozen history plan changed")
    plan = read(E / "plan.json")
    installed = read(E / "packaged-zone-identities.json")
    source = BASE / "reference-source"
    source.mkdir()
    for name, expected in plan["source_archives"].items():
        archive = BASE / "sources" / name
        if sha(archive) != expected:
            raise ValueError("Official source archive changed")
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(source, filter="data")
    if (source / "version").read_text().strip() != plan["iana_version"]:
        raise ValueError("Official and locked package versions differ")
    binaries = {p: row["sha256"] for p, row in plan["toolchain"].items()}
    binaries[plan["awk"]["path"]] = plan["awk"]["sha256"]
    if any(sha(Path(p)) != value for p, value in binaries.items()):
        raise ValueError("Frozen compiler/tool identity changed")
    source_before = {
        str(p.relative_to(source)): sha(p)
        for p in sorted(source.rglob("*"))
        if p.is_file()
    }
    forms = {}
    environment = {**os.environ, "LC_ALL": "C", "LANG": "C"}
    for form, packrat in (("primary", ""), ("full_backzone", "backzone")):
        arguments = [
            "/usr/bin/awk",
            "-v",
            "DATAFORM=main",
            "-v",
            "PACKRATDATA=" + packrat,
            "-v",
            "PACKRATLIST=",
            "-f",
            "ziguard.awk",
            *FILES,
            *([packrat] if packrat else []),
        ]
        guarded = subprocess.run(
            arguments, cwd=source, env=environment, capture_output=True, check=True
        )
        guarded_path = BASE / "sources" / (form + ".zi")
        with guarded_path.open("xb") as stream:
            stream.write(guarded.stdout)
        destination = BASE / "reference-data" / form
        destination.mkdir(parents=True)
        compile_command = [
            "/usr/sbin/zic",
            "-b",
            "fat",
            "-d",
            str(destination),
            str(guarded_path),
        ]
        compiled = subprocess.run(compile_command, env=environment, capture_output=True)
        write(
            E / ("compile-" + form + ".json"),
            {
                "guard_command": arguments,
                "guard_stderr": guarded.stderr.decode(),
                "compile_command": compile_command,
                "compile_exit_code": compiled.returncode,
                "compile_stdout": compiled.stdout.decode(),
                "compile_stderr": compiled.stderr.decode(),
                "source_sha256": sha(guarded_path),
            },
        )
        compiled.check_returncode()
        zones = []
        raw_outputs = []
        for index, name in enumerate(installed["zone_sha256"]):
            path = destination / name
            raw = subprocess.run(
                ["/usr/sbin/zdump", "-V", "-c", "1800,2400", str(path)],
                env=environment,
                capture_output=True,
                text=True,
                check=True,
            )
            compact = subprocess.run(
                ["/usr/sbin/zdump", "-i", "-c", "1800,1801", str(path)],
                env=environment,
                capture_output=True,
                text=True,
                check=True,
            )
            if raw.stderr or compact.stderr:
                raise ValueError(
                    "Unexpected C observer diagnostic: " + raw.stderr + compact.stderr
                )
            rows = transition_rows(raw.stdout, path)
            zones.append(
                {
                    "name": name,
                    "compiled_tzif_sha256": sha(path),
                    "initial": compact_initial(compact.stdout),
                    "boundary_observations": rows,
                }
            )
            raw_outputs.append(
                {"name": name, "verbose": raw.stdout, "initial_compact": compact.stdout}
            )
            if (index + 1) % 100 == 0:
                print(form, "zones", index + 1, flush=True)
        write(E / ("raw-zdump-" + form + ".json.gz"), raw_outputs)
        forms[form] = {
            "zones": zones,
            "boundary_observation_count": sum(
                len(z["boundary_observations"]) for z in zones
            ),
            "all_compiled_files": {
                str(p.relative_to(destination)): sha(p)
                for p in sorted(destination.rglob("*"))
                if p.is_file()
            },
        }
    source_after = {
        str(p.relative_to(source)): sha(p)
        for p in sorted(source.rglob("*"))
        if p.is_file()
    }
    if source_before != source_after or any(
        sha(Path(p)) != value for p, value in binaries.items()
    ):
        raise ValueError(
            "Independent toolchain or original source changed during reference generation"
        )
    anchors = [
        seconds(datetime(year, month, 1, 12, tzinfo=timezone.utc))
        for year in range(1800, 2400)
        for month in (3, 9)
    ]
    write(
        output,
        {
            "method_id": "human_design_all_named_iana_C_history_reference_v1",
            "plan_sha256": PLAN_SHA,
            "generator_sha256": sha(Path(__file__)),
            "zone_list_and_packaged_hashes_sha256": sha(
                E / "packaged-zone-identities.json"
            ),
            "source_archives": plan["source_archives"],
            "source_files_before": source_before,
            "source_files_after": source_after,
            "toolchain_binaries": binaries,
            "zone_count": len(installed["zone_sha256"]),
            "anchor_seconds_since1970": anchors,
            "boundary_columns": [
                "utc_seconds_since1970",
                "offset_seconds",
                "abbreviation",
                "isdst",
                "local_label",
            ],
            "forms": forms,
            "reference_imports_FateBridge_or_production_reader": False,
            "historical_truth_certified": False,
            "astronomical_accuracy_certified": False,
            "scope": "Exact installed C2022g interpretation of pinned official2026e primary and full-backzone source. All current public names retained. Backzone is a separate fallible corpus, never promoted to truth or selected production policy. Historical subsecond clock realizations, unknown offset placeholders, compiler universality and actual past clocks remain distinct.",
        },
    )
    print(
        json.dumps(
            {
                "zone_count": len(installed["zone_sha256"]),
                "anchors_per_zone": len(anchors),
                "forms_boundary_rows": {
                    k: v["boundary_observation_count"] for k, v in forms.items()
                },
                "sha256": sha(output),
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    build(parser.parse_args().output)

"""Freeze clock-label expectations from primary IANA data and reference zic.

No FateBridge, zoneinfo or dateutil clock implementation supplies these labels.
The provider inventory only determines which public zone names to cover.
"""

import argparse
import bisect
import gzip
import hashlib
import json
import struct
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/data/bazi_birth_fold_v1"
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
INPUT_LOW = int((datetime(1900, 1, 1, tzinfo=timezone.utc) - EPOCH).total_seconds())
INPUT_HIGH = int((datetime(2101, 1, 1, tzinfo=timezone.utc) - EPOCH).total_seconds())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def offset_text(seconds):
    sign = "+" if seconds >= 0 else "-"
    hours, remainder = divmod(abs(seconds), 3600)
    minutes, last = divmod(remainder, 60)
    return f"{sign}{hours:02d}:{minutes:02d}" + (f":{last:02d}" if last else "")


def instant(seconds):
    return (EPOCH + timedelta(seconds=seconds)).isoformat()


def parse_tzif(raw):
    def header(start):
        assert raw[start : start + 4] == b"TZif"
        return struct.unpack(">6I", raw[start + 20 : start + 44])

    def length(counts, width):
        utc, std, leap, transition, kinds, chars = counts
        return (
            transition * width
            + transition
            + kinds * 6
            + chars
            + leap * (width + 4)
            + utc
            + std
        )

    counts = header(0)
    position, width = 44, 4
    if raw[4] != 0:
        assert raw[4:5] in {b"2", b"3", b"4"}
        position = 44 + length(counts, 4)
        counts = header(position)
        position += 44
        width = 8
    utc, std, leap, count, kind_count, chars = counts
    assert leap == 0, "Civil reference must not silently use right/leap TZif"
    times = list(
        struct.unpack(
            f">{count}{'q' if width == 8 else 'i'}",
            raw[position : position + count * width],
        )
    )
    position += count * width
    indices = list(raw[position : position + count])
    position += count
    kinds = [
        struct.unpack(">lBB", raw[position + i * 6 : position + i * 6 + 6])
        for i in range(kind_count)
    ]
    assert all(i < len(kinds) for i in indices)
    assert all(a < b for a, b in zip(times, times[1:]))
    return times, indices, kinds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iana-source", type=Path, required=True)
    args = parser.parse_args()
    source = args.iana_source.resolve()
    output = FIXTURE / "reference.json.gz"
    if output.exists():
        parser.error("Keep previous references; do not overwrite")
    inventory_path = FIXTURE / "provider-inventory.json"
    inventory = json.loads(inventory_path.read_text())
    assert (
        digest(inventory_path)
        == inventory_path.with_suffix(".sha256").read_text().strip()
    )
    assert (
        (source / "version").read_text().strip() == inventory["iana_version"] == "2026e"
    )
    zic = source / "zic"
    version = subprocess.run(
        [str(zic), "--version"], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert "2026e" in version
    folder = FIXTURE / "compiled"
    assert not folder.exists()
    folder.mkdir()
    low = int((datetime(1898, 1, 1, tzinfo=timezone.utc) - EPOCH).total_seconds())
    high = int((datetime(2103, 1, 1, tzinfo=timezone.utc) - EPOCH).total_seconds())
    names = [
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
    ]
    command = [
        str(zic),
        "-b",
        "fat",
        "-r",
        f"@{low}/@{high}",
        "-d",
        str(folder),
        *[str(source / n) for n in names],
    ]
    compiled = subprocess.run(command, capture_output=True, text=True, check=True)
    zones, rows = {}, []
    counts = {
        "fold_events": 0,
        "gap_events": 0,
        "fold_points": 0,
        "gap_points": 0,
        "nonchanging_offset_transitions": 0,
    }
    for name in inventory["all_public_named_zones"]:
        path = folder / name
        assert (
            path.is_file()
        ), f"Public zone absent from primary default compile: {name}"
        raw = path.read_bytes()
        times, indices, kinds = parse_tzif(raw)
        offsets = {k[0] for k in kinds}
        zone_counts = {"fold_events": 0, "gap_events": 0, "points": 0}

        def offset_at(epoch):
            index = bisect.bisect_right(times, epoch) - 1
            return kinds[indices[index] if index >= 0 else 0][0]

        previous = 0
        for index, at in enumerate(times):
            old, new = kinds[previous][0], kinds[indices[index]][0]
            previous = indices[index]
            if old == new:
                counts["nonchanging_offset_transitions"] += 1
                continue
            wall_start, wall_end = at + min(old, new), at + max(old, new)
            start, end = max(wall_start, INPUT_LOW), min(wall_end, INPUT_HIGH)
            if start >= end:
                continue
            kind = "fold" if new < old else "gap"
            counts[kind + "_events"] += 1
            zone_counts[kind + "_events"] += 1
            points = sorted({start, (start + end - 1) // 2, end - 1})
            for point in points:
                valid = sorted(
                    (point - off, off)
                    for off in offsets
                    if offset_at(point - off) == off
                )
                assert len(valid) == (2 if kind == "fold" else 0), (
                    name,
                    at,
                    point,
                    kind,
                    valid,
                )
                expected = [
                    {
                        "utc": instant(epoch),
                        "offset": offset_text(off),
                        "offset_seconds": off,
                        "fold": order,
                    }
                    for order, (epoch, off) in enumerate(valid)
                ]
                wrong = old + 1
                while wrong in {old, new}:
                    wrong += 1
                row = {
                    "id": f"{name}@{at}:{point}",
                    "zone": name,
                    "kind": kind,
                    "transition_utc": instant(at),
                    "transition_epoch": at,
                    "source_before_offset_seconds": old,
                    "source_after_offset_seconds": new,
                    "wall": (EPOCH + timedelta(seconds=point))
                    .replace(tzinfo=None)
                    .isoformat(),
                    "source_wall_interval_seconds": [wall_start, wall_end],
                    "birth_range_clipped_wall_interval_seconds": [start, end],
                    "expected": expected,
                    "wrong_offset": offset_text(wrong),
                    "gap_offset_controls": (
                        [offset_text(old), offset_text(new)] if kind == "gap" else []
                    ),
                    "shift_seconds": new - old,
                }
                rows.append(row)
                counts[kind + "_points"] += 1
                zone_counts["points"] += 1
        zones[name] = {
            "compiled_sha256": hashlib.sha256(raw).hexdigest(),
            "provider_sha256": inventory["all_public_named_zones"][name],
            **zone_counts,
        }
    result = {
        "protocol_sha256": digest(FIXTURE / "protocol.json"),
        "provider_inventory_sha256": digest(inventory_path),
        "source_archives_sha256": digest(FIXTURE / "source-archives.json"),
        "version": inventory["iana_version"],
        "zic_version": version,
        "zic_sha256": digest(zic),
        "zic_command": command,
        "zic_stderr": compiled.stderr,
        "source_file_sha256": {n: digest(source / n) for n in names},
        "zone_count": len(zones),
        "zones": zones,
        "counts": counts,
        "rows": rows,
        "scope": "All declared public names, default primary IANA2026e profile, local birth years1900..2100. TZif parsed directly after official-source zic compile. Aliases overlap; future rules are conditional projections, not independent historical observation or real-world prediction. No FateBridge/zoneinfo/dateutil clock supplies truth.",
        "new_independent_observation_credit": 0,
        "candidate_code_used": False,
        "full_goal_complete": False,
    }
    output.write_bytes(
        gzip.compress(
            (
                json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n"
            ).encode(),
            mtime=0,
        )
    )
    output.with_suffix(".sha256").write_text(digest(output) + "\n")
    print(
        json.dumps(
            {
                "zones": len(zones),
                "counts": counts,
                "reference_sha256": digest(output),
                "bytes": output.stat().st_size,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

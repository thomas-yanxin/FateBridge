"""Compare all pinned standard/backzone TZif profiles without application imports."""

import bisect
import hashlib
import json
import runpy
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/data/bazi_historical_clock_profiles_v1"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    output = FIXTURE / "reference.json"
    assert not output.exists(), "Preserve first differential labels"
    protocol_path = FIXTURE / "protocol.json"
    assert (
        sha(protocol_path) == protocol_path.with_suffix(".sha256").read_text().strip()
    )
    protocol = json.loads(protocol_path.read_text())
    for name, digest in protocol["source_files"].items():
        assert sha(ROOT / name) == digest, name
    inventory_source = protocol["inventory"]
    assert sha(ROOT / inventory_source["path"]) == inventory_source["sha256"]
    parser = runpy.run_path(str(ROOT / protocol["parser"]["path"]))["parse_tzif"]
    inventory = json.loads((ROOT / protocol["inventory"]["path"]).read_text())
    low = int(datetime(1900, 1, 1, tzinfo=timezone.utc).timestamp())
    high = int(datetime(2101, 1, 1, tzinfo=timezone.utc).timestamp())
    counts, rows = Counter(), []

    def stamp(t):
        return datetime.fromtimestamp(t, timezone.utc).isoformat()

    for zone in inventory["all_public_named_zones"]:
        row = {"zone": zone, "compiled_profiles": {}, "offset_difference_intervals": []}
        profiles = {}
        for name in ["standard", "backzone"]:
            p = FIXTURE / ("compiled-" + name) / zone
            if not p.is_file():
                row.setdefault("missing_profiles", []).append(name)
                continue
            times, indices, kinds = parser(p.read_bytes())
            row["compiled_profiles"][name] = {
                "path": str(p.relative_to(ROOT)),
                "sha256": sha(p),
                "offset_types_seconds": sorted({k[0] for k in kinds}),
            }
            profiles[name] = (times, indices, kinds)
        if len(profiles) < 2:
            row["status"] = "unresolved_missing_profile"
            counts[row["status"]] += 1
            rows.append(row)
            continue
        cuts = {low, 0, high}
        for times, _, _ in profiles.values():
            cuts.update(t for t in times if low < t < high)
        ordered = sorted(cuts)
        for a, b in zip(ordered, ordered[1:]):
            offsets = {}
            for name, (times, indices, kinds) in profiles.items():
                assert times[0] <= a < b <= times[-1]
                index = bisect.bisect_right(times, a) - 1
                offsets[name] = kinds[indices[index]][0]
            if offsets["standard"] == offsets["backzone"]:
                continue
            row["offset_difference_intervals"].append(
                {
                    "start_utc": stamp(a),
                    "end_exclusive_utc": stamp(b),
                    "standard_offset_seconds": offsets["standard"],
                    "backzone_offset_seconds": offsets["backzone"],
                    "delta_seconds": offsets["backzone"] - offsets["standard"],
                    "era": "before1970" if b <= 0 else "since1970",
                }
            )
            counts["different_constant_offset_intervals"] += 1
            counts[
                (
                    "different_intervals_before1970"
                    if b <= 0
                    else "different_intervals_since1970"
                )
            ] += 1
            counts["different_name_seconds"] += b - a
        row["status"] = (
            "different_clock_profiles"
            if row["offset_difference_intervals"]
            else "same_offsets_in_supported_interval"
        )
        counts[row["status"]] += 1
        rows.append(row)
    assert len(rows) == inventory["zone_count"] == 597
    assert not any(
        k.split(".")[0] in {"fatebridge", "dateutil", "zoneinfo"} for k in sys.modules
    )
    report = {
        "protocol_sha256": sha(protocol_path),
        "zone_count": len(rows),
        "counts": dict(counts),
        "comparison_start_utc": stamp(low),
        "comparison_end_exclusive_utc": stamp(high),
        "rows": rows,
        "no_application_dateutil_zoneinfo_imported": True,
        "scope": "Every named zone in frozen provider inventory, both officialsource compile profiles. UTCoffset model differences, not truehistoricalcivilrecord labels or proof that backzone is moreaccurate. Pre/post1970 differences retained; no sourcepolicy chosen by application fit.",
        "new_application_calls": 0,
        "new_independent_observation_credit": 0,
        "full_goal_complete": False,
        "authority_certified": False,
        "overall_score": None,
    }
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    output.with_suffix(".sha256").write_text(sha(output) + "\n")
    print(
        json.dumps({"zones": len(rows), "counts": dict(counts), "sha256": sha(output)})
    )


if __name__ == "__main__":
    main()

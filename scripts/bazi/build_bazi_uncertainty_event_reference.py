"""Freeze every declared raw-civil Jie/hour coupling from archived sources.

No application or ZoneInfo calculation supplies the labels. The existing
primary TZif parser supplies offsets; archived root states supply year/month.
"""

import bisect
import gzip
import hashlib
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.bazi.build_bazi_birth_fold_reference import offset_text, parse_tzif

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/data/bazi_uncertainty_events_v1"
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
SECOND = 1_000_000
HOUR = 3600 * SECOND
JIE = {
    "小寒",
    "立春",
    "惊蛰",
    "清明",
    "立夏",
    "芒种",
    "小暑",
    "立秋",
    "白露",
    "寒露",
    "立冬",
    "大雪",
}
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def micros(moment):
    delta = moment - EPOCH
    return (delta.days * 86400 + delta.seconds) * SECOND + delta.microseconds


def iso(value):
    return (EPOCH + timedelta(microseconds=value)).isoformat()


def main():
    output = FIXTURE / "reference.json.gz"
    assert not output.exists(), "Preserve the original reference"
    protocol_path = FIXTURE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    for entry in protocol["sources"].values():
        assert sha(ROOT / entry["path"]) == entry["sha256"]
    clock = json.loads(
        gzip.decompress(
            (ROOT / protocol["sources"]["iana_reference"]["path"]).read_bytes()
        )
    )
    data = json.loads(
        (ROOT / protocol["sources"]["term_reference"]["path"]).read_text()
    )
    roots = sorted(
        [r for r in data["rows"] if r["side"] == "next_minute"],
        key=lambda r: r["reference_civil_under_frozen_policy"],
    )
    counts, rows, zone_hashes = Counter(), [], {}
    margin = round(protocol["known_reference_order_margin_seconds"] * SECOND)
    for zone, receipt in clock["zones"].items():
        path = ROOT / "tests/data/bazi_birth_fold_v1/compiled" / zone
        assert sha(path) == receipt["compiled_sha256"]
        zone_hashes[zone] = sha(path)
        times, indices, kinds = parse_tzif(path.read_bytes())

        def offset_at(at_us):
            index = bisect.bisect_right(times, at_us // SECOND) - 1
            return kinds[indices[index] if index >= 0 else 0][0]

        for index, root in enumerate(roots):
            if root["name"] not in JIE:
                continue
            at = micros(
                datetime.fromisoformat(root["reference_civil_under_frozen_policy"])
            )
            offset = offset_at(at)
            wall = at + offset * SECOND
            if not 1900 <= (EPOCH + timedelta(microseconds=wall)).year <= 2100:
                continue
            counts["jie_zone_pairs_in_birth_range"] += 1
            boundary_wall = ((wall + HOUR // 2) // HOUR) * HOUR
            hour = (boundary_wall // HOUR) % 24
            separation = wall - boundary_wall
            if hour % 2 == 0 or abs(separation) > 30 * SECOND:
                continue
            assert index > 0
            boundary = boundary_wall - offset * SECOND
            low, high = boundary - 90 * SECOND, boundary + 30 * SECOND
            left = bisect.bisect_left(times, (low + SECOND - 1) // SECOND)
            right = bisect.bisect_right(times, high // SECOND)
            overlaps = times[left:right]
            before = roots[index - 1]["reference_state_under_frozen_policy"]
            after = root["reference_state_under_frozen_policy"]
            assert before["month_branch"] != after["month_branch"]
            old_hour, new_hour = BRANCHES[hour // 2], BRANCHES[((hour + 1) // 2) % 12]

            def signature(instant):
                state = after if instant >= at else before
                return {
                    "bazi_year": state["bazi_year"],
                    "month_branch": state["month_branch"],
                    "hour_branch": new_hour if instant >= boundary else old_hour,
                }

            if overlaps:
                status = "unresolved_civil_transition_overlap"
            elif separation == 0:
                status = "coincident_control"
            elif abs(separation) <= margin:
                status = "unresolved_reference_order_margin"
            else:
                status = "resolved_three_regions"
            counts[status] += 1
            grid = [
                {"utc": iso(t), "signature": signature(t)}
                for t in [
                    boundary - 90 * SECOND,
                    boundary - 30 * SECOND,
                    boundary + 30 * SECOND,
                ]
            ]
            events = sorted({low, at, boundary, high})
            regions = []
            if status in {"resolved_three_regions", "coincident_control"}:
                for a, b in zip(events, events[1:]):
                    probe = (a + b) // 2
                    regions.append(
                        {
                            "start_utc": iso(a),
                            "end_utc": iso(b),
                            "end_inclusive": b == high,
                            "probe_utc": iso(probe),
                            "duration_seconds": (b - a) / SECOND,
                            "signature": signature(probe),
                        }
                    )
                assert len(regions) == (3 if status == "resolved_three_regions" else 2)
            missing = [
                r["signature"]
                for r in regions
                if r["signature"] not in [g["signature"] for g in grid]
            ]
            if status == "resolved_three_regions":
                assert len(missing) == 1
            center_wall = EPOCH + timedelta(microseconds=boundary_wall - 30 * SECOND)
            row = {
                "id": f"{root['year']}-{root['name']}@{zone}",
                "zone": zone,
                "root_name": root["name"],
                "root_utc_under_frozen_policy": iso(at),
                "hour_boundary_utc": iso(boundary),
                "source_offset_seconds": offset,
                "root_minus_hour_seconds": separation / SECOND,
                "status": status,
                "civil_transition_overlaps_utc": [iso(t * SECOND) for t in overlaps],
                "input": {
                    "birth_year": center_wall.year,
                    "birth_month": center_wall.month,
                    "birth_day": center_wall.day,
                    "birth_hour": center_wall.hour,
                    "birth_minute": center_wall.minute,
                    "birth_second": center_wall.second,
                    "birth_timezone": zone,
                    "birth_utc_offset": offset_text(offset),
                    "use_true_solar_time": False,
                },
                "uncertainty_minutes": 1,
                "range_utc": [iso(low), iso(high)],
                "expected_grid": grid,
                "expected_regions": regions,
                "expected_signatures_missing_from_grid": missing,
            }
            rows.append(row)
        if len(zone_hashes) % 100 == 0:
            print(
                json.dumps(
                    {"zones": len(zone_hashes), "selected": len(rows), "counts": counts}
                ),
                flush=True,
            )
    result = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": sha(protocol_path),
        "sources": protocol["sources"],
        "compiled_zone_sha256": zone_hashes,
        "zone_count": len(zone_hashes),
        "counts": dict(counts),
        "selected_points": len(rows),
        "rows": rows,
        "scope": protocol["first_diagnostic_scope"],
        "candidate_code_used_for_labels": False,
        "new_independent_observation_credit": 0,
        "full_goal_complete": False,
        "overall_score": None,
    }
    output.write_bytes(
        gzip.compress(
            (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode(), mtime=0
        )
    )
    output.with_suffix(".sha256").write_text(sha(output) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in {"rows", "compiled_zone_sha256"}
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()

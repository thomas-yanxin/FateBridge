"""Freeze first-dayun future-gap controls from primary TZif and archived Jie."""

import bisect
import gzip
import hashlib
import json
import runpy
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/data/bazi_dayun_future_gaps_v1"
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
SECOND = 1_000_000
DAY = 86400 * SECOND
MONTH = 21600 * SECOND
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


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def micros(delta):
    return (delta.days * 86400 + delta.seconds) * SECOND + delta.microseconds


def instant(value):
    return EPOCH + timedelta(microseconds=value)


def main():
    output = FIXTURE / "reference.json.gz"
    assert not output.exists(), "Preserve first source labels"
    protocol_path = FIXTURE / "protocol.json"
    assert (
        sha(protocol_path) == protocol_path.with_suffix(".sha256").read_text().strip()
    )
    protocol = json.loads(protocol_path.read_text())
    for name, digest in protocol["files"].items():
        assert sha(ROOT / name) == digest, name
    parser = runpy.run_path(
        str(ROOT / "scripts/bazi/build_bazi_birth_fold_reference.py")
    )
    clock_path = ROOT / "tests/data/bazi_birth_fold_v1/compiled/America/New_York"
    times, indices, kinds = parser["parse_tzif"](clock_path.read_bytes())
    integer_operator = runpy.run_path(
        str(ROOT / "scripts/bazi/build_bazi_dayun_carry_reference.py")
    )["initial_boundary"]
    offsets = sorted({kind[0] for kind in kinds})

    def offset_at(value):
        index = bisect.bisect_right(times, value // SECOND) - 1
        return kinds[indices[index] if index >= 0 else 0][0]

    gaps = []
    for i, at in enumerate(times):
        old = kinds[indices[i - 1] if i else 0][0]
        new = kinds[indices[i]][0]
        end_wall = at * SECOND + new * SECOND
        if new > old and 1900 <= instant(end_wall).year <= 2100:
            gaps.append(
                {
                    "at": at * SECOND,
                    "old": old,
                    "new": new,
                    "delta": new - old,
                    "start_wall": at * SECOND + old * SECOND,
                    "end_wall": end_wall,
                }
            )
    gaps.sort(key=lambda g: g["end_wall"])
    ends = [g["end_wall"] for g in gaps]

    def valid_wall_instants(wall):
        return sorted(
            {
                wall - offset * SECOND
                for offset in offsets
                if times[0] * SECOND <= wall - offset * SECOND < times[-1] * SECOND
                and offset_at(wall - offset * SECOND) == offset
            }
        )

    def resolve_wall(wall, birth):
        valid = valid_wall_instants(wall)
        if not valid:
            matches = [g for g in gaps if g["start_wall"] <= wall < g["end_wall"]]
            if len(matches) != 1:
                raise ValueError("source_gap_or_coverage_unresolved")
            valid = valid_wall_instants(wall + matches[0]["delta"] * SECOND)
        if not valid:
            raise ValueError("source_shifted_wall_unresolved")
        resolved = valid[0]  # fold0, earliest occurrence.
        if resolved < birth:
            later = [value for value in valid_wall_instants(wall) if value >= birth]
            if not later:
                raise ValueError("source_initial_boundary_before_birth")
            resolved = later[0]
        return resolved

    def wall_start(birth, root, offset):
        civil = instant(birth).astimezone(timezone(timedelta(seconds=offset)))
        wall = integer_operator(civil, root).replace(tzinfo=timezone.utc)
        return micros(wall - EPOCH)

    data = json.loads(
        (ROOT / "tests/data/bazi_boundary_decisions_v1/probes.json").read_text()
    )
    roots = sorted(
        [r for r in data["rows"] if r["side"] == "next_minute" and r["name"] in JIE],
        key=lambda r: r["reference_civil_under_frozen_policy"],
    )
    counts, rows = Counter(), []
    for previous, following in zip(roots, roots[1:]):
        root = datetime.fromisoformat(previous["reference_civil_under_frozen_policy"])
        low_root = micros(root - EPOCH)
        high_root = micros(
            datetime.fromisoformat(following["reference_civil_under_frozen_policy"])
            - EPOCH
        )
        assert high_root - low_root <= 133 * MONTH
        for month in range(133):
            low, high = (
                low_root + month * MONTH,
                min(high_root, low_root + (month + 1) * MONTH),
            )
            if low >= high:
                continue
            counts["jie_nominal_month_cells"] += 1
            zone_cuts = {low, high}
            zone_cuts.update(
                t * SECOND
                for t in times[
                    bisect.bisect_right(times, low // SECOND) : bisect.bisect_right(
                        times, high // SECOND
                    )
                ]
                if low < t * SECOND < high
            )
            cuts = set(zone_cuts)
            ordered_zone = sorted(zone_cuts)
            for a, b in zip(ordered_zone, ordered_zone[1:]):
                offset = offset_at((a + b) // 2)
                midnight = ((a + offset * SECOND) // DAY + 1) * DAY
                while midnight < b + offset * SECOND:
                    cuts.add(midnight - offset * SECOND)
                    midnight += DAY
            ordered = sorted(cuts)
            for cell_index, (a, b) in enumerate(zip(ordered, ordered[1:])):
                offset = offset_at(a)
                if not 1900 <= instant(a + offset * SECOND).year <= 2100:
                    counts["birth_date_cells_outside_public_domain"] += 1
                    continue
                counts["constant_birth_offset_date_month_cells"] += 1
                assert offset_at(b - 1) == offset
                assert (
                    instant(a + offset * SECOND).date()
                    == instant(b - 1 + offset * SECOND).date()
                )
                first, last = (
                    wall_start(a, root, offset),
                    wall_start(b - 1, root, offset),
                )
                assert last - first == 121 * (b - a - 1)
                for gap in gaps[
                    bisect.bisect_left(ends, first) : bisect.bisect_right(ends, last)
                ]:
                    quotient, remainder = divmod(gap["end_wall"] - first, 121)
                    lower = a + quotient
                    upper = lower + bool(remainder)
                    center = upper // SECOND * SECOND - 31 * SECOND
                    nominal_offset = offset_at(center)
                    civil = instant(center).astimezone(
                        timezone(timedelta(seconds=nominal_offset))
                    )
                    if not 1900 <= civil.year <= 2100:
                        counts["inverse_centers_outside_public_domain"] += 1
                        continue
                    counts["source_inverse_events"] += 1
                    bazi_year = previous["reference_state_under_frozen_policy"][
                        "bazi_year"
                    ]
                    assert bazi_year is not None
                    gender = "女" if (bazi_year - 4) % 2 == 0 else "男"
                    analysis = gap["at"] + gap["delta"] * SECOND - 40 * SECOND
                    grid = [center + shift * 60 * SECOND for shift in [-1, 0, 1]]
                    witnesses = [upper - 100000, lower, upper, upper + 100000]
                    record = {
                        "id": f"{previous['year']}-{previous['name']}-month{month}-cell{cell_index}-gap{gap['at'] // SECOND}",
                        "source_jie": previous,
                        "next_jie_utc": instant(high_root).isoformat(),
                        "nominal_months": month,
                        "birth_cell_utc": [
                            instant(a).isoformat(),
                            instant(b).isoformat(),
                        ],
                        "birth_cell_offset_seconds": offset,
                        "inverse_floor_utc": instant(lower).isoformat(),
                        "inverse_ceil_utc": instant(upper).isoformat(),
                        "inverse_bracket_us": upper - lower,
                        "analysis_at": instant(analysis).isoformat(),
                        "gap": {
                            "transition_utc": instant(gap["at"]).isoformat(),
                            "before_offset_seconds": gap["old"],
                            "after_offset_seconds": gap["new"],
                            "gap_seconds": gap["delta"],
                            "start_wall": instant(gap["start_wall"])
                            .replace(tzinfo=None)
                            .isoformat(),
                            "end_wall": instant(gap["end_wall"])
                            .replace(tzinfo=None)
                            .isoformat(),
                        },
                        "input": {
                            "birth_year": civil.year,
                            "birth_month": civil.month,
                            "birth_day": civil.day,
                            "birth_hour": civil.hour,
                            "birth_minute": civil.minute,
                            "birth_second": civil.second,
                            "birth_timezone": protocol["zone"],
                            "birth_utc_offset": parser["offset_text"](nominal_offset),
                            "gender": gender,
                            "use_true_solar_time": False,
                        },
                        "uncertainty_minutes": 1,
                        "range_utc": [
                            instant(grid[0]).isoformat(),
                            instant(grid[-1]).isoformat(),
                        ],
                    }
                    if min(grid + witnesses) < a or max(grid + witnesses) >= b:
                        record.update(
                            status="unresolved_interaction",
                            unresolved_reason="declared_range_or_witness_outside_constant_reference_month_date_offset_cell",
                        )
                        counts["unresolved_interaction"] += 1
                    else:
                        try:

                            def observe(at):
                                wall = wall_start(at, root, offset)
                                start = resolve_wall(wall, at)
                                return {
                                    "birth_utc": instant(at).isoformat(),
                                    "manual_wall_start": instant(wall)
                                    .replace(tzinfo=None)
                                    .isoformat(),
                                    "manual_start_at": instant(start).isoformat(),
                                    "expected_status": (
                                        "before_dayun" if analysis < start else "active"
                                    ),
                                }

                            observed_grid = [observe(at) for at in grid]
                            observed_witnesses = [observe(at) for at in witnesses]
                            states = sorted(
                                {
                                    p["expected_status"]
                                    for p in observed_grid + observed_witnesses
                                }
                            )
                            missing = sorted(
                                set(states)
                                - {p["expected_status"] for p in observed_grid}
                            )
                            record.update(
                                status="resolved_source_control",
                                expected_grid=observed_grid,
                                expected_witnesses=observed_witnesses,
                                expected_statuses=states,
                                missing_from_minute_grid=missing,
                            )
                            counts["resolved_source_controls"] += 1
                            counts["source_grid_missing_witness_state"] += bool(missing)
                        except ValueError as error:
                            record.update(
                                status="unresolved_source_resolution",
                                unresolved_reason=str(error),
                            )
                            counts["unresolved_source_resolution"] += 1
                    rows.append(record)
    assert len({r["id"] for r in rows}) == len(rows)
    assert not any(
        k.split(".")[0] in {"fatebridge", "dateutil", "zoneinfo"} for k in sys.modules
    )
    report = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": sha(protocol_path),
        "compiled_tzif_sha256": sha(clock_path),
        "positive_source_gaps": len(gaps),
        "counts": dict(counts),
        "rows": rows,
        "no_application_dateutil_zoneinfo_imported": True,
        "scope": "Primary TZif NewYork positive-gap ends and archived computed Jie, reverse initial-boundary cells only. Rational inverse and integer calendar software controls; unresolved interactions retained, no physical/originaltext/prediction authority credit.",
        "new_independent_observation_credit": 0,
        "full_goal_complete": False,
        "overall_score": None,
    }
    output.write_bytes(
        gzip.compress(
            (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode(), mtime=0
        )
    )
    output.with_suffix(".sha256").write_text(sha(output) + "\n")
    print(
        json.dumps(
            {
                "positive_source_gaps": len(gaps),
                "counts": dict(counts),
                "rows": len(rows),
                "sha256": sha(output),
            }
        )
    )


if __name__ == "__main__":
    main()

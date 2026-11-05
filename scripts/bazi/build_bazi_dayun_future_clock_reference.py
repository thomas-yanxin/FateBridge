"""Stream frozen multi-zone/direction future-clock controls without app imports."""

import argparse
import bisect
import calendar
import gzip
import hashlib
import json
import runpy
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/data/bazi_dayun_future_clocks_v2"
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


def initial_wall(birth_us, root_us, offset):
    civil = instant(birth_us + offset * SECOND)
    years, remainder = divmod(abs(birth_us - root_us) * 120, 360 * DAY)
    months, remainder = divmod(remainder, 30 * DAY)
    days, remainder = divmod(remainder, DAY)
    year, month0 = divmod((civil.year + years) * 12 + civil.month - 1 + months, 12)
    month = month0 + 1
    shifted = civil.replace(
        year=year, month=month, day=min(civil.day, calendar.monthrange(year, month)[1])
    )
    return micros(shifted + timedelta(days=days, microseconds=remainder) - EPOCH)


class SourceClock:
    def __init__(self, zone, parser):
        self.zone = zone
        self.path = (
            ROOT
            / "tests/data/bazi_historical_clock_profiles_v1/compiled-standard"
            / zone
        )
        self.times, self.indices, self.kinds = parser(self.path.read_bytes())
        self.offsets = sorted({kind[0] for kind in self.kinds})
        self.gaps = []
        # The first/last TZif transitions are synthetic -r coverage sentinels,
        # not civil laws. Keep the bounds, never reinterpret them as gaps.
        for i in range(1, len(self.times) - 1):
            at = self.times[i] * SECOND
            old, new = (
                self.kinds[self.indices[i - 1]][0],
                self.kinds[self.indices[i]][0],
            )
            if new > old:
                self.gaps.append(
                    {
                        "at": at,
                        "old": old,
                        "new": new,
                        "delta": new - old,
                        "start_wall": at + old * SECOND,
                        "end_wall": at + new * SECOND,
                    }
                )
        self.gaps.sort(key=lambda gap: gap["end_wall"])
        self.ends = [g["end_wall"] for g in self.gaps]

    def offset_at(self, at):
        if not self.times[0] * SECOND <= at < self.times[-1] * SECOND:
            raise ValueError("outside_compiled_clock_coverage")
        i = bisect.bisect_right(self.times, at // SECOND) - 1
        return self.kinds[self.indices[i]][0]

    def valid_wall(self, wall):
        values = []
        for offset in self.offsets:
            at = wall - offset * SECOND
            if (
                self.times[0] * SECOND <= at < self.times[-1] * SECOND
                and self.offset_at(at) == offset
            ):
                values.append(at)
        return sorted(set(values))

    def resolve(self, wall, birth):
        values = self.valid_wall(wall)
        if not values:
            gaps = [g for g in self.gaps if g["start_wall"] <= wall < g["end_wall"]]
            if len(gaps) != 1:
                raise ValueError("source_gap_or_coverage_unresolved")
            values = self.valid_wall(wall + gaps[0]["delta"] * SECOND)
        if not values:
            raise ValueError("source_shifted_wall_unresolved")
        resolved = values[0]
        if resolved < birth:
            later = [at for at in self.valid_wall(wall) if at >= birth]
            if not later:
                raise ValueError("source_initial_boundary_before_birth")
            resolved = later[0]
        return resolved

    def cuts(self, low, high):
        cuts = {low, high}
        cuts.update(
            t * SECOND
            for t in self.times[
                bisect.bisect_right(self.times, low // SECOND) : bisect.bisect_right(
                    self.times, high // SECOND
                )
            ]
            if low < t * SECOND < high
        )
        for a, b in zip(sorted(cuts), sorted(cuts)[1:]):
            offset = self.offset_at((a + b) // 2)
            midnight = ((a + offset * SECOND) // DAY + 1) * DAY
            while midnight < b + offset * SECOND:
                cuts.add(midnight - offset * SECOND)
                midnight += DAY
        ordered = sorted(cuts)
        return zip(ordered, ordered[1:])


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--protocol", default="protocol.json")
    cli.add_argument("--output-prefix", default="reference")
    args = cli.parse_args()
    output = FIXTURE / f"{args.output_prefix}.jsonl.gz"
    summary = FIXTURE / f"{args.output_prefix}-summary.json"
    partial = output.with_suffix(".partial")
    assert (
        not output.exists() and not partial.exists() and not summary.exists()
    ), "Preserve first labels"
    protocol_path = FIXTURE / args.protocol
    assert (
        sha(protocol_path) == protocol_path.with_suffix(".sha256").read_text().strip()
    )
    protocol = json.loads(protocol_path.read_text())
    for name, digest in protocol["files"].items():
        assert sha(ROOT / name) == digest, name
    parser = runpy.run_path(
        str(ROOT / "scripts/bazi/build_bazi_birth_fold_reference.py")
    )
    reference_operator = runpy.run_path(
        str(ROOT / "scripts/bazi/build_bazi_dayun_carry_reference.py")
    )["initial_boundary"]
    data = json.loads(
        (ROOT / "tests/data/bazi_boundary_decisions_v1/probes.json").read_text()
    )
    roots = sorted(
        [r for r in data["rows"] if r["side"] == "next_minute" and r["name"] in JIE],
        key=lambda r: r["reference_civil_under_frozen_policy"],
    )
    counts, cohorts, inventory = Counter(), {}, {}
    row_count = 0
    with (
        partial.open("xb") as raw,
        gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as stream,
    ):

        def emit(record):
            stream.write(
                (
                    json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
                ).encode()
            )

        emit(
            {
                "record_type": "header",
                "protocol_sha256": sha(protocol_path),
                "source_files": protocol["files"],
                "jie_root_count": len(roots),
                "jie_source_range_utc": [
                    roots[0]["reference_civil_under_frozen_policy"],
                    roots[-1]["reference_civil_under_frozen_policy"],
                ],
            }
        )
        for zone in protocol["zones"]:
            clock = SourceClock(zone, parser["parse_tzif"])
            inventory[zone] = {
                "tzif_sha256": sha(clock.path),
                "positive_gaps": len(clock.gaps),
                "gap_deltas_seconds": dict(
                    Counter(str(g["delta"]) for g in clock.gaps)
                ),
                "coverage_start_utc": instant(clock.times[0] * SECOND).isoformat(),
                "coverage_end_exclusive_utc": instant(
                    clock.times[-1] * SECOND
                ).isoformat(),
                "synthetic_coverage_endpoints_excluded": 2,
            }
            for direction in protocol["directions"]:
                local = Counter()
                slope = 121 if direction == "reverse" else -119
                for previous, following in zip(roots, roots[1:]):
                    first_root, next_root = (
                        micros(
                            datetime.fromisoformat(
                                r["reference_civil_under_frozen_policy"]
                            )
                            - EPOCH
                        )
                        for r in [previous, following]
                    )
                    root = first_root if direction == "reverse" else next_root
                    source_root = previous if direction == "reverse" else following
                    for month in range(133):
                        low, high = (
                            (root + month * MONTH, root + (month + 1) * MONTH)
                            if direction == "reverse"
                            else (
                                root - (month + 1) * MONTH + 1,
                                root - month * MONTH + 1,
                            )
                        )
                        low, high = max(first_root, low), min(next_root, high)
                        if low >= high:
                            continue
                        local["jie_nominal_month_cells"] += 1
                        for cell_index, (a, b) in enumerate(clock.cuts(low, high)):
                            offset = clock.offset_at(a)
                            if not 1900 <= instant(a + offset * SECOND).year <= 2100:
                                local["birth_date_cells_outside_public_domain"] += 1
                                continue
                            local["constant_birth_date_offset_month_cells"] += 1
                            assert clock.offset_at(b - 1) == offset
                            assert (
                                instant(a + offset * SECOND).date()
                                == instant(b - 1 + offset * SECOND).date()
                            )
                            first, last = (
                                initial_wall(a, root, offset),
                                initial_wall(b - 1, root, offset),
                            )
                            assert last - first == slope * (b - a - 1)
                            if direction == "reverse":
                                civil = instant(a).astimezone(
                                    timezone(timedelta(seconds=offset))
                                )
                                reference = reference_operator(
                                    civil, instant(root)
                                ).replace(tzinfo=timezone.utc)
                                assert micros(reference - EPOCH) == first
                                local["reverse_reference_operator_checks"] += 1
                            lo_wall, hi_wall = sorted([first, last])
                            for gap in clock.gaps[
                                bisect.bisect_left(
                                    clock.ends, lo_wall
                                ) : bisect.bisect_right(clock.ends, hi_wall)
                            ]:
                                q, remainder = divmod(gap["end_wall"] - first, slope)
                                lower, upper = a + q, a + q + bool(remainder)
                                assert a <= lower <= upper < b
                                center = upper // SECOND * SECOND - 31 * SECOND
                                center_offset = clock.offset_at(center)
                                civil = instant(center + center_offset * SECOND)
                                bazi_year = previous[
                                    "reference_state_under_frozen_policy"
                                ]["bazi_year"]
                                assert bazi_year is not None
                                is_yang = (bazi_year - 4) % 2 == 0
                                gender = (
                                    ("男" if is_yang else "女")
                                    if direction == "forward"
                                    else ("女" if is_yang else "男")
                                )
                                analysis = gap["at"] + gap["delta"] * SECOND // 2
                                guard = max(
                                    1, min(100000, gap["delta"] * SECOND // (4 * 121))
                                )
                                grid = [
                                    center + shift * 60 * SECOND for shift in [-1, 0, 1]
                                ]
                                witnesses = [upper - guard, lower, upper, upper + guard]
                                record = {
                                    "record_type": "control",
                                    "id": f"{zone}/{direction}/{previous['year']}-{previous['name']}/month{month}/cell{cell_index}/gap{gap['at'] // SECOND}",
                                    "direction": direction,
                                    "zone": zone,
                                    "source_jie": source_root,
                                    "birth_cell_utc": [
                                        instant(a).isoformat(),
                                        instant(b).isoformat(),
                                    ],
                                    "birth_cell_offset_seconds": offset,
                                    "nominal_months": month,
                                    "inverse_floor_utc": instant(lower).isoformat(),
                                    "inverse_ceil_utc": instant(upper).isoformat(),
                                    "inverse_bracket_us": upper - lower,
                                    "witness_guard_us": guard,
                                    "analysis_at": instant(analysis).isoformat(),
                                    "gap": {
                                        "transition_utc": instant(
                                            gap["at"]
                                        ).isoformat(),
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
                                        "birth_timezone": zone,
                                        "birth_utc_offset": parser["offset_text"](
                                            center_offset
                                        ),
                                        "gender": gender,
                                        "use_true_solar_time": False,
                                    },
                                    "uncertainty_minutes": 1,
                                    "range_utc": [
                                        instant(grid[0]).isoformat(),
                                        instant(grid[-1]).isoformat(),
                                    ],
                                }
                                if not 1900 <= civil.year <= 2100:
                                    record.update(
                                        status="unresolved_public_input_domain",
                                        unresolved_reason="nominal_reference_outside_public_birth_domain",
                                    )
                                elif (
                                    min(grid + witnesses) < a
                                    or max(grid + witnesses) >= b
                                ):
                                    record.update(
                                        status="unresolved_interaction",
                                        unresolved_reason="declared_range_or_witness_outside_constant_reference_month_date_offset_cell",
                                    )
                                else:
                                    try:

                                        def observe(at):
                                            wall = initial_wall(at, root, offset)
                                            resolved = clock.resolve(wall, at)
                                            return {
                                                "birth_utc": instant(at).isoformat(),
                                                "manual_wall_start": instant(wall)
                                                .replace(tzinfo=None)
                                                .isoformat(),
                                                "manual_start_at": instant(
                                                    resolved
                                                ).isoformat(),
                                                "expected_status": (
                                                    "before_dayun"
                                                    if analysis < resolved
                                                    else "active"
                                                ),
                                            }

                                        observed_grid, observed_witnesses = (
                                            [observe(at) for at in grid],
                                            [observe(at) for at in witnesses],
                                        )
                                        states = sorted(
                                            {
                                                p["expected_status"]
                                                for p in observed_grid
                                                + observed_witnesses
                                            }
                                        )
                                        missing = sorted(
                                            set(states)
                                            - {
                                                p["expected_status"]
                                                for p in observed_grid
                                            }
                                        )
                                        record.update(
                                            status="resolved_source_control",
                                            expected_grid=observed_grid,
                                            expected_witnesses=observed_witnesses,
                                            expected_statuses=states,
                                            missing_from_minute_grid=missing,
                                        )
                                        local[
                                            "source_grid_missing_witness_state"
                                        ] += bool(missing)
                                    except ValueError as error:
                                        record.update(
                                            status="unresolved_source_resolution",
                                            unresolved_reason=str(error),
                                        )
                                local[record["status"]] += 1
                                local["source_inverse_events"] += 1
                                row_count += 1
                                emit(record)
                key = f"{zone}/{direction}"
                cohorts[key] = dict(local)
                counts.update(local)
                print(
                    json.dumps(
                        {"cohort": key, "counts": dict(local), "rows_so_far": row_count}
                    ),
                    flush=True,
                )
        assert not any(
            k.split(".")[0] in {"fatebridge", "dateutil", "zoneinfo"}
            for k in sys.modules
        )
        emit(
            {
                "record_type": "footer",
                "counts": dict(counts),
                "cohorts": cohorts,
                "row_count": row_count,
                "no_application_dateutil_zoneinfo_imported": True,
            }
        )
    partial.rename(output)
    output.with_suffix(".sha256").write_text(sha(output) + "\n")
    report = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": sha(protocol_path),
        "reference": str(output.relative_to(ROOT)),
        "reference_sha256": sha(output),
        "counts": dict(counts),
        "cohorts": cohorts,
        "clock_inventory": inventory,
        "rows": row_count,
        "no_application_dateutil_zoneinfo_imported": True,
        "source_boundary_policy": "Synthetic -r1898/2103 coverage sentinel changes excluded from natural gap events; labels outside compiled UTC range unresolved, no clock-law extrapolation.",
        "scope": "Four predeclared zones and both directions, initial forward-gap ends only. Preserve sourcegrid-alreadycovered cases; counts are software controls, not independent observations or accuracy scores. OldNYgeometry unchanged; source coverage is bounded by compiled data and archived computed Jie.",
        "new_application_calls": 0,
        "new_independent_observation_credit": 0,
        "continuous_completeness_certified": False,
        "physical_precision_certified": False,
        "full_goal_complete": False,
        "overall_score": None,
    }
    summary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    summary.with_suffix(".sha256").write_text(sha(summary) + "\n")
    print(
        json.dumps({"rows": row_count, "counts": dict(counts), "sha256": sha(output)}),
        flush=True,
    )


if __name__ == "__main__":
    main()

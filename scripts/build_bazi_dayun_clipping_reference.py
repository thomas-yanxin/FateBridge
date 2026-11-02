"""Freeze decade-clipping controls using only Gregorian integers and TZif."""

import argparse
import calendar
import gzip
import hashlib
import json
import runpy
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-dayun-state-clipping-v1"
SECOND = 1_000_000
MONTH = 21600 * SECOND
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def micros(delta):
    return (delta.days * 86400 + delta.seconds) * SECOND + delta.microseconds


def instant(value):
    return EPOCH + timedelta(microseconds=value)


def add_years(wall, years):
    value = instant(wall)
    year = value.year + years
    return micros(
        value.replace(
            year=year, day=min(value.day, calendar.monthrange(year, value.month)[1])
        )
        - EPOCH
    )


class UTCClock:
    def offset_at(self, at):
        return 0

    def resolve(self, wall, birth):
        if wall < birth:
            raise ValueError("initial_before_birth")
        return wall

    def cuts(self, low, high):
        values = [low]
        midnight = (low // (86400 * SECOND) + 1) * 86400 * SECOND
        while midnight < high:
            values.append(midnight)
            midnight += 86400 * SECOND
        values.append(high)
        return zip(values, values[1:])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    pp = STUDY / "protocol.json"
    assert sha(pp) == pp.with_suffix(".sha256").read_text().strip()
    plan = json.loads(pp.read_text())
    assert all(sha(ROOT / n) == h for n, h in plan["files"].items())
    binding = json.loads((STUDY / "collector-binding.json").read_text())
    assert binding["collector_sha256"] == sha(Path(__file__))
    source = runpy.run_path(
        str(ROOT / "tests/fixtures/bazi_dayun_future_clocks_v2/collector-first.py.txt")
    )
    parse = runpy.run_path(str(ROOT / "scripts/build_bazi_birth_fold_reference.py"))
    source["SourceClock"].__init__.__globals__["ROOT"] = ROOT
    all_probes = json.loads(
        (ROOT / "tests/fixtures/bazi_boundary_decisions_v1/probes.json").read_text()
    )
    roots = sorted(
        [
            r
            for r in all_probes["rows"]
            if r["side"] == "next_minute" and r["name"] in source["JIE"]
        ],
        key=lambda r: r["reference_civil_under_frozen_policy"],
    )
    counts, rows = Counter(), []
    calendar_rows = []
    for year in range(1896, 2296):
        for index in range(13):
            if calendar.isleap(year):
                original = micros(datetime(year, 2, 29, tzinfo=timezone.utc) - EPOCH)
                projected = instant(add_years(original, index * 10))
                calendar_rows.append(
                    dict(
                        year=year,
                        boundary_index=index,
                        projected_date=projected.date().isoformat(),
                        clipped=projected.day == 28,
                    )
                )
    for zone in plan["source_plan"]["zones"]:
        clock = (
            UTCClock()
            if zone == "UTC"
            else source["SourceClock"](zone, parse["parse_tzif"])
        )
        for direction in plan["source_plan"]["directions"]:
            slope = 121 if direction == "reverse" else -119
            for previous, following in zip(roots, roots[1:]):
                if (
                    previous["year"]
                    not in plan["source_plan"]["root_interval_start_years"]
                ):
                    continue
                first = micros(
                    datetime.fromisoformat(
                        previous["reference_civil_under_frozen_policy"]
                    )
                    - EPOCH
                )
                end = micros(
                    datetime.fromisoformat(
                        following["reference_civil_under_frozen_policy"]
                    )
                    - EPOCH
                )
                reference = previous if direction == "reverse" else following
                root = first if direction == "reverse" else end
                cuts = {first, end}
                for k in range(abs(end - first) // MONTH + 2):
                    carry = root + (1 if direction == "reverse" else -1) * k * MONTH
                    for value in (carry, carry + 1):
                        if first < value < end:
                            cuts.add(value)
                for left, right in zip(sorted(cuts), sorted(cuts)[1:]):
                    for a, b in clock.cuts(left, right):
                        offset = clock.offset_at(a)
                        wall_a = source["initial_wall"](a, root, offset)
                        wall_b = source["initial_wall"](b - 1, root, offset)
                        assert wall_b - wall_a == slope * (b - 1 - a)
                        low, high = sorted((wall_a, wall_b))
                        for year in range(instant(low).year, instant(high).year + 1):
                            if not calendar.isleap(year):
                                continue
                            target = micros(
                                datetime(year, 2, 29, tzinfo=timezone.utc) - EPOCH
                            )
                            if not low <= target <= high:
                                continue
                            floor, remainder = divmod(target - wall_a, slope)
                            upper = a + floor + bool(remainder)
                            center = upper // SECOND * SECOND - 31 * SECOND
                            grid = [center - 60 * SECOND, center, center + 60 * SECOND]
                            witnesses = []
                            for displacement in (-1500000, -500000, 500000):
                                q, rem = divmod(target + displacement - wall_a, slope)
                                witnesses.append(a + q + bool(rem))
                            probes = [(x, True) for x in grid + witnesses] + [
                                (a + floor, False),
                                (upper, False),
                            ]
                            birth = instant(center + offset * SECOND)
                            bazi_year = previous["reference_state_under_frozen_policy"][
                                "bazi_year"
                            ]
                            is_yang = (bazi_year - 4) % 2 == 0
                            gender = (
                                ("男" if is_yang else "女")
                                if direction == "forward"
                                else ("女" if is_yang else "男")
                            )
                            for index in range(13):
                                identifier = f"{zone}/{direction}/{previous['year']}-{previous['name']}/cell{a}/leap{year}/boundary{index}"
                                row = dict(
                                    id=identifier,
                                    zone=zone,
                                    direction=direction,
                                    reference_jie=reference,
                                    initial_leap_year=year,
                                    boundary_index=index,
                                    clipped=not calendar.isleap(year + index * 10),
                                    inverse_floor_utc=instant(a + floor).isoformat(),
                                    inverse_ceil_utc=instant(upper).isoformat(),
                                    cell_utc=[
                                        instant(a).isoformat(),
                                        instant(b).isoformat(),
                                    ],
                                    input=dict(
                                        birth_year=birth.year,
                                        birth_month=birth.month,
                                        birth_day=birth.day,
                                        birth_hour=birth.hour,
                                        birth_minute=birth.minute,
                                        birth_second=birth.second,
                                        birth_timezone=zone,
                                        birth_utc_offset=parse["offset_text"](offset),
                                        gender=gender,
                                        use_true_solar_time=False,
                                    ),
                                    uncertainty_minutes=1,
                                )
                                try:
                                    if not 1900 <= birth.year <= 2100:
                                        raise ValueError("nominal_input_outside_domain")
                                    if (
                                        not a <= min(x for x, _ in probes)
                                        or not max(x for x, _ in probes) < b
                                    ):
                                        raise ValueError(
                                            "witness_or_window_leaves_declared_affine_cell"
                                        )
                                    target_year = year + index * 10
                                    following_day = (
                                        datetime(target_year, 3, 1, tzinfo=timezone.utc)
                                        if row["clipped"]
                                        else datetime(
                                            target_year, 2, 29, tzinfo=timezone.utc
                                        )
                                    )
                                    analysis_wall = (
                                        micros(following_day - EPOCH) - SECOND
                                    )
                                    analysis = clock.resolve(analysis_wall, center)
                                    observations = []
                                    for at, safe in probes:
                                        wall = source["initial_wall"](at, root, offset)
                                        boundaries = [
                                            clock.resolve(add_years(wall, k * 10), at)
                                            for k in range(13)
                                        ]
                                        state = (
                                            ("before_dayun", None)
                                            if analysis < boundaries[0]
                                            else next(
                                                (
                                                    ("active", k + 1)
                                                    for k in range(12)
                                                    if boundaries[k]
                                                    <= analysis
                                                    < boundaries[k + 1]
                                                ),
                                                ("beyond_calculation", None),
                                            )
                                        )
                                        observations.append(
                                            dict(
                                                birth_utc=instant(at).isoformat(),
                                                safe=safe,
                                                state=list(state),
                                                boundary_at=instant(
                                                    boundaries[index]
                                                ).isoformat(),
                                            )
                                        )
                                    grid_states = sorted(
                                        {tuple(x["state"]) for x in observations[:3]}
                                    )
                                    witness_states = sorted(
                                        {
                                            tuple(x["state"])
                                            for x in observations
                                            if x["safe"]
                                        }
                                    )
                                    row.update(
                                        status="resolved_source_control",
                                        analysis_at=instant(analysis).isoformat(),
                                        expected_probes=observations,
                                        source_grid_states=grid_states,
                                        source_witness_states=witness_states,
                                        missing_from_minute_grid=sorted(
                                            set(witness_states) - set(grid_states)
                                        ),
                                    )
                                except (ValueError, OverflowError) as exc:
                                    row.update(
                                        status="unresolved_source_interaction",
                                        unresolved_reason=str(exc),
                                    )
                                rows.append(row)
                                counts[row["status"]] += 1
    assert len({r["id"] for r in rows}) == len(rows)
    assert not any(
        k.split(".")[0] in {"fatebridge", "dateutil", "zoneinfo"} for k in sys.modules
    )
    assert all(sha(ROOT / n) == h for n, h in plan["files"].items())
    data = dict(
        protocol_sha256=sha(pp),
        collector_sha256=sha(Path(__file__)),
        rows=rows,
        counts=dict(counts),
        calendar_cycle_rows=calendar_rows,
        no_application_dateutil_zoneinfo_imported=True,
        scope="Finite safe witness coverage and exact calendar-year controls; not full continuous-state or physical precision certification.",
        new_independent_observation_credit=0,
        new_model_executions=0,
        full_goal_complete=False,
    )
    args.output.write_bytes(
        gzip.compress(
            (
                json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n"
            ).encode(),
            mtime=0,
        )
    )
    args.output.with_suffix(".sha256").write_text(sha(args.output) + "\n")
    print(
        json.dumps(
            dict(
                rows=len(rows),
                counts=counts,
                calendar_rows=len(calendar_rows),
                source_missing_states=sum(
                    bool(r.get("missing_from_minute_grid")) for r in rows
                ),
            )
        )
    )


if __name__ == "__main__":
    main()

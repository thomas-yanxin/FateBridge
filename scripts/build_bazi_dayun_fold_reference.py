"""Independent coupled fold-end inverses on the full predeclared clock cohort."""

import argparse
import bisect
import calendar
import gzip
import hashlib
import json
import runpy
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-dayun-state-clipping-v1"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    plan = json.loads((STUDY / "fold-protocol.json").read_text())
    assert (
        sha(STUDY / "fold-protocol.json")
        == (STUDY / "fold-protocol.sha256").read_text().strip()
    )
    assert all(sha(ROOT / n) == h for n, h in plan["source_dependencies"].items())
    binding = json.loads((STUDY / "fold-collector-binding.json").read_text())
    assert binding["runner_sha256"] == sha(Path(__file__))
    parent = json.loads((STUDY / "protocol.json").read_text())
    helper = runpy.run_path(
        str(ROOT / "scripts/build_bazi_dayun_clipping_reference.py")
    )
    source = runpy.run_path(
        str(ROOT / "tests/fixtures/bazi_dayun_future_clocks_v2/collector-first.py.txt")
    )
    parse = runpy.run_path(str(ROOT / "scripts/build_bazi_birth_fold_reference.py"))
    source["SourceClock"].__init__.__globals__["ROOT"] = ROOT
    micros, instant, epoch, second, month = (
        helper[k] for k in ("micros", "instant", "EPOCH", "SECOND", "MONTH")
    )
    data = json.loads(
        (ROOT / "tests/fixtures/bazi_boundary_decisions_v1/probes.json").read_text()
    )
    roots = sorted(
        [
            r
            for r in data["rows"]
            if r["side"] == "next_minute" and r["name"] in source["JIE"]
        ],
        key=lambda r: r["reference_civil_under_frozen_policy"],
    )
    rows, counts = [], Counter()
    for zone in parent["source_plan"]["zones"]:
        if zone == "UTC":
            continue
        clock = source["SourceClock"](zone, parse["parse_tzif"])
        targets = []
        for i in range(1, len(clock.times) - 1):
            old, new = (
                clock.kinds[clock.indices[i - 1]][0],
                clock.kinds[clock.indices[i]][0],
            )
            if new >= old:
                continue
            transition = clock.times[i] * second
            wall = instant(transition + old * second)
            for index in range(13):
                year = wall.year - index * 10
                if not 1 <= year <= 9999:
                    continue
                try:
                    candidates = [wall.replace(year=year)]
                except ValueError:
                    continue
                if (
                    wall.month == 2
                    and wall.day == 28
                    and not calendar.isleap(wall.year)
                    and calendar.isleap(year)
                ):
                    candidates.append(wall.replace(year=year, day=29))
                for candidate in candidates:
                    targets.append(
                        (micros(candidate - epoch), index, transition, old, new)
                    )
        targets.sort()
        keys = [v[0] for v in targets]
        for direction in parent["source_plan"]["directions"]:
            slope = 121 if direction == "reverse" else -119
            for previous, following in zip(roots, roots[1:]):
                if (
                    previous["year"]
                    not in parent["source_plan"]["root_interval_start_years"]
                ):
                    continue
                first = micros(
                    datetime.fromisoformat(
                        previous["reference_civil_under_frozen_policy"]
                    )
                    - epoch
                )
                end = micros(
                    datetime.fromisoformat(
                        following["reference_civil_under_frozen_policy"]
                    )
                    - epoch
                )
                root = first if direction == "reverse" else end
                cuts = {first, end}
                for k in range(abs(end - first) // month + 2):
                    carry = root + (1 if direction == "reverse" else -1) * k * month
                    cuts.update(v for v in (carry, carry + 1) if first < v < end)
                for left, right in zip(sorted(cuts), sorted(cuts)[1:]):
                    for a, b in clock.cuts(left, right):
                        offset = clock.offset_at(a)
                        wall_a, wall_b = (
                            source["initial_wall"](v, root, offset) for v in (a, b - 1)
                        )
                        assert wall_b - wall_a == slope * (b - 1 - a)
                        low, high = sorted((wall_a, wall_b))
                        for target, index, transition, old, new in targets[
                            bisect.bisect_left(keys, low) : bisect.bisect_right(
                                keys, high
                            )
                        ]:
                            q, rem = divmod(target - wall_a, slope)
                            upper = a + q + bool(rem)
                            center = upper // second * second - 31 * second
                            points = [
                                (center + v * second, True) for v in (-60, 0, 60)
                            ] + [
                                (upper - 100000, True),
                                (upper + 100000, True),
                                (a + q, False),
                                (upper, False),
                            ]
                            birth = instant(center + offset * second)
                            yang = (
                                previous["reference_state_under_frozen_policy"][
                                    "bazi_year"
                                ]
                                - 4
                            ) % 2 == 0
                            gender = (
                                ("男" if yang else "女")
                                if direction == "forward"
                                else ("女" if yang else "男")
                            )
                            row = dict(
                                id=f"{zone}/{direction}/{previous['year']}-{previous['name']}/cell{a}/fold{transition}/boundary{index}",
                                zone=zone,
                                direction=direction,
                                boundary_index=index,
                                clipped=False,
                                expected_event_kind="dayun_future_civil_fold_end",
                                inverse_floor_utc=instant(a + q).isoformat(),
                                inverse_ceil_utc=instant(upper).isoformat(),
                                gap_utc=instant(transition).isoformat(),
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
                                    not a <= min(v for v, _ in points)
                                    or not max(v for v, _ in points) < b
                                ):
                                    raise ValueError(
                                        "witness_or_window_leaves_declared_affine_cell"
                                    )
                                analysis = transition + (old - new) * second // 2
                                observations = []
                                for at, safe in points:
                                    wall_value = source["initial_wall"](
                                        at, root, offset
                                    )
                                    boundaries = [
                                        clock.resolve(
                                            helper["add_years"](wall_value, k * 10), at
                                        )
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
                                grid = sorted(
                                    {tuple(r["state"]) for r in observations[:3]}
                                )
                                states = sorted(
                                    {
                                        tuple(r["state"])
                                        for r in observations
                                        if r["safe"]
                                    }
                                )
                                row.update(
                                    status="resolved_source_control",
                                    analysis_at=instant(analysis).isoformat(),
                                    expected_probes=observations,
                                    source_grid_states=grid,
                                    source_witness_states=states,
                                    missing_from_minute_grid=sorted(
                                        set(states) - set(grid)
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
    assert all(sha(ROOT / n) == h for n, h in plan["source_dependencies"].items())
    result = dict(
        rows=rows,
        counts=dict(counts),
        protocol_sha256=sha(STUDY / "fold-protocol.json"),
        runner_sha256=sha(Path(__file__)),
        no_application_dateutil_zoneinfo_imports=True,
        full_goal_complete=False,
        new_independent_observation_credit=0,
        new_model_executions=0,
    )
    args.output.write_bytes(
        gzip.compress(
            (
                json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n"
            ).encode(),
            mtime=0,
        )
    )
    args.output.with_suffix(".sha256").write_text(sha(args.output) + "\n")
    print(json.dumps(dict(rows=len(rows), counts=counts)))


if __name__ == "__main__":
    main()

"""Factor every saved future-clock row without changing its original gate."""

import argparse
import gzip
import hashlib
import json
import runpy
import sys
from collections import Counter
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-root-clock-factorization-v1"
NAMES = ("original", "legacy", "exact_scalar", "split_skyfield", "actual")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def controls(path):
    with gzip.open(path, "rt") as stream:
        header = json.loads(next(stream))
        assert header["record_type"] == "header"
        count = 0
        for line in stream:
            row = json.loads(line)
            if row["record_type"] == "footer":
                assert count == row["row_count"]
                assert not stream.read()
                return
            assert row["record_type"] == "control"
            count += 1
            yield row
        raise AssertionError("Source footer missing")


def point(parts):
    return sum(map(Fraction, parts), Fraction())


def transition_counts(masks):
    """Keep both directions and nonmonotone cancellations, never add fixes."""
    return {
        left
        + "_to_"
        + right: {
            "outside_to_inside": sum(
                n for mask, n in masks.items() if mask[i] == "1" and mask[i + 1] == "0"
            ),
            "inside_to_outside": sum(
                n for mask, n in masks.items() if mask[i] == "0" and mask[i + 1] == "1"
            ),
        }
        for i, (left, right) in enumerate(zip(NAMES, NAMES[1:]))
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output = args.output.resolve()
    records = args.output.with_suffix(".records.jsonl.gz")
    partial = records.with_suffix(".partial")
    assert not args.output.exists() and not records.exists() and not partial.exists()
    protocol_path = STUDY / "protocol.json"
    plan = json.loads(protocol_path.read_text())
    binding = json.loads((STUDY / "factorization-binding.json").read_text())
    assert binding["runner_sha256"] == sha(Path(__file__))
    assert binding["protocol_sha256"] == sha(protocol_path)
    assert all(sha(ROOT / p) == h for p, h in plan["files"].items())
    legs_path = STUDY / "root-clock-legs-first.json.gz"
    assert sha(legs_path) == binding["root_clock_legs_sha256"]
    legs = json.loads(gzip.decompress(legs_path.read_bytes()))
    lookup = {(r["year"], r["name"]): r for r in legs["rows"]}
    assert len(lookup) == 4872
    clock_protocol_path = (
        ROOT / "tests/fixtures/bazi_dayun_future_clocks_v2/protocol.json"
    )
    assert (
        sha(clock_protocol_path)
        == clock_protocol_path.with_suffix(".sha256").read_text().strip()
    )
    clock_dependencies = json.loads(clock_protocol_path.read_text())["files"]
    assert all(sha(ROOT / p) == h for p, h in clock_dependencies.items())
    source = runpy.run_path(
        str(ROOT / "tests/fixtures/bazi_dayun_future_clocks_v2/collector-first.py.txt")
    )
    parse = runpy.run_path(str(ROOT / "scripts/build_bazi_birth_fold_reference.py"))[
        "parse_tzif"
    ]
    source["SourceClock"].__init__.__globals__["ROOT"] = ROOT
    micros, epoch = source["micros"], source["EPOCH"]
    clocks, counts, masks, per_era = {}, Counter(), Counter(), {}
    root_observations = {}
    audit_path = (
        ROOT / "docs/validation/bazi-dayun-future-clocks-split-pipeline-v1.json"
    )
    audit = json.loads(audit_path.read_text())
    with (
        gzip.open(ROOT / audit["records"], "rt") as saved,
        partial.open("xb") as raw,
        gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as out,
    ):
        for row, line in zip(
            controls(
                ROOT / "tests/fixtures/bazi_dayun_future_clocks_v2/reference.jsonl.gz"
            ),
            saved,
            strict=True,
        ):
            original = json.loads(line)
            assert row["id"] == original["id"]
            counts["all_rows"] += 1
            result = {"id": row["id"], "source_status": row["status"]}
            if not original["adjudicated"]:
                counts["unresolved_retained"] += 1
                result["unresolved_reason"] = original["unresolved_reason"]
            else:
                counts["known_rows"] += 1
                root = row["source_jie"]
                key = root["year"], root["name"]
                leg = lookup[key]
                roots = {
                    "original": leg["original_frozen_civil"],
                    "legacy": leg["current_legacy_scalar_civil"],
                    "exact_scalar": leg["current_exact_scalar_point_civil"],
                    "split_skyfield": leg["independent_split_point_civil"],
                    "actual": original["timeline_probes"][0][
                        "actual_consumed_reference_at"
                    ],
                }
                roots = {
                    k: datetime.fromisoformat(v).astimezone(timezone.utc).isoformat()
                    for k, v in roots.items()
                }
                root_us = {
                    k: micros(datetime.fromisoformat(v) - epoch)
                    for k, v in roots.items()
                }
                assert root_us["original"] == micros(
                    datetime.fromisoformat(root["reference_civil_under_frozen_policy"])
                    - epoch
                )
                values = [
                    r
                    for r in original["actual_range"]["dayun_boundary_ranges"]
                    if r["period"] == 1
                ]
                assert len(values) == 1
                low = micros(
                    datetime.fromisoformat(values[0]["earliest_start_at"]) - epoch
                )
                high = micros(
                    datetime.fromisoformat(values[0]["latest_start_at"]) - epoch
                )
                zone = row["zone"]
                if zone not in clocks:
                    clocks[zone] = source["SourceClock"](zone, parse)
                clock = clocks[zone]
                outside = {name: [] for name in NAMES}
                for i, probe in enumerate(original["timeline_probes"]):
                    birth = micros(
                        datetime.fromisoformat(probe["reference"]["birth_utc"]) - epoch
                    )
                    expected = micros(
                        datetime.fromisoformat(probe["reference"]["manual_start_at"])
                        - epoch
                    )
                    actual = micros(
                        datetime.fromisoformat(probe["actual_start_at"]) - epoch
                    )
                    assert (
                        micros(
                            datetime.fromisoformat(
                                probe["actual_consumed_reference_at"]
                            )
                            - epoch
                        )
                        == root_us["actual"]
                    )
                    calculated = {}
                    for name in NAMES:
                        calculated[name] = clock.resolve(
                            source["initial_wall"](
                                birth, root_us[name], row["birth_cell_offset_seconds"]
                            ),
                            birth,
                        )
                    assert calculated["original"] == expected
                    assert calculated["actual"] == actual
                    counts["all_known_probes"] += 1
                    if probe["safe_distance_gate"]:
                        counts["safe_probes"] += 1
                        for name, value in calculated.items():
                            if not low <= value <= high:
                                outside[name].append(i)
                assert bool(outside["original"]) == bool(
                    original["safe_source_witnesses_outside_probe_envelope"]
                )
                mask = "".join("1" if outside[name] else "0" for name in NAMES)
                masks[mask] += 1
                era = (
                    "pre_1960"
                    if key[0] < 1960
                    else "1960_1971" if key[0] < 1972 else "1972_onward"
                )
                per_era.setdefault(era, Counter())[mask] += 1
                for name in NAMES:
                    counts[name + "_outside_rows"] += bool(outside[name])
                actual_tt = probe["actual_root_tt_parts"]
                assert actual_tt is not None
                observation = {
                    "year": key[0],
                    "name": key[1],
                    "civil_root_legs": roots,
                    "split_minus_scalar_tt_us": leg[
                        "split_minus_original_scalar_tt_microseconds"
                    ],
                    "actual_minus_split_skyfield_tt_us": float(
                        (point(actual_tt) - point(leg["independent_split_tt_parts"]))
                        * 86_400_000_000
                    ),
                }
                observation_key = key + (tuple(actual_tt), root_us["actual"])
                if observation_key in root_observations:
                    assert root_observations[observation_key] == observation
                else:
                    root_observations[observation_key] = observation
                result.update(
                    root_key=list(key), outside_probe_indices=outside, mask=mask
                )
            out.write(
                (
                    json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n"
                ).encode()
            )
            if counts["all_rows"] % 10000 == 0:
                print(json.dumps(dict(counts)), flush=True)
    assert counts["all_rows"] == audit["registered_rows"] == 116906
    assert counts["known_rows"] == 116124 and counts["unresolved_retained"] == 782
    assert counts["original_outside_rows"] == 54818
    assert counts["actual_outside_rows"] == 0
    assert all(sha(ROOT / p) == h for p, h in clock_dependencies.items())
    assert not any(
        k.split(".")[0] in {"fatebridge", "dateutil", "zoneinfo"} for k in sys.modules
    )
    assert all(sha(ROOT / p) == h for p, h in plan["files"].items())
    partial.rename(records)
    data = dict(
        counts=dict(counts),
        mask_order=NAMES,
        masks=dict(masks),
        transition_counts=transition_counts(masks),
        per_era_masks={k: dict(v) for k, v in per_era.items()},
        distinct_consumed_root_realizations=len(root_observations),
        distinct_root_keys=len({key[:2] for key in root_observations}),
        roots=list(root_observations.values()),
        source_clock_protocol_sha256=sha(clock_protocol_path),
        source_clock_dependencies_checked_before_and_after=clock_dependencies,
        protocol_sha256=sha(protocol_path),
        runner_sha256=sha(Path(__file__)),
        root_clock_legs_sha256=sha(legs_path),
        records=str(records.relative_to(ROOT)),
        records_sha256=sha(records),
        no_application_imports=True,
        original_strict_gate_passed=False,
        original_gate_superseded=False,
        production_changes=0,
        new_model_executions=0,
        independent_observation_credit=0,
        full_goal_complete=False,
        scope="Five counterfactual root/conversion legs on every saved control. Changing the root for diagnosis never changes the original source label, envelope or 54818 failures. Transitions are paired interventions with cancellations, not additive improvement credit or physical truth.",
    )
    args.output.write_bytes(
        gzip.compress(
            (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode(), mtime=0
        )
    )
    args.output.with_suffix(".sha256").write_text(sha(args.output) + "\n")
    print(
        json.dumps(
            {
                "counts": data["counts"],
                "masks": data["masks"],
                "transitions": data["transition_counts"],
            }
        )
    )


if __name__ == "__main__":
    main()

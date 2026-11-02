"""Independently factor labels for every saved full-cohort consumed TT root."""

import argparse
import gzip
import hashlib
import importlib.metadata
import json
import runpy
import sys
import tempfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-consumed-root-clock-reference-v1"
UNIX = datetime(1970, 1, 1, tzinfo=timezone.utc)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(
        gzip.decompress(path.read_bytes())
        if path.suffix == ".gz"
        else path.read_bytes()
    )


def write(name, value):
    path = STUDY / name
    assert not path.exists()
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
    path.write_bytes(gzip.compress(data, mtime=0) if path.suffix == ".gz" else data)
    path.with_suffix(".sha256").write_text(sha(path) + "\n")


def utc(text):
    moment = datetime.fromisoformat(text)
    assert moment.utcoffset() is not None
    return moment.astimezone(timezone.utc)


def micros(delta):
    return (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds


def point(value):
    return (
        sum(map(Fraction.from_float, value), Fraction())
        if isinstance(value, list)
        else Fraction.from_float(value)
    )


def collect(plan):
    original = {
        (r["year"], r["name"]): r
        for r in read(ROOT / plan["original_scalar_roots"])["rows"]
    }
    independent = {
        (r["year"], r["name"]): r
        for r in read(ROOT / plan["independent_split_roots"])["rows"]
    }
    assert len(original) == len(independent) == 4872
    roots, signature_ids, counts = [], {}, Counter()
    target = STUDY / "input-mapping-first.records.jsonl.gz"
    assert not target.exists()
    with (
        gzip.open(ROOT / plan["source_cohort"], "rt") as source,
        gzip.open(ROOT / plan["baseline_records"], "rt") as saved,
        target.open("xb") as raw,
        gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as out,
    ):
        header = json.loads(next(source))
        assert header["record_type"] == "header"
        for index, line in enumerate(saved):
            before, control = json.loads(line), json.loads(next(source))
            assert before["id"] == control["id"] and before["cohort_index"] == index
            assert before["source_status"] == control["status"]
            counts["all_original_rows"] += 1
            if not before["adjudicated"]:
                counts["unknown_rows_retained"] += 1
                item = dict(
                    cohort_index=index,
                    id=before["id"],
                    unknown_source=control,
                    unknown_saved=before,
                )
            else:
                counts["known_rows"] += 1
                src = control["source_jie"]
                key = (src["year"], src["name"])
                assert src["reference_root_tt"] == original[key]["jd_tt"]
                ids = []
                for probe in before["timeline_probes"]:
                    counts["saved_point_observations"] += 1
                    actual_label = utc(
                        probe["actual_consumed_reference_at"]
                    ).isoformat()
                    signature = (
                        key,
                        tuple(probe["actual_root_tt_parts"]),
                        actual_label,
                        probe["actual_reference_provider"],
                    )
                    if signature not in signature_ids:
                        rid = len(roots)
                        signature_ids[signature] = rid
                        roots.append(
                            dict(
                                realization_id=rid,
                                year=key[0],
                                name=key[1],
                                original_source=src,
                                original_scalar_tt=src["reference_root_tt"],
                                independent_split_root=independent[key],
                                actual_tt_parts=probe["actual_root_tt_parts"],
                                actual_jd_tt=probe["actual_root_jd_tt"],
                                actual_consumed_label_utc=actual_label,
                                actual_reference_provider=probe[
                                    "actual_reference_provider"
                                ],
                            )
                        )
                    ids.append(signature_ids[signature])
                counts["rows_with_multiple_consumed_realizations"] += len(set(ids)) != 1
                item = dict(
                    cohort_index=index, id=before["id"], point_realization_ids=ids
                )
            out.write(
                (
                    json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n"
                ).encode()
            )
        footer = json.loads(next(source))
        assert (
            footer["record_type"] == "footer"
            and footer["row_count"] == counts["all_original_rows"]
        )
        assert not source.read()
    assert counts["all_original_rows"] == 116906 and counts["known_rows"] == 116124
    assert (
        counts["unknown_rows_retained"] == 782
        and counts["saved_point_observations"] == 812868
    )
    write(
        "inputs-first.json.gz",
        dict(
            counts=dict(counts),
            roots=roots,
            distinct_realizations=len(roots),
            mapping=target.name,
            mapping_sha256=sha(target),
            production_changed=False,
            original_gates_superseded=False,
            new_model_executions=0,
            full_goal_complete=False,
        ),
    )
    print(json.dumps(dict(counts=dict(counts), distinct_realizations=len(roots))))


def reference(plan):
    # Freeze all reference answers before comparison with any delivered label.
    import swisseph as swe

    data = read(STUDY / "inputs-first.json.gz")
    helper = runpy.run_path(str(ROOT / plan["atomic_helper"]))
    segments = helper["utc_segments"]((ROOT / plan["raw_sofa"]).read_text())
    atomic_invert = helper["invert"]
    first_tt = Fraction(4881175, 2) + Fraction(segments[0]["start"], 86400)
    first_tt += (
        Fraction(4023, 125)
        + segments[0]["offset"]
        + (40587 + Fraction(segments[0]["start"], 86400) - segments[0]["reference"])
        * segments[0]["rate"]
    ) / 86400
    calls, rows, counts = 0, [], Counter()
    with tempfile.TemporaryDirectory(prefix="bazi-clock-reference-empty-") as empty:
        swe.set_ephe_path(empty)
        tid_acc = swe.get_tid_acc()
        with localcontext() as context:
            context.prec = 90
            for root in data["roots"]:
                points = dict(
                    original_scalar=point(root["original_scalar_tt"]),
                    independent_split=point(root["independent_split_root"]["tt_parts"]),
                    actual_consumed_split=point(root["actual_tt_parts"]),
                )
                answers = {}
                for name, value in points.items():
                    if value >= first_tt:
                        label = atomic_invert(value, segments)
                        method = "SOFA_raw_table_rational_affine_or_constant"
                        extra = dict(
                            status=(
                                "conditional_atomic_point"
                                if label
                                else "unrepresentable_or_ambiguous_atomic_point"
                            )
                        )
                    else:
                        tt = Decimal(value.numerator) / Decimal(value.denominator)
                        low, high = tt - 1, tt + 1
                        for _ in range(120):
                            mid = (low + high) / 2
                            modeled = mid + Decimal.from_float(
                                swe.deltat_ex(float(mid), -1)
                            )
                            calls += 1
                            if modeled < tt:
                                low = mid
                            else:
                                high = mid
                        at = (low + high) / 2
                        rounding = int(
                            (
                                (at - Decimal("2440587.5")) * Decimal(86400) * 1000000
                            ).to_integral_value(rounding=ROUND_HALF_EVEN)
                        )
                        label = (UNIX + timedelta(microseconds=rounding)).isoformat()
                        method = "shared_Swiss_DeltaT_minus1_Decimal90_bisection120"
                        extra = dict(
                            status="preUTC_conventional_label_not_historical_truth",
                            bracket_days=str(high - low),
                        )
                    counts[method] += 1
                    answers[name] = dict(
                        label_utc=label,
                        method=method,
                        exact_tt_days=dict(
                            numerator=value.numerator, denominator=value.denominator
                        ),
                        **extra,
                    )
                rows.append(
                    dict(
                        realization_id=root["realization_id"],
                        year=root["year"],
                        name=root["name"],
                        answers=answers,
                    )
                )
    assert not any(
        n == "fatebridge" or n.startswith("fatebridge.") for n in sys.modules
    )
    write(
        "independent-reference-first.json.gz",
        dict(
            rows=rows,
            counts=dict(counts),
            point_count=sum(counts.values()),
            inputs_sha256=sha(STUDY / "inputs-first.json.gz"),
            runner_sha256=sha(__file__),
            versions=dict(
                python=sys.version, pyswisseph=importlib.metadata.version("pyswisseph")
            ),
            configured_tidal_acceleration=tid_acc,
            native_deltat_calls=calls,
            no_application_imports=True,
            historical_physical_UTC_certified=False,
            future_offsets_physically_certified=False,
            original_gates_superseded=False,
            new_independent_observation_credit=0,
            new_model_executions=0,
            full_goal_complete=False,
        ),
    )
    print(
        json.dumps(
            dict(points=sum(counts.values()), counts=dict(counts), deltat_calls=calls)
        )
    )


def assess():
    inputs, reference = read(STUDY / "inputs-first.json.gz"), read(
        STUDY / "independent-reference-first.json.gz"
    )
    assert reference["inputs_sha256"] == sha(STUDY / "inputs-first.json.gz")
    rows, counts, by_era, maxima = [], Counter(), {}, Counter()
    for root, answer in zip(inputs["roots"], reference["rows"], strict=True):
        assert root["realization_id"] == answer["realization_id"]
        a = answer["answers"]
        era = (
            "pre1960"
            if root["year"] < 1960
            else "1960_1971" if root["year"] < 1972 else "post1972"
        )
        era_counts = by_era.setdefault(era, Counter())
        labels = dict(
            original_delivered=utc(
                root["original_source"]["reference_civil_under_frozen_policy"]
            ),
            actual_delivered=utc(root["actual_consumed_label_utc"]),
        )
        for name, row in a.items():
            assert row["label_utc"] is not None, (root["realization_id"], name, row)
            labels[name] = utc(row["label_utc"])
        legs = dict(
            original_clock_label=micros(
                labels["original_scalar"] - labels["original_delivered"]
            ),
            scalar_to_split_same_skyfield=micros(
                labels["independent_split"] - labels["original_scalar"]
            ),
            independent_to_actual_model=micros(
                labels["actual_consumed_split"] - labels["independent_split"]
            ),
            actual_point_clock=micros(
                labels["actual_delivered"] - labels["actual_consumed_split"]
            ),
        )
        total = micros(labels["actual_delivered"] - labels["original_delivered"])
        assert sum(legs.values()) == total
        counts["all_realizations"] += 1
        era_counts["all_realizations"] += 1
        for name, value in legs.items():
            counts[name + "_nonzero"] += value != 0
            era_counts[name + "_nonzero"] += value != 0
            maxima[name] = max(maxima[name], abs(value))
        rows.append(
            dict(
                root=root,
                independent_answer=answer,
                label_legs_microseconds=legs,
                total_delivered_label_difference_microseconds=total,
                telescoping_residual_microseconds=0,
            )
        )
    write(
        "assessment-first.json.gz",
        dict(
            rows=rows,
            counts=dict(counts),
            per_era={k: dict(v) for k, v in by_era.items()},
            maximum_absolute_label_leg_microseconds=dict(maxima),
            inputs_sha256=sha(STUDY / "inputs-first.json.gz"),
            independent_reference_sha256=sha(
                STUDY / "independent-reference-first.json.gz"
            ),
            actual_point_clock_convention_passed=counts["actual_point_clock_nonzero"]
            == 0,
            root_model_physical_correctness_adjudicated=False,
            original_gates_superseded=False,
            original116906_strict_gate_passed=False,
            production_changed=False,
            new_model_executions=0,
            full_goal_complete=False,
            overall_score=None,
        ),
    )
    print(
        json.dumps(
            dict(
                counts=dict(counts),
                per_era={k: dict(v) for k, v in by_era.items()},
                maxima=dict(maxima),
            )
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("collect", "reference", "assess"))
    args = parser.parse_args()
    path = STUDY / "protocol.json"
    assert sha(path) == path.with_suffix(".sha256").read_text().strip()
    plan = read(path)
    for name, digest in plan["files"].items():
        assert sha(ROOT / name) == digest
    binding = read(STUDY / "implementation-binding-first.json")
    assert sha(__file__) == binding["runner_sha256"]
    if args.mode == "collect":
        collect(plan)
    elif args.mode == "reference":
        reference(plan)
    else:
        assess()


if __name__ == "__main__":
    main()

"""A partial saved-record diagnosis must not replace the original full gate."""

import gzip
import hashlib
import json
import zlib
from collections import Counter
from datetime import datetime
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-boundary-replay-prefix-diagnostic-v1"


def bound(name):
    path = STUDY / name
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == path.with_suffix(".sha256").read_text().strip()
    )
    return json.loads(path.read_text())


SNAPSHOT = bound("snapshot-first.json")
DIAGNOSTIC = bound("diagnostic-first.json")
ROOT_LABELS = bound("root-label-first.json")
with gzip.open(STUDY / "diagnostic-first.records.jsonl.gz", "rt") as stream:
    RECORDS = list(map(json.loads, stream))


def micros(delta):
    return (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds


def test_every_complete_prefix_row_is_retained_and_unterminated_bytes_are_not_graded():
    decoded = {}
    for item in SNAPSHOT["snapshots"]:
        data = (STUDY / item["file"]).read_bytes()
        assert len(data) == item["bytes"]
        assert hashlib.sha256(data).hexdigest() == item["sha256"]
        decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
        complete, tail = decoder.decompress(data).rsplit(b"\n", 1)
        receipt = next(
            r for r in DIAGNOSTIC["decode_receipts"] if r["shard"] == item["shard"]
        )
        assert receipt["unterminated_inflated_bytes"] == len(tail)
        assert (
            receipt["unterminated_inflated_sha256"] == hashlib.sha256(tail).hexdigest()
        )
        rows = list(map(json.loads, complete.splitlines()))
        assert receipt["complete_json_rows"] == len(rows)
        for row in rows:
            assert row["cohort_index"] % 6 == item["shard"]
            assert row["id"] not in decoded
            decoded[row["id"]] = row["cohort_index"]
    assert decoded == {r["paired"]["id"]: r["paired"]["cohort_index"] for r in RECORDS}
    assert len(decoded) == 4436


def test_unknowns_point_objects_and_original_failed_memberships_are_not_regraded():
    known = [r["paired"] for r in RECORDS if r["paired"]["adjudicated"]]
    unknown = [r["paired"] for r in RECORDS if not r["paired"]["adjudicated"]]
    assert len(known) == 4422 and len(unknown) == 14
    assert all(not r["paired"]["preservation_failures"] for r in RECORDS)
    assert all(r["unknown_record_exact"] for r in unknown)
    assert all(r["point_probes_exact"] for r in known)
    assert Counter(r["strict_transition"] for r in known) == {
        "retained": 1536,
        "passing": 2886,
    }
    assert sum(r["strict_before_failed"] for r in known) == 1536
    assert sum(r["strict_after_failed"] for r in known) == 1536


def test_each_saved_strict_miss_separates_actual_point_from_reference_point():
    points = [p for row in RECORDS for p in row.get("outside_points", [])]
    assert len(points) == 1536
    for point in points:
        assert point["category"] == "only_reference_outside_actual_point_inside"
        obs = point["observation"]
        low, high = map(datetime.fromisoformat, (point["low_utc"], point["high_utc"]))
        actual = datetime.fromisoformat(obs["actual_start_at"])
        reference = datetime.fromisoformat(obs["reference"]["manual_start_at"])
        assert low <= actual <= high
        assert not low <= reference <= high
        assert obs["safe_distance_gate"] is True
    excursions = [p["reference_excursion_microseconds"] for p in points]
    assert min(excursions) == 120 and max(excursions) == 5520


def test_every_outside_start_shift_is_exactly_the_saved_root_shift_times120():
    roots = {r["reference"]["id"]: r for r in ROOT_LABELS["roots"]}
    assert len(roots) == 487
    comparisons = []
    for row in ROOT_LABELS["records"]:
        for item in row["outside_points"]:
            root = roots[row["source_jie"]["id"]]
            delta = micros(
                datetime.fromisoformat(root["actual_consumed_reference_at"])
                - datetime.fromisoformat(
                    row["source_jie"]["reference_civil_under_frozen_policy"]
                )
            )
            point = item["original_outside_point"]["observation"]
            actual_delta = micros(
                datetime.fromisoformat(point["actual_start_at"])
                - datetime.fromisoformat(point["reference"]["manual_start_at"])
            )
            assert delta == item["root_label_shift_microseconds"]
            assert actual_delta == item["actual_start_shift_microseconds"]
            assert abs(actual_delta) == abs(delta) * 120
            assert item["residual_microseconds"] == 0
            comparisons.append(item)
    assert len(comparisons) == 1536
    for root in roots.values():
        exact = (
            (
                sum(map(Fraction.from_float, root["actual_tt_parts"]))
                - Fraction.from_float(root["reference"]["reference_root_tt"])
            )
            * 86400
            * 1000000
        )
        stored = root["exact_split_tt_minus_reference_scalar_tt_microseconds"]
        assert exact == Fraction(stored["numerator"], stored["denominator"])


def test_this_prefix_is_never_claimed_as_whole_cohort_or_oracle_adjudication():
    assert DIAGNOSTIC["original_global_denominator"] == 116906
    assert ROOT_LABELS["original_global_denominator"] == 116906
    assert ROOT_LABELS["physical_or_oracle_correction_determined"] is False
    for result in (DIAGNOSTIC, ROOT_LABELS):
        assert result["whole_candidate_cohort_acceptance"] == "not_completed"
        assert result["original_gates_superseded"] is False
        assert result["full_goal_complete"] is False
        assert result["production_changed"] is False
        assert result["calculation_calls"] == result["new_model_executions"] == 0

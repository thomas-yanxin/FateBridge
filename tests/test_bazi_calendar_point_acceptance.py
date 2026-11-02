"""A precise-input pass must never replace the retained scalar/default failures."""

import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_bound(relative):
    path = ROOT / relative
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == path.with_suffix(".sha256").read_text().strip()
    )
    return json.loads(
        gzip.decompress(path.read_bytes())
        if path.suffix == ".gz"
        else path.read_bytes()
    )


def test_calendar_point_and_legacy_default_keep_the_same6391_inputs_and_distinct_gates():
    point = read_bound("docs/validation/bazi-calendar-point-utc-first-v1.json.gz")
    legacy = read_bound("docs/validation/bazi-legacy-float-utc-v34-retained-v1.json.gz")
    ledger = read_bound("docs/validation/bazi-tt-scalar-conflicts-retained-v1.json")
    oracle = read_bound("tests/fixtures/bazi_tt_utc_exact_v1/oracle.json.gz")
    assert point["row_count"] == legacy["row_count"] == len(oracle["rows"]) == 6391
    for actual in (point, legacy):
        assert [
            {k: r[k] for k in expected}
            for r, expected in zip(actual["rows"], oracle["rows"], strict=True)
        ] == oracle["rows"]
        assert actual["counts"]["unadjudicated_rows_retained"] == 2218
        assert not actual["source_drift"]
        assert not actual["historical_truth_certified"]
        assert not actual["future_offsets_physically_certified"]
        assert not actual["full_goal_complete"]
    assert point["counts"]["normal_exact_microsecond_matches"] == 3930
    assert point["counts"]["correct_leap_label_rejections"] == 243
    assert point["maximum_absolute_microsecond_error"] == 0
    assert point["registered_exact_atomic_conversion_gate_passed"]
    assert point["legacy_float_default_gate_superseded"] is False
    failures = [
        r["id"]
        for r in legacy["rows"]
        if (
            r["status"] == "normal"
            and (r.get("error_type") or r.get("difference_microseconds") != 0)
        )
        or (
            r["status"] == "unrepresentable_utc_label"
            and not r.get("expected_leap_label_rejection")
        )
    ]
    assert sorted(failures) == sorted(r["id"] for r in ledger["rows"])
    assert len(failures) == 41
    assert not legacy["registered_exact_atomic_conversion_gate_passed"]


def test_original26_cases_and_all234_unknowns_remain_in_the_adopted_rule_delta():
    delta = read_bound("docs/validation/bazi-complete-bureau-adoption-delta-v1.json")
    original = read_bound("docs/validation/bazi-all26-conditions-review-v1.json")
    assert [r["pillars"] for r in delta["rows"]] == [
        r["pillars"] for r in original["rows"]
    ]
    for current, previous in zip(delta["rows"], original["rows"], strict=True):
        assert current["original_disagreements"] == previous["original_disagreements"]
        assert current["literal_source_records"] == previous["literal_source_records"]
        assert current["source_labels_changed"] is False
    assert sum(r["current_status"] == "unresolved" for r in delta["rows"]) == 23
    assert delta["resolved_known_inputs"] == 3 and delta["known_regressions"] == 0
    assert delta["unknown_records_retained"] == 234
    assert delta["original_reports_rewritten"] is False
    assert delta["full_classical_acceptance"] is False

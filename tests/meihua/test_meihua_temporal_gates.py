"""Independent integer-clock controls, not new weather observations or scores."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fatebridge.validation import meihua_weather_prospective as audit

FOLDER = Path(__file__).parents[1] / "fixtures/meihua_temporal_gates_v1"
MANIFEST_SHA256 = "065cb780830bd1922965ee2c714cbcf771450bbe8563b539302bb975c989b0cf"
raw = (FOLDER / "manifest.json").read_bytes()
assert hashlib.sha256(raw).hexdigest() == MANIFEST_SHA256
for name, digest in json.loads(raw)["files"].items():
    if str(name).endswith((".py", ".py.txt")):
        continue
    assert hashlib.sha256((FOLDER / name).read_bytes()).hexdigest() == digest
CASES = json.loads((FOLDER / "cases324.json").read_bytes())
UNKNOWN = json.loads((FOLDER / "unknown11.json").read_bytes())
LEDGER = Path(__file__).parents[1] / "fixtures/meihua-prospective-v1"
OPAQUE = b"\xffopaque synthetic bytes; no weather outcome content"


@pytest.mark.parametrize("case", CASES, ids=lambda r: r["id"])
def test_shared_study_timestamp_preserves_the_integer_constructed_instant(case):
    expected = datetime(*case["expected_utc_components"], tzinfo=timezone.utc)
    actual = audit.parse_study_timestamp(case["label"])
    assert actual == expected
    assert actual.utcoffset() == timedelta(0)
    assert audit._aware(case["label"]) == expected
    boundary = datetime(*case["boundary_utc_components"], tzinfo=timezone.utc)
    assert (actual >= boundary) == case["expected_at_or_after_boundary"]
    assert (actual > boundary) == case["expected_strictly_after_boundary"]


@pytest.mark.parametrize("case", CASES, ids=lambda r: r["id"])
def test_source_receipt_gate_rejects_retrieval_after_its_actual_audit_instant(case):
    boundary = datetime(*case["boundary_utc_components"], tzinfo=timezone.utc)
    receipt = {
        "source_url": audit.SOURCE_URL,
        "retrieved_at": case["label"],
        "body_sha256": hashlib.sha256(OPAQUE).hexdigest(),
        "data_kind": "synthetic",
    }
    if case["relative_microseconds"] > 0:
        with pytest.raises(ValueError, match="retrieval time cannot follow"):
            audit._receipt(OPAQUE, receipt, boundary)
    else:
        value = audit._receipt(OPAQUE, receipt, boundary)
        assert value["retrieved_at"] == case["label"]
        assert value["body_hash_verified"]
        assert not value["origin_authenticated"]
        assert not value["retrieval_time_authenticated"]


@pytest.mark.parametrize("label", UNKNOWN)
def test_unknown_offset_invalid_or_unrepresentable_time_is_never_rounded(label):
    with pytest.raises(ValueError):
        audit.parse_study_timestamp(label)


@pytest.mark.parametrize(
    "label,delta",
    [
        ("2026-10-21T21:03:44.000001000Z", 1),
        ("2026-10-21T21:03:44.0000000Z", 0),
        ("2026-10-21T21:03:44+00:00:00.000001000", -1),
        ("2026-10-21T21:03:44-00:00:00.000001000", 1),
    ],
)
def test_extra_zero_digits_do_not_lose_a_nonzero_microsecond(label, delta):
    expected = datetime(2026, 10, 21, 21, 3, 44, tzinfo=timezone.utc) + timedelta(
        microseconds=delta
    )
    assert audit.parse_study_timestamp(label) == expected


ANALYSIS_CASES = [
    r
    for r in CASES
    if r["boundary"] == "single_analysis_after"
    and abs(r["offset_microseconds"]) == 500000
    and r["id"].endswith(":False:False")
]
assert len(ANALYSIS_CASES) == 6


@pytest.mark.parametrize("case", ANALYSIS_CASES, ids=lambda r: r["id"])
@pytest.mark.parametrize("kind", ["synthetic", "unverified_submission"])
def test_original_analysis_gate_precedes_any_outcome_parse(case, kind, monkeypatch):
    class ParseAttempt(Exception):
        pass

    def no_outcomes(*args, **kwargs):
        raise ParseAttempt("synthetic probe only; no outcome content was parsed")

    monkeypatch.setattr(
        audit, "_now_utc", lambda: datetime(2026, 10, 25, tzinfo=timezone.utc)
    )
    monkeypatch.setattr(audit.weather, "parse_hko_rainfall", no_outcomes)
    monkeypatch.setattr(audit.weather, "evaluate_weather_cohort", no_outcomes)
    receipt = {
        "source_url": audit.SOURCE_URL,
        "retrieved_at": "2027-11-01T00:00:00+08:00",
        "body_sha256": hashlib.sha256(OPAQUE).hexdigest(),
        "data_kind": kind,
    }
    args = {
        "as_of": audit.parse_study_timestamp(case["label"]),
        "observation_bytes": OPAQUE,
        "source_receipt": receipt,
    }
    if kind == "synthetic" and case["relative_microseconds"] >= 0:
        with pytest.raises(ParseAttempt):
            audit.audit_prospective_weather_study(
                LEDGER / "study", LEDGER / "attestation", **args
            )
    else:
        value = audit.audit_prospective_weather_study(
            LEDGER / "study", LEDGER / "attestation", **args
        )
        assert value["ledger"]["cohort_days"] == 365
        assert not value["analysis_gate"]["outcome_parsing_allowed"]
        assert (
            value["analysis_gate"]["declared_as_of_reached"]
            == case["expected_at_or_after_boundary"]
        )
        assert not value["analysis_gate"]["local_clock_reached"]
        assert value["ingested_outcome_rows"] == 0
        assert value["outcome_report"] is None
        assert (
            value["source_content_status"] == "opaque_bytes_hashed_content_not_parsed"
        )
        assert not value["real_world_predictive_efficacy_established"]

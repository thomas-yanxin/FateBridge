"""Keep the first oracle and independently expose rounded-label conflicts."""

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.astro.historical_utc import HistoricalUTCAdjustment
from fatebridge.core.astro.time_scales import datetime_from_tt
from fatebridge.core.astro.tt_epoch import TTInstant

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/data/bazi_historical_point_v1"


def test_all506_original_rows_and_first_seven_failures_are_retained() -> None:
    p = FIXTURE / "oracle.json.gz"
    assert (
        hashlib.sha256(p.read_bytes()).hexdigest()
        == p.with_suffix(".sha256").read_text().strip()
    )
    oracle = json.loads(gzip.decompress(p.read_bytes()))
    first = json.loads((FIXTURE / "first-diagnostic.json").read_text())
    assert oracle["row_count"] == len(oracle["rows"]) == len(first["rows"]) == 506
    assert (
        oracle["normal_rows"],
        oracle["unrepresentable_rows"],
        oracle["pre_utc_unadjudicated_rows"],
    ) == (412, 90, 4)
    assert len(first["failures"]) == 7


def test_original506_and_source_domain_qualification_are_kept_separate() -> None:
    oracle = json.loads(gzip.decompress((FIXTURE / "oracle.json.gz").read_bytes()))
    first = json.loads((FIXTURE / "first-diagnostic.json").read_text())
    primary = json.loads(
        (ROOT / "tests/fixtures/historical-utc-domain-reference-v1.json").read_text()
    )["old506"]
    normal = rejected = unknown = 0
    available_ids = set()
    for row, reference in zip(oracle["rows"], primary["rows"], strict=True):
        assert row["id"] == reference["id"]
        if reference["source_domain_class"] == "pre_utc_model_not_adjudicated":
            assert row["status"] == reference["source_domain_class"]
            unknown += 1
            continue
        else:
            pass
        point = TTInstant.from_parts(*row["tt_parts"])
        if reference["source_domain_class"] != "unique":
            with pytest.raises(HistoricalUTCAdjustment):
                datetime_from_tt(point)
            rejected += 1
            continue
        else:
            pass
        actual = datetime_from_tt(point).isoformat()
        assert actual == reference["expected_UTC"], row["id"]
        available_ids.add(row["id"])
        normal += 1
    assert (normal, rejected, unknown) == (426, 76, 4)
    assert {row["id"] for row in first["failures"]} <= available_ids

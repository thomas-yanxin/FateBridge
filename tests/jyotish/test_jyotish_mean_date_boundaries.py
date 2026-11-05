"""Frozen independent calendar references, not natal/observational precision."""

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from fatebridge.core.jyotish_kala import ahargana_lords, mean_date

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / "tests/fixtures/jyotish-mean-date-reference.json"
DATA = json.loads(REF.read_text())


def test_independent_ERFA_reference_seal_range_and_full_domain_are_retained():
    assert (
        hashlib.sha256(REF.read_bytes()).hexdigest()
        == "da4e09518176784e7fe48a9de4f2134940673ab99d2cf516b2b1c95ec090940c"
    )
    check = DATA["complete_supported_calendar_anchor_check"]
    assert check["days"] == date.max.toordinal() == 3652059
    assert check["all_midnights_exact"]
    assert check["first"] == "0001-01-01" and check["last"] == "9999-12-31"
    assert check["julian_midnight_at_ordinal1"] == "1721425.5"
    assert len(DATA["probes"]) == DATA["probe_count"] == 297
    assert len(DATA["protocol"]["midnight_ordinals"]) == 11
    assert len(DATA["protocol"]["longitudes"]) == 9
    assert DATA["real_events"] == 0 and DATA["independent_model_blind_reviews"] == 0


@pytest.mark.parametrize(
    "row",
    DATA["probes"],
    ids=lambda r: f"{r['target_midnight_ordinal']}:{r['longitude']}:{r['position']}",
)
def test_every_frozen_binary_midnight_probe_matches_reference_without_tolerance(row):
    assert row["jd_ut1"].hex() == row["jd_hex"]
    assert row["longitude"].hex() == row["longitude_hex"]
    value = mean_date(row["jd_ut1"], row["longitude"])
    assert (value.isoformat() if value else None) == row["expected_date"]


def test_two_preexisting_primary_ahargana_examples_are_unmodified():
    for stamp, count, year_lord, month_lord in [
        ("1918-10-16", 714404130045, "Saturn", "Mercury"),
        ("1984-06-01", 714404154015, "Jupiter", "Venus"),
    ]:
        result = ahargana_lords(date.fromisoformat(stamp))
        assert (result["ahargana"], result["year_lord"], result["month_lord"]) == (
            count,
            year_lord,
            month_lord,
        )

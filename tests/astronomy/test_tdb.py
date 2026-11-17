"""Unchanged independent ERFA time controls and a rejected source identity."""

import json
from pathlib import Path

import pytest

from fatebridge.core.astro import tdb

REFERENCE = json.loads(
    (
        Path(__file__).parents[1] / "fixtures/geocentric-tdb-erfa-reference-v1.json"
    ).read_text()
)
RATE_REFERENCE = json.loads(
    (
        Path(__file__).parents[1] / "fixtures/geocentric-tdb-rate-reference-v1.json"
    ).read_text()
)


@pytest.mark.parametrize("row", REFERENCE["rows"])
def test_shared_geocentric_tdb_matches_uncontracted_original_erfa_c(row):
    # Installed ERFA's seven stricter-line misses remain in the frozen rows.
    assert tdb.geocentric_tdb_state(row["tt_days"]).seconds == pytest.approx(
        row["uncontracted_original_C_seconds"], rel=0, abs=REFERENCE["gate_seconds"]
    )


@pytest.mark.parametrize("row", RATE_REFERENCE["rows"])
def test_complete_time_derivative_matches_independent_complex_step(row):
    actual = tdb.geocentric_tdb_state(row["tt_days"]).rate_seconds_per_TT_day
    assert (
        abs(actual - float(row["rate_seconds_per_TT_day"]))
        <= RATE_REFERENCE["gate_seconds_per_TT_day"]
    )


def test_tdb_source_identity_failure_is_not_used_as_orbital_data(monkeypatch, tmp_path):
    folder = tmp_path / "data/astronomy"
    folder.mkdir(parents=True)
    (folder / "geocentric-tdb-v1.json").write_bytes(b"{}")
    tdb._parameters.cache_clear()
    monkeypatch.setattr(tdb, "files", lambda _: tmp_path)
    with pytest.raises(RuntimeError, match="parameters differ"):
        tdb._parameters()
    tdb._parameters.cache_clear()

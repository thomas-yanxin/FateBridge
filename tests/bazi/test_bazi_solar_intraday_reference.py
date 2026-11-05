"""Check selection and independently reconstruct every frozen source clock value."""

import csv
import gzip
import hashlib
import io
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FOLDER = ROOT / "tests/data/bazi_solar_intraday_v2"


def test_full_grid_preserves_dates_hours_overlap_and_original_protocol_history():
    protocol = json.loads((FOLDER / "protocol.json").read_text())
    raw = (FOLDER / "selected-instants.json").read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == protocol["selection"]["selected_instants_sha256"]
    )
    grid = [datetime.fromisoformat(t) for t in json.loads(raw)]
    assert len(grid) == len(set(grid)) == 76606
    assert grid[0] == datetime(1900, 1, 1, tzinfo=timezone.utc)
    assert grid[-1] < datetime(2101, 1, 1, tzinfo=timezone.utc)
    assert grid[-1] + timedelta(hours=23) >= datetime(2101, 1, 1, tzinfo=timezone.utc)
    assert all(b - a == timedelta(hours=23) for a, b in zip(grid, grid[1:]))
    assert len({t.date() for t in grid}) == 73414
    assert {t.hour for t in grid} == set(range(24))
    assert sum(t.hour == 12 for t in grid) == 3192
    assert protocol["tolerance_seconds"] == 5


def test_decimal_reconstruction_matches_all_raw_horizons_clock_columns():
    protocol = json.loads((FOLDER / "protocol.json").read_text())
    raw_manifest = (FOLDER / "manifest.json").read_bytes()
    assert (
        hashlib.sha256(raw_manifest).hexdigest()
        == (FOLDER / "manifest.sha256").read_text().strip()
    )
    manifest = json.loads(raw_manifest)
    assert (
        manifest["protocol_sha256"]
        == hashlib.sha256((FOLDER / "protocol.json").read_bytes()).hexdigest()
    )
    raw_reference = gzip.decompress((FOLDER / "reference.json.gz").read_bytes())
    assert hashlib.sha256(raw_reference).hexdigest() == manifest["reference_sha256"]
    reference = json.loads(raw_reference)
    reference_by_time = {r["instant"]: r for r in reference}
    assert len(reference_by_time) == len(reference) == 76606
    seen, unavailable = set(), 0
    for chunk in manifest["references"]:
        packed = (FOLDER / chunk["file"]).read_bytes()
        assert hashlib.sha256(packed).hexdigest() == chunk["sha256"]
        raw = gzip.decompress(packed)
        assert hashlib.sha256(raw).hexdigest() == chunk["raw_sha256"]
        source = json.loads(raw)["result"]
        assert "L_Ap_SOL_Time" in source and "UT1-UTC" in source
        assert chunk["parameters"]["STEP_SIZE"] == "'23h'"
        assert chunk["parameters"]["QUANTITIES"] == "'34,49'"
        table = source.split("$$SOE\n", 1)[1].split("$$EOE", 1)[0]
        count = 0
        for fields in csv.reader(io.StringIO(table)):
            instant = datetime.strptime(
                fields[0].strip(), "%Y-%b-%d %H:%M:%S.%f"
            ).replace(tzinfo=timezone.utc)
            key = instant.isoformat()
            assert key not in seen
            seen.add(key)
            count += 1
            converted = reference_by_time[key]
            # Independent Decimal arithmetic in seconds, with explicit midnight
            # wrap; collector uses floating-point hours and a modulo expression.
            apparent = Decimal(fields[3].strip()) * 3600
            clock = (
                Decimal(instant.hour * 3600 + instant.minute * 60 + instant.second)
                + Decimal(instant.microsecond) / 1000000
            )
            difference = apparent - clock
            while difference < -43200:
                difference += 86400
            while difference >= 43200:
                difference -= 86400
            if fields[4].strip() == "n.a.":
                unavailable += 1
                assert converted["dut1_seconds"] is None
            else:
                dut1 = Decimal(fields[4].strip())
                difference -= dut1
                assert converted["dut1_seconds"] == float(dut1)
            assert (
                abs(float(difference) - converted["equation_of_time_minutes"] * 60)
                < 1e-8
            )
        assert count == chunk["rows"]
    assert (
        seen
        == set(reference_by_time)
        == set(json.loads((FOLDER / "selected-instants.json").read_text()))
    )
    assert unavailable == manifest["missing_dut1"] == 23649
    assert protocol["classification"].startswith(
        "Independent official-source intraday expansion"
    )

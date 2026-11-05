"""Keep the first oracle and independently expose rounded-label conflicts."""

import gzip
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from pathlib import Path

from fatebridge.core.astro.historical_utc import HistoricalUTCAdjustment
from fatebridge.core.astro.time_scales import datetime_from_tt_point
from fatebridge.core.astro.tt_epoch import TTInstant

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/data/bazi_historical_point_v1"


def test_all506_original_rows_and_first_seven_failures_are_retained():
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


def test_every_returned_label_and_rejected_rounding_conflict_preserves_the_policy():
    oracle = json.loads(gzip.decompress((FIXTURE / "oracle.json.gz").read_bytes()))
    first = json.loads((FIXTURE / "first-diagnostic.json").read_text())
    tables = [
        json.loads((ROOT / p).read_text())
        for p in (
            "src/fatebridge/data/knowledge/western-utc1960.json",
            "src/fatebridge/data/knowledge/western-historical-utc.json",
        )
    ]
    entries = [e for t in tables for e in t["entries"]]
    normal = rejected = unknown = 0
    conflicts = []
    for row in oracle["rows"]:
        if row["status"] == "pre_utc_model_not_adjudicated":
            unknown += 1
            continue
        try:
            actual = datetime_from_tt_point(TTInstant.from_parts(*row["tt_parts"]))
        except HistoricalUTCAdjustment:
            rejected += 1
            if row["status"] == "normal":
                # Check the first oracle's rounded label by independent
                # forward arithmetic. Do not change it into a passing row.
                moment = datetime.fromisoformat(row["expected_utc"]).astimezone(
                    timezone.utc
                )
                entry = next(
                    e
                    for e in reversed(entries)
                    if e["effective_date"] <= moment.date().isoformat()
                )
                with localcontext() as context:
                    context.prec = 80
                    seconds = (
                        moment.hour * 3600
                        + moment.minute * 60
                        + moment.second
                        + Decimal(moment.microsecond) / 1_000_000
                    )
                    utc = (
                        Decimal(moment.toordinal())
                        + Decimal("1721424.5")
                        + seconds / 86400
                    )
                    offset = Decimal(str(entry["offset_seconds"])) + (
                        utc - Decimal("2400000.5") - entry["reference_mjd"]
                    ) * Decimal(str(entry["rate_seconds_per_day"]))
                    forward = utc + (offset + Decimal("32.184")) / 86400
                    target = sum(
                        (Decimal.from_float(v) for v in row["tt_parts"]), Decimal(0)
                    )
                    assert abs(forward - target) * 86400 > Decimal("0.0002")
                conflicts.append(row["id"])
        else:
            assert row["status"] == "normal", row["id"]
            assert actual.isoformat() == row["expected_utc"], row["id"]
            normal += 1
    assert (normal, rejected, unknown) == (405, 97, 4)
    assert conflicts == [r["id"] for r in first["failures"]]

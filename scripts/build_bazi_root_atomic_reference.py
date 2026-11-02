"""Independent rational TT-to-UTC controls from unchanged SOFA factual tables."""

import argparse
import gzip
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-root-clock-factorization-v1"
UNIX = datetime(1970, 1, 1, tzinfo=timezone.utc)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc_segments(text):
    drift = text.split("static const double drift[][2] = {", 1)[1].split("};", 1)[0]
    changes = text.split("} changes[] = {", 1)[1].split("};", 1)[0]
    rates = re.findall(r"\{\s*([\d.]+),\s*([\d.]+)\s*\}", drift)
    dates = re.findall(r"\{\s*(\d+),\s*(\d+),\s*([\d.]+)\s*\}", changes)
    assert len(rates) == 14 and len(dates) == 42
    result = []
    for i, (year, month, offset) in enumerate(dates):
        moment = datetime(int(year), int(month), 1, tzinfo=timezone.utc)
        elapsed = moment - UNIX
        reference, rate = (
            map(Fraction, rates[i]) if i < 14 else (Fraction(0), Fraction(0))
        )
        result.append(
            dict(
                start=elapsed.days * 86400 + elapsed.seconds,
                offset=Fraction(offset),
                reference=reference,
                rate=rate,
            )
        )
    return result


def invert(point, segments):
    seconds = (point - Fraction(4881175, 2)) * 86400
    candidates = []
    for i, segment in enumerate(segments):
        rate = segment["rate"]
        utc = (
            seconds
            - Fraction(4023, 125)
            - segment["offset"]
            - (40587 - segment["reference"]) * rate
        ) / (1 + rate / 86400)
        if utc < segment["start"] or (
            i + 1 < len(segments) and utc >= segments[i + 1]["start"]
        ):
            continue
        rounded = Fraction(round(utc * 1_000_000), 1_000_000)
        forward = (
            rounded
            + Fraction(4023, 125)
            + segment["offset"]
            + (40587 + rounded / 86400 - segment["reference"]) * rate
        )
        assert abs(forward - seconds) <= Fraction(1, 2_000_000) * (1 + rate / 86400)
        candidates.append(
            (UNIX + timedelta(microseconds=round(utc * 1_000_000))).isoformat()
        )
    if len(candidates) > 1:
        raise ValueError("Atomic segment overlap must remain unresolved")
    return candidates[0] if candidates else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    protocol_path = STUDY / "atomic-reference-protocol.json"
    plan = json.loads(protocol_path.read_text())
    assert (
        sha(protocol_path) == protocol_path.with_suffix(".sha256").read_text().strip()
    )
    raw = STUDY / "sofa-dat.c"
    assert sha(raw) == plan["source_file_sha256"]
    segments = utc_segments(raw.read_text())
    old_path = ROOT / "tests/fixtures/bazi_all_terms_v1/reference.json"
    split_path = STUDY / "independent-roots-first.json.gz"
    assert sha(old_path) == plan["old_reference_sha256"]
    assert sha(split_path) == plan["reference_roots_sha256"]
    old = json.loads(old_path.read_text())
    split = json.loads(gzip.decompress(split_path.read_bytes()))
    rows = []
    for a, b in zip(old["rows"], split["rows"], strict=True):
        assert (a["year"], a["name"]) == (b["year"], b["name"])
        scalar = invert(Fraction(a["jd_tt"]), segments)
        two_part = invert(sum(map(Fraction, b["tt_parts"]), Fraction()), segments)
        assert (scalar is None) == (a["year"] < 1960) == (two_part is None)
        rows.append(
            dict(
                year=a["year"],
                name=a["name"],
                scalar_point_utc=scalar,
                split_point_utc=two_part,
                status=(
                    "pre_UTC_unavailable"
                    if scalar is None
                    else "frozen_atomic_table_point"
                ),
                later_than_source_release=(
                    two_part is not None
                    and datetime.fromisoformat(two_part).date()
                    > datetime(2023, 10, 11).date()
                ),
            )
        )
    assert len(rows) == 4872
    assert not any(
        k.split(".")[0] in {"fatebridge", "swisseph", "erfa", "dateutil", "zoneinfo"}
        for k in sys.modules
    )
    data = dict(
        rows=rows,
        row_count=len(rows),
        unavailable_pre_UTC=sum(r["scalar_point_utc"] is None for r in rows),
        atomic_points=sum(r["scalar_point_utc"] is not None for r in rows),
        protocol_sha256=sha(protocol_path),
        runner_sha256=sha(Path(__file__)),
        source_file_sha256=sha(raw),
        no_application_or_native_imports=True,
        scope=plan["scope"],
        original_gates_superseded=False,
        new_model_executions=0,
        future_leaps_are_assumed_unchanged=True,
        full_goal_complete=False,
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
                "rows": len(rows),
                "atomic_points": data["atomic_points"],
                "unavailable_pre_UTC": data["unavailable_pre_UTC"],
            }
        )
    )


if __name__ == "__main__":
    main()

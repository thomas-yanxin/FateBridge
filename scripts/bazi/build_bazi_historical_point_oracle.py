"""Independent Decimal oracle for split TT points and frozen affine UTC.

No FateBridge imports or runtime outputs are used. All published SOFA cases
and all frozen coefficient-change boundaries are retained, including gaps.
"""

import argparse
import gzip
import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UNIX = datetime(1970, 1, 1, tzinfo=timezone.utc)
JD_UNIX = Decimal("2440587.5")
DAY_US = Decimal(86_400_000_000)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), "Keep the first oracle"
    protocol = json.loads(args.protocol.read_text())
    assert (
        sha(args.protocol) == args.protocol.with_suffix(".sha256").read_text().strip()
    )
    assert all(sha(ROOT / p) == v for p, v in protocol["inputs"].items())
    tables = [
        json.loads((ROOT / p).read_text()) for p in protocol["coefficient_tables"]
    ]
    entries = [e for t in tables for e in t["entries"]]
    sofa = json.loads((ROOT / protocol["sofa_cases"]).read_text())["cases"]
    rows = []
    with localcontext() as context:
        context.prec = 80

        def jd(value):
            elapsed = datetime.fromisoformat(value).replace(tzinfo=timezone.utc) - UNIX
            return JD_UNIX + Decimal(elapsed.days * 86400 + elapsed.seconds) / 86400

        def tt(utc, entry):
            offset = Decimal(str(entry["offset_seconds"]))
            rate = Decimal(str(entry["rate_seconds_per_day"]))
            return (
                utc
                + (
                    Decimal("32.184")
                    + offset
                    + (utc - Decimal("2400000.5") - entry["reference_mjd"]) * rate
                )
                / 86400
            )

        segments = []
        boundaries = []
        for i, entry in enumerate(entries):
            start = jd(entry["effective_date"])
            stop = jd(
                entries[i + 1]["effective_date"]
                if i + 1 < len(entries)
                else tables[-1]["valid_until"]
            )
            a, b = tt(start, entry), tt(stop, entry)
            segments.append((start, stop, a, b, entry))
            boundaries.append((f"start:{i}", a))
            boundaries.append((f"stop:{i}", b))
            if i:
                prior = segments[i - 1][3]
                if prior != a:
                    boundaries.append((f"step_midpoint:{i}", (prior + a) / 2))
        leap_entries = json.loads((ROOT / protocol["leap_table"]).read_text())[
            "entries"
        ]
        modern = [
            (
                jd(r["effective_date"])
                + (Decimal(r["tai_minus_utc_seconds"]) + Decimal("32.184")) / 86400,
                jd(r["effective_date"]),
                Decimal(r["tai_minus_utc_seconds"]) + Decimal("32.184"),
            )
            for r in leap_entries
        ]
        modern_start = modern[0][0]
        boundaries.append(("modern_start", modern_start))
        inputs = [
            {"id": f"sofa:{i}", "tt_parts": r["tt_jd_parts"], "published_utc": r["utc"]}
            for i, r in enumerate(sofa)
        ]
        for label, boundary in boundaries:
            for offset in ("-0.2", "-0.1", "-0.000001", "0", "0.000001", "0.1", "0.2"):
                value = boundary + Decimal(offset) / 86400
                whole = int(value)
                inputs.append(
                    {
                        "id": f"{label}:{offset}",
                        "tt_parts": [float(whole), float(value - whole)],
                    }
                )
        for item in inputs:
            point = sum((Decimal.from_float(v) for v in item["tt_parts"]), Decimal(0))
            candidates = []
            if point >= modern_start:
                selected = next(r for r in reversed(modern) if point >= r[0])
                civil = point - selected[2] / 86400
                label = next((r for r in reversed(modern) if civil >= r[1]), None)
                if label is not None and label[2] == selected[2]:
                    candidates.append(civil)
            elif point >= segments[0][2]:
                for start, stop, a, b, entry in segments:
                    if a <= point < b:
                        rate = Decimal(str(entry["rate_seconds_per_day"]))
                        civil = start + (point - a) / (1 + rate / 86400)
                        if start <= civil < stop:
                            candidates.append(civil)
            if point < segments[0][2]:
                expected = {"status": "pre_utc_model_not_adjudicated"}
            elif len(candidates) != 1:
                expected = {
                    "status": "fractional_adjustment_unrepresentable",
                    "candidate_count": len(candidates),
                }
            else:
                micros = int(
                    ((candidates[0] - JD_UNIX) * DAY_US).to_integral_value(
                        rounding=ROUND_HALF_EVEN
                    )
                )
                expected = {
                    "status": "normal",
                    "expected_epoch_microseconds": micros,
                    "expected_utc": (UNIX + timedelta(microseconds=micros)).isoformat(),
                }
            rows.append({**item, **expected})
    result = {
        "method_id": "historical_split_tt_decimal_oracle_v1",
        "protocol_sha256": sha(args.protocol),
        "rows": rows,
        "row_count": len(rows),
        "normal_rows": sum(r["status"] == "normal" for r in rows),
        "unrepresentable_rows": sum(
            r["status"] == "fractional_adjustment_unrepresentable" for r in rows
        ),
        "pre_utc_unadjudicated_rows": sum(
            r["status"] == "pre_utc_model_not_adjudicated" for r in rows
        ),
        "source_coefficients_are_frozen_assumptions": True,
        "new_independent_observation_credit": 0,
        "original233_sofa_cases_replaced": False,
        "physical_clock_accuracy_certified": False,
    }
    args.output.write_bytes(
        gzip.compress(
            (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode(), mtime=0
        )
    )
    args.output.with_suffix(".sha256").write_text(sha(args.output) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}))


if __name__ == "__main__":
    main()

"""Independent Decimal oracle for the frozen post-1972 atomic-offset policy.

No FateBridge import, ephemeris call, civil inversion or runtime output is used.
Every input source row survives, with pre-policy rows explicitly unadjudicated.
"""

import argparse
import gzip
import hashlib
import json
import math
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
JD_EPOCH = Decimal("2440587.5")
US_DAY = Decimal(86_400_000_000)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), "Preserve first oracle"
    protocol_path = ROOT / "tests/fixtures/bazi_tt_utc_exact_v1/protocol.json"
    assert (
        sha(protocol_path) == protocol_path.with_suffix(".sha256").read_text().strip()
    )
    protocol = json.loads(protocol_path.read_text())
    assert sha(Path(__file__)) == protocol["collector_sha256"]
    sources = protocol["sources"]
    assert all(sha(ROOT / p) == value for p, value in sources.items())
    policy_path = ROOT / protocol["leap_table"]
    policy = json.loads(policy_path.read_text())
    entries = []
    with localcontext() as ctx:
        ctx.prec = 80
        for row in policy["entries"]:
            effective = datetime.fromisoformat(row["effective_date"]).replace(
                tzinfo=timezone.utc
            )
            seconds = int((effective - EPOCH).total_seconds())
            offset_us = Decimal(row["tai_minus_utc_seconds"]) * 1_000_000 + 32_184_000
            jd_utc = JD_EPOCH + Decimal(seconds) / 86400
            entries.append(
                {
                    "effective": effective,
                    "utc_seconds": seconds,
                    "offset_us": offset_us,
                    "jd_tt": jd_utc + offset_us / US_DAY,
                }
            )
        inputs = []
        for group, relative in protocol["input_groups"].items():
            document = json.loads((ROOT / relative).read_text())
            for i, row in enumerate(document["rows"]):
                inputs.append(
                    {
                        "id": f"{group}:{i}",
                        "group": group,
                        "source_index": i,
                        "jd_tt": row["jd_tt"],
                    }
                )
        for i, entry in enumerate(entries):
            bounds = [("offset_start", entry["jd_tt"])]
            if i:
                gap_start = (
                    entry["jd_tt"]
                    - (entry["offset_us"] - entries[i - 1]["offset_us"]) / US_DAY
                )
                bounds.append(("leap_label_start", gap_start))
            for label, boundary in bounds:
                anchor = float(boundary)
                for step in range(-4, 5):
                    value = anchor
                    for _ in range(abs(step)):
                        value = math.nextafter(
                            value, -math.inf if step < 0 else math.inf
                        )
                    inputs.append(
                        {
                            "id": f"transition:{i}:{label}:{step}",
                            "group": "transition",
                            "effective_date": entry["effective"].date().isoformat(),
                            "boundary": label,
                            "ulp_step": step,
                            "jd_tt": value,
                        }
                    )
        rows = []
        counts = {
            "normal": 0,
            "unrepresentable_utc_label": 0,
            "pre_atomic_policy_unadjudicated": 0,
        }
        for item in inputs:
            target = Decimal.from_float(item["jd_tt"])
            selected = next(
                (r for r in reversed(entries) if target >= r["jd_tt"]), None
            )
            if selected is None:
                result = {
                    "status": "pre_atomic_policy_unadjudicated",
                    "expected_datetime_utc": None,
                }
            else:
                micros = (
                    (target - JD_EPOCH) * US_DAY - selected["offset_us"]
                ).to_integral_value(rounding=ROUND_HALF_EVEN)
                expected = EPOCH + timedelta(microseconds=int(micros))
                # A nominal civil label may alias a positive leap second or
                # round into an unrepresentable :60 label. Do not guess it.
                label_policy = next(
                    (r for r in reversed(entries) if expected >= r["effective"]), None
                )
                if (
                    label_policy is None
                    or label_policy["offset_us"] != selected["offset_us"]
                ):
                    result = {
                        "status": "unrepresentable_utc_label",
                        "expected_datetime_utc": None,
                    }
                else:
                    result = {
                        "status": "normal",
                        "expected_datetime_utc": expected.isoformat(),
                        "expected_epoch_microseconds": int(micros),
                        "adopted_offset_microseconds": int(selected["offset_us"]),
                        "future_offsets_are_frozen_policy_assumptions": expected
                        >= datetime.fromisoformat(policy["expires_at"]),
                    }
            counts[result["status"]] += 1
            rows.append({**item, **result})
    assert not any(
        k == "fatebridge" or k.startswith("fatebridge.") for k in sys.modules
    )
    assert all(sha(ROOT / p) == value for p, value in sources.items())
    result = {
        "method_id": protocol["method_id"],
        "protocol_sha256": sha(protocol_path),
        "collector_sha256": sha(Path(__file__)),
        "rows": rows,
        "counts": counts,
        "row_count": len(rows),
        "oracle": "Decimal.from_float exact IEEE64 input, precision80, exact TT-TAI32184000us, frozen integer atomic offsets; round civil microseconds half-even. No source/runtime interpolation or tolerance fitting.",
        "pre1972_rows_retained_unadjudicated": True,
        "new_independent_observation_credit": 0,
        "physical_future_offsets_certified": False,
        "full_goal_complete": False,
    }
    args.output.write_bytes(
        gzip.compress(
            (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode(), mtime=0
        )
    )
    args.output.with_suffix(".sha256").write_text(sha(args.output) + "\n")
    print(json.dumps({"rows": len(rows), "counts": counts, "sha256": sha(args.output)}))


if __name__ == "__main__":
    main()

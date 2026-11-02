"""Decode all before-run selected IEEE roots without importing FateBridge."""

import argparse
import gzip
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-native-solar-point-v1"
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
JD_EPOCH = Decimal("2440587.5")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    binding_path = STUDY / "selected-reference-binding.json"
    binding = json.loads(binding_path.read_text())
    assert sha(binding_path) == binding_path.with_suffix(".sha256").read_text().strip()
    assert sha(__file__) == binding["runner_sha256"]
    assert all(sha(ROOT / p) == h for p, h in binding["inputs"].items())
    before = json.loads(
        gzip.decompress((STUDY / "native-control-before-first.json.gz").read_bytes())
    )
    table = json.loads(
        (ROOT / "src/fatebridge/data/knowledge/western-leap-seconds.json").read_text()
    )
    entries, rows, counts = [], [], Counter()
    with localcontext() as context:
        context.prec = 90
        for row in table["entries"]:
            effective = datetime.fromisoformat(row["effective_date"]).replace(
                tzinfo=timezone.utc
            )
            offset = Decimal(row["tai_minus_utc_seconds"]) + Decimal("32.184")
            jd = JD_EPOCH + Decimal((effective - EPOCH).days)
            entries.append(
                {
                    "effective": effective,
                    "offset_us": offset * 1_000_000,
                    "tt_start": jd + offset / 86400,
                }
            )
        for observed in before["rows"]:
            point = Decimal.from_float(observed["actual_selected_jd_tt"])
            segment = next(
                (e for e in reversed(entries) if point >= e["tt_start"]), None
            )
            if segment is None:
                result = {
                    "selected_point_status": "pre_atomic_policy_unadjudicated",
                    "expected_datetime_utc": None,
                }
            else:
                micros = int(
                    (
                        (point - JD_EPOCH) * 86_400_000_000 - segment["offset_us"]
                    ).to_integral_value(rounding=ROUND_HALF_EVEN)
                )
                label = EPOCH + timedelta(microseconds=micros)
                effective = next(
                    (e for e in reversed(entries) if label >= e["effective"]), None
                )
                if effective is None or effective["offset_us"] != segment["offset_us"]:
                    result = {
                        "selected_point_status": "unrepresentable_utc_label",
                        "expected_datetime_utc": None,
                    }
                else:
                    result = {
                        "selected_point_status": "normal",
                        "expected_datetime_utc": label.isoformat(),
                    }
            counts[result["selected_point_status"]] += 1
            rows.append(
                {
                    "original_reference": observed["original_reference"],
                    "actual_selected_jd_tt": observed["actual_selected_jd_tt"],
                    **result,
                }
            )
    assert len(rows) == 6391
    assert not any(
        k == "fatebridge" or k.startswith("fatebridge.") for k in sys.modules
    )
    result = {
        "rows": rows,
        "row_count": len(rows),
        "counts": dict(counts),
        "binding_sha256": sha(binding_path),
        "runner_sha256": sha(__file__),
        "reference": "Exact IEEE selected root;90-digit Decimal;unchanged integer offsets;round final civil microsecond half-even;no FateBridge conversion import.",
        "original_requested_point_oracle_overwritten": False,
        "new_independent_observation_credit": 0,
        "physical_accuracy_certified": False,
        "full_goal_complete": False,
    }
    args.output.write_bytes(
        gzip.compress((json.dumps(result, ensure_ascii=False) + "\n").encode(), mtime=0)
    )
    args.output.with_suffix(".sha256").write_text(sha(args.output) + "\n")
    print(json.dumps({"counts": dict(counts), "rows": len(rows)}))


if __name__ == "__main__":
    main()

"""Freeze Gregorian carry witnesses without importing application arithmetic."""

import calendar
import gzip
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/data/bazi_dayun_calendar_carries_v1"
US = timedelta(microseconds=1)
DAY_US = 86400 * 1_000_000
JIE = {
    "小寒",
    "立春",
    "惊蛰",
    "清明",
    "立夏",
    "芒种",
    "小暑",
    "立秋",
    "白露",
    "寒露",
    "立冬",
    "大雪",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def initial_boundary(birth, root):
    """Integer nominal conversion followed by explicit Gregorian clipping."""
    elapsed = birth - root
    elapsed_us = (
        elapsed.days * 86400 + elapsed.seconds
    ) * 1_000_000 + elapsed.microseconds
    assert elapsed_us >= 0
    years, remainder = divmod(elapsed_us * 120, 360 * DAY_US)
    months, remainder = divmod(remainder, 30 * DAY_US)
    days, micros = divmod(remainder, DAY_US)
    year, month_index = divmod((birth.year + years) * 12 + birth.month - 1 + months, 12)
    month = month_index + 1
    day = min(birth.day, calendar.monthrange(year, month)[1])
    shifted = birth.replace(year=year, month=month, day=day)
    return shifted + timedelta(days=days, microseconds=micros)


def main():
    output = FIXTURE / "reference.json.gz"
    assert not output.exists(), "Preserve first source reference"
    protocol_path = FIXTURE / "protocol.json"
    assert (
        sha(protocol_path) == protocol_path.with_suffix(".sha256").read_text().strip()
    )
    protocol = json.loads(protocol_path.read_text())
    source = ROOT / protocol["source"]["path"]
    assert sha(source) == protocol["source"]["sha256"]
    data = json.loads(source.read_text())
    roots = sorted(
        [r for r in data["rows"] if r["side"] == "next_minute" and r["name"] in JIE],
        key=lambda r: r["reference_civil_under_frozen_policy"],
    )
    rows, counts = [], Counter()
    for previous, following in zip(roots, roots[1:]):
        root = datetime.fromisoformat(previous["reference_civil_under_frozen_policy"])
        next_root = datetime.fromisoformat(
            following["reference_civil_under_frozen_policy"]
        )
        if root.year < 1899 or root.year > 2100:
            continue
        for k in range(1, 133):
            carry = root + timedelta(hours=k * 6)
            if not 1900 <= carry.year <= 2100 or carry >= next_root:
                continue
            counts["nominal_month_carries_in_birth_domain"] += 1
            before = initial_boundary(carry - US, root)
            after = initial_boundary(carry + US, root)
            jump = (after - before).total_seconds()
            if jump >= 0:
                counts["nonnegative_jump_controls"] += 1
                continue
            counts["negative_calendar_carry_jumps"] += 1
            center = carry.replace(microsecond=0) - timedelta(seconds=30)
            low, high = center - timedelta(minutes=1), center + timedelta(minutes=1)
            assert low > root and high < next_root
            analysis_at = before - timedelta(minutes=40)
            bazi_year = previous["reference_state_under_frozen_policy"]["bazi_year"]
            assert bazi_year is not None
            # Opposite of the yang-male/yin-female forward rule.
            gender = "女" if (bazi_year - 4) % 2 == 0 else "男"

            def observation(at):
                start = initial_boundary(at, root)
                return {
                    "birth_utc": at.isoformat(),
                    "manual_start_at": start.isoformat(),
                    "expected_status": (
                        "before_dayun" if analysis_at < start else "active"
                    ),
                }

            grid = [observation(center + timedelta(minutes=i)) for i in [-1, 0, 1]]
            witnesses = [
                observation(at)
                for at in [carry - timedelta(seconds=10), carry - US, carry, carry + US]
            ]
            gap = sorted(
                {p["expected_status"] for p in witnesses}
                - {p["expected_status"] for p in grid}
            )
            counts["source_grid_missing_witness_state"] += bool(gap)
            rows.append(
                {
                    "id": f"{previous['year']}-{previous['name']}-carry{k}",
                    "reference_jie": previous,
                    "next_jie_utc": next_root.isoformat(),
                    "nominal_months": k,
                    "carry_utc": carry.isoformat(),
                    "negative_jump_seconds": jump,
                    "input": {
                        "birth_year": center.year,
                        "birth_month": center.month,
                        "birth_day": center.day,
                        "birth_hour": center.hour,
                        "birth_minute": center.minute,
                        "birth_second": center.second,
                        "birth_timezone": "UTC",
                        "gender": gender,
                        "use_true_solar_time": False,
                    },
                    "uncertainty_minutes": 1,
                    "analysis_at": analysis_at.isoformat(),
                    "range_utc": [low.isoformat(), high.isoformat()],
                    "expected_grid": grid,
                    "expected_witnesses": witnesses,
                    "expected_statuses": sorted(
                        {p["expected_status"] for p in grid + witnesses}
                    ),
                    "missing_from_minute_grid": gap,
                }
            )
    assert not any(
        k == "fatebridge"
        or k.startswith("fatebridge.")
        or k == "dateutil"
        or k.startswith("dateutil.")
        for k in sys.modules
    )
    result = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": sha(protocol_path),
        "source_sha256": sha(source),
        "counts": dict(counts),
        "rows": rows,
        "scope": protocol["source_scope"],
        "no_application_or_dateutil_imported": True,
        "new_independent_observation_credit": 0,
        "full_goal_complete": False,
    }
    output.write_bytes(
        gzip.compress(
            (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode(), mtime=0
        )
    )
    output.with_suffix(".sha256").write_text(sha(output) + "\n")
    print(
        json.dumps(
            {"counts": dict(counts), "selected": len(rows), "sha256": sha(output)}
        )
    )


if __name__ == "__main__":
    main()

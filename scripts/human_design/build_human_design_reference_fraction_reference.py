"""Reproduce the original126 civil-clock facts without FateBridge or ISO parsing."""

import argparse
import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/data/human_design/reference_fraction"


def derive():
    raw = (FIXTURE / "plan.json").read_bytes()
    if (
        hashlib.sha256(raw).hexdigest()
        != "bffb59b2fee9886b469e5a3ce2643a87aecd92358e94ffb390a5635997b563e4"
    ):
        raise ValueError("Original reference-fraction plan changed")
    plan = json.loads(raw)
    rows = []
    for case in plan["cases"]:
        value = case["input"]
        if case["id"].startswith("date-spelling-"):
            date_text = value[:-6]  # one separator,12.5Z
            if "W" in date_text:
                digits = date_text.replace("-", "").split("W")[1]
                day = int(digits[2]) if len(digits) == 3 else 1
                calendar = date.fromisocalendar(2020, 53, day)
            else:
                calendar = date(2020, 12, 29)
            hour, minute = 12, 0
        else:
            calendar = date(*map(int, value[:10].split("-")))
            clock = value[11:].replace(",", ".").split(".")[0].replace(":", "")
            hour, minute = int(clock[:2]), int(clock[2:] or "0")
        digits = case["fraction"]
        micros = (
            int(digits)
            * (3600 if case["unit"] == "hour" else 60)
            * 10 ** (6 - len(digits))
        )
        expected = datetime(
            calendar.year,
            calendar.month,
            calendar.day,
            hour,
            minute,
            tzinfo=timezone.utc,
        ) + timedelta(microseconds=micros - case["offset_microseconds"])
        if expected.isoformat() != case["expected_utc_label"]:
            raise ValueError("Plan's independent label or expansion changed")
        rows.append({"id": case["id"], "utc_label": expected.isoformat()})
    return {
        "plan_sha256": hashlib.sha256(raw).hexdigest(),
        "reference_imports_fatebridge": False,
        "cases": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(derive(), ensure_ascii=False, indent=2) + "\n").encode()
    target = FIXTURE / "reference.json"
    if args.check:
        if target.read_bytes() != raw:
            raise SystemExit("Original frozen civil reference differs")
    else:
        target.write_bytes(raw)
    print(
        json.dumps(
            {
                "cases": 126,
                "reference_sha256": hashlib.sha256(raw).hexdigest(),
                "checked": args.check,
            }
        )
    )


if __name__ == "__main__":
    main()

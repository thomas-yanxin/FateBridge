"""Read selected phase/clock quotations back from actual publisher captures."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_phase_clock import validate_selected_claims
from scripts.check_sukuyo_commentarial_clock import source_lines

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/fatebridge/data/sukuyo_phase_clock.json"
FIXTURE = ROOT / "tests/fixtures/sukuyo-phase-clock-primary.json"


def verify_primary(captures: dict[str, Path] | None = None) -> dict[str, Any]:
    raw = SOURCE.read_bytes()
    data = json.loads(raw)
    fixture = json.loads(FIXTURE.read_bytes())
    if hashlib.sha256(raw).hexdigest() != fixture["source_bundle_sha256"]:
        raise ValueError("定日分时数据与冻结控制不同")
    for key, value in [
        ("phase_day_distinction", "phase_controls"),
        ("morning_reference", "morning_controls"),
        ("time_wording_reference", "time_controls"),
    ]:
        if data[key] != fixture[value]:
            raise ValueError("定日分时控制与来源不同")
    validate_selected_claims(data)
    sources = {row["id"]: row for row in data["sources"]}
    if fixture["source_capture_sha256"] != {
        key: row["capture_sha256"] for key, row in sources.items()
    }:
        raise ValueError("出版方来源身份与冻结控制不同")
    checked = []
    quotations = 0
    for key, path in (captures or {}).items():
        if key not in sources:
            raise ValueError("未登记定日分时来源")
        row = sources[key]
        actual = path.read_bytes()
        if (
            len(actual) != row["capture_bytes"]
            or hashlib.sha256(actual).hexdigest() != row["capture_sha256"]
        ):
            raise ValueError("定日分时实际来源字节不同")
        if row["format"] == "SAT_HTML":
            actual = re.sub(rb"<button\b[^>]*>.*?</button>", b"", actual, flags=re.S)
        lines = source_lines(actual, row["format"])
        for quote in row["selected_quotations"]:
            window = re.sub(
                r"\s+",
                "",
                "".join(
                    text
                    for line, text in sorted(lines.items())
                    if quote["first_line"] <= line <= quote["last_line"]
                ),
            )
            if quote["literal"] != window:
                raise ValueError(f"定日分时选段与实际出版方行不同：{quote['locator']}")
            quotations += 1
        checked.append(key)
    return {
        "source_bundle_sha256": hashlib.sha256(raw).hexdigest(),
        "actual_capture_bytes_rechecked": checked,
        "all_actual_captures_rechecked": set(checked) == set(sources),
        "actual_quotations_rechecked": quotations,
        "numerical_controls_bound_to_selected_text": True,
        "nested_originals_or_manuscript_collation_accepted": False,
        "actual_lunar_phase_or_tithi_computed": False,
        "historical_day_boundary_or_hinoo_half_established": False,
        "leap_short_month_priority_established": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", action="append", default=[], metavar="ID=PATH")
    args = parser.parse_args()
    captures = {}
    for value in args.capture:
        key, path = value.split("=", 1)
        if key in captures:
            raise ValueError("重复定日分时来源")
        captures[key] = Path(path)
    print(json.dumps(verify_primary(captures), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

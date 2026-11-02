"""Complete predeclared 24-term TT audit, separate from original-book selection."""

import hashlib
import json
import math
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.fengshui.calendar import solar_term_resolution
from fatebridge.utils.errors import EphemerisSourceError

PROTOCOL_SHA256 = "0d81e9f0f564c3c4d44a08a15d8fb0495ba33f053183c80580dd630e3c13a0dd"
CAPTURE_HASHES = {
    "protocol.json": PROTOCOL_SHA256,
    "reference.json": "ab7ddadaa02e0fd71b3049c3146f3ec5bae01441309356372b9668c65afab371",
    "collector.py.txt": "b9433d30e62773b69d903e39629ea744b59cab0ee6e3a207f0033992b6eeda56",
}
TERMS = tuple(
    "小寒 大寒 立春 雨水 惊蛰 春分 清明 谷雨 立夏 小满 芒种 夏至 "
    "小暑 大暑 立秋 处暑 白露 秋分 寒露 霜降 立冬 小雪 大雪 冬至".split()
)


def load_solar_terms_reference(folder: Path) -> dict[str, Any]:
    manifest = json.loads((folder / "hashes.json").read_text())
    if manifest != CAPTURE_HASHES:
        raise ValueError("Retain the independently frozen complete capture manifest")
    for name, digest in CAPTURE_HASHES.items():
        if hashlib.sha256((folder / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Frozen solar-term capture changed: {name}")
    reference = json.loads((folder / "reference.json").read_text())
    if not isinstance(reference, dict):
        raise ValueError("Frozen solar-term reference must be an object")
    if reference["protocol"] != json.loads((folder / "protocol.json").read_text()):
        raise ValueError("Reference protocol differs from its frozen source")
    validate_solar_terms_reference(reference)
    return reference


def validate_solar_terms_reference(reference: dict[str, Any]) -> None:
    protocol = reference["protocol"]
    protocol_bytes = (
        json.dumps(protocol, ensure_ascii=False, indent=2) + "\n"
    ).encode()
    if (
        hashlib.sha256(protocol_bytes).hexdigest() != PROTOCOL_SHA256
        or reference["collector_sha256"] != CAPTURE_HASHES["collector.py.txt"]
        or any(
            reference["versions"].get(name) != version
            for name, version in (
                ("skyfield", "1.53"),
                ("jplephem", "2.24"),
                ("numpy", "2.2.6"),
            )
        )
        or protocol["id"] != "fengshui_all24_de440_tt_v1"
        or protocol["years"] != [1784, 2204]
        or protocol["terms"] != list(TERMS)
        or protocol["longitudes_degrees"] != [(285 + 15 * i) % 360 for i in range(24)]
        or type(protocol["rows"]) is not int
        or protocol["rows"] != 10104
        or type(protocol["numeric_implementation_tolerance_seconds"]) is not float
        or protocol["numeric_implementation_tolerance_seconds"] != 1.0
        or protocol["reference_max_bracket_seconds"] != 0.001
        or protocol["time_scale"] != "TT"
        or reference["protocol_sha256"] != PROTOCOL_SHA256
    ):
        raise ValueError("Retain all frozen years, terms and the one-second TT gate")
    rows = reference["rows"]
    if [(r["year"], r["term_index"]) for r in rows] != [
        (y, i) for y in range(1784, 2205) for i in range(24)
    ]:
        raise ValueError("Require all10104 distinct ordered year/term identities")
    previous = -math.inf
    for row in rows:
        i = row["term_index"]
        if (
            type(row["year"]) is not int
            or type(i) is not int
            or row["term"] != TERMS[i]
            or type(row["longitude_degrees"]) is not int
            or row["longitude_degrees"] != (285 + 15 * i) % 360
        ):
            raise ValueError("Reference identity and physical longitude must agree")
        for key in ("jd_tt", "bracket_width_seconds"):
            value = row[key]
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError("Reference values must be finite real numbers")
        month = i // 2 + 1
        low_day, high_day = (1, 12) if i % 2 == 0 else (12, 28)
        low = date(row["year"], month, low_day).toordinal() + 1721424.5
        high = date(row["year"], month, high_day).toordinal() + 1721424.5
        if not low < row["jd_tt"] < high or row["jd_tt"] <= previous:
            raise ValueError("Reference roots must lie in their ordered fixed brackets")
        if not 0 <= row["bracket_width_seconds"] <= 0.001:
            raise ValueError("Do not degrade the independently collected bracket")
        previous = row["jd_tt"]


def compare_resolution(
    row: dict[str, Any], resolution: dict[str, Any]
) -> dict[str, Any]:
    """Judge actual civil output and the raw root separately with the same gate."""
    civil_difference = None
    root_difference = None
    model = resolution.get("ephemeris_model")
    calculated = (
        resolution.get("approximate") is False
        and resolution.get("provider")
        in {
            "swisseph",
            "jpl_de440",
            "jpl_spk",
            "fatebridge_analytic",
            "moshier_aa1996",
            "vsop2013",
        }
        and isinstance(model, str)
        and bool(model)
        and resolution.get("time_basis", {}).get("root_time_scale") == "TT"
    )
    if calculated:
        moment = datetime.fromisoformat(resolution["moment"])
        if moment.utcoffset() is None:
            raise ValueError("Calculated civil results must retain their time zone")
        clock = ephemeris_time(moment)
        if clock.jd_tt is not None:
            civil_difference = (clock.jd_tt - row["jd_tt"]) * 86400
        root = resolution.get("solar_model_details", {}).get("selected_crossing_jd_tt")
        if type(root) in (int, float) and math.isfinite(root):
            root_difference = (root - row["jd_tt"]) * 86400
    named_root_required = resolution.get("provider") in {
        "jpl_de440",
        "jpl_spk",
        "fatebridge_analytic",
        "moshier_aa1996",
        "vsop2013",
    }
    passed = (
        civil_difference is not None
        and math.isfinite(civil_difference)
        and abs(civil_difference) <= 1.0
        and (
            not named_root_required
            or (root_difference is not None and abs(root_difference) <= 1.0)
        )
    )
    return {
        "year": row["year"],
        "term_index": row["term_index"],
        "term": row["term"],
        "reference_jd_tt": row["jd_tt"],
        "civil_roundtrip_difference_seconds_tt": civil_difference,
        "selected_root_difference_seconds_tt": root_difference,
        "resolution": resolution,
        "within_tolerance": passed,
    }


def audit_solar_terms_reference(
    reference: dict[str, Any],
    *,
    progress: Callable[[int], None] | None = None,
) -> dict[str, Any]:
    validate_solar_terms_reference(reference)
    input_digest = hashlib.sha256(
        (json.dumps(reference, ensure_ascii=False, indent=2) + "\n").encode()
    ).hexdigest()
    reference_intact = input_digest == CAPTURE_HASHES["reference.json"]
    comparisons = []
    for row in reference["rows"]:
        try:
            resolution = solar_term_resolution(row["year"], row["term"], "UTC")
            item = compare_resolution(row, resolution)
        except (EphemerisSourceError, ValueError, ImportError, OverflowError) as error:
            item = {
                "year": row["year"],
                "term_index": row["term_index"],
                "term": row["term"],
                "reference_jd_tt": row["jd_tt"],
                "within_tolerance": False,
                "error_type": type(error).__name__,
                "error": str(error),
            }
        comparisons.append(item)
        if progress is not None and len(comparisons) % 24 == 0:
            progress(len(comparisons))
    failed = [c for c in comparisons if not c["within_tolerance"]]
    differences = [
        abs(c["civil_roundtrip_difference_seconds_tt"])
        for c in comparisons
        if c.get("civil_roundtrip_difference_seconds_tt") is not None
    ]
    root_differences = [
        abs(c["selected_root_difference_seconds_tt"])
        for c in comparisons
        if c.get("selected_root_difference_seconds_tt") is not None
    ]
    return {
        "protocol_id": reference["protocol"]["id"],
        "frozen_reference_sha256": CAPTURE_HASHES["reference.json"],
        "actual_reference_input_sha256": input_digest,
        "reference_matches_frozen_capture": reference_intact,
        "rows": len(comparisons),
        "matched": len(comparisons) - len(failed),
        "failed_count": len(failed),
        "tolerance_seconds": 1.0,
        "maximum_civil_roundtrip_difference_seconds_tt": max(differences, default=None),
        "maximum_selected_root_difference_seconds_tt": max(
            root_differences, default=None
        ),
        "actual_model_counts": dict(
            Counter(c.get("resolution", {}).get("ephemeris_model") for c in comparisons)
        ),
        "failed_by_term": dict(Counter(c["term"] for c in failed)),
        "all_scoped_tt_checks_passed": reference_intact and not failed,
        "scope": "All10104 declared solar crossings in TT, including actual civil serialization; not absolute UTC accuracy, original-book date-table selection or real-world prediction",
        "original_book_table_selection_verified": False,
        "real_world_prediction_established": False,
        "comparisons": comparisons,
    }

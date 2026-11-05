"""Retain both input paths and require every qualified reference to agree.

Only reference integrity/quality determines availability. Candidate failures
are never used to choose an encoding, and no planned case can be omitted.
"""

import sys
from pathlib import Path

from scripts.astrodice.audit_astrodice_local_motion import (
    FAIL,
    PASS,
    UNRESOLVED,
)

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


ENCODINGS = {"JD", "MJD"}
QUALIFIED = "qualified_under_declared_numerical_model"


def intersects(intervals):
    return all(
        max(value[axis][0] for value in intervals)
        <= min(value[axis][1] for value in intervals)
        for axis in (0, 1)
    )


def outcome(qualities, reports, intervals, center_boxes):
    if any(set(value) != ENCODINGS for value in [qualities, reports]):
        raise ValueError("Both declared encodings must remain present")
    qualified = [name for name in sorted(ENCODINGS) if qualities[name] == QUALIFIED]
    if set(intervals) != set(qualified):
        raise ValueError("Only independently qualified reference intervals are allowed")
    statuses = [
        value["status"] for report in reports.values() for value in report.values()
    ]
    # Even a failure in a path whose other layer is unavailable remains fatal.
    if FAIL in statuses:
        return FAIL
    if "candidate_error" in statuses:
        return "candidate_error"
    if (
        not qualified
        or not any(report["position"]["status"] == PASS for report in reports.values())
        or any(reports[name]["rate"]["status"] != PASS for name in qualified)
        or not center_boxes
        or not intersects(list(center_boxes.values()))
        or not intersects([intervals[name] for name in qualified])
    ):
        return UNRESOLVED
    return PASS

"""Load hash-verified Dayun future-gap controls used by range regressions."""

import gzip
import hashlib
import json
from pathlib import Path
from typing import TypedDict

from pydantic import JsonValue


class FutureGapControl(TypedDict):
    id: str
    input: dict[str, JsonValue]
    analysis_at: str
    status: str
    expected_statuses: list[str]


class FutureGapReference(TypedDict):
    rows: list[FutureGapControl]
    counts: dict[str, int]
    no_application_dateutil_zoneinfo_imported: bool


FIXTURE = Path(__file__).parents[2] / "data/bazi_dayun_future_gaps_v1"
REFERENCE = FIXTURE / "reference.json.gz"
assert (
    hashlib.sha256(REFERENCE.read_bytes()).hexdigest()
    == REFERENCE.with_suffix(".sha256").read_text().strip()
)
FUTURE_GAP_REFERENCE: FutureGapReference = json.loads(
    gzip.decompress(REFERENCE.read_bytes())
)
RESOLVED_CONTROLS = [
    r for r in FUTURE_GAP_REFERENCE["rows"] if r["status"] == "resolved_source_control"
]
INITIAL_BOUNDARY_CONTROLS = [
    RESOLVED_CONTROLS[0],
    next(
        control
        for control in RESOLVED_CONTROLS
        if isinstance(birth_year := control["input"]["birth_year"], int)
        and birth_year >= 2000
    ),
]

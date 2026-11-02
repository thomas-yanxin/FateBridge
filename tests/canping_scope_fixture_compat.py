"""Remove only a verified R80 disclosure receipt from old-fact comparisons.

The expected receipt comes from the frozen pre-edit reference, never from
production. A wrong new receipt is an error, not an ignored difference.
Original snapshots, numbers, words, faults and old test nodes remain intact.
"""

import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).parent / "fixtures/canping_scope_rendering_v1"
REFERENCE = json.loads((ROOT / "reference.json").read_bytes())
EXPECTED = REFERENCE["receipts"][REFERENCE["current_revision"]]
POLICY = "canping_schedule_source_mapping_v1"


def _copies(output):
    rows = [
        row
        for row in output["numerology_evidence"]["rule_trace"]
        if row["rule_id"] == POLICY
    ]
    assert len(rows) == 1
    return [output["canping_timing"]["schedule_basis"], rows[0]["facts"]]


def rewind_scope_receipt_checked(current, *, require_present=False):
    output = deepcopy(current)
    copies = _copies(output)
    present = ["scope_rendering" in copy for copy in copies]
    assert all(present) or not any(present)
    if require_present:
        assert all(present)
    if all(present):
        for copy in copies:
            assert copy.pop("scope_rendering") == EXPECTED
    return output


def upgrade_scope_receipt_checked(prior):
    output = deepcopy(prior)
    for copy in _copies(output):
        assert "scope_rendering" not in copy
        assert (
            copy["scope_statement"]
            == REFERENCE["revisions"][REFERENCE["current_revision"]]
        )
        copy["scope_rendering"] = deepcopy(EXPECTED)
    assert rewind_scope_receipt_checked(output) == prior
    return output

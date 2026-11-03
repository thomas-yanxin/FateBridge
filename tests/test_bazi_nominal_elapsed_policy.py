"""A disclosed clock policy must retain every frozen calculation and failure."""

import hashlib
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import pytest

from fatebridge.core.almanac import elapsed_days_between
from fatebridge.core.timing import TimingAnalysis

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = ROOT / "docs/validation/bazi-elapsed-scale-discovery-v1"
STUDY = ROOT / "docs/validation/bazi-nominal-elapsed-policy-v1"
DECLARATIONS = {
    "elapsed_scale": "nominal_utc_label_seconds",
    "leap_second_policy": "not_counted",
}


def bound(path):
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == path.with_suffix(".sha256").read_text().strip()
    )
    return json.loads(path.read_text())


AUDIT = bound(DISCOVERY / "audit-first.json")
PATHS = bound(DISCOVERY / "dayun-path-first.json")
PROTOCOL = bound(STUDY / "protocol.json")


@pytest.fixture(autouse=True)
def same_declared_solar_model(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    monkeypatch.setenv("SE_EPHE_PATH", "/tmp/fatebridge-elapsed-scale-empty")
    for name in ("FATEBRIDGE_SOLAR_SPK_FILE", "FATEBRIDGE_JPL_FILE"):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize("row", AUDIT["rows"], ids=lambda r: r["reference"]["id"])
def test_all_actual_elapsed_values_retain_the_original_float_and_scale(row):
    reference = row["reference"]
    actual = (
        elapsed_days_between(
            datetime.fromisoformat(reference["start_utc"]),
            datetime.fromisoformat(reference["end_utc"]),
        )
        * 86400
    )
    assert actual == row["actual_seconds"]
    assert actual == reference["nominal_utc_label_seconds"]
    assert (actual == reference["uniform_atomic_elapsed_seconds"]) is row[
        "matches_uniform_atomic_elapsed_seconds"
    ]


@pytest.mark.parametrize("row", PATHS["records"], ids=lambda r: r["input"]["id"])
def test_every_actual_dayun_object_only_adds_the_two_predeclared_fields(row):
    source = row["input"]
    actual = TimingAnalysis.calculate_dayun_timeline(
        datetime.fromisoformat(source["birth_utc"]),
        source["gender"],
        ("甲", "子"),
        "UTC",
    )
    assert {k: actual["start_details"][k] for k in DECLARATIONS} == DECLARATIONS
    expected = deepcopy(row["actual_timeline"])
    expected["start_details"].update(DECLARATIONS)
    # Whole objects, including consumed solar-root metadata and all12periods.
    # No float tolerance, dropped failing rows, or newly computed expectations.
    assert actual == expected


def test_no_original_gate_or_atomic_time_policy_is_adopted():
    assert PROTOCOL["uniform_si_duration_implemented"] is False
    assert PROTOCOL["original_gates_superseded"] is False
    assert PROTOCOL["original_116906_full_replay_runtime_unchanged"] is True
    assert PROTOCOL["new_model_executions"] == 0

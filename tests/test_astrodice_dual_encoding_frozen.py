"""Replay both complete sources and retain all historical/alternate failures."""

import hashlib
import json
import shutil
from decimal import Decimal
from fractions import Fraction as Q
from pathlib import Path

import pytest

from scripts.audit_astrodice_encoding_envelope import audit
from scripts.audit_astrodice_local_motion import FAIL, PASS
from scripts.audit_astrodice_local_reference import replay
from scripts.diagnose_astrodice_epoch_serialization import assess

FIXTURE = Path(__file__).parent / "fixtures/astrodice-dual-encoding-tt-v1"


def read(name, root=FIXTURE):
    return json.loads((root / name).read_text())


def test_every_frozen_input_and_the_original_outage_remain_intact():
    assert hashlib.sha256((FIXTURE / "manifest.json").read_bytes()).hexdigest() == (
        "5b8e7d6dc03a58ff49416399cfd0a7d320c6df92d3d32c80c3a1cdd91f8d7222"
    )
    for name, expected in read("manifest.json")["files"].items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == expected
    old = FIXTURE / "original-outage-fixture"
    assert hashlib.sha256((old / "manifest.json").read_bytes()).hexdigest() == (
        "7df1a27fab43825e3000309af5c8111d497a6387a4231ba3e41753cb4518fd76"
    )
    result = replay(
        old / "protocol.json",
        old / "reference.json",
        old / "raw",
        old / "reference-seal.json",
        read("certificates.json", old),
    )
    assert result["exit_code"] == 2
    assert (
        sum(
            len(row["missing_offsets_seconds"])
            for row in read("reference.json", old)["rows"]
        )
        == 2308
    )
    assert read("first-acceptance.json", old)["exit_code"] == 2


@pytest.mark.parametrize("cohort", ["A", "B"])
def test_complete_reference_replay_matches_first_measurement_and_original_lines(cohort):
    result = audit(FIXTURE, FIXTURE / "dual-encoding-plan-before-B.json", cohort)
    assert result == read("dual-" + cohort + "-first.json")
    assert result["exit_code"] == 0 and result["planned_conditions"] == 4
    assert result["fixed_position_arcsec"] == 0.02
    assert result["fixed_rate_arcsec_per_day"] == 0.002
    assert all(row["status"] == PASS for row in result["rows"])
    assert not result["individual_reference_failures_regraded"]
    assert not result["full_goal_complete"]


def test_all_four_individual_path_results_stay_unresolved_with_every_missing_node():
    for prefix, expected in [
        ("recovered-TT", [0, 0, 4, 0]),
        ("MJD-A", [0, 0, 0, 8]),
        ("JD-B", [0, 0, 9, 0]),
        ("MJD-B", [0, 0, 0, 12]),
    ]:
        raw = read(prefix + "-reference-first.json")
        assert [len(row["missing_offsets_seconds"]) for row in raw["rows"]] == expected
        assert all(len(row["samples"]) == 577 for row in raw["rows"])
        assert read(prefix + "-native-first.json")["exit_code"] == 2
    assert read("dual-before-B-open.json")["B_four_conditions_unopened"]
    plan = read("dual-encoding-plan-before-B.json")
    for a, b in zip(plan["cases"]["A"], plan["cases"]["B"]):
        # Input labels were frozen with the same fixed 12347-second offset.
        from scripts.audit_astrodice_horizons_wide_reference import center_tick

        assert center_tick(b["date_tt"]) - center_tick(a["date_tt"]) == 12347 * 1000000


def test_every_shared_accepted_observation_has_consistent_full_lsb_printing_intervals():
    count = 0
    for left, right in [("recovered-TT", "MJD-A"), ("JD-B", "MJD-B")]:
        for a, b in zip(
            read(left + "-reference-first.json")["rows"],
            read(right + "-reference-first.json")["rows"],
        ):
            assert all(a[k] == b[k] for k in ["id", "body", "date_tt", "jd_tt"])
            for offset, x in a["samples"].items():
                y = b["samples"][offset]
                if x is None or y is None:
                    continue
                count += 1
                assert x["requested_calendar_label"] == y["requested_calendar_label"]
                for axis, (u, v) in enumerate(
                    zip(x["printed_angles"], y["printed_angles"])
                ):
                    difference = Q(u) - Q(v)
                    if axis == 0:
                        difference -= 360 * ((difference + 180) // 360)
                    radius = sum(
                        (
                            Q(Decimal(10) ** Decimal(z).as_tuple().exponent)
                            for z in [u, v]
                        ),
                        Q(),
                    )
                    assert abs(difference) <= radius
    assert count == 4583


def test_a_new_candidate_failure_cannot_be_hidden_by_the_other_encoding(tmp_path):
    data = tmp_path / "data"
    shutil.copytree(FIXTURE, data)
    path = data / "JD-B-native-first.json"
    value = json.loads(path.read_text())
    value["rows"][3]["layers"]["position"]["status"] = FAIL
    path.write_text(json.dumps(value))
    result = audit(data, data / "dual-encoding-plan-before-B.json", "B")
    assert result["exit_code"] == 1 and result["rows"][3]["status"] == FAIL
    assert len(result["rows"]) == 4


def test_a_dropped_candidate_case_cannot_shrink_the_denominator(tmp_path):
    data = tmp_path / "data"
    shutil.copytree(FIXTURE, data)
    path = data / "MJD-B-native-first.json"
    value = json.loads(path.read_text())
    value["rows"].pop()
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="case coverage changed"):
        audit(data, data / "dual-encoding-plan-before-B.json", "B")


def test_the_same_exact_epoch_diagnostic_retains_the_jd_counterexample():
    plan = read("epoch-serialization-before.json")
    outcomes = {}
    for encoding in ["JD", "MJD", "CAL"]:
        raw = (
            FIXTURE / "epoch-serialization-first" / (encoding + "-raw.json")
        ).read_bytes()
        result = assess(raw, plan)
        outcomes[encoding] = result["labels_within_original_budget"]
        assert result["candidate_accuracy_passes"] == 0
        assert not result["failed_reference_replaced"]
    assert outcomes == {"JD": 9, "MJD": 13, "CAL": 13}

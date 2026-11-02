"""Actual small candidate receipts reject rehashed probe and reading forgeries."""

import gzip
import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest

from fatebridge.core.human_design_sensitivity import LEGACY_METHOD
from fatebridge.services.replay_metadata import digest
from fatebridge.validation.human_design import verify_human_design_reading
from fatebridge.validation.human_design_sampling import verify_sampled_interval

E = (
    Path(__file__).resolve().parents[1]
    / "docs/validation/human-design-interval-coordinate-extrema-v1/evidence"
)


@pytest.fixture(scope="module")
def complete():
    with gzip.open(E / "wheel-final-rest.json.gz", "rt") as source:
        return json.load(source)


def rehash(value):
    value["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in value.items() if k != "run_metadata"}
    )


def test_actual_selected_probe_all_samples_and_explanation_replay_without_native(
    complete,
):
    with (
        patch(
            "fatebridge.core.astro.runtime.ephemeris_call",
            side_effect=AssertionError("native replay"),
        ),
        patch(
            "fatebridge.core.astro.native_execution.calculate",
            side_effect=AssertionError("native dispatch"),
        ),
    ):
        check = verify_human_design_reading(complete)
    report = complete["time_sensitivity"]
    assert check["status"] == "verified_fixed_template_reading"
    assert (
        check["checked_interval_evaluation_count"]
        == report["sampling"]["total_evaluation_count"]
    )
    assert report["station_coordinate_extremum_assessment"]["probe_count"] == 1
    assert (
        complete["run_metadata"]["contract_sha256"]
        == "410a32d4ebddb1cbad641450b5b4701d00e037dbb6729046bedf3b73ea82f52b"
    )


@pytest.mark.parametrize(
    "fault",
    [
        "missing_probe_evidence",
        "coordinate",
        "selected_birth_tt",
        "parameter_axis",
        "gain",
        "sample_omission",
        "invented_budget_exhaustion",
        "physical_certification",
        "summary_downplay",
        "legacy_downgrade",
        "unknown_method",
    ],
)
def test_rehash_cannot_forge_or_remove_coordinate_evidence_or_downgrade(
    complete, fault
):
    value = deepcopy(complete)
    report = value["time_sensitivity"]
    assessment = report["station_coordinate_extremum_assessment"]
    probe = assessment["probes"][0]
    if fault == "missing_probe_evidence":
        report.pop("station_coordinate_extremum_assessment")
    elif fault == "coordinate":
        probe["observations"][0][1] += 0.01
    elif fault == "selected_birth_tt":
        probe["selected"][0] += 1 / 86400
    elif fault == "parameter_axis":
        assessment["parameter_axis"] = "design_jd_tt"
    elif fault == "gain":
        probe["observed_coordinate_gain_exact"]["numerator"] = "999999999999"
    elif fault == "sample_omission":
        selected = probe["selected"][0]
        rows = report["evaluation_witnesses"]["samples"]
        before = len(rows)
        rows[:] = [
            r for r in rows if r["time_scales"]["personality"]["jd_tt"] != selected
        ]
        assert len(rows) == before - 1
    elif fault == "invented_budget_exhaustion":
        assert not assessment["budget_exhausted"]
        assessment["budget_exhausted"] = True
    elif fault == "physical_certification":
        probe["physical_station_certified"] = True
    elif fault == "summary_downplay":
        report["summary"]["coordinate_extremum_probes"] = 0
    elif fault == "legacy_downgrade":
        report["method_id"] = LEGACY_METHOD
    elif fault == "unknown_method":
        report["method_id"] = "unknown_method"
    rehash(value)
    with (
        patch(
            "fatebridge.core.astro.runtime.ephemeris_call",
            side_effect=AssertionError("native replay"),
        ),
        patch(
            "fatebridge.core.astro.native_execution.calculate",
            side_effect=AssertionError("native dispatch"),
        ),
    ):
        assert verify_sampled_interval(value)["errors"]
        assert verify_human_design_reading(value)["status"] == "rejected"


def test_rehash_cannot_replace_bound_interval_explanation_with_stability_claim(
    complete,
):
    value = deepcopy(complete)
    value["interpretation"]["birth_interval_meaning"] = "附近所有时刻都绝对稳定。"
    rehash(value)
    with patch(
        "fatebridge.core.astro.runtime.ephemeris_call",
        side_effect=AssertionError("native replay"),
    ):
        assert verify_human_design_reading(value)["status"] == "rejected"

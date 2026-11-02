"""Reject false clock labels, forged receipts and changed original business facts."""

from copy import deepcopy

import pytest

from fatebridge.core.local_techniques.canping import build_canping_result
from tests.canping_witness_fixture_compat import upgrade_frozen_witnesses
from tests.test_canping_first_row import REFERENCES
from tests.test_numerology_solar_providers import (
    preserve_original_canping_snapshot_with_source_changes_checked,
)


@pytest.fixture(scope="module")
def paired_result(tmp_path_factory):
    reference = REFERENCES[0]
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
        patch.setenv("SE_EPHE_PATH", str(tmp_path_factory.mktemp("empty-ephe")))
        actual = build_canping_result(**reference["arguments"])
    del actual["canping_timing"]["first_row"]
    return actual, reference["output"]


def require_all_original_facts(actual, expected):
    normalized = preserve_original_canping_snapshot_with_source_changes_checked(
        actual, expected
    )
    expected = upgrade_frozen_witnesses(expected)
    assert normalized == expected


def test_three_metadata_additions_preserve_every_frozen_original_fact(paired_result):
    actual, expected = paired_result
    before = deepcopy(actual)
    require_all_original_facts(actual, expected)
    assert actual == before


@pytest.mark.parametrize(
    "fault",
    [
        "policy",
        "historical",
        "future",
        "missing_label",
        "timing_receipt",
        "series_receipt",
        "trace_receipt",
        "civil_date",
        "boundary_instant",
        "number",
        "extra_claim",
    ],
)
def test_metadata_migration_cannot_hide_false_labels_or_business_changes(
    paired_result, fault
):
    actual, expected = paired_result
    wrong = deepcopy(actual)
    details = wrong["liunian_series"]["year_boundaries"][0]["record"][
        "solar_model_details"
    ]
    if fault == "policy":
        details["civil_time_policy"] = "invented_measured_UTC"
    elif fault == "historical":
        details["historical_ut1_convention"] = True
    elif fault == "future":
        future = wrong["liunian_series"]["year_boundaries"][4]["record"][
            "solar_model_details"
        ]
        assert future["future_leap_seconds_assumed_unchanged"] is True
        future["future_leap_seconds_assumed_unchanged"] = False
    elif fault == "missing_label":
        del details["civil_time_policy"]
    elif fault == "timing_receipt":
        wrong["canping_timing"]["solar_year_context"]["boundary_receipts_sha256"] = (
            "0" * 64
        )
    elif fault == "series_receipt":
        wrong["liunian_series"]["solar_context"]["boundary_receipts_sha256"] = "0" * 64
    elif fault == "trace_receipt":
        next(
            t["facts"]
            for t in wrong["numerology_evidence"]["rule_trace"]
            if t["rule_id"] == "canping_actual_lichun_dependencies"
        )["boundary_receipts_sha256"] = ("0" * 64)
    elif fault == "civil_date":
        wrong["calendar_context"]["current_solar_term"][
            "datetime"
        ] = "2024-03-21 00:00:00"
    elif fault == "boundary_instant":
        wrong["liunian_series"]["year_boundaries"][0][
            "instant_utc"
        ] = "2024-02-05T00:00:00+00:00"
    elif fault == "number":
        wrong["dayun"][0]["numShun"] += 1
    else:
        details["fabricated_accuracy_certified"] = True
    with pytest.raises((AssertionError, KeyError)):
        require_all_original_facts(wrong, expected)

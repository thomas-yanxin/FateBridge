"""Exact interval diagnostics checked against real pre-code Node JSON parsing."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.sukuyo_date_support import local_date_support

FIXTURE = (
    Path(__file__).parents[1]
    / "data/sukuyo-number-transport-before-production-v78.json"
)
RAW = FIXTURE.read_bytes()
REF = json.loads(RAW)
EXPECTED = {r["id"]: r for r in REF["expected"]["cases"]}


def node_projection(row):
    result = copy.deepcopy(row)
    result.pop("string_bigint_duration_microseconds")
    for edge in ("start", "end"):
        result[edge].pop("string_bigint_roundtrip")
    return result


def test_node_reference_was_fixed_before_production_and_covers_the_original_full_set():
    assert (
        hashlib.sha256(RAW).hexdigest()
        == "be55dfabd318b0b9702d83878a460e4cb8e5bddb98da73eedacca93913124840"
    )
    assert REF["independent_real_node_before_production"]
    assert len(REF["case_inputs"]) == 366
    assert REF["node_receipt"]["counts"]["all_original_preimage_intervals"] == 705
    assert REF["node_receipt"]["counts"]["decimal_integer_string_fields"] == 888
    assert REF["node_receipt"]["counts"]["number_collapsed_intervals"] == 30
    assert REF["node_receipt"]["counts"]["string_bigint_collapsed_intervals"] == 0


@pytest.mark.parametrize("case", REF["case_inputs"], ids=lambda row: row["id"])
def test_all_366_actual_preimages_match_the_independent_node_endpoint_results(case):
    support = local_date_support(
        case["date"], case["zone"], calendar_offset_hours=case["reference_hours"]
    )
    expected = EXPECTED[case["id"]]["intervals"]
    if not expected:
        assert "integer_transport" not in support
        return
    diagnostic = support["integer_transport"]
    assert diagnostic["intervals"] == [node_projection(r) for r in expected]
    assert diagnostic["checked_microsecond_intervals"] == len(expected)
    assert diagnostic["conversion_is_hypothetical"]
    assert not diagnostic["node_executed_for_this_request"]
    assert diagnostic["wire_epoch_values_are_decimal_strings"]
    assert diagnostic["collapsed_interval_count"] == sum(
        r["number_collapsed"] for r in expected
    )
    assert diagnostic["changed_endpoint_count"] == sum(
        edge["number_error"] != "0"
        for row in expected
        for edge in (row["start"], row["end"])
    )
    for interval in support["utc_support_intervals"]:
        for edge in ("start", "end"):
            key = edge + "_utc_epoch_microseconds"
            if key in interval:
                assert isinstance(interval[key], str)


def test_all_predeclared_positive_negative_tie_and_safe_threshold_vectors():
    from fatebridge.core.sukuyo_integer_transport import binary64_integer_diagnostic

    for expected in REF["expected"]["integer_vectors"]:
        expected = {k: v for k, v in expected.items() if k != "string_bigint_roundtrip"}
        assert binary64_integer_diagnostic(expected["exact"]) == expected


def test_unsafe_but_exact_integer_is_not_reported_as_loss_or_a_safe_integer():
    from fatebridge.core.sukuyo_integer_transport import binary64_integer_diagnostic

    row = binary64_integer_diagnostic("9007199254740992")
    assert row["number_error"] == "0"
    assert not row["number_is_safe_integer"]
    assert row["after_number"] == row["exact"]


@pytest.mark.parametrize(
    "value", [True, 3, 3.5, "", "1.0", "+1", "01", " 1", str(1 << 1024)]
)
def test_invalid_noncanonical_or_unsupported_endpoints_fail_explicitly(value):
    from fatebridge.core.sukuyo_integer_transport import binary64_integer_diagnostic

    with pytest.raises(ValueError):
        binary64_integer_diagnostic(value)


@pytest.mark.parametrize(
    "row",
    [
        {"start_utc_epoch_microseconds": "1"},
        {"end_utc_epoch_microseconds": "2"},
        {"start_utc_epoch_microseconds": "2", "end_utc_epoch_microseconds": "2"},
        {"start_utc_epoch_microseconds": "3", "end_utc_epoch_microseconds": "2"},
    ],
)
def test_missing_or_nonpositive_intervals_do_not_become_zero_loss_success(row):
    from fatebridge.core.sukuyo_integer_transport import integer_transport_diagnostic

    with pytest.raises(ValueError):
        integer_transport_diagnostic([{"calendar_date": "2000-01-01", **row}])


def test_absent_microsecond_fields_is_not_a_passing_conversion_check():
    from fatebridge.core.sukuyo_integer_transport import integer_transport_diagnostic

    assert integer_transport_diagnostic([]) is None
    assert integer_transport_diagnostic([{"calendar_date": "2000-01-01"}]) is None


def test_native_reports_actual_current_collapsed_interval_without_claiming_a_node_run():
    from fatebridge.core.sukuyo import calendar_mansion, day_evidence

    result = calendar_mansion(
        "0001-01-01",
        zone="9.0000000002777778",
        calendar_basis="japanese_naoj_historical_utc09",
    )
    first = result["date_support"]["integer_transport"]["intervals"][0]
    assert first["start"]["exact"] == "-62135629200000001"
    assert first["start"]["after_number"] == "-62135629200000000"
    assert first["exact_duration_microseconds"] == "1"
    assert first["after_number_duration_microseconds"] == "0"
    text = day_evidence(result)["reading_text"]
    assert "-62135629200000001" in text and "-62135629200000000" in text
    assert "1微秒变为0微秒" in text
    assert "本次未运行Node" in text
    assert not result["profile_calculation"][
        "candidate_set_complete_under_declared_reconstructions"
    ]

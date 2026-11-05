"""Calendar facts and actual source receipts survive adapters and same-run delivery."""

import json

import pytest

from fatebridge.application import result_delivery as delivery
from tests.astronomy.test_de440_extended import BASE, NEW, OLD, refuse_profile
from tests.evaluation import test_agentic_nested_outputs as adapters
from tests.integration.test_result_delivery import reconstruct
from tests.liuyao.test_liuyao_clash_transports import all_surfaces
from tests.liuyao.test_liuyao_transports import assert_same_run_receipt
from tests.support.transports import AS_OF, SPECS

rest = adapters.rest

CASES = json.loads((BASE / "boundary-cases.json").read_text())["cases"]
FIELDS = [
    "nongli",
    "calendar_context",
    "liuyao_evidence.calendar_conventions",
    "snapshot_text",
]


def assert_calendar(output, case):
    assert output["nongli"]["monthGanZi"][1] == case["expected_month_branch"]
    context = output["calendar_context"]
    term = context["current_solar_term"]
    assert term["name"] == case["expected_previous_term"]
    assert term["ephemeris_model"] == NEW
    assert term["solar_model_details"]["model_id"] == NEW
    assert term["solar_model_details"]["accuracy_certified"] is False
    assert term["solar_model_details"]["future_leap_seconds_assumed_unchanged"] is True
    assert (
        output["liuyao_evidence"]["calendar_conventions"]["month_branch"]
        == case["expected_month_branch"]
    )
    metadata = output["run_metadata"]
    assert NEW in metadata["provenance"]["ephemeris_model"]
    assert metadata["runtime"]["solar_term_policy"]["model_id"] == NEW
    assert metadata["runtime"]["solar_term_policy"]["auto_software_years"] == [
        1700,
        2300,
    ]


@pytest.mark.parametrize("case", CASES, ids=lambda r: r["id"])
def test_all_previous21_boundary_cases_keep_reference_facts_in_three_local_adapters(
    case, rest, tmp_path, capsys
):
    for output in all_surfaces(case["payload"], FIELDS, rest, tmp_path, capsys):
        assert_calendar(output, case)
        assert not output.get("projection_warnings")


def test_observed_extension_receipt_does_not_load_an_unused_default_profile(
    rest, monkeypatch
):
    refuse_profile(monkeypatch, OLD)
    case = CASES[0]
    response = rest.post(
        SPECS["sixyao"].rest_path,
        json=case["payload"],
        params=dict(
            as_of=AS_OF, fields=FIELDS, strict_fields="true", response_char_limit=0
        ),
    )
    assert response.status_code == 200, response.text
    assert_calendar(response.json(), case)


def test_selected_extension_fault_is_a_structured_source_error(rest, monkeypatch):
    refuse_profile(monkeypatch, NEW)
    response = rest.post(SPECS["sixyao"].rest_path, json=CASES[0]["payload"])
    assert response.status_code == 503
    body = response.json()
    assert body["retryable"] is False
    assert "solar_de440_invalid" in str(body["issues"])
    assert "liuyao_evidence" not in body


def test_mixed_year_public_receipt_names_both_actual_profiles(rest):
    payload = dict(
        date="1799-12-31",
        time="12:00:00",
        zone="UTC",
        gua_code="111111",
        changed_code="111111",
        timing_days=0,
    )
    response = rest.post(
        SPECS["sixyao"].rest_path,
        json=payload,
        params=dict(as_of=AS_OF, response_char_limit=0),
    )
    assert response.status_code == 200, response.text
    output = response.json()
    receipt = output["run_metadata"]["runtime"]["solar_term_policy"]
    assert receipt["source_resolution"] == "observed_multiple_packaged_profiles"
    assert set(receipt["observed_model_ids"]) == {OLD, NEW}
    assert "model_id" not in receipt
    assert {s["model_id"] for s in receipt["sources"]} == {OLD, NEW}


def test_same_run_full_result_preserves_new_profile_and_boundary_facts(
    rest, tmp_path, capsys, monkeypatch
):
    import fatebridge.api as api

    store = delivery.ResultStore(tmp_path / "extended-results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    case = next(c for c in CASES if c["id"] == "2260-06")
    for shaped in all_surfaces(
        case["payload"], None, rest, tmp_path, capsys, budget=8192
    ):
        result_id = shaped["result_delivery"]["result_id"]
        original = reconstruct(store, result_id)
        assert_same_run_receipt(store, shaped, original)
        assert_calendar(original, case)
        restored = reconstruct(store, result_id, "calendar_context")
        assert restored == original["calendar_context"]

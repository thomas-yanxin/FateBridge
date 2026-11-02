"""An additional whole printed table cannot certify a narrower p115 method."""

import copy

import pytest

import scripts.audit_western_lilly_merchant as merchant


@pytest.fixture(scope="module")
def audited():
    return merchant.audit()


def test_complete_eight_entry_source_arithmetic_is_retained(audited):
    assert audited["printed_planet_applications"] == 7
    assert audited["printed_fortune_application"] == 1
    assert audited["all_eight_printed_arithmetic_sums_match"]
    assert {r["planet"] for r in audited["comparisons"]} == {
        "Saturn",
        "Jupiter",
        "Mars",
        "Sun",
        "Venus",
        "Mercury",
        "Moon",
    }
    assert audited["fortune"]["calculated_reproduction"] is None


def test_explicit_domicile_and_term_accumulation_rejects_maximum_only(audited):
    value = audited["essential_positive_additivity"]
    assert [(r["code"], r["expected"]) for r in value["printed_rows"]] == [
        ("E01", 5),
        ("E04", 2),
    ]
    assert value["printed_sum"] == value["calculated_sum"] == 7
    assert value["maximum_only_counterfactual"] == 5
    assert not value["global_maximum_only_supported"]
    assert not value["sun_leo_omission_resolved"]


def test_minute_printed_cazimi_example_preserves_exact_nominal_endpoint(audited):
    value = audited["printed_cazimi_control"]
    assert value["nominal_separation_arcminutes"] == "17"
    assert (
        value["printed_classification"]
        == value["calculated_classification"]
        == "cazimi"
    )
    assert value["minute_quantized_source_not_subminute_observational_bound"]


@pytest.mark.parametrize("name", ["Sun", "Venus", "Mercury"])
def test_printed_book3_house_four_point_debit_is_not_hidden_or_fitted(name, audited):
    row = next(r for r in audited["comparisons"] if r["planet"] == name)
    debit = next(r for r in row["known_row_differences"] if r["code"] == "D02")
    assert debit["printed_contribution"] == -4
    assert debit["p115_contribution"] == -2


def test_missing_motion_nodes_and_stars_do_not_become_complete_totals(audited):
    for row in audited["comparisons"]:
        codes = {c["code"] for c in row["unknown_rows"]}
        assert {"F07", "D04", "F14", "D11", "F17", "F18", "D15"} <= codes
        assert row["p115_literal_balance"] is None
        assert not row["full_reproduced"]
    assert not audited["numeric_daily_motion_invented"]
    assert not audited["unknown_rows_converted_to_zero"]
    assert not audited["full_worked_case_reproduction_passed"]
    assert not audited["original_p177_seven_application_gate_replaced"]
    assert not audited["full_original_text_acceptance"]


def test_complete_p115_row_comparison_retains_other_known_disagreements(audited):
    rows = {
        r["planet"]: {x["code"] for x in r["known_row_differences"]}
        for r in audited["comparisons"]
    }
    assert rows["Sun"] == {"F13", "D02"}
    assert rows["Mercury"] == {"E08", "D02", "D06"}
    assert rows["Moon"] == {"D12"}


def test_changing_an_actual_dignity_cannot_pass_by_source_transcription(monkeypatch):
    original = merchant.evaluate_fortitudes

    def wrong(*args, **kwargs):
        result = copy.deepcopy(original(*args, **kwargs))
        term = next(r for r in result["planets"]["Venus"]["rows"] if r["code"] == "E04")
        term["contribution"] = 0
        return result

    monkeypatch.setattr(merchant, "evaluate_fortitudes", wrong)
    result = merchant.audit()["essential_positive_additivity"]
    assert result["printed_sum"] == 7 and result["calculated_sum"] == 5
    assert not all(r["matched"] for r in result["printed_rows"])


def test_old_five_degree_stellar_diagnosis_cannot_describe_current_six_degree_rule(
    audited,
):
    value = audited["prior_regulus_resolution"]
    old = value["prior_diagnosis"]
    assert old["coarse_five_degree_condition"] is True
    assert old["minute_five_degree_condition"] is False
    rows = value["current_rule_controls"]
    assert [r["gap_arcminutes"] for r in rows] == ["293", "327"]
    assert all(r["current_orb_degrees"] == 6 for r in rows)
    assert all(r["current_condition"] and r["current_moon_balance"] == 2 for r in rows)
    assert not value["original_fixture_replaced"]
    assert not value["source_acceptance_passed"]

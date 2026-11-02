"""Interaction checks retain thin branches, textual ambiguity and adverse controls."""

import copy
import hashlib
import json
from collections import Counter

import pytest

from fatebridge.core.sukuyo import calendar_mansion
from scripts import check_sukuyo_boundary_composition as audit


@pytest.fixture(scope="module")
def selected():
    wanted = {
        ("japanese_naoj_historical_utc09", value)
        for value in (
            "0801-02-21",
            "0806-07-23",
            "0814-08-23",
            "0817-05-24",
            "0814-09-21",
        )
    } | {
        ("chinese_hko_utc08", "2025-01-29"),
        ("japanese_hutime_1002_1_utc09", "1872-02-09"),
    }
    return [
        r for r in audit.source_expectations()[0] if (r["basis"], r["date"]) in wanted
    ]


def calculate(row):
    return calendar_mansion(
        row["date"],
        zone=row["zone"],
        calendar_basis=row["basis"],
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part=None if row["half"] == "None" else row["half"],
    )


def test_original_domain_composed_in_full_before_comparison():
    protocol_raw = audit.PROTOCOL.read_bytes()
    assert audit.monthly.sha(protocol_raw) == audit.PROTOCOL_SHA256
    protocol = json.loads(protocol_raw)
    digest, counts = hashlib.sha256(), Counter()
    for row in audit.source_expectations()[0]:
        digest.update(audit.encode(row))
        counts[row["basis"]] += 1
    assert counts == protocol["counts"]
    assert sum(counts.values()) == 165486
    assert digest.hexdigest() == protocol["oracle_sha256"]
    assert protocol["original_protocol_sha256"] == audit.monthly.PROTOCOL_SHA256
    assert protocol["classes"]["excluded_date_cases"] == 3
    assert protocol["classes"]["incomplete_candidate_cases"] == 5


def test_all_selected_hosts_halves_and_edge_directions(selected):
    assert len(selected) == 42
    for row in selected:
        assert not audit.compare_case(row, calculate(row)), row["id"]


@pytest.mark.parametrize(
    "mutation",
    [
        "thin_date",
        "thin_interval",
        "epoch_number",
        "false_complete",
        "lunar_year",
        "second_half",
        "priority",
    ],
)
def test_corrupted_evidence_cannot_hide_behind_same_merged_mansions(selected, mutation):
    if mutation == "false_complete":
        row = next(r for r in selected if r["excluded"])
    else:
        row = next(
            r
            for r in selected
            if r["date"] == "0806-07-23"
            and r["half"] == "first_half"
            and r["zone"].startswith("9.")
        )
    result = copy.deepcopy(calculate(row))
    if mutation == "thin_date":
        result["date_support"]["possible_calendar_dates"].pop(0)
    elif mutation == "thin_interval":
        result["date_support"]["utc_support_intervals"].pop(0)
    elif mutation == "epoch_number":
        interval = result["date_support"]["utc_support_intervals"][0]
        interval["start_utc_epoch_microseconds"] = int(
            interval["start_utc_epoch_microseconds"]
        )
    elif mutation == "false_complete":
        result["profile_calculation"][
            "candidate_set_complete_under_declared_reconstructions"
        ] = True
    else:
        branch = next(b for b in result["calendar_candidates"] if b["lunar_day"] == 1)
        if mutation == "lunar_year":
            branch["lunar_year"] += 1
        elif mutation == "second_half":
            branch["profile_calculation"]["short_month_assignment"]["slots"][1][
                "candidate_mansions"
            ] = ["星"]
        else:
            branch["profile_calculation"]["short_month_assignment"][
                "leap_short_month_precedence"
            ]["source_rule_priority_established"] = True
    assert audit.compare_case(row, result)


def test_narrowed_passing_domain_is_rejected_before_calculation(tmp_path, monkeypatch):
    changed = json.loads(audit.PROTOCOL.read_bytes())
    changed["counts"]["japanese_naoj_historical_utc09"] -= 1
    replacement = tmp_path / "narrowed.json"
    replacement.write_bytes(audit.encode(changed))
    monkeypatch.setattr(audit, "PROTOCOL", replacement)
    with pytest.raises(ValueError, match="Fixed composition protocol changed"):
        audit.verify_all()


@pytest.mark.parametrize(
    "mutation", ["first_calculation", "second_calculation", "model_previous_year"]
)
def test_each_reconstruction_must_carry_its_actual_inputs_and_both_calculations(
    selected, mutation
):
    row = next(
        r
        for r in selected
        if r["date"] == "0806-07-23"
        and r["half"] == "first_half"
        and r["zone"].startswith("9.")
    )
    result = copy.deepcopy(calculate(row))
    center = next(b for b in result["calendar_candidates"] if b["lunar_day"] == 1)
    models = center["profile_calculation"]["short_month_assignment"][
        "leap_short_month_precedence"
    ]["reconstruction_calculations"]
    if mutation == "first_calculation":
        models[0]["first_half_calculation"]["direct_mansion"] = "室"
    elif mutation == "second_calculation":
        models[1]["second_half_calculation"]["lunar_month"] = 5
    else:
        models[1]["previous_lunar"]["lunar_year"] += 1
    assert audit.compare_case(row, result)

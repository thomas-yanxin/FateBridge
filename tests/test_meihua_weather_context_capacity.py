"""Independent small-N bounds and frozen counterfactuals, never real outcomes."""

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from fatebridge.validation import meihua_weather_context_capacity as capacity
from fatebridge.validation.meihua_weather_feasibility import (
    attainable_binary_skill_bound,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/meihua_weather_context_capacity_v1"
PLAN = json.loads((FIXTURE / "plan.json").read_bytes())
BOUNDS = json.loads((FIXTURE / "independent-capacity-bounds125.json").read_bytes())
COMMITMENTS = json.loads((FIXTURE / "producer-commitments2880.json").read_bytes())
GEOMETRY = json.loads((FIXTURE / "noon-geometry24.json").read_bytes())
CLAUSES = json.loads((FIXTURE / "prior-source-clauses.json").read_bytes())


def test_source_context_domain_and_brute_force_bound_were_frozen_before_producer():
    ref = json.loads((FIXTURE / "reference-freeze.json").read_bytes())
    producer = json.loads((FIXTURE / "producer-freeze.json").read_bytes())
    assert not ref["new_module_present"] and not ref["producer_executed"]
    assert not producer["new_module_present"]
    assert producer["all_old120_noon_trace_and_decision_hashes_match"] == 120
    assert producer[
        "producer_is_drift_reference_not_independent_source_or_reality_oracle"
    ]
    assert producer["not_blind_to_old_negative_results"]
    for name, sha in ref["files"].items():
        if name == "git-before.z":
            continue  # Raw Git state is retained in the sealed supporting archive.
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == sha
    assert (
        hashlib.sha256(
            (FIXTURE / "producer-commitments2880.json").read_bytes()
        ).hexdigest()
        == producer["files_sha256"]["references/producer-commitments2880.json"]
    )
    assert PLAN["formula_predeclared_before_new_producer_probe"]
    assert PLAN["exhaustive_symbolic_case_count"] == 2880
    assert PLAN["new_real_world_observations"] == 0
    assert len(BOUNDS) == 125


@pytest.mark.parametrize(
    "case",
    BOUNDS,
    ids=lambda c: f"{c['rain_only']}:{c['dry_only']}:{c['both']}:{c['only_abstain']}",
)
def test_exact_oracle_bound_matches_preimplementation_bruteforce(case):
    variants = (
        [["rain", "abstain"]] * case["rain_only"]
        + [["dry", "abstain"]] * case["dry_only"]
        + [["rain", "dry", "abstain"]] * case["both"]
        + [["abstain"]] * case["only_abstain"]
    )
    ids = [f"case{i}" for i in range(len(variants))]
    actual = capacity.context_oracle_credit_bound(
        ids, dict(zip(ids, variants, strict=True))
    )
    assert actual["exact_maximum_margin_over_better_constant"] == case["maximum_margin"]
    assert actual["cohort_days"] == len(variants)
    assert actual["cannot_strictly_beat_better_constant_even_with_context_oracle"] == (
        case["maximum_margin"] <= 0
    )
    assert not actual["oracle_is_an_admissible_forecasting_method"]
    assert not actual["outcome_data_used"]
    assert actual["observed_accuracy"] is None
    assert not actual["predictive_efficacy_established"]
    witness = case["witness"]
    if witness is None:
        # The frozen brute-force initializer tied its optimum for N=1,
        # all-abstain. Keep the original scalar and null witness unchanged.
        assert [case[k] for k in ["rain_only", "dry_only", "both", "only_abstain"]] == [
            0,
            0,
            0,
            1,
        ]
        assert case["maximum_margin"] == -1
        witness = {"forecast_correct_credit": 0, "better_constant_credit": 1}
    assert (
        witness["forecast_correct_credit"] - witness["better_constant_credit"]
        == case["maximum_margin"]
    )


def test_singleton_capabilities_reduce_to_the_unchanged_original_fixed_vector_bound():
    forecasts = {"a": "rain", "b": "dry", "c": "abstain", "d": "rain"}
    actual = capacity.context_oracle_credit_bound(
        list(forecasts), {key: [value] for key, value in forecasts.items()}
    )
    old = attainable_binary_skill_bound(list(forecasts), forecasts)
    assert (
        actual["exact_maximum_margin_over_better_constant"]
        == old["exact_maximum_margin_over_better_constant"]
    )
    assert actual["oracle_forecast_counts_witness"] == old["forecast_counts"]


@pytest.mark.parametrize(
    "ids,values",
    [
        ([], {}),
        (["a", "a"], {"a": ["rain"]}),
        (["a"], {}),
        (["a"], {"a": []}),
        (["a"], {"a": "rain"}),
        (["a"], {"a": [None]}),
        (["a"], {"a": [True]}),
        (["a"], {"a": ["rain", "rain"]}),
        (["a"], {"a": ["missing"]}),
        (["a"], {"a": ["rain"], "b": ["dry"]}),
    ],
)
def test_missing_duplicate_and_unknown_capabilities_never_shrink_the_cohort(
    ids, values
):
    with pytest.raises(ValueError):
        capacity.context_oracle_credit_bound(ids, values)


def test_restricting_the_context_options_cannot_raise_this_optimistic_bound():
    ids = ["a", "b", "c", "d", "e"]
    broad = {key: ["rain", "dry", "abstain"] for key in ids}
    restricted = {
        "a": ["rain"],
        "b": ["dry"],
        "c": ["abstain"],
        "d": ["abstain"],
        "e": ["abstain"],
    }
    assert (
        capacity.context_oracle_credit_bound(ids, restricted)[
            "exact_maximum_margin_over_better_constant"
        ]
        <= capacity.context_oracle_credit_bound(ids, broad)[
            "exact_maximum_margin_over_better_constant"
        ]
    )
    assert restricted["c"] == ["abstain"]


@pytest.fixture(scope="module")
def domain():
    return capacity.audit_noon_context_domain()


def test_all2880_new_rows_keep_frozen_before_geometry_trace_and_decision_commitments(
    domain,
):
    assert len(domain["rows"]) == 2880
    assert domain["source_guard_held"]
    assert domain["context_patterns"] == 120
    assert domain["fixed_hour_branch"] == "午"
    assert not domain["hour_selection_performed"]
    for actual, old in zip(domain["rows"], COMMITMENTS, strict=True):
        assert actual["geometry"] == old["geometry"]
        assert actual["context"] == old["context"]
        assert actual["trace_sha256"] == old["trace_sha256"]
        assert actual["decision_sha256"] == old["decision_sha256"]
    assert domain["context_values_are_counterfactual_not_actual_observations"]
    assert domain["unknown_prior_is_not_neither"]
    assert not domain["number_of_days_for_久_inferred"]
    assert not domain["threshold_is_unique_original_text_rule"]
    assert not domain["real_calendar_date_witness_established"]
    assert not domain["predictive_efficacy_established"]


def test_all24_context_summaries_keep_all_five_seasons_and_never_select_a_winner(
    domain,
):
    assert len(domain["all24_prior_threshold_summaries"]) == 24
    assert {
        (r["prior_condition"], r["many_min_count"])
        for r in domain["all24_prior_threshold_summaries"]
    } == {(p, m) for p in capacity.PRIORS for m in capacity.THRESHOLDS}
    for row in domain["all24_prior_threshold_summaries"]:
        assert (
            sum(row["label_counts"].values())
            == row["cases_including_all5_season_states"]
            == 120
        )
    assert (
        sum(
            row["label_counts"]["rain"]
            for row in domain["all24_prior_threshold_summaries"]
            if row["prior_condition"] is None and row["many_min_count"] is None
        )
        == 0
    )


@pytest.mark.parametrize(
    "prior", [None, "prolonged_rain", "prolonged_clear", "neither_prolonged"]
)
def test_three_literal_prior_clauses_distinguish_unknown_from_confirmed_false(
    domain, prior
):
    decode = dict(
        zip(
            ["111", "110", "101", "100", "011", "010", "001", "000"],
            "乾兑离震巽坎艮坤",
            strict=True,
        )
    )
    rules = {r["id"]: r for r in CLAUSES if "present" in r["conditions"]}
    assert len(rules) == 3
    for row in domain["rows"]:
        if row["context"] != {
            "season": None,
            "prior_condition": prior,
            "many_min_count": None,
        }:
            continue
        g = row["geometry"]
        present = {
            decode[g[key][offset : offset + 3]]
            for key in ["base_code", "mutual_code", "changed_code"]
            for offset in [0, 3]
        }
        for clause in row["prior_clause_qualifications"]:
            if clause["rule_id"] not in rules:
                continue
            rule = rules[clause["rule_id"]]
            structural = all(name in present for name in rule["conditions"]["present"])
            expected = (
                "not_met"
                if not structural
                else (
                    "pending_context"
                    if prior is None
                    else (
                        "matched"
                        if prior == rule["conditions"]["prior_condition"]
                        else "not_met"
                    )
                )
            )
            assert clause["status"] == expected


def test_math_capacity_abstentions_keep_original_zero_correct_credit():
    ids = [str(i) for i in range(273)]
    capabilities = {
        key: ["rain", "dry", "abstain"] if int(key) < 77 else ["abstain"] for key in ids
    }
    result = capacity.context_oracle_credit_bound(ids, capabilities)
    assert result["maximum_possible_categorical_days"] == 77
    assert result["exact_maximum_margin_over_better_constant"] == -60
    assert result["cannot_strictly_beat_better_constant_even_with_context_oracle"]


@pytest.mark.parametrize("kind", ["inside", "existing", "hardlink", "symlink"])
def test_cli_output_guards_protect_the_original_study_and_existing_reports(
    kind, tmp_path
):
    study = tmp_path / "study"
    study.mkdir()
    original = study / "evidence.json"
    original.write_text("immutable")
    output = study / "new.json" if kind == "inside" else tmp_path / "report.json"
    if kind == "existing":
        output.write_text("existing")
    elif kind == "hardlink":
        output.hardlink_to(original)
    elif kind == "symlink":
        output.symlink_to(original)
    run = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/audit_meihua_weather_context_capacity.py"),
            "--study",
            str(study),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    assert run.returncode == 2
    assert "new file outside" in run.stderr
    assert original.read_text() == "immutable"


def test_capacity_bound_does_not_mutate_or_fill_supplied_context_capabilities():
    values = {"a": ["rain", "abstain"], "b": ["dry"]}
    saved = copy.deepcopy(values)
    capacity.context_oracle_credit_bound(["a", "b"], values)
    assert values == saved

"""Edition-specific day evidence and exact, conditional phase diagnostics."""

import copy
import hashlib
import json
import shutil
import subprocess
import sys
from fractions import Fraction

import pytest

from fatebridge.validation.taiyi_epoch import mean_origin_hypothesis
from scripts.audit_taiyi_origin_phase import audit
from scripts.taiyi_origin_sources import (
    CORPUS,
    FREEZE_SHA256,
    ROOT,
    read_origin_sources,
)


@pytest.fixture(scope="module")
def report():
    return audit()


def fraction(value):
    return Fraction(value["numerator"], value["denominator"])


def parameters():
    return dict(
        year_accumulation=1937061,
        chapter_years=657,
        chapter_months=8126,
        month_numerator=1447,
        day_denominator=49,
        qi_denominator=32193,
        annual_residue_numerator=168842,
        month_year_shift=-1,
        solstice_year_shift=-1,
        whole_cycle_days_per_year=360,
    )


def test_new_correction_is_not_a_rewritten_old_source_or_blind_case():
    source = read_origin_sources()
    frozen = json.loads((CORPUS / "freeze.json").read_text())
    assert (
        hashlib.sha256((CORPUS / "freeze.json").read_bytes()).hexdigest()
        == FREEZE_SHA256
    )
    assert len(frozen["prior_sources"]) == 48
    assert frozen["new_production_comparisons_before_freeze"] == 0
    assert (
        not frozen["blinded"]
        and not frozen["original_source_or_prior_outputs_overwritten"]
    )
    tokens = source["day_tokens"]
    assert tokens["ncl_ming"]["anecdote_literal"].count("甲申") == 2
    assert "六月八日甲申" in tokens["ncl_ming"]["anecdote_literal"]
    assert tokens["siku"]["explicit_day_ganzhi"] is None
    assert tokens["siku"]["anecdote_literal"].count("甲申") == 1
    old = json.loads(
        (ROOT / "tests/fixtures/taiyi_jinjing_v31/readings.json").read_text()
    )
    assert (
        source["old_overbroad_statement"]["literal"]
        in old["predeclared_comparison"]["scope"]
    )


@pytest.mark.parametrize("rewrite_manifest", [False, True])
def test_cannot_replace_explicit_day_to_make_the_nearest_candidate_match(
    tmp_path, rewrite_manifest
):
    corpus = tmp_path / "corpus"
    shutil.copytree(CORPUS, corpus)
    path = corpus / "readings.json"
    data = json.loads(path.read_text())
    data["day_tokens"]["ncl_ming"]["explicit_day_ganzhi"] = "癸未"
    path.write_text(json.dumps(data))
    if rewrite_manifest:
        frozen = json.loads((corpus / "freeze.json").read_text())
        frozen["files"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        (corpus / "freeze.json").write_text(json.dumps(frozen))
    with pytest.raises(ValueError, match="V33"):
        read_origin_sources(corpus)


def test_prior_calendar_and_reports_are_pinned_too(tmp_path):
    frozen = json.loads((CORPUS / "freeze.json").read_text())
    for name in frozen["prior_sources"]:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    path = tmp_path / "tests/fixtures/taiyi_jinjing_v28/liang-504-months.json"
    data = json.loads(path.read_text())
    data["months"][5]["printed_cycle_base"] += 1
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="V33.*prior evidence"):
        read_origin_sources(root=tmp_path)


def test_given_accumulation_matches_the_ming_day_only_under_one_numbering(report):
    rows = report["given_source_day_labels"]
    assert [
        (r["jiazi_origin"], r["day_ganzhi"], r["matches_ming_explicit_day"])
        for r in rows
    ] == [(0, "乙酉", False), (1, "甲申", True)]
    assert all(r["matches_explicit_siku_day"] is None for r in rows)
    days = report["printed_calendar_selected_days_from_frozen_v28_report"]
    assert [(r["day"], r["day_ganzhi"]) for r in days] == [(8, "癸未"), (9, "甲申")]
    assert report["old_calendar_rows_retained"] == 355
    assert report["old_calendar_report_is_new_independent_observation"] is False


def test_all_old_serial_fields_and_failures_remain_with_new_day_constraint(report):
    old = json.loads(
        (ROOT / "docs/validation/taiyi-jinjing-v32/report.json").read_text()
    )
    rows = report["all_eight_retained_serial_cohorts"]
    assert len(rows) == 8
    for previous, current in zip(
        old["full_lunation_cohort_hypotheses"], rows, strict=True
    ):
        assert {
            k: v for k, v in current.items() if k != "new_explicit_ming_day_constraint"
        } == previous
        assert len(current["records"]) == 13
        assert (
            sum(r["month_length_matches"] is not None for r in current["records"]) == 12
        )
        assert not current["all_listed_calendar_constraints_match"]
        assert len(current["new_explicit_ming_day_constraint"]) == 2
    assert (
        sum(
            r["matches_ming_explicit_day"]
            for row in rows
            for r in row["new_explicit_ming_day_constraint"]
        )
        == 0
    )
    near = next(
        r
        for r in rows
        if r["edition"] == "ncl_ming"
        and r["year_shift"] == -1
        and r["extra_preceding_lunation"] == 0
    )
    assert near["matching_month_lengths"] == 10
    assert near["matching_first_labels_by_origin"] == {"0": 12, "1": 0}
    assert [
        r["candidate_day_ganzhi"] for r in near["new_explicit_ming_day_constraint"]
    ] == ["癸未", "壬午"]


def test_remainder_units_and_conditional_absolute_lift_are_not_collapsed(report):
    full, completed = report["phase_hypotheses"]
    assert (full["month_year_shift"], completed["month_year_shift"]) == (0, -1)
    assert (
        completed["chapter_remainder"],
        completed["chapter_remainder_denominator"],
    ) == (334, 657)
    assert (
        completed["initial_day_small_remainder"],
        completed["initial_day_small_remainder_denominator"],
    ) == (41, 49)
    assert fraction(completed["same_year_annual_minus_newmoon"]) == Fraction(
        334 * 1447, 657 * 49
    )
    assert fraction(completed["exact_initial_newmoon"]) % 1 == Fraction(41, 49)
    assert fraction(full["unwrapped_solstice_minus_newmoon"]) < 0
    assert (
        0
        <= fraction(completed["unwrapped_solstice_minus_newmoon"])
        < Fraction(1447, 49)
    )
    assert [r["conditional_solstice_in_mean_month"] for r in (full, completed)] == [
        False,
        True,
    ]
    # Both pass modulo60: residues alone cannot decide the annual origin.
    assert all(r["modulo60_interval_within_one_mean_month"] for r in (full, completed))
    assert all(
        not r["unwrapped_epoch_adjudicated"]
        and not r["production_year_reading_selected"]
        for r in (full, completed)
    )


def test_literal_annual_identity_does_not_force_a_calendar_name_to36525():
    args = parameters()
    before = copy.deepcopy(args)
    result = mean_origin_hypothesis(**args)
    assert args == before and result["source_annual_identity_holds"]
    annual = Fraction(8126 * 1447, 657 * 49)
    assert annual == 360 + Fraction(168842, 32193)
    assert annual != Fraction(1461, 4)
    args["whole_cycle_days_per_year"] = 300
    incompatible = mean_origin_hypothesis(**args)
    assert not incompatible["source_annual_identity_holds"]
    assert not incompatible["conditional_solstice_in_mean_month"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("year_accumulation", True),
        ("chapter_years", 0),
        ("chapter_months", -1),
        ("month_numerator", 1.5),
        ("day_denominator", False),
        ("qi_denominator", 0),
        ("annual_residue_numerator", "168842"),
        ("month_year_shift", -2),
        ("solstice_year_shift", True),
        ("whole_cycle_days_per_year", 0),
        ("whole_cycle_days_per_year", 365),
    ],
)
def test_implicit_or_invalid_units_are_rejected(field, value):
    args = parameters()
    args[field] = value
    with pytest.raises(ValueError, match="Explicit exact mean-origin"):
        mean_origin_hypothesis(**args)


def test_current_old_auditors_correct_the_unqualified_absence_without_regrading():
    from scripts.audit_taiyi_day_epoch import audit as day_audit
    from scripts.audit_taiyi_liang_collation import audit as liang_audit

    day, liang = day_audit(), liang_audit()
    assert "jinjing_explicit_year_ganzhi_is_not_explicit_day_ganzhi" not in liang
    for report in (day, liang):
        tokens = report["jinjing_date_token_evidence"]
        assert tokens["by_edition"]["ncl_ming"]["explicit_day_ganzhi"] == "甲申"
        assert tokens["by_edition"]["siku"]["explicit_day_ganzhi"] is None
        assert tokens["earlier_unqualified_absence_claim_corrected"]
        assert not report["whole_goal_complete"]
    old = json.loads(
        (ROOT / "docs/validation/taiyi-jinjing-v31/report.json").read_text()
    )
    assert old["jinjing_explicit_year_ganzhi_is_not_explicit_day_ganzhi"] is True
    assert (
        liang["all_six_candidate_comparisons"] == old["all_six_candidate_comparisons"]
    )
    assert [
        r["matches_ncl_ming_explicit_day"]
        for r in day["original_accumulation_day_labels"]
    ] == [False, True]
    assert day["hypotheses_matching_original_accumulation"] == 0
    assert day["hypothesis_convention_pairs_matching_Liang_day"] == 1


def test_unparsed_siku_and_full_goal_remain_unresolved(report, tmp_path):
    assert report["siku_phase"]["annual_residue_numerator"] is None
    assert report["siku_phase"]["status"] == "unresolved"
    assert report["new_complete_dated_classical_cases_passed"] == 0
    assert (
        not report["whole_calendar_acceptance_passed"]
        and not report["whole_goal_complete"]
    )
    outputs = []
    for entry in (
        [str(ROOT / "scripts/audit_taiyi_origin_phase.py")],
        ["-m", "scripts.audit_taiyi_origin_phase"],
    ):
        path = tmp_path / f"report{len(outputs)}.json"
        result = subprocess.run(
            [sys.executable, *entry, "--output", str(path)],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        assert result.returncode == 1 and not result.stderr
        outputs.append(path.read_bytes())
    assert outputs[0] == outputs[1]

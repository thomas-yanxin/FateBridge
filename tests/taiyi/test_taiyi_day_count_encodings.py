"""External phase controls, coupled representations and all old failures."""

import hashlib
import json
import shutil
import subprocess
import sys

import pytest

from fatebridge.validation.taiyi_epoch import (
    decode_day_counter,
    lunar_day_counter_views,
    sexagenary_hypothesis,
)
from scripts.taiyi.audit_taiyi_day_count_encodings import (
    CORPUS,
    FREEZE_SHA256,
    ROOT,
    audit,
    verify_sources,
)

LITERATURE = json.loads((CORPUS / "literature-controls.json").read_text())
WITNESSES = [
    (row, LITERATURE["lin2008"]["epoch_ganzhi"])
    for row in LITERATURE["lin2008"]["rows"]
] + [(row, row["epoch_ganzhi"]) for row in LITERATURE["gao2009"]["rows"]]


@pytest.fixture(scope="module")
def report():
    return audit()


def test_new_source_controls_precede_implementation_and_are_not_taiyi_cases():
    frozen = verify_sources()
    assert (
        hashlib.sha256((CORPUS / "freeze.json").read_bytes()).hexdigest()
        == FREEZE_SHA256
    )
    assert len(frozen["files"]) == 3 and len(frozen["prior_sources"]) == 52
    assert not frozen["new_counter_normalization_implementation_before_freeze"]
    assert frozen["new_production_core_comparisons_before_freeze"] == 0
    assert not frozen["blinded"]
    assert not list(CORPUS.glob("*.pdf"))
    assert len(LITERATURE["lin2008"]["rows"]) == 25
    assert sum(r["leap"] for r in LITERATURE["lin2008"]["rows"]) == 1
    assert (
        LITERATURE["gao2009"]["other_unit_retained"]["counted_as_day_phase_case"]
        is False
    )
    assert [r["month_numerator_as_printed"] for r in LITERATURE["gao2009"]["rows"]] == [
        2392,
        2393,
    ]
    assert LITERATURE["gao2009"]["2392_vs2393_adjudicated"] is False


@pytest.mark.parametrize("row,epoch", WITNESSES)
def test_all27_published_phase_labels_survive_a_coupled_change_of_representation(
    row, epoch
):
    phase = row["phase_remainder"]
    zero = decode_day_counter(phase, encoding="completed_days", epoch_ganzhi=epoch)
    one = decode_day_counter(
        phase + 1, encoding="one_based_day_number", epoch_ganzhi=epoch
    )
    assert zero["day_ganzhi"] == one["day_ganzhi"] == row["expected_ganzhi"]
    assert zero["completed_days"] == one["completed_days"] == phase
    if phase:
        # Keeping the same integer while changing its encoding changes the day.
        uncoupled = decode_day_counter(
            phase, encoding="one_based_day_number", epoch_ganzhi=epoch
        )
        assert uncoupled["day_ganzhi"] != row["expected_ganzhi"]


@pytest.mark.parametrize(
    "value,encoding,label",
    [
        (0, "completed_days", "甲子"),
        (1, "one_based_day_number", "甲子"),
        (59, "completed_days", "癸亥"),
        (60, "one_based_day_number", "癸亥"),
        (60, "completed_days", "甲子"),
        (61, "one_based_day_number", "甲子"),
    ],
)
def test_zero_origin_and_rollover_are_not_silently_changed(value, encoding, label):
    result = decode_day_counter(value, encoding=encoding, epoch_ganzhi="甲子")
    assert result["day_ganzhi"] == label
    assert not result["source_encoding_adjudicated"]
    assert not result["absolute_epoch_identity_adjudicated"]


@pytest.mark.parametrize(
    "value,encoding,epoch",
    [
        (True, "completed_days", "甲子"),
        (-1, "completed_days", "甲子"),
        (0, "one_based_day_number", "甲子"),
        (1.0, "completed_days", "甲子"),
        ("1", "completed_days", "甲子"),
        (1, "auto", "甲子"),
        (1, "completed_days", "甲丑"),
        (1, "completed_days", None),
    ],
)
def test_encoding_and_epoch_must_be_explicit_and_valid(value, encoding, epoch):
    with pytest.raises(ValueError, match="Explicit"):
        decode_day_counter(value, encoding=encoding, epoch_ganzhi=epoch)


@pytest.mark.parametrize("day", [0, 31, True, "8", 8.5])
def test_lunar_day_is_an_ordinal_not_an_elapsed_offset(day):
    with pytest.raises(ValueError, match="Explicit lunar day ordinal"):
        lunar_day_counter_views(
            100, day, month_start_encoding="completed_days", epoch_ganzhi="甲子"
        )


def test_counter_epoch_name_does_not_make_different_actual_origins_equal():
    first = decode_day_counter(0, encoding="completed_days", epoch_ganzhi="甲子")
    later = decode_day_counter(60, encoding="completed_days", epoch_ganzhi="甲子")
    assert first["day_ganzhi"] == later["day_ganzhi"]
    assert first["completed_days"] != later["completed_days"]
    assert not first["absolute_epoch_identity_adjudicated"]


@pytest.mark.parametrize("rewrite_manifest", [False, True])
def test_cannot_change_a_published_label_by_updating_a_local_manifest(
    tmp_path, rewrite_manifest
):
    corpus = tmp_path / "corpus"
    shutil.copytree(CORPUS, corpus)
    path = corpus / "literature-controls.json"
    data = json.loads(path.read_text())
    data["lin2008"]["rows"][17]["expected_ganzhi"] = "乙酉"
    path.write_text(json.dumps(data))
    if rewrite_manifest:
        freeze = json.loads((corpus / "freeze.json").read_text())
        freeze["files"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        (corpus / "freeze.json").write_text(json.dumps(freeze))
    with pytest.raises(ValueError, match="V34"):
        verify_sources(corpus)


def test_both_initial_encodings_keep_all355_dates_and_all13_firsts(report):
    assert len(report["all_eight_legacy_cohorts"]) == 8
    series = report["whole_calendar_encoding_series"]
    assert len(series) == 16
    for row in series:
        assert row["required_days"] == len(row["records"]) == 355
        assert len(row["month_firsts"]) == 13
        assert row["legacy_joint_flag_is_not_reused_as_typed_gate"]
        assert not row["all_typed_calendar_observations_match"]
        for day in row["records"]:
            assert day["completed_days"] + 1 == day["one_based_day_number"]
            assert day["representations_agree"]
            assert (
                sexagenary_hypothesis(day["completed_days"], jiazi_origin=0)
                == day["actual_ganzhi"]
            )
            assert (
                sexagenary_hypothesis(day["one_based_day_number"], jiazi_origin=1)
                == day["actual_ganzhi"]
            )
    near = next(
        r
        for r in series
        if r["cohort_index"] == 2 and r["initial_encoding"] == "completed_days"
    )
    assert near["matching_day_labels"] == 326
    assert near["valid_matching_dates"] == 325
    assert {r["month"] for r in near["records"] if not r["day_label_matches"]} == {3}
    assert sum(not r["day_label_matches"] for r in near["records"]) == 29
    nonexistent = [r for r in near["records"] if not r["ordinal_exists_in_hypothesis"]]
    assert len(nonexistent) == 1
    assert (nonexistent[0]["month"], nonexistent[0]["day"]) == (2, 30)
    assert (
        nonexistent[0]["day_label_matches"]
        and not nonexistent[0]["calendar_day_matches"]
    )
    assert not near["all12_month_lengths_match"]


def test_matching_old_integer_on_day9_cannot_replace_day8_or_xing22(report):
    cases = report["date_encoding_candidates"]
    assert len(cases) == 48 and sum(len(r["counter_comparisons"]) for r in cases) == 96
    matched = [
        (r, v)
        for r in cases
        for v in r["counter_comparisons"]
        if v["matches_quoted_original_integer"]
    ]
    assert len(matched) == 1
    row, view = matched[0]
    assert (
        row["edition"],
        row["year_shift"],
        row["extra_preceding_lunation"],
        row["initial_encoding"],
        row["lunar_day"],
    ) == ("ncl_ming", -1, 0, "completed_days", 9)
    assert view["encoding"] == "one_based_day_number" and view["value"] == 707501061
    assert row["normalized"]["day_ganzhi"] == "甲申"
    assert not row["observations"]["is_original_literal_day8"]
    assert row["observations"]["is_xing_corrected_day9"]
    assert row["one_based_in_cycle_remainder_under_old_assumption"] == 21
    assert not row["observations"][
        "matches_shoushi22_under_same_raw_remainder_assumption"
    ]
    assert not row["source_corrected_absolute_accumulation_stated"]
    assert row["matches_xing_corrected_absolute_accumulation"] is None
    assert row["board"]["matching_fields"] == 9
    mismatched = [r for r in row["board"]["observations"] if not r["matches"]]
    assert mismatched == [
        {"field": "shiji", "source": "卯", "actual": "酉", "matches": False}
    ]
    assert not view["all_original_observed_constraints_match"]
    assert not view["all_xing_observed_constraints_match"]
    assert (
        report["original_observed_joint_matches"]
        == report["xing_observed_joint_matches"]
        == 0
    )
    for candidate in cases:
        assert len(candidate["board"]["observations"]) == 10


def test_same_printed_integer_still_has_two_unadjudicated_interpretations(report):
    zero, one = report["given_source_integer_encoding_hypotheses"]
    assert (
        zero["decoded"]["day_ganzhi"] == "乙酉"
        and not zero["matches_ming_explicit_day"]
    )
    assert one["decoded"]["day_ganzhi"] == "甲申" and one["matches_ming_explicit_day"]
    assert [r["board"]["matching_fields"] for r in (zero, one)] == [0, 9]
    assert not report["source_counter_encoding_adjudicated"]
    assert not report["source_epoch_identity_adjudicated"]
    assert not report["fixed_day_correction_installed"]
    assert report["new_complete_dated_classical_cases_passed"] == 0


def test_all27_external_controls_and_failure_exit_remain_visible(report, tmp_path):
    assert report["external_observation_count"] == 27
    assert all(
        r["both_match_published_label"] for r in report["external_phase_controls"]
    )
    assert not report["external_controls_are_taiyi_case_accuracy"]
    assert not report["whole_goal_complete"]
    outputs = []
    for entry in (
        [str(ROOT / "scripts/taiyi/audit_taiyi_day_count_encodings.py")],
        ["-m", "scripts.taiyi.audit_taiyi_day_count_encodings"],
    ):
        path = tmp_path / f"report{len(outputs)}.json"
        result = subprocess.run(
            [sys.executable, *entry, "--output", str(path)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert result.returncode == 1 and not result.stderr
        outputs.append(path.read_bytes())
    assert outputs[0] == outputs[1]

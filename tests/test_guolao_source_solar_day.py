"""Source-frame transfer, event timing and preserved incomplete source days."""

import hashlib
import json
import shutil
from dataclasses import replace
from fractions import Fraction as F
from pathlib import Path

import pytest

from fatebridge.core import guolao_source_solar_day as subject
from fatebridge.core.guolao_daily_solar import POLICIES
from fatebridge.core.guolao_midnight_anchors import RATE_POLICIES
from fatebridge.core.guolao_solar_fold import PROFILES as FOLD_PROFILES
from fatebridge.validation.guolao_source_solar_day import audit_named_source_solar_day

FIXTURE = Path(__file__).parent / "fixtures/guolao-source-solar-day-v1"


def model(**changes):
    args = dict(
        anchor_rate_policy=RATE_POLICIES[2],
        daily_policy=POLICIES[0],
        fold_profile=FOLD_PROFILES[0],
        table_profile="gujin37_siku",
        side_policy=subject.SIDE_POLICY,
        basis="dadu_source_table",
    )
    args.update(changes)
    return subject.load_named_source_solar_day(subject.PROFILE, **args)


def test_reused_source_witnesses_and_policy_freeze_do_not_claim_new_collation():
    ref = json.loads((FIXTURE / "reference.json").read_text())
    assert hashlib.sha256(subject.DATA.read_bytes()).hexdigest() == ref["data_sha256"]
    for item in ref["artifacts"]:
        blob = (FIXTURE / item["path"]).read_bytes()
        assert len(blob) == item["bytes"]
        assert hashlib.sha256(blob).hexdigest() == item["sha256"]
    for name, wanted in ref["source_inputs_reused_with_separate_fingerprints"].items():
        assert (
            hashlib.sha256((subject.DATA.parent / name).read_bytes()).hexdigest()
            == wanted
        )
    assert not ref["new_independent_facsimile_collation_claimed"]
    assert ref["origin_noon_definition_transferred_to_midnight_as_reconstruction"]
    assert not ref["independent_expert"]


def test_day1_against_closed_form_source_polynomial_and_literal_night_rate():
    def p88(n):
        return F(n * (5133200 - n * (24600 + 31 * n)), 100000000)

    winter = F("4.6380") - F(".0796") * F("1.05108569")
    spring = F("95.94885") - F(".98875") * F(".99970229")
    difference = (spring - winter - (88 + p88(88))) / 88
    expected_relative = winter + F("1.05108569") + difference - F("4.6380")
    expected_sunrise = (F("3092.04") - expected_relative * F(".09")) / 10000
    result = model().day(1)
    assert result["status"] == "calculated"
    transfer = result["coordinate_transfer"]
    assert F(transfer["relative_accumulation_du_exact"]) == expected_relative
    assert transfer["subtracted_winter_event_position_du_exact"] == str(F("4.6380"))
    assert F(result["folded_sunrise_argument"]) == expected_relative
    assert F(result["usable_source_sunrise_fraction_exact"]) == expected_sunrise
    absolute = F(transfer["input_position_du_exact"])
    assert absolute != expected_relative
    wrong = model().fold_model.sunrise(
        absolute,
        origin_reference="deliberately_wrong_frame_counterexample",
        table_profile="gujin37_siku",
        solar_side="outside",
        basis="dadu_source_table",
    )
    assert F(wrong["usable_source_sunrise_fraction_exact"]) != expected_sunrise


def test_before_winter_midnight_retains_negative_accumulation_without_querying_previous_year(
    monkeypatch,
):
    m = model()

    def must_not_query(*args, **kwargs):
        pytest.fail("pre-winter source day must not receive a wrapped sunrise")

    monkeypatch.setattr(type(m.fold_model), "sunrise", must_not_query)
    result = m.day(0)
    assert result["status"] == "before_named_winter_event"
    assert F(result["coordinate_transfer"]["relative_accumulation_du_exact"]) < 0
    assert result["folded_sunrise_argument"] is None
    assert result["fold_and_sunrise_result"] is None
    assert result["usable_source_sunrise_fraction_exact"] is None
    assert not result["coordinate_transfer"]["previous_year_or_modulo_repair_applied"]


@pytest.mark.parametrize(
    "index,side,segment",
    [
        (88, "outside", "spring"),
        (89, "inside", "spring"),
        (276, "inside", "autumn"),
        (277, "outside", "autumn"),
    ],
)
def test_cardinal_midnight_segment_is_not_the_event_time_side(index, side, segment):
    result = model().day(index)
    assert result["source_midnight_result"]["segment"] == segment
    assert result["solar_side_reconstruction"]["selected_side"] == side
    assert result["solar_side_reconstruction"]["time_interval_side"] == side
    assert result["solar_side_reconstruction"]["coordinate_interval_side"] == side
    assert not result["solar_side_reconstruction"][
        "cardinal_midnight_segment_name_used_as_solar_side"
    ]


@pytest.mark.parametrize("event", [1, 3])
def test_exact_equinox_is_not_forced_to_fifty_ke_or_given_one_sided_night(event):
    m = model()
    row = m.side_at(m.event_times[event], m.event_positions[event])
    assert row["status"] == "exact_equinox_boundary_unassigned"
    assert row["selected_side"] is None


@pytest.mark.parametrize("time,position", [(F(131), F(95)), (F(130), F(96))])
def test_source_time_and_coordinate_disagreement_is_not_resolved_by_best_side(
    time, position
):
    row = model().side_at(time, position)
    assert row["status"] == "source_time_position_side_disagreement"
    assert row["selected_side"] is None
    assert not row["disagreement_resolved_by_selecting_favorable_side"]


@pytest.mark.parametrize(
    "position,status",
    [
        (F(95), "source_time_position_side_disagreement"),
        (F("95.94885"), "exact_equinox_boundary_unassigned"),
        (F("369.8814"), "relative_accumulation_outside_declared_fold_cycle"),
    ],
)
def test_chain_retains_nonregular_partial_cases(position, status):
    m = model()
    index = 365 if status.startswith("relative") else 89
    original = m.anchor_model

    class ChangedPosition:
        rate_policy = original.rate_policy

        def day(self, n, *, policy):
            result = original.day(n, policy=policy)
            return {
                **result,
                "midnight_unwrapped_from_ji_start_du_exact": str(position),
            }

    result = replace(m, anchor_model=ChangedPosition()).day(index)
    assert result["status"] == status
    assert result["fold_and_sunrise_result"] is None
    assert result["usable_source_sunrise_fraction_exact"] is None
    if status.startswith("relative"):
        assert F(result["coordinate_transfer"]["relative_accumulation_du_exact"]) == F(
            "365.2434"
        )


def test_declared_cardinal_accumulations_do_not_get_aligned_to_fold_critical_values():
    audit = model().audit()
    assert [
        F(row["event_accumulation_minus_fold_critical_du_exact"])
        for row in audit["cardinal_event_frames"]
    ] == [F(), F(".000225"), F(".00045"), F(".000675"), F(".0009")]
    assert not audit["source_side_and_origin_reconstructions_accepted"]
    assert not audit["same_source_day_location_and_clock_relation_accepted"]


def test_full24_policy_matrix_retains_every_midnight_and_pre_winter_failure():
    audit = audit_named_source_solar_day()
    assert len(audit["all24_policy_configurations"]) == 24
    assert audit["source_midnight_cases_retained"] == 8784
    for config in audit["all24_policy_configurations"]:
        assert len(config["all366_day_statuses"]) == 366
        assert sum(config["status_counts"].values()) == 366
        assert config["status_counts"]["before_named_winter_event"] == 1
        assert config["all_partial_records"][0]["source_day_index"] == 0
        rows = {q["index"]: q for q in config["all366_day_statuses"]}
        for index, side in [
            (88, "outside"),
            (89, "inside"),
            (276, "inside"),
            (277, "outside"),
        ]:
            assert rows[index]["selected_side"] == side
        assert not config["coverage_count_used_as_accuracy_score"]
        for row in rows.values():
            if row["source_sunrise_fraction_exact"] is not None:
                assert 0 < F(row["source_sunrise_fraction_exact"]) < F(1, 2)
        assert not config["physical_sunrise_validated"]
    assert not audit["best_configuration_selected_using_coverage_or_matching"]
    assert not audit["four_axis_perfect_scores_established"]


def test_last_midnight_does_not_require_or_fabricate_next_year_motion():
    row = model().day(365)
    assert row["status"] == "calculated"
    assert (
        row["source_midnight_result"]["following_corrected_daily_motion_du_exact"]
        is None
    )
    assert (
        row["source_midnight_result"]["noon_unwrapped_from_ji_start_du_exact"] is None
    )
    assert row["usable_source_sunrise_fraction_exact"] is not None
    assert not row["phase_day_or_birth_chart_backfilled"]
    assert not row["modern_calendar_date_assigned"]


@pytest.mark.parametrize("value", [True, 1.0, "1", F(1)])
def test_source_day_index_is_not_coerced(value):
    with pytest.raises(TypeError):
        model().day(value)


@pytest.mark.parametrize("value", [-1, 366, 2451545])
def test_no_neighbor_year_or_modern_JD_as_source_day(value):
    with pytest.raises(ValueError):
        model().day(value)


@pytest.mark.parametrize(
    "option,value",
    [
        ("anchor_rate_policy", "best"),
        ("daily_policy", "best"),
        ("fold_profile", "best"),
        ("table_profile", "Qizheng_table"),
        ("side_policy", "auto"),
        ("basis", "birthplace"),
    ],
)
def test_every_source_policy_is_explicit(option, value):
    with pytest.raises(ValueError):
        model(**{option: value})


@pytest.mark.parametrize(
    "mutation", ["origin", "side", "missing_input", "changed_input"]
)
def test_changed_chain_inputs_reject_instead_of_rebaselining(
    monkeypatch, tmp_path, mutation
):
    raw = json.loads(subject.DATA.read_bytes())
    for name in subject.INPUTS:
        shutil.copy2(subject.DATA.parent / name, tmp_path / name)
    if mutation == "origin":
        raw["origin_policy"] = "use_ji_start_without_subtraction"
    elif mutation == "side":
        raw["side_policy"] = "midnight_segment"
    elif mutation == "missing_input":
        raw["input_data_sha256"].pop("solar-fold-v1.json")
    else:
        raw["input_data_sha256"]["daily-solar-motion-v1.json"] = "0" * 64
    file = tmp_path / "source-solar-day-v1.json"
    file.write_text(json.dumps(raw))
    monkeypatch.setattr(subject, "DATA", file)
    with pytest.raises(ValueError):
        model()

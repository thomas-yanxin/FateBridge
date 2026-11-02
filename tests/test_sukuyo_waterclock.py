"""Named source calibration controls against frozen pre-production publisher facts."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

RAW = (
    Path(__file__).parent / "fixtures/sukuyo-waterclock-before-production-v73.json"
).read_bytes()
R = json.loads(RAW)


def module():
    from fatebridge.core import sukuyo_waterclock

    return sukuyo_waterclock


def test_reference_frozen_before_production():
    assert (
        hashlib.sha256(RAW).hexdigest()
        == "6d7d3ca5693097a28073a77587d9a4a9bd9c6adcc57cdbb44196c78931bef54f"
    )
    assert R["no_production_or_domain_imports"]
    assert len(R["expected"]["nalanda_counter_cases"]) == 33


def test_all_named_count_identities_and_units_match_independent_source_reference():
    ref = module().source_specific_time_reference()
    assert ref["count_arithmetic"] == {
        k: v for k, v in R["expected"].items() if k != "nalanda_counter_cases"
    }
    assert ref["T2125"]["mahbodhi_kusinagara"]["whole_day_night_sinkings"] is None
    assert not ref["T2125"]["kulun"]["count_is_bowl_sinkings"]
    assert not ref["T2216_internal_comparison"]["counts_equal"]


@pytest.mark.parametrize(
    "expected",
    R["expected"]["nalanda_counter_cases"],
    ids=lambda v: str(v["completed_sinkings"]),
)
def test_every_counter_state_matches_frozen_fraction_arithmetic(expected):
    result = module().nalanda_group_count(expected["completed_sinkings"])
    assert {k: result[k] for k in expected} == expected
    assert not result["physical_clock_conversion"]
    assert "秒数" in result["reading_text"] and "平明" in result["reading_text"]


@pytest.mark.parametrize("value", [True, False, -1, 33, 100, 0.0, 4.0, "4", None])
def test_counter_does_not_coerce_bool_out_of_cycle_or_inexact_input(value):
    with pytest.raises(ValueError):
        module().nalanda_group_count(value)


@pytest.mark.parametrize(
    "path,value",
    [
        (("T2125", "nalanda", "sinkings_per_named_part"), 8),
        (("T2125", "nalanda", "named_parts_to_noon"), 4),
        (("T2125", "mahbodhi_kusinagara", "sinkings_dawn_to_noon"), 8),
        (("T2125", "kulun", "night_drum_strikes"), 16),
    ],
)
def test_source_count_corruption_is_rejected(path, value):
    data = deepcopy(R["source_bundle"])
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError):
        module().validate_source_controls(data)


def test_source_reference_is_detached_and_preserves_unfavorable_literals():
    one = module().source_specific_time_reference()
    one["T2125"]["retained_unadjudicated_literals"].clear()
    two = module().source_specific_time_reference()
    assert [r["literal"] for r in two["T2125"]["retained_unadjudicated_literals"]] == [
        "洛州無影",
        "椀水既盡",
    ]
    assert two["T2216_internal_comparison"]["later"]["inline_small_type"][
        "0233b14"
    ] == ["下之十五", "晝四時夜四時"]
    assert two["T2216_internal_comparison"]["later"]["conjectural_marker"] == "歟"
    assert not two["scope"]["runtime_host_or_mansion_override"]


def test_calendar_day_keeps_existing_16_parts_and_delivers_named_calibration():
    from fatebridge.core.sukuyo_calendar_text import calendar_day_evidence

    day = calendar_day_evidence(1)
    clock = day["clock_doctrine"]
    ref = clock["source_specific_time_calibration"]
    assert (clock["day_parts"], clock["night_parts"]) == (8, 8)
    assert ref["count_arithmetic"]["T2216_parts_totals"] == [16, 8]
    assert ref["T2125"]["calibration"]["fixed_modern_seconds_per_sinking"] is None


@pytest.mark.parametrize(
    "civil,zone,basis",
    [
        ("2025-01-29", "+08:00", "chinese_hko_utc08"),
        ("0806-07-23", "+09:00", "japanese_naoj_historical_utc09"),
    ],
)
def test_native_full_day_explanation_delivers_source_units_and_never_moves_mansion(
    civil, zone, basis
):
    from fatebridge.core.sukuyo import calendar_mansion, day_evidence

    c = calendar_mansion(civil, zone=zone, calendar_basis=basis)
    before = deepcopy(c)
    d = day_evidence(c)
    assert c == before
    assert (
        "那烂陀" in d["reading_text"]
        and "半抄" in d["reading_text"]
        and "歟" in d["reading_text"]
        and "洛州無影" in d["reading_text"]
    )
    assert (
        d["calendar_day"]["clock_doctrine"]["source_specific_time_calibration"]["id"]
        == R["source_bundle"]["id"]
    )


def test_out_of_range_rejection_names_selected_hutime_snapshot_not_global_absence():
    from fatebridge.core.sukuyo import calendar_mansion

    with pytest.raises(ValueError) as error:
        calendar_mansion(
            "1868-01-25", zone="+09:00", calendar_basis="japanese_hutime_1002_1_utc09"
        )
    text = str(error.value)
    assert "1872-02-09" in text and "2031-01-22" in text
    assert (
        "japanese_hutime_1002_1_utc09" in text
        and "所选" in text
        and "冻结" in text
        and "不代表" in text
    )


def test_native_ordinary_counting_drums_remain_distinct_from_special_signals():
    from fatebridge.core.sukuyo import calendar_mansion, day_evidence

    result = day_evidence(calendar_mansion("2025-01-29", "12:00:00", "+08:00"))
    ref = result["calendar_day"]["clock_doctrine"]["source_specific_time_calibration"]
    ordinary = ref["T2125"]["nalanda"]["ordinary_sinking_drums"]
    assert ordinary in result["reading_text"]
    assert "更過四椀同前打四" in result["reading_text"]
    assert "另打一声" in result["reading_text"] and "另打两声" in result["reading_text"]

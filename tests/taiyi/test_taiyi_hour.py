"""Independent full hour example, clock/phase boundaries and source conflicts."""

import hashlib
import json
import shutil
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from fatebridge.core.almanac import get_solar_terms_for_year
from fatebridge.core.metaphysics.taiyi_gates import key_hour_gate_cycle
from fatebridge.core.metaphysics.taiyi_hour import KEY_HOUR_PROFILE, key_hour_origin
from fatebridge.core.metaphysics.taiyi_periods import period_frame
from fatebridge.core.metaphysics.taiyi_year import cyclic_core
from fatebridge.core.output_taiyi_gates import TaiyiDeterminate
from fatebridge.core.output_taiyi_hour import TaiyiHourOrigin
from fatebridge.services.metaphysics import calculate_taiyi_analysis
from scripts.taiyi.audit_taiyi_hour import CORPUS, audit, worked_board
from tests.taiyi.test_taiyi_periods import seed_at

CASE = json.loads((CORPUS / "hour-worked.json").read_text())


def test_full_original_example_retains_numerical_facts_and_unadjudicated_judgment():
    report = audit()
    example = report["hour_example"]
    assert example["required_fields"] == 20
    assert example["evaluated_fields"] == 19 and example["matching_fields"] == 16
    assert {r["field"] for r in example["disagreements"]} == {
        "set_count",
        "set_general",
        "set_vice_general",
    }
    assert example["unadjudicated"] == [
        {"field": "menju_jiangfa", "source_value": True, "computed_value": None}
    ]
    assert report["hour_example_acceptance_passed"] is False
    assert report["calendar_adapter_validated_for_ancient_dates"] is False
    assert report["four_gate_sequences"]["matching_fields"] == 8
    assert all(r["equal"] is False for r in report["calendar_units"]["checks"])
    assert report["calendar_units"]["source_consistency_passed"] is False
    assert [r["status"] for r in report["calendar_units"]["checks"]] == [
        "uniform_unit_hypothesis_rejected",
        "uniform_unit_hypothesis_rejected",
        "quotation_numeral_difference_unresolved",
    ]
    assert report["calendar_units"]["unresolved_source_questions"] == [
        "quotation_year_numeral_equals_this_facsimile"
    ]
    alternative = report["calendar_units"]["qian_distinct_unit_reading"]
    assert alternative["term_equals_year_divided_by_24"] is True
    assert alternative["mean_lunation_equals_lunation_integral"] is True
    assert alternative["applied_to_public_calendar"] is False


def test_47_is_not_a_replacement_for_the_complete_887_counter():
    board = worked_board(CASE)
    short = cyclic_core(CASE["shortcut_counter"])
    assert board["core_board"]["accumulation"] == 887
    assert board["core_board"]["kook_number"] == 23
    assert short["taiyi_number"] == board["core_board"]["taiyi_number"] == 9
    assert short["wenchang_palace"] == "卯"
    assert board["wenchang_palace"] == "乾"
    assert "只以太乙行宫" in CASE["shortcut_scope"]
    assert board["core_board"]["heshen"] == "卯"
    assert board["core_board"]["dingmu"] == "巳"
    assert board["core_board"]["set_count"] == 32
    assert CASE["expected"]["set_count"] == 33
    assert [
        (r["source_value"], r["rule_derived_value"])
        for r in board["determinate_calculation"]["source_disagreements"]
    ] == [(33, 32), (3, 2), (9, 6)]
    assert board["gates"]["counter"]["duty_gate"] == "生"
    assert board["gates"]["counter"]["unit_in_gate"] == 17
    assert board["gates"]["moving_frame"]["anchor_source_value"] == "巳"
    assert board["condition_assessment"]["menju_jiangfa"] is None
    TaiyiDeterminate.model_validate(board["determinate_calculation"])


def test_different_jiazi_origin_dates_preserve_every_computed_cycle_phase():
    # A phase invariant, not 1,440 independent historical cases: any two
    # Jiazi day origins differ by 60 days = 720 double hours. The core's
    # 72/24/18/12 cycles and the Key's 120-hour gate cycle divide 720.
    for yin in (False, True):
        for count in range(1, 721):
            first = cyclic_core(count, yin=yin)
            other = cyclic_core(count + 720, yin=yin)
            first.pop("accumulation")
            other.pop("accumulation")
            assert first == other
            a, b = key_hour_gate_cycle(count, yin), key_hour_gate_cycle(
                count + 720, yin
            )
            a.pop("accumulation")
            b.pop("accumulation")
            assert a == b


def test_modern_date_phase_against_published_naoj_anchor_across_century_leap_rules():
    # NAOJ's JDN 2000-01-01=2451545 and cycle=(JDN+49)%60 -> 戊午(54).
    # This is a derived civil-date sweep, not thousands of observed anchors.
    reference = datetime(2000, 1, 1)
    winter = datetime(1899, 12, 21, 12)
    day = datetime(1900, 1, 1)
    end = datetime(2101, 1, 1)
    while day < end:
        result = key_hour_origin(winter, day.replace(hour=12))
        phase = (54 + (day - reference).days) % 60
        assert (result["accumulation"] - 1) % 720 == phase * 12 + 6
        day += timedelta(days=1)


def test_zi_initial_and_midnight_are_explicit_and_do_not_double_count():
    winter = datetime(2025, 12, 21, 23, 3)
    clocks = [
        datetime.fromisoformat(t)
        for t in [
            "2026-04-04T22:59:59.999999",
            "2026-04-04T23:00:00",
            "2026-04-05T00:59:59.999999",
            "2026-04-05T01:00:00",
        ]
    ]
    rows = [key_hour_origin(winter, c) for c in clocks]
    counts = [r["accumulation"] for r in rows]
    assert counts == [counts[0], counts[0] + 1, counts[0] + 1, counts[0] + 2]
    assert rows[0]["target_day_ganzhi"] == "戊申"
    assert rows[1]["target_day_ganzhi"] == "己酉"
    assert rows[1]["target_effective_date"] == "2026-04-05"
    assert all("modern_convention" in r["day_boundary"] for r in rows)
    TaiyiHourOrigin.model_validate(rows[0])


@pytest.mark.parametrize("term_name", ["夏至", "冬至"])
def test_solstice_switches_dun_without_resetting_the_key_phase_to_one(term_name):
    term = next(t for t in get_solar_terms_for_year(2026, "UTC") if t.name == term_name)
    moments = [
        (term.moment + timedelta(minutes=n)).replace(tzinfo=None) for n in (-2, 2)
    ]
    rows = [
        period_frame(seed_at(t, zone="UTC"), "hour", KEY_HOUR_PROFILE) for t in moments
    ]
    assert rows[0]["yin"] != rows[1]["yin"]
    assert (rows[0]["accumulation"] - rows[1]["accumulation"]) % 720 == 0
    assert rows[1]["accumulation"] != 1


def test_apparent_clock_hour_origin_is_invariant_under_timezone_representation():
    instant = datetime(2026, 8, 1, 12, 34, 56)
    rows = []
    for offset, zone in [(0, "UTC"), (8, "Asia/Shanghai"), (-4, "America/New_York")]:
        seed = seed_at(
            instant + timedelta(hours=offset), zone=zone, solar=True, longitude=121.47
        )
        rows.append(period_frame(seed, "hour", KEY_HOUR_PROFILE))
    assert rows[0]["hour_origin"] == rows[1]["hour_origin"] == rows[2]["hour_origin"]
    assert len({r["accumulation"] for r in rows}) == 1


@pytest.mark.parametrize("month,day,hour", [(3, 8, 2), (11, 1, 1)])
def test_key_profile_also_rejects_ambiguous_or_nonexistent_local_clocks(
    month, day, hour
):
    with pytest.raises(ValueError, match="local time"):
        seed = seed_at(datetime(2026, month, day, hour, 30), zone="America/New_York")
        period_frame(seed, "hour", KEY_HOUR_PROFILE)


@pytest.mark.parametrize(
    "mode,profile",
    [
        ("year", KEY_HOUR_PROFILE),
        ("month", KEY_HOUR_PROFILE),
        ("hour", []),
        ("hour", {}),
        ("hour", "made_up"),
    ],
)
def test_hour_profile_is_not_silently_ignored_or_coerced(mode, profile):
    with pytest.raises(ValueError, match="hour_profile"):
        period_frame(seed_at(datetime(2026, 4, 4, 12)), mode, profile)


def test_output_snapshots_explain_selected_counter_and_do_not_claim_gates_passed():
    result = calculate_taiyi_analysis(
        analysis_year=2026,
        analysis_month=1,
        analysis_day=3,
        analysis_hour=20,
        analysis_timezone="Asia/Shanghai",
        calculation_mode="hour",
        hour_profile=KEY_HOUR_PROFILE,
        use_true_solar_time=False,
    )
    assert "error" not in result
    board = result["taiyi"]
    assert board["calendar_summary"]["hour_profile"] == KEY_HOUR_PROFILE
    assert (
        board["calendar_rules"]["heshen_branch_basis"] == "selected_clock_hour_branch"
    )
    assert "完整积时" in result["snapshot_text"]
    assert "= " + str(board["core_board"]["accumulation"]) in result["snapshot_text"]
    assert (
        "三门主体" in result["snapshot_text"]
        or "主客核对主体" in result["snapshot_text"]
    )
    assert board["condition_assessment"]["menju_jiangfa"] is None
    assert board["ruleset"]["classical_acceptance_passed"] is False
    assert board["ruleset"]["real_world_efficacy"] == "not_tested"
    assert "原文33，按本盘算路32" in result["snapshot_text"]


@pytest.mark.parametrize(
    "attempt", ["drop_unknown_judgment", "drop_unit_conflict", "alter_facsimile"]
)
def test_audit_cannot_pass_by_removing_unadjudicated_or_failed_material(
    tmp_path, attempt
):
    corpus = tmp_path / "taiyi_jinjing_v6"
    shutil.copytree(CORPUS, corpus)
    prior = tmp_path / "taiyi_jinjing_v5"
    prior.mkdir()
    shutil.copy2(
        CORPUS.parent / "taiyi_jinjing_v5/key-sequel-clean.txt",
        prior / "key-sequel-clean.txt",
    )
    if attempt == "alter_facsimile":
        (corpus / "key-page46.jpg").write_bytes(b"changed")
    else:
        path = corpus / (
            "hour-worked.json"
            if attempt == "drop_unknown_judgment"
            else "calendar-units.json"
        )
        data = json.loads(path.read_text())
        if attempt == "drop_unknown_judgment":
            del data["expected"]["menju_jiangfa"]
        else:
            data["requirements"].pop()
        path.write_text(json.dumps(data))
        p = corpus / "manifest.json"
        manifest = json.loads(p.read_text())
        for source in manifest["source_files"]:
            if source["file"] == path.name:
                source["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        p.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        audit(corpus)


def test_calendar_source_literals_and_strict_optional_hour_schema_are_preserved():
    data = json.loads((CORPUS / "calendar-units.json").read_text())
    assert data["book"]["year_integral"] == "3835046.25"
    assert data["qian"]["year_integral"] == "3835048.25"
    assert "四十八分" in (CORPUS / "qian-excerpt.txt").read_text()
    for payload in [
        {"day_number": "74"},
        {"hour_number": True},
        {"accumulation": 887.0},
    ]:
        with pytest.raises(ValidationError):
            TaiyiHourOrigin.model_validate(payload)

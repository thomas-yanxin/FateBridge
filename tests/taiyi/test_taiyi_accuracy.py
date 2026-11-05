"""Independent text cases, boundary failures and evidence-preserving delivery."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from fatebridge.core.local_techniques.sanshi import _build_taiyi_with_options
from fatebridge.core.metaphysics.taiyi_year import (
    PALACES,
    count_categories,
    count_to_taiyi,
    general_for_count,
    structural_patterns,
    yearly_core,
)
from fatebridge.core.output_chinese import Taiyi
from fatebridge.core.requests.metaphysics import TaiyiAnalysisRequest
from fatebridge.services.divination import calculate_sanshiunited_analysis
from fatebridge.services.metaphysics import (
    _build_analysis_seed,
    calculate_taiyi_analysis,
)
from scripts.taiyi.audit_taiyi_classical import CORPUS, audit

CASES = json.loads((CORPUS / "cases.json").read_text())


@pytest.mark.parametrize(
    "invalid",
    [
        {"rule_trace": {"main": {"count": "16"}}},
        {"calendar_rules": {"year": "2026"}},
        {"rule_trace": {"guest": {"terminal_excluded": "false"}}},
    ],
)
def test_public_evidence_contract_rejects_facts_with_wrong_types(invalid):
    with pytest.raises(ValidationError):
        Taiyi.model_validate(invalid)


@pytest.mark.parametrize(
    "case", [c for c in CASES if c["status"] == "transcribed"], ids=lambda c: c["id"]
)
def test_yearly_core_against_frozen_primary_table(case):
    core = yearly_core(case["year"])
    assert core["kook_number"] == case["ju"]
    for field, expected in case["expected"].items():
        assert core[field] == expected


def test_unresolved_cases_are_counted_and_block_classical_acceptance():
    report = audit()
    assert report["total_cases"] == 72
    assert report["matching_cases"] == 70
    assert report["matching_fields"] == 142
    assert {d["ju"] for d in report["disagreements"]} == {39, 50}
    assert report["classical_acceptance_passed"] is False
    assert report["real_world_efficacy"] == "not_tested"


def test_independent_corpus_tampering_is_rejected(tmp_path):
    import shutil

    shutil.copytree(CORPUS, tmp_path / "corpus")
    cases = tmp_path / "corpus" / "cases.json"
    cases.write_text("[]")
    with pytest.raises(ValueError, match="指纹"):
        audit(tmp_path / "corpus")


@pytest.mark.parametrize("attempt", ["drop_cases", "drop_fields"])
def test_audit_cannot_be_gamed_by_removing_disagreements(tmp_path, attempt):
    import hashlib
    import shutil

    corpus = tmp_path / "corpus"
    shutil.copytree(CORPUS, corpus)
    path = corpus / "cases.json"
    cases = json.loads(path.read_text())
    if attempt == "drop_cases":
        cases = [c for c in cases if c["ju"] not in (39, 50)]
    else:
        del cases[38]["expected"]["main_count"]
    path.write_text(json.dumps(cases))
    manifest_path = corpus / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["cases_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="72|每局必须"):
        audit(corpus)


def test_volume_two_worked_example_and_count_categories():
    trace = count_to_taiyi("亥", 9)
    assert trace["count"] == 16
    assert [(p["palace"], p["value"]) for p in trace["path"]] == [
        ("亥", 1),
        ("子", 8),
        ("艮", 3),
        ("卯", 4),
    ]
    # Fifteen is not a complete 10/5/1 decomposition. The later literal
    # 杜塞 classification is named, not converted into a physical gate result.
    assert count_categories(15) == ["杜塞（淘金歌）"]
    assert count_categories(10) == ["无人"]
    assert count_categories(11) == ["无地"]
    same = count_to_taiyi("艮", 3)
    assert same["count"] == 3
    assert same["terminal_excluded"] is False
    assert same["counting_rule"] == "同宫取本宫数"


@pytest.mark.parametrize(
    "count,expected", [(10, 1), (20, 2), (30, 3), (40, 4), (25, 5), (39, 9)]
)
def test_generals_from_same_count_including_exact_tens(count, expected):
    assert general_for_count(count) == expected


def test_volume_nine_forty_is_four_not_five():
    core = yearly_core(700)  # 阳遁25局，卷九《推敌使言虚实》例
    assert (core["guest_count"], core["guest_general"], core["guest_vice_general"]) == (
        40,
        4,
        2,
    )


def test_full_cycle_trace_and_general_consistency():
    for year in range(1900, 2101):
        core = yearly_core(year)
        for side, key in (("main", "main_count"), ("guest", "guest_count")):
            assert core[key] == sum(
                p["value"] for p in core["count_trace"][side]["path"]
            )
            assert 1 <= core[key] <= 40
            assert core[f"{side}_general"] == general_for_count(core[key])
            assert core[f"{side}_vice_general"] in PALACES


def test_structural_interpretation_references_actual_returned_fields():
    for year in range(676, 748):
        core = yearly_core(year)
        board = {
            "core_board": core,
            "taiyi_palace": core["taiyi_palace"],
            "wenchang_palace": core["wenchang_palace"],
        }
        for pattern in structural_patterns(core):
            for fact in pattern["basis"]:
                node = board
                for part in fact["field"].split("."):
                    node = node[part]
                assert node == fact["value"]


def call_taiyi(year=2026, month=4, day=4, hour=12, minute=0, **kwargs):
    return calculate_taiyi_analysis(
        analysis_year=year,
        analysis_month=month,
        analysis_day=day,
        analysis_hour=hour,
        analysis_minute=minute,
        analysis_timezone="Asia/Shanghai",
        use_true_solar_time=False,
        **kwargs,
    )


@pytest.mark.parametrize(
    "month,day,lunar_year,branch",
    [(2, 4, 2025, "巳"), (2, 16, 2025, "巳"), (2, 17, 2026, "午"), (4, 17, 2026, "午")],
)
def test_hko_2026_new_year_is_distinct_from_lichun(month, day, lunar_year, branch):
    # HKO Gregorian-Lunar Calendar Conversion Table of 2026, Feb/Apr rows.
    board = call_taiyi(month=month, day=day)["taiyi"]
    assert board["calendar_rules"]["year"] == lunar_year
    assert board["core_board"]["suijun"] == branch


def test_yearly_default_does_not_require_longitude_for_hourly_correction():
    request = TaiyiAnalysisRequest(
        analysis_year=2026, analysis_month=4, analysis_day=4, analysis_hour=12
    )
    assert request.use_true_solar_time is False
    result = calculate_taiyi_analysis(**request.model_dump())
    assert "taiyi" in result
    assert result["analysis_context"]["time_algorithm"] == "直接时间"


def test_apparent_solar_midnight_cannot_rewrite_civil_lunar_year():
    result = calculate_taiyi_analysis(
        analysis_year=2026,
        analysis_month=2,
        analysis_day=17,
        analysis_hour=0,
        analysis_minute=1,
        analysis_timezone="Asia/Shanghai",
        analysis_longitude=100.0,
        use_true_solar_time=True,
    )
    assert result["calendar_context"]["lunar_calendar"]["year"] == 2025
    assert result["taiyi"]["calendar_rules"]["year"] == 2026
    assert result["taiyi"]["core_board"]["suijun"] == "午"


@pytest.mark.parametrize(
    "year,month,day,expected_year",
    [
        (2025, 1, 28, 2024),
        (2025, 1, 29, 2025),
        (2025, 7, 25, 2025),
        (2033, 1, 30, 2032),
        (2033, 1, 31, 2033),
        (2033, 12, 22, 2033),
        (2034, 2, 18, 2033),
        (2034, 2, 19, 2034),
    ],
)
def test_frozen_hko_years_include_2033_leap_eleven(year, month, day, expected_year):
    board = call_taiyi(year=year, month=month, day=day)["taiyi"]
    assert board["calendar_rules"]["year"] == expected_year
    assert (
        board["core_board"]["suijun"]
        == "子丑寅卯辰巳午未申酉戌亥"[(expected_year - 4) % 12]
    )


def test_center_general_is_preserved_and_explained_from_same_board():
    result = call_taiyi(year=2017)
    board = result["taiyi"]
    assert board["core_board"]["main_count"] == 5
    assert "主大" in board["center_marks"]["markers"]
    assert len(board["palace_marks"]) == 16
    assert "[中宫标记]" in result["snapshot_text"]
    for label, trace in board["rule_trace"].items():
        assert f"= {trace['count']}" in result["snapshot_text"]
    assert "疾疫" not in result["snapshot_text"]


@pytest.mark.parametrize(
    "options",
    [
        {"accNum": 1},
        {"acc_num": -1},
        {"accNum": True},
        {"rotation": "reverse"},
        {"rotation": "阴遁"},
        {"invented": "x"},
        {"accNum": 0, "acc_num": 1},
    ],
)
def test_unsupported_transformations_never_create_a_plausible_board(options):
    seed = _build_analysis_seed(
        analysis_year=2026, analysis_month=4, analysis_day=4, analysis_hour=12
    )
    with pytest.raises(ValueError):
        _build_taiyi_with_options(seed, options)


@pytest.mark.parametrize("mode", ["year", "month", "day", "hour"])
@pytest.mark.parametrize(
    "obsolete",
    [{"accNum": 0}, {"acc_num": 0}, {"rotation": "顺布"}, {"rotation": "forward"}],
)
def test_obsolete_noop_keys_are_rejected_in_every_current_mode(mode, obsolete):
    seed = _build_analysis_seed(
        analysis_year=2026, analysis_month=4, analysis_day=4, analysis_hour=12
    )
    with pytest.raises(ValueError, match="未实现的太乙选项"):
        _build_taiyi_with_options(seed, {"calculation_mode": mode, **obsolete})


def test_default_current_options_do_not_fabricate_patterns():
    seed = _build_analysis_seed(
        analysis_year=2026, analysis_month=4, analysis_day=4, analysis_hour=12
    )
    default = _build_taiyi_with_options(seed, {})
    assert "big_pattern" not in default
    assert "small_pattern" not in default
    assert default["ruleset"]["classical_acceptance_passed"] is False


def test_sanshi_does_not_conflate_yearly_background_with_hourly_event():
    result = calculate_sanshiunited_analysis(
        date="2026-04-04",
        time="12:00:00",
        zone="Asia/Shanghai",
        use_true_solar_time=False,
    )
    assert result["taiyi"] == call_taiyi()["taiyi"]
    assert result["subresults"]["taiyi"]["pan"] == result["taiyi"]
    assert result["synthesis"]["time_scopes"]["taiyi"] == "year"
    assert result["synthesis"]["independent_evidence_count"] is None
    assert result["synthesis"]["real_world_efficacy"] == "not_tested"
    assert "[合参范围]" in result["snapshot_text"]

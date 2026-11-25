"""Source cases, counterexamples and actual public transport parity."""

import asyncio
import copy
import json
from fractions import Fraction
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.application.examples import suggested_fields
from fatebridge.core.bazi.bazi_evidence import (
    build_natal_evidence,
    build_topic_evidence,
)
from fatebridge.core.contracts.output_bazi_evidence import BaziEvidenceChain
from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.strength import assess_strength
from tests.support.result_delivery import reconstruct
from tests.support.result_delivery import store as _shared_store
from tests.support.transports import SPECS, business, call_cli, inputs, native
from tests.support.transports import rest as _shared_rest
from tests.support.transports import surface_calls

CASES = json.loads(
    (Path(__file__).parents[1] / "data/bazi_classical_v1/cases.json").read_text()
)


def pillars(values):
    return {n: tuple(p) for n, p in zip(("year", "month", "day", "hour"), values)}


def source_case(case_id):
    return pillars(next(c["pillars"] for c in CASES if c["id"] == case_id))


def check(result, key):
    return next(c for c in result["structure_checks"] if c["id"] == key)


rest = _shared_rest
store = _shared_store


@pytest.mark.parametrize(
    "case_id,distance,intervening,combination",
    [
        ("ZP31-XUE", 2, ["day"], False),
        ("ZP31-LONE", 1, [], True),
        ("ZP41-DUTONG", 3, ["month", "day"], True),
        ("ZP41-CHENGXIANG", 3, ["month", "day"], True),
    ],
)
def test_frozen_book_cases_retain_financial_seal_separation(
    case_id: str, distance: int, intervening, combination: bool
) -> None:
    # These spatial distinctions are explicitly described on PDF65/66/84.
    result = build_natal_evidence(source_case(case_id))
    relation = result["financial_seal_positions"][0]
    assert relation["distance"] == distance
    assert relation["intervening_positions"] == intervening
    assert relation["stem_combination"] is combination
    # 丁壬 separated by 戊己 still have a pair relation, not an automatic 合去.
    assert relation["adjudication"] == "position_observation_only"


def test_frozen_liang_food_wealth_keeps_root_in_wei_and_unresolved_force() -> None:
    result = build_natal_evidence(source_case("ZP37-LIANG"))
    wealth = result["ten_gods"]["偏财"]
    visible = next(e for e in wealth if e["location"] == "天干")
    assert visible["stem"] == "丁" and visible["pillar"] == "year"
    assert {
        "pillar": "year",
        "branch": "未",
        "stem": "丁",
        "hidden_rank": 1,
        "kind": "same_stem",
    } in visible["roots"]
    c = check(result, "food_generates_wealth")
    assert c["status"] == "pending_adjudication"
    assert c["formation_status"] == "not_adjudicated"
    assert (
        next(x for x in c["conditions"] if x["id"] == "strength_and_relative_force")[
            "status"
        ]
        == "unknown"
    )


def test_hurt_seal_cooccurrence_is_refuted_by_no_root_and_not_certified_by_root() -> (
    None
):
    no_root = pillars(["甲午", "丙午", "甲午", "壬午"])
    rooted = {**no_root, "hour": ("壬", "子")}
    a = check(build_natal_evidence(no_root), "hurt_with_seal")
    b = check(build_natal_evidence(rooted), "hurt_with_seal")
    assert a["status"] == "prerequisite_not_met"
    assert b["status"] == "pending_adjudication"
    assert a["formation_status"] == b["formation_status"] == "not_adjudicated"
    assert (
        next(c for c in a["conditions"] if c["id"] == "helper_present")["status"]
        == "matched"
    )


def test_hurt_seal_candidate_respects_the_shared_root_prerequisite() -> None:
    no_root = build_natal_evidence(pillars(["乙丑", "乙酉", "戊辰", "丙辰"]))
    rooted = build_natal_evidence(source_case("ZP41-BO"))
    stage_only = build_natal_evidence(source_case("ZP41-DUTONG"))

    for result, expected in (
        (no_root, "observable_prerequisite_not_met"),
        (rooted, "requires_force_adjudication"),
        (stage_only, "requires_force_adjudication"),
    ):
        path = next(
            path
            for path in result["candidate_selection"]["paths"]
            if path["id"] == "hurt_seal"
        )
        assert path["status"] == expected
        assert path["formation_status"] == "not_adjudicated"
        gate = next(
            (
                item
                for item in path["observed_conditions"]
                if item["id"] == "seal_root_present"
            ),
            None,
        )
        if result is stage_only:
            assert gate is None
            assert {
                "condition": "印仅见阶段根参考，印有根须复核",
                "status": "unknown",
            } in path["force_conditions"]
        else:
            assert gate["status"] == ("not_matched" if result is no_root else "matched")


@pytest.mark.parametrize(
    "values,path_id,status,root_status",
    [
        (
            ["戊子", "乙卯", "癸酉", "丙辰"],
            "food_wealth",
            "observable_prerequisite_not_met",
            "not_matched",
        ),
        (
            ["丙午", "丁酉", "戊午", "壬戌"],
            "hurt_wealth",
            "observable_prerequisite_not_met",
            "not_matched",
        ),
        (
            ["癸卯", "辛酉", "己酉", "癸酉"],
            "food_wealth",
            "requires_force_adjudication",
            "unknown",
        ),
    ],
)
def test_wealth_candidates_respect_the_shared_root_prerequisite(
    values, path_id: str, status: str, root_status: str
) -> None:
    evidence = build_natal_evidence(pillars(values))
    path = next(
        row for row in evidence["candidate_selection"]["paths"] if row["id"] == path_id
    )
    roots = [
        item
        for item in path["observed_conditions"]
        if item["id"] == "wealth_root_present"
    ]
    assert path["status"] == status
    assert path["formation_status"] == "not_adjudicated"
    if root_status == "unknown":
        assert not roots
        assert {"condition": "财仅见阶段根参考，财有根须复核", "status": "unknown"} in (
            path["force_conditions"]
        )
    else:
        assert [item["status"] for item in roots] == [root_status]
        assert roots[0]["star_refs"]
    if path_id == "food_wealth":
        structure = check(evidence, "food_generates_wealth")
        assert (
            next(
                c["status"]
                for c in structure["conditions"]
                if c["id"] == "helper_root_present"
            )
            == root_status
        )
    else:
        pass


def test_root_kind_does_not_fabricate_yin_growth_phase_hidden_stems() -> None:
    result = build_natal_evidence(pillars(["乙午", "丁酉", "甲戌", "癸丑"]))
    yi = result["visible_stems"][0]
    ding = result["visible_stems"][1]
    assert all(r["branch"] != "午" for r in yi["roots"])
    assert all(r["branch"] != "酉" for r in ding["roots"])
    assert any(
        r["pillar"] == "year" and r["stage"] == "长生" for r in yi["growth_phase_roots"]
    )
    assert any(
        r["pillar"] == "month" and r["stage"] == "长生"
        for r in ding["growth_phase_roots"]
    )


def test_yin_growth_reference_is_not_rejected_as_certainly_rootless() -> None:
    result = build_natal_evidence(pillars(["乙午", "戊午", "丁午", "己巳"]))
    condition = next(
        c
        for c in check(result, "hurt_with_seal")["conditions"]
        if c["id"] == "helper_root_present"
    )
    assert condition["status"] == "unknown"


def test_rob_wealth_in_month_is_not_automatically_yang_blade() -> None:
    # The frozen 孤官无辅 case is 戊 in 未; its 乙官 is actually 透 in 时.
    month = build_natal_evidence(source_case("ZP31-LONE"))["month_command"]
    assert month["selected_god"]["ten_god"] == "正官"  # preserved old single anchor
    assert {w["ten_god"] for w in month["use_resolution"]["witnesses"]} == {
        "正印",
        "正官",
    }  # actual revelations coexist; not an automatic month blade.
    assert not month["yang_blade_seat"]
    officer = next(c for c in month["candidates"] if c["ten_god"] == "正官")
    assert officer["visible_in"] == ["hour"]


def test_timing_retains_hidden_wealth_and_joint_dayun_liunian_bureau() -> None:
    p = pillars(["庚申", "丁巳", "甲午", "丙寅"])
    natal = build_natal_evidence(p)
    before = copy.deepcopy(natal)
    result = build_topic_evidence(natal, p, "wealth", "男", ("甲", "子"), ("丙", "辰"))
    assert any(
        g["kind"] == "三合" and set(g["branches"]) == set("申子辰")
        for g in result["timing"]["combined_groups"]
    )
    assert all(
        g["effect_status"] == "relation_only"
        for g in result["timing"]["combined_groups"]
    )
    changed = build_topic_evidence(natal, p, "wealth", "男", None, ("辛", "未"))
    assert any(
        e["stem"] == "己" and e["location"] == "地支藏干" and e["in_topic"]
        for e in changed["timing"]["layers"][0]["stars"]
    )
    assert natal == before  # Changing target time cannot mutate the natal chart.


def test_book_weak_label_is_not_replaced_by_modern_strength_as_classical_truth() -> (
    None
):
    p = source_case("ZP41-BO")
    strength = ElementAnalysis.analyze_day_master_strength(p)
    result = build_natal_evidence(p, strength)
    condition = next(
        c
        for c in check(result, "hurt_with_seal")["conditions"]
        if c["id"] == "strength_and_relative_force"
    )
    assert condition["status"] == "unknown"
    assert (
        condition["model_observation"]["strength_level"] == strength["strength_level"]
    )
    # v10's reversed summer water phase yielded120/1133 (<3/20).
    # With 水囚/金死 the same coefficients yield180/1153 (>3/20), so the
    # engineering extreme flag is false. Neither flag adjudicates the book's
    # relative-force condition; that condition must remain unknown above.
    exact = strength["assessment"]["threshold_arithmetic"]
    assert exact["share_exact"] == "180/1153"
    assert Fraction(exact["share_exact"]) > Fraction(3, 20)
    assert result["strength_context"]["requires_special_structure_review"] is False
    historical = assess_strength(
        p, {**ElementAnalysis.seasonal_phases("午"), "水": "死", "金": "囚"}
    )
    assert historical["threshold_arithmetic"]["share_exact"] == "120/1133"
    assert Fraction("120/1133") < Fraction(3, 20)
    assert historical["requires_special_structure_review"] is True


def test_spouse_star_only_in_day_palace_is_not_lost() -> None:
    chart = pillars(["甲寅", "丙寅", "甲戌", "丙寅"])
    topic = build_topic_evidence(
        build_natal_evidence(chart), chart, "marriage", "男", None, None
    )
    assert any(
        row["pillar"] == "day" and row["stem"] == "戊" and row["location"] == "地支藏干"
        for row in topic["stars"]["偏财"]
    )


def test_unknown_gender_retains_both_spouse_star_conventions() -> None:
    chart = source_case("ZP31-LONE")
    topic = build_topic_evidence(
        build_natal_evidence(chart), chart, "marriage", None, None, None
    )
    assert topic["selection_basis"] == "unselected_gender_alternatives"
    assert topic["selection_alternatives"] == {
        "male": ["正财", "偏财"],
        "female": ["正官", "七杀"],
    }
    assert set(topic["stars"]) == {"正财", "偏财", "正官", "七杀"}


def test_shensha_target_without_actual_branch_is_not_a_hit() -> None:
    chart = pillars(["甲子", "乙丑", "丙子", "己丑"])
    topic = build_topic_evidence(
        build_natal_evidence(chart), chart, "marriage", "男", None, None
    )
    assert topic["first_view"]["markers"] == []
    chart["hour"] = ("丁", "卯")
    topic = build_topic_evidence(
        build_natal_evidence(chart), chart, "marriage", "男", None, None
    )
    assert [
        (row["name"], row["natal_positions"]) for row in topic["first_view"]["markers"]
    ] == [("红鸾", ["hour"])]


def test_male_tomb_lookup_uses_wealth_not_officer_element() -> None:
    earth_wealth = pillars(["戊戌", "乙丑", "甲子", "辛丑"])
    fire_wealth = pillars(["丙戌", "乙丑", "壬子", "辛丑"])
    for chart, expected in ((earth_wealth, []), (fire_wealth, [("year", "戌", "火")])):
        topic = build_topic_evidence(
            build_natal_evidence(chart), chart, "marriage", "男", None, None
        )
        assert [
            (row["pillar"], row["branch"], row["element"])
            for row in topic["storage_matches"]
        ] == expected


@pytest.mark.parametrize(
    "topic",
    [
        "career",
        "wealth",
        "marriage",
        "romance",
        "education",
        "personality",
        "relatives",
        "children",
        "health",
    ],
)
@pytest.mark.parametrize("gender", ["男", "未知"])
def test_nine_depth_views_match_actual_rest_mcp_cli(
    topic: str, gender: str, surface_calls
) -> None:
    spec = SPECS["bazi_" + topic]
    request = inputs(spec)
    request.pop("dayun_pillar", None)
    request.pop("liunian_pillar", None)
    request.update(gender=gender, analysis_year=2027, analysis_month=2, analysis_day=4)
    fields = suggested_fields(spec, view="depth")
    flags = {
        "fields": fields,
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 0,
    }
    http, protocol, code, output = surface_calls(
        spec,
        request,
        params=flags,
        options=flags,
        flags=[
            "--no-metadata",
            "--fields",
            *fields,
            "--strict-fields",
            "--no-include-snapshot-text",
            "--response-char-limit",
            "0",
        ],
        cli_first=False,
    )
    assert http.status_code == 200, http.text
    assert not protocol.is_error and code == 0
    assert business(http.json()) == business(protocol.structured_content) == output
    analysis = output[topic + "_analysis"]
    evidence = analysis["evidence_chain"]
    assert evidence["topic"]["topic"] == topic
    assert evidence["strength_context"]["method_id"]
    assert evidence["rulesets"][0]["id"] == "ziping_prerequisites_v1"
    assert (
        evidence["topic"]["timing"]["layers"][-1]["pillar"]
        == analysis["timing_context"]["liunian_pillar"]
    )
    assert analysis["timing_context"]["boundary_status"] == "year_boundary_day"
    if gender == "未知":
        assert analysis["timing_context"]["dayun_pillar"] is None
        assert (
            analysis["timing_context"]["dayun_status"] == "unavailable_gender_direction"
        )
        assert len(evidence["topic"]["timing"]["layers"]) == 1
    else:
        pass


def test_new_nested_contract_rejects_corrupt_root_rank() -> None:
    result = build_natal_evidence(source_case("ZP37-LIANG"))
    BaziEvidenceChain.model_validate(result)
    entry = next(
        e for entries in result["ten_gods"].values() for e in entries if e["roots"]
    )
    entry["roots"][0]["hidden_rank"] = "0"
    with pytest.raises(ValidationError):
        BaziEvidenceChain.model_validate(result)


@pytest.mark.parametrize(
    "topic",
    [
        "career",
        "wealth",
        "marriage",
        "romance",
        "education",
        "personality",
        "relatives",
        "children",
        "health",
    ],
)
def test_nine_recommended_first_views_keep_analysis_within_default_budget(
    topic: str,
) -> None:
    spec = SPECS["bazi_" + topic]
    response = asyncio.run(
        native(
            spec,
            inputs(spec),
            fields=suggested_fields(spec),
            strict_fields=True,
            include_snapshot_text=False,
            response_char_limit=8192,
        )
    )
    assert not response.is_error
    result = response.structured_content
    # A large installed file inventory may be deferred; the actual first-view
    # analysis must still be inline, without another calculation or call.
    if "result_delivery" in result:
        deferred = result["result_delivery"]["deferred_fields"]
        assert deferred and set(deferred) <= {
            "run_metadata.runtime",
            "run_metadata.provenance",
            "run_metadata.calculation_evidence",
        }
        assert len(deferred) == len(set(deferred))
    else:
        pass
    analysis = result[topic + "_analysis"]
    assert analysis["evidence_chain"]["topic"]["first_view"]["timing"]


def test_same_core_evidence_is_published_by_comprehensive_and_birth_surfaces(
    rest, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    for key, field in (
        ("analyze_destiny", "structure_profile.evidence_chain"),
        ("bazi_birth", "bazi_birth.structure_profile.evidence_chain"),
    ):
        spec = SPECS[key]
        request = inputs(spec)
        flags = {
            "fields": [field],
            "strict_fields": True,
            "include_snapshot_text": False,
            "response_char_limit": 0,
        }
        protocol = asyncio.run(native(spec, request, **flags))
        code, output = call_cli(
            spec,
            request,
            tmp_path,
            capsys,
            [
                "--no-metadata",
                "--fields",
                field,
                "--strict-fields",
                "--no-include-snapshot-text",
                "--response-char-limit",
                "0",
            ],
        )
        assert code == 0 and not protocol.is_error
        assert business(protocol.structured_content) == output
        if spec.rest_path:
            http = rest.post(spec.rest_path, json=request, params=flags)
            assert http.status_code == 200 and business(http.json()) == output
            output = output["bazi_birth"]
        else:
            pass
        evidence = output["structure_profile"]["evidence_chain"]
        assert evidence["ten_gods"] and evidence["structure_checks"]
    # Use a common actual input, since catalog examples may use distinct people.
    from fatebridge.services.bazi import calculate_bazi_birth
    from fatebridge.services.calculation import calculate_destiny_analysis
    from fatebridge.utils.birth_input import create_person_info

    person = create_person_info(2000, 12, 10, 9, "虚构", "男", "北京")
    a = calculate_destiny_analysis(person)["structure_profile"]["evidence_chain"]
    b = calculate_bazi_birth(person, analysis_year=2027)["bazi_birth"][
        "structure_profile"
    ]["evidence_chain"]
    assert a == b


def test_large_depth_response_preserves_same_run_complete_conditions(store) -> None:
    spec = SPECS["bazi_career"]
    response = asyncio.run(
        native(
            spec, inputs(spec), include_snapshot_text=False, response_char_limit=4096
        )
    )
    assert not response.is_error
    result = response.structured_content
    reference = result["result_delivery"]
    restored = reconstruct(store, reference["result_id"])
    assert restored["run_metadata"]["run_id"] == result["run_metadata"]["run_id"]
    assert restored["career_analysis"]["evidence_chain"]["structure_checks"]

"""Chapter Ten clauses and classical counterexamples, without outcome grading."""

import hashlib
import json
from datetime import datetime
from itertools import product
from pathlib import Path

import pytest

from fatebridge.core.liuyao_judgment import build_conditional_analysis
from fatebridge.core.liuyao_roles import PROFILE, evaluate
from scripts.liuyao.build_profile import build_profile
from tests.liuyao.test_liuyao_conditions import mounted

REFERENCE = Path(__file__).parents[1] / "fixtures/liuyao_effects_v4"
CASES = json.loads((REFERENCE / "cases.json").read_text(encoding="utf-8"))["cases"]


def classical(case):
    info, lines = mounted(case["base_code"], case["changed_code"])
    return build_conditional_analysis(
        lines=lines,
        hidden=[],
        month=case["month"],
        day_ganzhi=case["day_ganzhi"],
        palace=info["current_palace_element"],
        moment=datetime.fromisoformat("2000-01-07T12:00:00+08:00"),
        focus_line=case["focus_line"],
        focus_kinship=None,
        focus_kind=case.get("focus_kind"),
        timing_days=0,
    )


def test_frozen_scan_clauses_and_expectations_are_not_engine_derived():
    assert build_profile("role") == PROFILE
    freeze = json.loads((REFERENCE / "freeze.json").read_text(encoding="utf-8"))
    for name, expected in freeze["sha256"].items():
        assert hashlib.sha256((REFERENCE / name).read_bytes()).hexdigest() == expected
    assert len(PROFILE["rules"]) == 23
    assert len({r["rule_id"] for r in PROFILE["rules"]}) == 23
    assert "五墓" in next(
        r["quote"] for r in PROFILE["rules"] if r["rule_id"] == "yuan_obstruction_5"
    )
    assert PROFILE["textual_issues"][0]["resolution"].startswith("Unresolved")


@pytest.mark.parametrize("fault", ["changed_profile", "changed_scan", "escaped_scan"])
def test_profile_publisher_rejects_changed_or_detached_source_material(
    tmp_path, monkeypatch, fault
):
    from scripts.liuyao import build_profile as publisher

    monkeypatch.setattr(publisher, "ROOT", tmp_path)
    reference = tmp_path / "tests/fixtures/liuyao_effects_v4"
    reference.mkdir(parents=True)
    source = (
        tmp_path / "outside.txt" if fault == "escaped_scan" else reference / "scan.txt"
    )
    source.write_text("independent source bytes")
    profile = {
        "source": {
            "file": "../../../outside.txt" if fault == "escaped_scan" else "scan.txt",
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        }
    }
    if fault == "changed_scan":
        source.write_text("replaced source bytes")
    original = reference / "profile.json"
    original.write_text(json.dumps(profile))
    (reference / "freeze.json").write_text(
        json.dumps(
            {
                "sha256": {
                    "profile.json": hashlib.sha256(original.read_bytes()).hexdigest()
                }
            }
        )
    )
    if fault == "changed_profile":
        profile["unregistered_claim"] = True
        original.write_text(json.dumps(profile))
    with pytest.raises(ValueError):
        publisher.build_profile("role")


@pytest.mark.parametrize("values", list(product((True, False, None), repeat=3)))
def test_unknown_predicates_are_not_silently_filled_or_counted(values):
    atoms = dict(zip("abc", values))
    and_expected = (
        False
        if any(v is False for v in values)
        else (True if all(v is True for v in values) else None)
    )
    or_expected = (
        True
        if any(v is True for v in values)
        else (False if all(v is False for v in values) else None)
    )
    assert evaluate(["all", "a", "b", "c"], atoms) is and_expected
    assert evaluate(["any", "a", "b", "c"], atoms) is or_expected
    assert evaluate(["all", "a", ["any", "b", "c"]], atoms) is evaluate(
        ["all", "a", "d"], {**atoms, "d": evaluate(["any", "b", "c"], atoms)}
    )


def test_original_daguo_chain_is_retained_without_claiming_effectiveness():
    result = classical(CASES[0])
    roles = result["role_effects"]
    chain = next(
        c for c in roles["chains"] if c["positions"] == CASES[0]["expected_chain"]
    )
    assert chain["status"] == "successive_generation_candidate"
    assert roles["focus_robustness"] == "not_adjudicated"
    edge = next(
        e
        for e in result["interaction_edges"]
        if e["source_kind"] == "base"
        and e["source_position"] == 6
        and e["target_position"] == 4
    )
    assert edge["relation"] == "克爻"
    assert edge["effect_status"] == "direct_control_requires_yuan_routing_review"
    assert chain["chain_id"] in edge["routing_chain_ids"]
    for row in roles["lines"]:
        assert len(row["supporting_conditions"]) == 5
        assert len(row["obstructing_conditions"]) == (6 if row["role"] == "元神" else 7)
        assessed = result["classical_assessment"]["lines"][row["position"] - 1]
        assert (
            row["atom_values"]["strength_wang"] is assessed["strength"]["is_supported"]
        )
        # The newly collated three-location definition has no 丑/辰 tomb
        # actor for these particular metal/earth roles in 大过之鼎.
        assert row["atom_values"]["entered_tomb"] is False
        assert row["adjudication"] == "requires_strength_timing_and_focus_robustness"
    assert "prediction" not in roles and "score" not in roles
    ji = next(r for r in roles["lines"] if r["position"] == 6)
    assert ji["atom_values"]["strength_wang"] is True  # 未日临爻、巳月生土


def test_bound_yuan_does_not_erase_the_direct_ji_control_candidate():
    result = classical(CASES[1])
    chain = next(
        c
        for c in result["role_effects"]["chains"]
        if c["positions"] == CASES[1]["expected_chain"]
    )
    assert chain["status"] == CASES[1]["expected_chain_status"]
    edge = next(
        e
        for e in result["interaction_edges"]
        if e["source_kind"] == "base"
        and e["source_position"] == 2
        and e["target_position"] == 3
    )
    assert edge["effect_status"] == "conditional"
    assert "routing_chain_ids" not in edge
    yuan = next(r for r in result["role_effects"]["lines"] if r["position"] == 4)
    assert yuan["binding_cues"]
    # Co-motion matches, but this cannot resolve the whole effect against a binder.
    assert (
        next(
            c for c in yuan["supporting_conditions"] if c["rule_id"] == "yuan_support_4"
        )["matched"]
        is True
    )


def test_static_yuan_is_not_upgraded_to_co_motion():
    result = classical(CASES[2])["role_effects"]
    assert result["chains"] == []
    assert all(not row["atom_values"]["paired_active"] for row in result["lines"])


def test_bound_ji_cannot_be_presented_as_a_ready_successive_generation_path():
    # Synthetic calendar variant: 未忌逢午日合，酉元并未逢此合。
    result = classical({**CASES[0], "day_ganzhi": "甲午"})["role_effects"]
    chain = next(c for c in result["chains"] if c["positions"] == [6, 5, 4])
    assert chain["status"] == "ji_binding_prevents_routing_candidate"
    assert chain["binding_positions"] == [6]


def test_changed_focus_cannot_receive_other_base_line_control():
    result = classical(CASES[3])["role_effects"]
    assert result["status"] == CASES[3]["expected_status"]
    assert result["chains"] == [] and result["lines"] == []


def test_no_selected_focus_and_calendar_focus_keep_their_own_scope():
    base = CASES[0]
    for kwargs, expected in [
        ({"focus_line": None}, "requires_selected_focus"),
        (
            {"focus_line": None, "focus_kind": "day"},
            "calendar_focus_not_subject_to_line_control",
        ),
    ]:
        result = classical({**base, **kwargs})["role_effects"]
        assert result["status"] == expected
        assert result["chains"] == []


def condition(result, position, rule_id):
    row = next(r for r in result["role_effects"]["lines"] if r["position"] == position)
    return next(
        c
        for c in row["supporting_conditions"] + row["obstructing_conditions"]
        if c["rule_id"] == rule_id
    )


def test_back_generation_is_a_matched_ji_condition_even_on_a_clash_day():
    # Synthetic focus on 四爻未土. The known 渙→坎 transformation is 卯→子.
    result = classical(
        {
            "base_code": "010011",
            "changed_code": "010010",
            "month": "丑",
            "day_ganzhi": "丁酉",
            "focus_line": 4,
        }
    )
    assert condition(result, 6, "ji_support_2")["matched"] is True
    row = next(r for r in result["role_effects"]["lines"] if r["position"] == 6)
    assert row["atom_values"]["injured_relation"] is True
    assert row["adjudication"] == "requires_strength_timing_and_focus_robustness"


def test_advance_condition_and_static_void_condition_are_distinct():
    from fatebridge.core.local_techniques.sixyao import build_sixyao_result

    result = build_sixyao_result(
        date="2000-01-07",
        time="12:00:00",
        zone="Asia/Shanghai",
        gua_code="010100",
        changed_code="010110",
        focus_kind="hidden",
        focus_line=1,
    )
    conditional = result["liuyao_evidence"]["conditional_analysis"]
    assert conditional["focus"]["selected"]["branch"] == "子"
    assert condition(conditional, 5, "yuan_support_2")["matched"] is True
    static = classical(
        {
            "base_code": "111111",
            "changed_code": "111111",
            "month": "丑",
            "day_ganzhi": "甲子",
            "focus_line": 1,
        }
    )
    assert condition(static, 6, "ji_obstruction_2")["matched"] is True
    assert condition(static, 3, "ji_obstruction_2")["matched"] is False


def test_chou_co_motion_is_not_confused_with_yuan_co_motion():
    result = classical(
        {
            "base_code": "111111",
            "changed_code": "110011",
            "month": "丑",
            "day_ganzhi": "甲子",
            "focus_line": 1,
        }
    )
    assert condition(result, 3, "ji_support_5")["matched"] is True
    assert condition(result, 3, "ji_obstruction_7")["matched"] is False
    assert result["role_effects"]["chains"] == []


def test_fire_stage_gap_is_unknown_instead_of_absence_or_another_school_table():
    case = {
        "base_code": "111111",
        "changed_code": "111111",
        "month": "辰",
        "day_ganzhi": "甲子",
        "focus_line": 3,
    }
    assert condition(classical(case), 4, "yuan_support_3")["matched"] is None
    assert (
        condition(classical({**case, "day_ganzhi": "庚寅"}), 4, "yuan_support_3")[
            "matched"
        ]
        is True
    )


def test_all_base_changed_pairs_and_visible_foci_conserve_role_route_directions():
    # 24,576 finite structures at one explicitly fixed month/day. This is
    # an invariant audit, not 24,576 independent classical or reality cases.
    codes = ["".join(bits) for bits in product("01", repeat=6)]
    generates = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
    controls = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
    moment = datetime.fromisoformat("2000-01-07T12:00:00+08:00")
    for base, changed in product(codes, repeat=2):
        info, lines = mounted(base, changed)
        for focus_position in range(1, 7):
            result = build_conditional_analysis(
                lines=lines,
                hidden=[],
                month="辰",
                day_ganzhi="甲子",
                palace=info["current_palace_element"],
                moment=moment,
                focus_line=focus_position,
                focus_kinship=None,
                timing_days=0,
            )
            role_effects = result["role_effects"]
            chains = {c["chain_id"]: c for c in role_effects["chains"]}
            for chain in chains.values():
                j, y, f = chain["positions"]
                assert f == focus_position
                ji, yuan, focus = [lines[p - 1] for p in (j, y, f)]
                assert generates[ji["element"]] == yuan["element"]
                assert generates[yuan["element"]] == focus["element"]
                assert controls[ji["element"]] == focus["element"]
                assert set(chain["binding_positions"]) <= {j, y}
                if chain["status"] == "successive_generation_candidate":
                    assert chain["binding_positions"] == []
                    assert chain["obstructed_positions"] == []
                    assert not result["lines"][j - 1]["outgoing_obstructions"]
                    assert not result["lines"][y - 1]["outgoing_obstructions"]
                assert role_effects["focus_robustness"] == "not_adjudicated"
            for edge in result["interaction_edges"]:
                if (
                    edge["effect_status"]
                    == "direct_control_requires_yuan_routing_review"
                ):
                    assert edge["source_kind"] == "base"
                    assert edge["target_position"] == focus_position
                    assert edge["relation"] == "克爻"
                    for chain_id in edge["routing_chain_ids"]:
                        assert (
                            chains[chain_id]["status"]
                            == "successive_generation_candidate"
                        )
                        assert (
                            chains[chain_id]["positions"][0] == edge["source_position"]
                        )

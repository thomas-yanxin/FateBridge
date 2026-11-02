"""Co-motion routes require both stages, permission and target admission."""

import hashlib
import json
from pathlib import Path

import pytest

from tests.test_liuyao_conditions import conditional_case

REFERENCE = Path(__file__).parent / "fixtures/liuyao_routing_v13"
CASES = json.loads((REFERENCE / "cases.json").read_text())["cases"]


def routing_case(case):
    if case.get("focus_kind") == "hidden":
        from fatebridge.core.local_techniques.sixyao import build_sixyao_result

        r = build_sixyao_result(
            date=case["date"],
            time="12:00:00",
            gua_code=case["base_code"],
            changed_code=case["changed_code"],
            focus_kind="hidden",
            focus_line=case["focus_line"],
        )
        assert r["nongli"]["dayGanZi"] == case["day_ganzhi"]
        assert r["nongli"]["monthGanZi"][1] == case["month_branch"]
        return r["liuyao_evidence"]["conditional_analysis"]
    return conditional_case(case)


def test_routing_original_and_case_bytes_remain_frozen():
    from fatebridge.core.liuyao_routing import PROFILE
    from scripts.build_liuyao_routing_profile import build

    assert PROFILE == build()
    for name, digest in json.loads((REFERENCE / "freeze.json").read_text())[
        "sha256"
    ].items():
        assert hashlib.sha256((REFERENCE / name).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_frozen_route_qualification_and_alternative_aggregation(case):
    result = routing_case(case)
    routes = result["routing_conditions"]
    assert routes["focus"]["condition_match"] is case["expected_focus_condition"]
    if case["positions"] is None:
        assert not routes["routes"]
        return
    route = next(r for r in routes["routes"] if r["positions"] == case["positions"])
    assert route["condition_match"] is case["expected_route"]
    assert route["status"] and route["conditions"]
    if case.get("other_route"):
        assert (
            next(r for r in routes["routes"] if r["positions"] == case["other_route"])[
                "condition_match"
            ]
            is True
        )
    assert "success_probability" not in route and "predicted_success" not in route


def test_rootless_original_keeps_raw_path_but_does_not_present_ready_relief():
    result = routing_case(CASES[0])
    raw = next(
        c for c in result["role_effects"]["chains"] if c["positions"] == [6, 5, 4]
    )
    assert raw["status"] == "successive_generation_candidate"
    assert raw["route_condition_match"] is False
    edge = next(
        e
        for e in result["interaction_edges"]
        if e["source_kind"] == "base"
        and (e["source_position"], e["target_position"]) == (6, 4)
    )
    assert edge["relation"] == "克爻"
    assert edge["qualified_routing_condition"] is False


def test_back_controlled_route_snapshot_is_not_the_generic_candidate_text():
    from fatebridge.core.local_techniques.sixyao import build_sixyao_result

    r = build_sixyao_result(
        date="2000-09-02",
        time="12:00:00",
        gua_code="011110",
        changed_code="010111",
        focus_line=4,
    )
    # Snapshot assertions inspect the selected branch only, not event outcomes.
    assert "回头克阻断当前接续条件" in r["snapshot_text"]


def test_qualified_route_edges_keep_their_own_controller_and_original_direction():
    for case in CASES:
        result = routing_case(case)
        routes = result["routing_conditions"]["routes"]
        by_id = {r["chain_id"]: r for r in routes}
        for edge in result["interaction_edges"]:
            if "qualified_routing_status" not in edge:
                continue
            assert result["focus"]["selected"]["location"] == "visible"
            assert edge["source_kind"] == edge["target_kind"] == "base"
            assert edge["relation"] == "克爻"
            for key in ("conditional_routing_chain_ids", "rejected_routing_chain_ids"):
                for chain_id in edge[key]:
                    route = by_id[chain_id]
                    assert (route["positions"][0], route["positions"][2]) == (
                        edge["source_position"],
                        edge["target_position"],
                    )
                    assert (route["condition_match"] is False) == (
                        key == "rejected_routing_chain_ids"
                    )


def test_page59_variant_is_exposed_without_rewriting_old_transcription():
    from fatebridge.core.liuyao_routing import PROFILE

    note = next(
        n for n in PROFILE["textual_issues"] if n["id"] == "page59-he-versus-ling"
    )
    assert note["scan_reading"].endswith("合之")
    assert "令之" in note["frozen_transcription_reading"]
    assert "v13" in note["resolution_update"]
    root = Path(__file__).resolve().parents[1]
    assert (
        hashlib.sha256(
            (root / note["frozen_transcription_file"]).read_bytes()
        ).hexdigest()
        == note["frozen_transcription_sha256"]
    )


def test_changed_focus_does_not_borrow_original_receiving_gate():
    result = conditional_case(CASES[0], focus_line=5, focus_kind="changed")
    assert result["routing_conditions"]["focus"]["condition_match"] is None
    assert result["routing_conditions"]["routes"] == []


def test_original_rootless_snapshot_does_not_upgrade_a_route_to_receiving_help():
    from fatebridge.core.local_techniques.sixyao import build_sixyao_result

    r = build_sixyao_result(
        date="2002-05-27",
        time="12:00:00",
        gua_code="011110",
        changed_code="011101",
        focus_line=4,
    )
    statements = [
        s for s in r["snapshot_text"].splitlines() if s.startswith("元忌同动路径")
    ]
    assert statements and all("不能据路径认定已受生" in s for s in statements)
    assert all("接续相生候选" not in s for s in statements)

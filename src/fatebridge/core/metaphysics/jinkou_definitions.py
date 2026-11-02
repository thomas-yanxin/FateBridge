"""Collated unresolved clauses and conditional facts, never new predicates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...utils.data import EARTHLY_BRANCHES
from .common import ELEMENT_CONTROLS, ELEMENT_GENERATES, stem_element_text
from .jinkou_stems import wuzidun_stem


def chapter_provenance() -> dict[str, Any]:
    """The witness's bounded chapter inventory, never a predicate oracle."""
    path = Path(__file__).resolve().parents[2] / "data/jinkou_waseda_chapter.json"
    value: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return value


def definition_evidence(
    *, day_stem: str, hour_branch: str, is_diurnal: bool, rows: list[dict[str, Any]]
) -> dict[str, Any]:
    # Lazy import: the board builder calls this function after module loading.
    from fatebridge.core.metaphysics.jinkou_guishen import (
        GUISHEN_IDENTITIES,
        _build_guishen_mapping,
    )

    if [r.get("label") for r in rows] != ["人元", "贵神", "将神", "地分"]:
        raise ValueError("课钤疑义证据需要按次序排列的四位")
    by_label = {r["label"]: r for r in rows}
    ground, human = rows[3]["content"], rows[0]["content"]
    path = Path(__file__).resolve().parents[2] / "data/jinkou_definition_witnesses.json"
    readings = json.loads(path.read_text(encoding="utf-8"))
    next(w for w in readings["witnesses"] if w["id"] == "waseda_book6").update(
        chapter_provenance()
    )
    alternatives = []
    for mode, flag in (("day", True), ("night", False)):
        start, mapping = _build_guishen_mapping(day_stem, hour_branch, flag)
        name = mapping[ground]
        steps = (EARTHLY_BRANCHES.index(ground) - EARTHLY_BRANCHES.index(start)) % 12
        alternatives.append(
            dict(
                mode=mode,
                assumed_is_diurnal=flag,
                selected_under_current_policy=flag == is_diurnal,
                start_branch=start,
                ground_branch=ground,
                god_name=name,
                intrinsic_ganzhi=GUISHEN_IDENTITIES[name],
                ground_clockwise_steps=steps,
                ground_counterclockwise_steps=(-steps) % 12,
            )
        )
    hypotheses = []
    up_a = [("地分", "人元"), ("贵神", "将神")]
    up_b = [("地分", "将神"), ("贵神", "人元")]
    for pid, upwards in (("P52", True), ("P53", False)):
        for hid, pairs in (
            ("outer_inner", up_a),
            ("adjacent_pairs", up_b),
            ("conjunction", up_a + up_b),
        ):
            checks = []
            for a, b in pairs:
                a, b = (a, b) if upwards else (b, a)
                ae, be = by_label[a]["element"], by_label[b]["element"]
                checks.append(
                    dict(
                        source_position=a,
                        target_position=b,
                        source_element=ae,
                        target_element=be,
                        relation="生",
                        matched=ELEMENT_GENERATES[ae] == be,
                    )
                )
            hypotheses.append(
                dict(
                    pattern_id=pid,
                    hypothesis_id=hid,
                    condition_checks=checks,
                    all_conditions_met=all(c["matched"] for c in checks),
                    adjudicated_predicate=None,
                )
            )
    intrinsic = rows[1]["intrinsic_ganzhi"]
    routes = []
    for rid, stem, anchor, branch in (
        ("intrinsic_god", intrinsic[0], None, rows[1]["content"]),
        (
            "daily_god",
            wuzidun_stem(day_stem, rows[1]["content"]),
            day_stem,
            rows[1]["content"],
        ),
        (
            "daily_general",
            wuzidun_stem(day_stem, rows[2]["content"]),
            day_stem,
            rows[2]["content"],
        ),
        ("human_redun_at_ground", wuzidun_stem(human, ground), human, ground),
    ):
        element = stem_element_text(stem)
        routes.append(
            dict(
                route_id=rid,
                anchor_stem=anchor,
                target_branch=branch,
                stem=stem,
                element=element,
                is_ding=stem == "丁",
                controls_human=ELEMENT_CONTROLS[element] == rows[0]["element"],
                controls_ground=ELEMENT_CONTROLS[element] == rows[3]["element"],
                identified_by_original_clause=None,
            )
        )
    return dict(
        ruleset_id="jinkou_unresolved_definition_evidence_v1",
        day_stem=day_stem,
        hour_branch=hour_branch,
        selected_is_diurnal=is_diurnal,
        **readings,
        cross_generation_hypotheses=hypotheses,
        day_night_candidates=alternatives,
        ground_equals_day_start=ground == alternatives[0]["start_branch"],
        ground_equals_night_start=ground == alternatives[1]["start_branch"],
        ground_equals_other_start=ground
        == alternatives[0 if not is_diurnal else 1]["start_branch"],
        ding_routes=routes,
        observed_twilight_transition=None,
        front_back_predicate=None,
        complete_classical_conformance=False,
        scope="六条原典疑义逐条保留书影文字与例课差异。隔生三种配对是待裁定数学假设，昼夜两候选是同课条件换算，前后只列地支环距离，人元再遁仅列候选路径；均不进入六十四课命中。书影数量不等于独立事件数，固定时支或显式昼夜也不证明观星交界，不给现实预测结论。",
    )

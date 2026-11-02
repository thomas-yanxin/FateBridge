"""Two-eye elemental relations, separate from spatial 關 and whole outcomes."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .common import ELEMENT_CONTROLS, ELEMENT_GENERATES

CATALOG_SHA256 = "dff1e69e6dcbc69ce9ebe4dc53c6e2f2ca785f2dc20eceb5214fb38494ed043b"
LABELS = {
    "same_element": "同一五行",
    "main_generates_guest": "主生客",
    "guest_generates_main": "客生主",
    "main_controls_guest": "主克客",
    "guest_controls_main": "客克主",
}


@lru_cache(maxsize=1)
def source_catalog() -> dict[str, Any]:
    p = (
        Path(__file__).resolve().parents[2]
        / "data/classical/taiyi-elemental-relations-v1.json"
    )
    raw = p.read_bytes()
    if hashlib.sha256(raw).hexdigest() != CATALOG_SHA256:
        raise ValueError("二目五行资料指纹不符")
    data: dict[str, Any] = json.loads(raw)
    if len(data["spirit_elements"]) != 16:
        raise ValueError("二目五行表须保留十六神")
    return data


def element_relation(main: str, guest: str) -> str:
    if main not in ELEMENT_CONTROLS or guest not in ELEMENT_CONTROLS:
        raise ValueError("二目元素必须为明确的木火土金水")
    if main == guest:
        return "same_element"
    if ELEMENT_CONTROLS[main] == guest:
        return "main_controls_guest"
    if ELEMENT_CONTROLS[guest] == main:
        return "guest_controls_main"
    return (
        "main_generates_guest"
        if ELEMENT_GENERATES[main] == guest
        else "guest_generates_main"
    )


def elemental_guan_assessment(
    core: dict[str, Any],
    patterns: list[dict[str, Any]] | None = None,
    *,
    calculation_mode: str | None = None,
) -> dict[str, Any]:
    if calculation_mode not in {None, "year", "month", "day", "hour"}:
        raise ValueError("二目五行时间层须为明确计法或未知")
    data = source_catalog()
    mapping = {s["position"]: s for s in data["spirit_elements"]}
    ruleset = {
        k: data[k]
        for k in [
            "id",
            "version",
            "author",
            "source_title",
            "classical_author",
            "source_manifest_sha256",
        ]
    }
    ruleset.update(source_urls=list(data["source_urls"]), catalog_sha256=CATALOG_SHA256)
    usage = (
        "day_mode_selected_fragment_only"
        if calculation_mode == "day"
        else (
            "reference_only_source_names_day_method"
            if calculation_mode
            else "time_method_not_supplied"
        )
    )
    result: dict[str, Any] = {
        "ruleset": ruleset,
        "calculation_mode": calculation_mode,
        "source_day_usage": usage,
        "full_daily_na_yin_method_verified": False,
        "role_scope": data["role_scope"],
        "method_scope": data["method_scope"],
        "scope": data["interpretation_scope"],
        "real_world_efficacy": "not_tested",
        "implemented_spatial_guan": {
            "status": (
                "supplied_implemented_patterns_only"
                if patterns is not None
                else "not_assessed"
            ),
            "present": (
                any(p.get("name") == "关" for p in patterns)
                if patterns is not None
                else None
            ),
            "pattern_paths": [
                f"patterns.{i}"
                for i, p in enumerate(patterns or [])
                if p.get("name") == "关"
            ],
            "scope": "仅回指本盘已实现的空间关列表；未列不证明所有版本无关，不参与本项五行关系。",
        },
    }
    if not all(
        type(core.get(k)) is str and core[k] in mapping
        for k in ["wenchang_palace", "shiji"]
    ):
        result.update(
            status="not_assessed",
            reason="二目实际十六神位置缺失或无效，不猜缺失宫位或五行。",
            eyes=[],
        )
        return result
    eyes = []
    for camp, field, role, path in [
        ("main", "wenchang_palace", "文昌", "wenchang_palace"),
        ("guest", "shiji", "始击", "core_board.shiji"),
    ]:
        spirit = mapping[core[field]]
        eyes.append(
            {
                "camp": camp,
                "role": role,
                "actual_path": path,
                "position": core[field],
                "source_name": spirit["source_name"],
                "element": spirit["element"],
            }
        )
    m, g = eyes[0]["element"], eyes[1]["element"]
    relation = element_relation(m, g)
    controller = (
        "main"
        if relation == "main_controls_guest"
        else "guest" if relation == "guest_controls_main" else None
    )
    if controller:
        kind = "conditional_source_rule"
        reading = "主來克客主軍贏" if controller == "main" else "客克主兮主不利"
        bound = "所读二目五行相制的传统原断片段，不是本次现实胜负或五将空间合取。"
    elif relation == "same_element":
        kind = "same_element_source_verse"
        reading = "若也同音三陣平"
        bound = "仅所选十六神五行表的同类关系；不宣称现实平局。"
    elif {m, g} == {"金", "土"}:
        kind = "source_example_analogy"
        reading = "金土相生，陰陽和同，戰必和解也"
        bound = "所读原例为主目武德申金、客目阳德丑土；本次只作同类元素关系参照，不当作同一古例或真实和解。"
    else:
        kind = "relation_only"
        reading = None
        bound = "只交付所选五行生关系；没有把金土原例推广成所有相生必和解。"
    result.update(
        status="computed_selected_eye_elements",
        eyes=eyes,
        relation=relation,
        relation_label=LABELS[relation],
        elemental_control=controller is not None,
        controlling_camp=controller,
        source_interpretation={
            "kind": kind,
            "reading": reading,
            "source": data["source_urls"][1],
            "applicability": usage,
            "scope": bound,
            "overall_outcome_assessed": False,
        },
    )
    return result


def elemental_relations_text(a: dict[str, Any]) -> str:
    if a["status"] == "not_assessed":
        return str(a["reason"])
    main, guest = a["eyes"]
    s = a["source_interpretation"]
    text = f"二目五行片段：主方{main['role']}在{main['position']}（{main['source_name']}、{main['element']}），客方{guest['role']}在{guest['position']}（{guest['source_name']}、{guest['element']}）；{a['relation_label']}。"
    if s["reading"]:
        text += f"传统原文参照：{s['reading']}。"
    text += str(s["scope"]) + str(a["method_scope"]) + str(a["scope"])
    if a["calculation_mode"] != "day":
        text += "本次不是已确认采用该日计方法，只保留位置关系与原文参照。"
    return text

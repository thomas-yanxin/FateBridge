"""Join actual boards by physical position, with no joint outcome inference.

Jinjing vol. 2 numbers Taiyi palaces differently from the Later Heaven chart.
Its vol. 1 太乙當時法 motivates consulting the actual twelve gods, but does
not license an invented four-corner lodging rule. List both actual same-sector
branches while leaving each corner's selected lodging unassessed.
"""

from typing import Any

from fatebridge.core.metaphysics.taiyi_geometry import PALACES, SOURCES

# Taiyi number -> physical trigram, Later Heaven/Qimen number, compass bearing.
PHYSICAL = {
    1: ("乾", 6, "西北"),
    2: ("离", 9, "南"),
    3: ("艮", 8, "东北"),
    4: ("震", 3, "东"),
    5: ("中", 5, "中央"),
    6: ("兑", 7, "西"),
    7: ("坤", 2, "西南"),
    8: ("坎", 1, "北"),
    9: ("巽", 4, "东南"),
}
MARKERS = {
    "太乙": "taiyi_number",
    "主大将": "main_general",
    "主参将": "main_vice_general",
    "客大将": "guest_general",
    "客参将": "guest_vice_general",
}
SECTOR_BRANCHES = {1: ("戌", "亥"), 3: ("丑", "寅"), 7: ("未", "申"), 9: ("辰", "巳")}


def liuren_at_taiyi_palace(number: int, liureng: dict[str, Any]) -> dict[str, Any]:
    """Read actual branch rows; a sector pair never chooses a lodging."""
    if type(number) is not int or number not in PALACES:
        raise ValueError("三式对应需要一至九的实际太乙宫数")
    palace = PALACES[number]

    def actual_row(branch: str) -> dict[str, Any]:
        matches = [
            (i, p)
            for i, p in enumerate(liureng["twelve_board"])
            if p["earth_branch"] == branch
        ]
        if len(matches) != 1:
            raise ValueError("三式对应要求唯一的六壬实际地盘支位")
        index, row = matches[0]
        return {"source_path": f"liureng.twelve_board.{index}", **row}

    if palace in "子卯午酉":
        return {"status": "direct_branch_match", **actual_row(palace)}
    if number == 5:
        return {"status": "not_assessed", "reason": "中宫无直接地支，不自动寄坤"}
    return {
        "status": "not_assessed",
        "reason": "四维寄支未校勘；同方位两支仅并列，不据神将吉凶择一",
        "candidate_scope": "same_sector_branches_not_adjudicated_lodging",
        "sector_source_urls": [
            SOURCES["2"] + "#推九宫所主法",
            SOURCES["9"] + "#推太乙與太嵗格",
        ],
        "sector_candidates": [actual_row(branch) for branch in SECTOR_BRANCHES[number]],
    }


def palace_correspondences(
    taiyi: dict[str, Any], qimen: dict[str, Any], liureng: dict[str, Any]
) -> dict[str, Any]:
    """Read positions from the supplied boards; never recalculate a subchart."""
    entries = []
    for label, field in MARKERS.items():
        number = taiyi["core_board"][field]
        trigram, qimen_number, direction = PHYSICAL[number]
        palace = PALACES[number]
        qmatch = [
            (i, p) for i, p in enumerate(qimen["palaces"]) if p["index"] == qimen_number
        ]
        if len(qmatch) != 1 or qmatch[0][1]["trigram"] != trigram:
            raise ValueError("三式对应要求唯一且同方位的奇门实际宫，不能直接套太乙宫数")
        qi, qp = qmatch[0]
        qrow = {
            "source_path": f"qimen.palaces.{qi}",
            "index": qp["index"],
            "trigram": qp["trigram"],
            "star": qp["star"],
            "door": qp["door"],
            "god": qp["god"],
            "hosted_stars": qp.get("hosted_stars", []),
        }
        lrow = liuren_at_taiyi_palace(number, liureng)
        entries.append(
            {
                "marker": label,
                "taiyi_source_path": "taiyi.core_board." + field,
                "taiyi_number": number,
                "taiyi_palace": palace,
                "trigram": trigram,
                "direction": direction,
                "qimen": qrow,
                "liureng": lrow,
            }
        )
    return {
        "ruleset": {
            "id": "sanshi_physical_correspondence_v1",
            "version": "1.1.0",
            "author": "FateBridge contributors",
            "sources": [
                SOURCES["2"] + "#推九宫所主法",
                SOURCES["9"] + "#推太乙與太嵗格",
                SOURCES["1"] + "#太乙當時法",
            ],
            "conformance": "modern_geometric_join_not_full_classical_joint_judgment",
        },
        "scope": "按原盘同方位对应星门神；子卯午酉直接查六壬地盘十二神，四维并列同方位两支且不选寄支，中五不寄宫。年/月/日计为跨时间层结构对照，时计仍需校定古法寄宫。",
        "entries": entries,
        "joint_judgment": "not_implemented",
        "missing_rules": [
            "四维和中五寄支未完成他本校勘",
            "太乙当时法的贵人、顺逆与本次六壬配置是否同派尚待课例裁定",
            "完整门具将发、主客吉神凶神的联合断法尚未实现",
        ],
    }


def correspondence_text(joined: dict[str, Any]) -> str:
    lines = [joined["scope"]]
    for entry in joined["entries"]:
        q = entry["qimen"]
        ren = entry["liureng"]
        liuren_text = (
            f"六壬地盘{ren['earth_branch']}、天盘{ren['sky_branch']}、{ren['god']}"
            if ren["status"] == "direct_branch_match"
            else "六壬未评估：" + ren["reason"]
        )
        if ren.get("sector_candidates"):
            candidates = "；".join(
                f"地盘{p['earth_branch']}／天盘{p['sky_branch']}／{p['god']}"
                for p in ren["sector_candidates"]
            )
            liuren_text += "；同方位候选（未选寄支）：" + candidates
        lines.append(
            f"{entry['marker']}：太乙{entry['taiyi_number']}宫{entry['taiyi_palace']}／{entry['direction']}，对应奇门{q['index']}宫{q['trigram']}：{q['star'] or '无独立星'}、{q['door'] or '无独立门'}、{q['god'] or '无独立神'}；{liuren_text}。"
        )
    lines.append("以上只列已计算的对应事实；联合成败断法未实现。")
    return "\n".join(lines)

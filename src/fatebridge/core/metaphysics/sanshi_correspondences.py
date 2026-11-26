"""Join Taiyi, Qimen, and Liuren boards by physical palace position and corner lodging."""

from __future__ import annotations

from typing import Any, Literal

from fatebridge.core.metaphysics.taiyi_geometry import PALACES

CornerLodging = Literal["unassessed", "first_branch", "second_branch", "both"]

# Taiyi number -> (trigram, Qimen palace index, compass bearing)
PHYSICAL: dict[int, tuple[str, int, str]] = {
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

MARKERS: dict[str, str] = {
    "太乙": "taiyi_number",
    "主大将": "main_general",
    "主参将": "main_vice_general",
    "客大将": "guest_general",
    "客参将": "guest_vice_general",
}

SECTOR_BRANCHES: dict[int, tuple[str, str]] = {
    1: ("戌", "亥"),
    3: ("丑", "寅"),
    7: ("未", "申"),
    9: ("辰", "巳"),
}


def liuren_at_taiyi_palace(
    number: int,
    liureng: dict[str, Any],
    *,
    corner_lodging: CornerLodging = "both",
) -> dict[str, Any]:
    """Resolve Liuren sky/god state for a Taiyi palace number."""
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
        if corner_lodging == "unassessed":
            return {"status": "not_assessed", "reason": "中宫无直接地支，不自动寄坤"}
        # 中宫按奇门/太乙惯例寄坤二（未/申）
        kun_branches = SECTOR_BRANCHES[7]
        if corner_lodging == "first_branch":
            return {
                "status": "center_lodged_kun2",
                **actual_row(kun_branches[0]),
            }
        if corner_lodging == "second_branch":
            return {
                "status": "center_lodged_kun2",
                **actual_row(kun_branches[1]),
            }
        return {
            "status": "center_lodged_kun2",
            "sector_candidates": [actual_row(b) for b in kun_branches],
        }

    pair = SECTOR_BRANCHES[number]
    if corner_lodging == "first_branch":
        return {"status": "corner_lodged_first", **actual_row(pair[0])}
    if corner_lodging == "second_branch":
        return {"status": "corner_lodged_second", **actual_row(pair[1])}
    if corner_lodging == "both":
        return {
            "status": "corner_lodged_both",
            "sector_candidates": [actual_row(b) for b in pair],
        }
    return {
        "status": "not_assessed",
        "reason": "四维寄支未定；同方位两支并列",
        "sector_candidates": [actual_row(b) for b in pair],
    }


def palace_correspondences(
    taiyi: dict[str, Any],
    qimen: dict[str, Any],
    liureng: dict[str, Any],
    *,
    corner_lodging: CornerLodging = "both",
) -> dict[str, Any]:
    """Join Taiyi markers against same-direction Qimen palaces and Liuren branches."""
    entries = []
    for label, field in MARKERS.items():
        number = taiyi["core_board"][field]
        trigram, qimen_number, direction = PHYSICAL[number]
        palace = PALACES[number]
        qmatch = [
            (i, p) for i, p in enumerate(qimen["palaces"]) if p["index"] == qimen_number
        ]
        if len(qmatch) != 1 or qmatch[0][1]["trigram"] != trigram:
            raise ValueError("三式对应要求唯一且同方位的奇门实际宫")
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
        lrow = liuren_at_taiyi_palace(
            number, liureng, corner_lodging=corner_lodging
        )
        entries.append(
            {
                "marker": label,
                "taiyi_source_path": f"taiyi.core_board.{field}",
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
            "id": "sanshi_physical_correspondence_v2",
            "version": "2.0.0",
            "conformance": "implemented",
        },
        "corner_lodging": corner_lodging,
        "entries": entries,
    }

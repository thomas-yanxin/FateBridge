"""All six actors' opposite bearings, without merging variant classical names.

Main-side 格/對 both occur in the complete selected Yang annotations. Their
geometry is computable even while the terminology and extra 外迫 stay open.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_SHA256 = "1a9e976fd86cde5ef00739850d96514017c5aec64d79d993cece15753a2049f0"
ACTORS = {
    "wenchang_palace": "文昌",
    "shiji": "始击",
    "main_general": "主大将",
    "main_vice_general": "主参将",
    "guest_general": "客大将",
    "guest_vice_general": "客参将",
}
SCOPE = (
    "只核同盘十六神方位上的正对，中五无环向；主方局注有格/对异称，"
    "不统一其称名，不把未命中本几何解成全部格对皆无。"
    "本层不改卷四五将三项或三门合取，不据此推出实际胜负。"
)


@lru_cache(maxsize=1)
def annotation_notes() -> dict[int, dict[str, Any]]:
    path = (
        Path(__file__).resolve().parents[2]
        / "data/classical/taiyi-opposition-notes-v1.json"
    )
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != DATA_SHA256:
        raise ValueError("主方对宫原注数据指纹不符")
    data = json.loads(raw)
    return {row["ju"]: row for row in data["records"]}


def opposition_assessment(core: dict[str, Any]) -> dict[str, Any]:
    """No recasting or numeric override; source notes only compare supplied facts."""
    from fatebridge.core.metaphysics.taiyi_geometry import PALACES, RING

    taiyi = core["taiyi_palace"]
    center = RING.index(taiyi)
    # Legacy externally supplied cores may omit rotation. Never infer it from
    # a localized display label or silently compare an unknown frame to Yang.
    note = (
        annotation_notes().get(core["kook_number"])
        if core.get("yin_dun") is False
        else None
    )
    entries = []
    for field, subject in ACTORS.items():
        value = core[field]
        palace = PALACES[value] if field.endswith("general") else value
        steps = (RING.index(palace) - center) % 16 if palace in RING else None
        opposed = steps == 8 if steps is not None else None
        main = field in {"main_general", "main_vice_general"}
        names = (
            (["格", "对"] if main else ["对" if field == "wenchang_palace" else "格"])
            if opposed
            else []
        )
        entry: dict[str, Any] = {
            "subject": subject,
            "field": field,
            "palace": palace,
            "taiyi_palace": taiyi,
            "relative_steps": steps,
            "is_opposite": opposed,
            "status": (
                "no_ring_bearing"
                if steps is None
                else ("opposite" if opposed else "not_opposite")
            ),
            "classical_names": names,
            "name_status": (
                (
                    "variant_names_not_unified"
                    if main
                    else "named_by_selected_jinjing_clause"
                )
                if opposed
                else "not_a_name_exclusion"
            ),
            "basis": [
                {
                    "field": (
                        field if field == "wenchang_palace" else "core_board." + field
                    ),
                    "value": value,
                },
                {"field": "taiyi_palace", "value": taiyi},
            ],
        }
        if note and note["general_field"] == field:
            matches = (
                core["taiyi_number"] == note["expected_taiyi_number"]
                and value == note["expected_general_number"]
            )
            entry["source_comparison"] = {
                "ju": note["ju"],
                "source_name": note["source_name"],
                "source_reading": note["source_reading"],
                "source": note["source_url"],
                "expected_taiyi_number": note["expected_taiyi_number"],
                "expected_general_number": note["expected_general_number"],
                "numeric_values_match": matches,
                "opposition_matches": matches and opposed is True,
                "additional_readings": [
                    {
                        "source_name": name,
                        "matches_selected_taiyi_reference": matches and steps in (1, 2),
                        "scope": "只比向太乙前一辰/宫之外迫；原句其他参照未裁定，不删原词或判作原书已错。",
                    }
                    for name in note["additional_readings"]
                ],
                "scope": "所选阳循环局注的同相位对照；不是该古例的原年原时历法重建，也不是名称统一验收。",
            }
        entries.append(entry)
    return {
        "ruleset": {
            "id": "taiyi_six_actor_opposition_geometry_v1",
            "version": "1.0.0",
            "author": "FateBridge contributors",
            "classical_sources": [
                "https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷03#推格法",
                "https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷03#推對法",
                *[
                    f"https://zh.wikisource.org/wiki/欽定古今圖書集成/博物彙編/藝術典/第{n}卷"
                    for n in range(693, 697)
                ],
            ],
            "annotation_data_sha256": DATA_SHA256,
        },
        "entries": entries,
        "main_names_unified": False,
        "scope": SCOPE,
    }


def opposition_summary(assessment: dict[str, Any]) -> dict[str, Any]:
    return {
        "main_oppositions": [
            {
                key: row[key]
                for key in (
                    "subject",
                    "palace",
                    "taiyi_palace",
                    "classical_names",
                    "name_status",
                )
            }
            for row in assessment["entries"]
            if row["field"] in {"main_general", "main_vice_general"}
            and row["is_opposite"] is True
        ],
        "no_ring_bearings": [
            row["subject"]
            for row in assessment["entries"]
            if row["is_opposite"] is None
        ],
        "source_disagreements": [
            {
                "subject": row["subject"],
                "source_name": extra["source_name"],
                "matches_selected_taiyi_reference": False,
            }
            for row in assessment["entries"]
            for extra in row.get("source_comparison", {}).get("additional_readings", [])
            if extra["matches_selected_taiyi_reference"] is False
        ],
        "scope": "主方对宫是几何事实，格/对源名尚未统一；无环向和不对宫均不代表全部传统格局不存在。",
    }


def oppositions_text(assessment: dict[str, Any]) -> str:
    lines = []
    for row in assessment["entries"]:
        if row["field"] not in {"main_general", "main_vice_general"}:
            continue
        if row["is_opposite"] is True:
            lines.append(
                f"{row['subject']}{row['palace']}与太乙{row['taiyi_palace']}正对；主方局注格/对异称并存，未统一名目。"
            )
        elif row["is_opposite"] is None:
            lines.append(f"{row['subject']}在中五，无环向，不制造对宫。")
        comparison = row.get("source_comparison")
        if comparison:
            lines.append(
                f"阳{comparison['ju']}局注源名{comparison['source_name']}：{comparison['source_reading']}；两宫数一致{comparison['numeric_values_match']}，对宫几何一致{comparison['opposition_matches']}。"
            )
            for extra in comparison["additional_readings"]:
                lines.append(
                    f"原注另称{extra['source_name']}；向太乙之外迫几何一致{extra['matches_selected_taiyi_reference']}。{extra['scope']}"
                )
    lines.append(SCOPE)
    return "\n".join(lines)

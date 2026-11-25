"""Source-scoped count qualities; literal ranks never replace contextual rules."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CATALOG_SHA256 = "3aaa4ee2f3ff3649ad81836620722bfcfdeb5a74a2d398d50577ab05cf99d8bb"
VOL2 = "https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷02"
VOL6 = "https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷06"
YANG_POSITIONS = frozenset("乾午艮卯酉坤子巽")
YIN_POSITIONS = frozenset("亥丑寅辰巳未申戌")
SCOPE = (
    "主客算分层阅读：缺数按卷六明列，足数是十/五/一筹分解推导，杜塞为淘金歌数格，"
    "不等于实际八门全闭。和数清单逐源保留，未列不是否定；太乙宫与二目配数分别计算，"
    "孤单数族不替代位置重阴阳。不以字面上和替代位置配数，不裁成总体和或现实胜负。定计归属及完整断法仍待核。"
)


def _validate(count: int) -> None:
    if type(count) is not int or not 1 <= count <= 40:
        raise ValueError("主客算分类需要1至40的整数")


@lru_cache(maxsize=1)
def source_profiles() -> list[dict[str, Any]]:
    path = (
        Path(__file__).resolve().parents[2]
        / "data/classical/taiyi-count-profiles-v1.json"
    )
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != CATALOG_SHA256:
        raise ValueError("主客算分源目录指纹不符")
    profiles: list[dict[str, Any]] = json.loads(raw)["profiles"]
    return profiles


def components(count: int) -> dict[str, int]:
    _validate(count)
    return {"ten": count // 10 * 10, "five": count % 10 // 5 * 5, "one": count % 5}


def count_labels(count: int) -> list[str]:
    """Keep literal negative lists distinct from an explicitly named inference."""
    _validate(count)
    labels = []
    if count < 10:
        labels.append("无天")
    if 1 <= count % 10 <= 4:
        labels.append("无地")
    if count % 10 == 0:
        labels.append("无人")
    if all(components(count).values()):
        labels.append("三才足数（数理推导）")
    if count % 10 == 5:
        labels.append("杜塞（淘金歌）")
    return labels


def contextual_harmony(
    count: int, *, reference: str, field: str, value: int | str
) -> dict[str, Any]:
    """Vol. 2 pairs count parity with each separately specified reference."""
    _validate(count)
    if type(value) not in (int, str):
        raise ValueError("配数参照需要宫数或方位，不接受布尔代替宫数")
    if reference == "太乙" and type(value) is int:
        polarity = (
            "阳" if value in (8, 3, 4, 9) else ("阴" if value in (2, 7, 6, 1) else None)
        )
    elif reference == "太乙":
        polarity = None
    else:
        polarity = (
            "阳"
            if value in YANG_POSITIONS
            else ("阴" if value in YIN_POSITIONS else None)
        )
    odd = count % 2 == 1
    harmonious = (odd == (polarity == "阴")) if polarity else None
    return {
        "reference": reference,
        "field": field,
        "value": value,
        "polarity": polarity,
        "count_parity": "奇" if odd else "偶",
        "is_harmonious": harmonious,
        "reading": (
            "参照未定"
            if polarity is None
            else (
                "阴阳和"
                if harmonious
                else ("重阳不和" if polarity == "阳" else "重阴不和")
            )
        ),
    }


def count_reading(count: int) -> dict[str, Any]:
    _validate(count)
    parts = components(count)
    families = [
        name
        for name, values in (
            ("单阳", (1, 3, 7, 9)),
            ("单阴", (2, 4, 6, 8)),
            ("孤阳", (10, 30)),
            ("孤阴", (20, 40)),
            ("重阳", (11, 13, 17, 19, 31, 33, 37, 39)),
            ("重阴", (22, 24, 26, 28)),
        )
        if count in values
    ]
    listings = [
        {
            "profile_id": p["id"],
            "harmony_tiers": [
                name for name, values in p["harmony_tiers"].items() if count in values
            ],
            "three_talents_listed": (
                None
                if p["three_talents_explicit_list"] is None
                else count in p["three_talents_explicit_list"]
            ),
        }
        for p in source_profiles()
    ]
    ranks = {t for row in listings for t in row["harmony_tiers"]}
    all_listed = all(row["harmony_tiers"] for row in listings)
    return {
        "value": count,
        "missing_labels": [
            s for s in count_labels(count) if s in {"无天", "无地", "无人"}
        ],
        "components": parts,
        "three_talents_inferred": all(parts.values()),
        "duse": count % 10 == 5,
        "length_label": (
            "短算" if count <= 9 else ("原条未定" if count == 10 else "长算")
        ),
        "is_long": None if count == 10 else count >= 11,
        "number_families": families,
        "source_memberships": listings,
        "literal_rank_status": (
            "different_source_ranks"
            if len(ranks) > 1
            else (
                "all_selected_list_same_rank"
                if ranks and all_listed
                else (
                    "partial_listing_not_unified"
                    if ranks
                    else "not_listed_not_a_negative"
                )
            )
        ),
        "literal_rank_consensus": (
            next(iter(ranks)) if len(ranks) == 1 and all_listed else None
        ),
    }


def count_assessment(core: dict[str, Any]) -> dict[str, Any]:
    entries = []
    for camp, subject, marker_field, marker_path in (
        ("main", "主算", "wenchang_palace", "wenchang_palace"),
        ("guest", "客算", "shiji", "core_board.shiji"),
    ):
        count = core[camp + "_count"]
        entries.append(
            {
                **count_reading(count),
                "subject": subject,
                "field": "core_board." + camp + "_count",
                "contexts": [
                    contextual_harmony(
                        count,
                        reference="太乙",
                        field="core_board.taiyi_number",
                        value=core["taiyi_number"],
                    ),
                    contextual_harmony(
                        count,
                        reference="文昌" if camp == "main" else "始击",
                        field=marker_path,
                        value=core[marker_field],
                    ),
                ],
            }
        )
    return {
        "ruleset": {
            "id": "taiyi_count_source_readings_v1",
            "version": "1.0.0",
            "author": "FateBridge contributors",
            "primary_sources": [VOL2, VOL6],
            "catalog_sha256": CATALOG_SHA256,
        },
        "sources": [
            {k: p[k] for k in ("id", "title", "source", "evidence_level")}
            for p in source_profiles()
        ],
        "unadjudicated_source_readings": [
            {"profile_id": p["id"], "kind": key, **r}
            for p in source_profiles()
            for key in ("unadjudicated_readings", "out_of_range_readings")
            for r in p.get(key, [])
        ],
        "entries": entries,
        "overall_harmony_assessed": False,
        "scope": SCOPE,
    }


def counts_text(assessment: dict[str, Any]) -> str:
    lines = []
    titles = {s["id"]: s["title"] for s in assessment["sources"]}
    for row in assessment["entries"]:
        parts = row["components"]
        lines.append(
            f"{row['subject']}{row['value']}（{row['field']}）：{row['length_label']}；"
            f"卷六算族{'、'.join(row['number_families']) or '无所列算族'}；"
            f"原条缺数{'、'.join(row['missing_labels']) or '无所列缺数'}；"
            f"筹分解{parts['ten']}+{parts['five']}+{parts['one']}，"
            f"足数推导{'具足' if row['three_talents_inferred'] else '不具足'}，不是原清单成员认证；"
            f"淘金歌杜塞数格{'命中' if row['duse'] else '未命中'}。"
        )
        for c in row["contexts"]:
            lines.append(
                f"{row['subject']}以{c['reference']}{c['value']}为参照（{c['field']}），参照{c['polarity'] or '未定'}、算{c['count_parity']}：{c['reading']}。"
            )
        lines.append(
            "和数源列："
            + "；".join(
                f"{titles[m['profile_id']]}：{'/'.join(m['harmony_tiers']) or '未列，不是否定'}"
                for m in row["source_memberships"]
            )
            + "。"
        )
    for pending in assessment["unadjudicated_source_readings"]:
        reason = (
            pending.get("scope")
            or "原文数值超出当前1至40主客算范围，底本未覆核，不作校改"
        )
        lines.append(
            f"源文未决：{titles[pending['profile_id']]}：{pending['reading']}；{reason}。"
        )
    lines.append(SCOPE)
    return "\n".join(lines)

"""Public Qimen Dunjia calculation entry points and ju builder."""

from __future__ import annotations

from typing import Any, Literal

from fatebridge.core.divination import build_hexagram
from fatebridge.core.metaphysics.common import (
    MetaphysicsSeed,
    kongwang_for_ganzhi,
    xun_head_for_ganzhi,
)
from fatebridge.core.qimen.board import (
    DEFAULT_GOD_PROFILE,
    DEFAULT_LODGING_POLICY,
    QIMEN_CN_NUMBERS,
    QIMEN_DOOR_DISPLAY,
    QIMEN_DOOR_TO_TRIGRAM,
    QIMEN_STAR_DISPLAY,
    LayoutMode,
    LodgingPolicy,
    build_earth_plate,
    build_palace_geometry,
    build_qimen_leaders,
)
from fatebridge.core.qimen.calendar import (
    JuMethod,
    qimen_futou_for_ganzhi,
    resolve_effective_ganzhi,
    resolve_ju_decision,
)
from fatebridge.core.qimen.patterns import (
    DEFAULT_SEASON_PROFILE,
    enrich_qimen_evidence,
    validate_profiles,
)


def build_ju_text(dun_type: str, ju_number: int, yuan: str) -> str:
    if dun_type not in {"阳遁", "阴遁"} or yuan not in {"上元", "中元", "下元"}:
        raise ValueError("未知奇门遁型或三元")
    if type(ju_number) is not int or not 1 <= ju_number <= 9:
        raise ValueError("奇门局数必须是1至9的整数")
    return f"{dun_type}{QIMEN_CN_NUMBERS[ju_number - 1]}局{yuan}"


def build_qimen_board(
    seed: MetaphysicsSeed,
    *,
    ju_method: JuMethod = "zhirun",
    layout: LayoutMode = "direct",
    lodging_policy: LodgingPolicy = DEFAULT_LODGING_POLICY,
    god_profile: str = DEFAULT_GOD_PROFILE,
    season_profile: str = DEFAULT_SEASON_PROFILE,
) -> dict[str, Any]:
    """Compute a complete Qimen Dunjia board for the given seed and options."""
    validate_profiles(god_profile, season_profile)
    day_ganzhi, time_ganzhi = resolve_effective_ganzhi(seed)
    fu_tou = qimen_futou_for_ganzhi(day_ganzhi)
    ju_meta = resolve_ju_decision(seed, ju_method)
    current_term = ju_meta["current_term"]
    dun_type: Literal["阳遁", "阴遁"] = ju_meta["dun_type"]
    yuan = ju_meta["yuan"]
    ju_number = ju_meta["ju_number"]
    ju_text = build_ju_text(dun_type, ju_number, yuan)

    earth = build_earth_plate(ju_text)
    leaders = build_qimen_leaders(
        time_ganzhi,
        earth,
        dun_type=dun_type,
        lodging_policy=lodging_policy,
        layout=layout,
    )
    palaces = build_palace_geometry(
        earth=earth,
        leader=leaders,
        god_profile=god_profile,
        time_ganzhi=time_ganzhi,
        layout=layout,
    )
    palace_map = {palace["trigram"]: palace for palace in palaces}
    zhifu_palace = palace_map[leaders["star_gong"]]
    zhifu_star = QIMEN_STAR_DISPLAY[leaders["star"]]
    zhishi_palace = palace_map[leaders["door_gong"]]
    zhishi_door = zhishi_palace["door"]
    if zhishi_door is None:
        zhishi_door = QIMEN_DOOR_DISPLAY[leaders["door"]]

    fushi_hexagram = build_hexagram(
        upper_name=(
            leaders["lodged_gong"]
            if zhifu_palace["trigram"] == "中"
            else zhifu_palace["trigram"]
        ),
        lower_name=QIMEN_DOOR_TO_TRIGRAM[zhishi_door],
    )

    board: dict[str, Any] = {
        "dun_type": dun_type,
        "ju_number": ju_number,
        "ju_text": ju_text,
        "yuan": yuan,
        "yuan_order": yuan,
        "fu_tou": fu_tou,
        "xun_head": xun_head_for_ganzhi(time_ganzhi),
        "kongwang": kongwang_for_ganzhi(time_ganzhi),
        "zhifu": {
            "star": zhifu_star,
            "palace": zhifu_palace["name"],
            "trigram": zhifu_palace["trigram"],
            "content_palace": zhifu_palace["content_palace"],
            "content_trigram": zhifu_palace["content_trigram"],
            "code": leaders["star"],
        },
        "zhishi": {
            "door": zhishi_door,
            "palace": zhishi_palace["name"],
            "trigram": zhishi_palace["trigram"],
            "content_palace": zhishi_palace["content_palace"],
            "content_trigram": zhishi_palace["content_trigram"],
            "code": leaders["door"],
        },
        "fushi_hexagram": {
            "name": fushi_hexagram["name"],
            "binary_code": fushi_hexagram["binary_code"],
        },
        "palaces": palaces,
        "layout": layout,
        "lodging_policy": lodging_policy,
        "ju_method": ju_method,
        "god_profile": god_profile,
        "season_profile": season_profile,
        "ju_decision": dict(ju_meta),
        "day_ganzhi": day_ganzhi,
        "time_ganzhi": time_ganzhi,
        "day_xun_head": xun_head_for_ganzhi(day_ganzhi),
        "day_kongwang": kongwang_for_ganzhi(day_ganzhi),
        "ju_term": current_term,
    }
    return enrich_qimen_evidence(board, seed=seed, leader=leaders)


def build_qimen_with_options(
    seed: MetaphysicsSeed, options: dict[str, Any] | None
) -> dict[str, Any]:
    normalized = dict(options or {})
    unknown = set(normalized) - {
        "layout",
        "lodging_policy",
        "palaceShift",
        "palace_shift",
        "ju_method",
        "god_profile",
        "season_profile",
    }
    if unknown:
        raise ValueError(f"不支持的奇门选项：{sorted(unknown)}")
    layout = normalized.get("layout", "direct")
    if layout not in ("direct", "rotating", "fei"):
        raise ValueError("layout仅支持direct、rotating（转盘）或fei（飞盘）")
    for key in ("palaceShift", "palace_shift"):
        shift = normalized.get(key, 0)
        if type(shift) is not int or shift != 0:
            raise ValueError("palaceShift仅允许0")
    method = normalized.get("ju_method", "zhirun")
    if method not in ("zhirun", "chaibu", "maoshan"):
        raise ValueError(
            "ju_method仅支持zhirun（置闰）、chaibu（拆补）或maoshan（茅山）"
        )
    lodging_policy = normalized.get("lodging_policy", DEFAULT_LODGING_POLICY)
    if lodging_policy not in ("kun2", "gen8", "yin_gen_yang_kun"):
        raise ValueError(
            "lodging_policy仅支持kun2（寄坤二）、gen8（寄艮八）或yin_gen_yang_kun（阳坤阴艮）"
        )
    return build_qimen_board(
        seed,
        ju_method=method,
        layout=layout,
        lodging_policy=lodging_policy,
        god_profile=normalized.get("god_profile", DEFAULT_GOD_PROFILE),
        season_profile=normalized.get("season_profile", DEFAULT_SEASON_PROFILE),
    )

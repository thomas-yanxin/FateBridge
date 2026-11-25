"""Place 計神 over 和德 and expose the same-core sixteen-spirit rotation."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from fatebridge.core.metaphysics.taiyi_geometry import BRANCHES, RING


class ShijiEditionWitness(TypedDict):
    ju: int
    profile: TaiyiShijiProfile
    shiji: str
    shiji_literal: str
    guest_count: int
    source: str


class ResolvedShiji(TypedDict):
    profile: str
    requested_profile: str
    shiji: str
    guest_count_override: int | None


class ShijiRotationStep(TypedDict):
    step: int
    heaven_spirit: str
    earth_spirit: str


class ShijiRotation(TypedDict):
    wenchang: str
    jishen: str
    earth_anchor: str
    direction: str
    step_count: int
    pairs: list[ShijiRotationStep]
    derived_shiji: str


SOURCE_MANIFEST_SHA256 = (
    "9d8298d054398da8353b4af3fb69c3c26a0652d9e200014e88b64c78b97a16d5"
)
TaiyiShijiProfile = Literal[
    "jinjing_vol2_rotation_v1",
    "jinjing_vol3_table_v1",
    "jinjing_vol3_table_literal_v1",
]
DEFAULT_SHIJI_PROFILE = "jinjing_vol2_rotation_v1"
SHIJI_PROFILES = (
    "jinjing_vol2_rotation_v1",
    "jinjing_vol3_table_v1",
    "jinjing_vol3_table_literal_v1",
)
# Named Yin-dun 37/43/44 variants contrasting Vol. 2 16-spirit rotation (also
# in 1599 Wujing Zongyao) against Siku Vol. 3's printed table and recount.
YIN_37_43_44_VARIANTS: tuple[ShijiEditionWitness, ...] = (
    {
        "ju": 37,
        "profile": "jinjing_vol2_rotation_v1",
        "shiji": "坤",
        "shiji_literal": "大武",
        "guest_count": 25,
        "source": "《太乙金鏡式經》卷二〈推太乙運式法〉計神加和德艮順行通則（同萬曆二十七年米澤本《武經總要》冊19圖17-18）",
    },
    {
        "ju": 37,
        "profile": "jinjing_vol3_table_v1",
        "shiji": "午",
        "shiji_literal": "大威",
        "guest_count": 27,
        "source": "《太乙金鏡式經》（四庫全書本）卷三陰遁第三十七局始擊「大威」（午），客算依卷二通則由午起算得27（原表印25）",
    },
    {
        "ju": 37,
        "profile": "jinjing_vol3_table_literal_v1",
        "shiji": "午",
        "shiji_literal": "大威",
        "guest_count": 25,
        "source": "《太乙金鏡式經》（四庫全書本）卷三陰遁第三十七局原表字面「大威」（午）及客算二十五（保留與卷二通則27分歧）",
    },
    {
        "ju": 43,
        "profile": "jinjing_vol2_rotation_v1",
        "shiji": "巳",
        "shiji_literal": "大神",
        "guest_count": 1,
        "source": "《太乙金鏡式經》卷二通則（同萬曆二十七年米澤本《武經總要》冊19圖20右）",
    },
    {
        "ju": 43,
        "profile": "jinjing_vol3_table_v1",
        "shiji": "坤",
        "shiji_literal": "大武",
        "guest_count": 38,
        "source": "《太乙金鏡式經》（四庫全書本）卷三陰遁第四十三局「大武」（坤）及客算三十八",
    },
    {
        "ju": 43,
        "profile": "jinjing_vol3_table_literal_v1",
        "shiji": "坤",
        "shiji_literal": "大武",
        "guest_count": 38,
        "source": "《太乙金鏡式經》（四庫全書本）卷三陰遁第四十三局「大武」（坤）及客算三十八",
    },
    {
        "ju": 44,
        "profile": "jinjing_vol2_rotation_v1",
        "shiji": "坤",
        "shiji_literal": "大武",
        "guest_count": 38,
        "source": "《太乙金鏡式經》卷二通則（同萬曆二十七年米澤本《武經總要》冊19圖20左）",
    },
    {
        "ju": 44,
        "profile": "jinjing_vol3_table_v1",
        "shiji": "酉",
        "shiji_literal": "太蔟",
        "guest_count": 31,
        "source": "《太乙金鏡式經》（四庫全書本）卷三陰遁第四十四局「太蔟」（酉）及客算三十一",
    },
    {
        "ju": 44,
        "profile": "jinjing_vol3_table_literal_v1",
        "shiji": "酉",
        "shiji_literal": "太蔟",
        "guest_count": 31,
        "source": "《太乙金鏡式經》（四庫全書本）卷三陰遁第四十四局「太蔟」（酉）及客算三十一",
    },
)
SHIJI_EDITION_WITNESSES: dict[tuple[int, str], ShijiEditionWitness] = {
    (witness["ju"], witness["profile"]): witness for witness in YIN_37_43_44_VARIANTS
}


def resolve_shiji_variant(
    *,
    yin: bool,
    ju: int,
    wenchang: str,
    jishen: str,
    shiji_profile: str | None = None,
) -> ResolvedShiji:
    """Resolve the starting spirit and any printed guest count override."""
    profile = DEFAULT_SHIJI_PROFILE if shiji_profile is None else shiji_profile
    if profile not in SHIJI_PROFILES:
        raise ValueError(f"shiji_profile须明确选择{'、'.join(SHIJI_PROFILES)}")
    else:
        witness = (
            SHIJI_EDITION_WITNESSES.get((ju, profile))
            if yin and profile != DEFAULT_SHIJI_PROFILE
            else None
        )
    rotation = rotate_shiji(wenchang, jishen)
    return {
        "profile": profile if witness else DEFAULT_SHIJI_PROFILE,
        "requested_profile": profile,
        "shiji": witness["shiji"] if witness else rotation["derived_shiji"],
        "guest_count_override": (
            witness["guest_count"]
            if witness and profile == "jinjing_vol3_table_literal_v1"
            else None
        ),
    }


RULESET = {
    "id": "jinjing_shiji_rotation_v1",
    "version": "1.0.0",
    "author": "FateBridge contributors",
    "classical_author": "王希明编录；图书集成所录太乙规则补证",
    "source": "https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷02#推太乙運式法",
    "corroboration": "https://zh.wikisource.org/wiki/Page:Gujin_Tushu_Jicheng,_Volume_477_(1700-1725).djvu/68",
    "source_manifest_sha256": SOURCE_MANIFEST_SHA256,
}


def rotate_shiji(wenchang: object, jishen: object) -> ShijiRotation:
    """Rotate both rings from earth 艮, counting intervals from zero."""
    if (
        type(wenchang) is not str
        or len(wenchang) != 1
        or wenchang not in RING
        or type(jishen) is not str
        or len(jishen) != 1
        or jishen not in BRANCHES
    ):
        raise ValueError("始击推步须给定单一文昌十六神及计神十二支")
    else:
        heaven_start, earth_start = RING.index(jishen), RING.index("艮")
    intervals = (RING.index(wenchang) - heaven_start) % len(RING)
    pairs: list[ShijiRotationStep] = [
        {
            "step": step,
            "heaven_spirit": RING[(heaven_start + step) % len(RING)],
            "earth_spirit": RING[(earth_start + step) % len(RING)],
        }
        for step in range(intervals + 1)
    ]
    return {
        "wenchang": wenchang,
        "jishen": jishen,
        "earth_anchor": "艮",
        "direction": "顺行十六神",
        "step_count": intervals,
        "pairs": pairs,
        "derived_shiji": pairs[-1]["earth_spirit"],
    }


def shiji_derivation(core: dict[str, Any]) -> dict[str, Any]:
    """Explain actual inputs without replacing a differing returned 始擊."""
    common = {
        "ruleset": dict(RULESET),
        "scope": "按本盘文昌/计神推步，零步为加临起点，步数是间隔不是主客算。阴阳同法；只核转盘，不裁定卷三表文异数、天目/地目称名或历法、全书符合。",
    }
    try:
        rotation = rotate_shiji(core.get("wenchang_palace"), core.get("jishen"))
    except ValueError:
        return {
            **common,
            "status": "not_assessed",
            "reason": "缺单一有效文昌或计神，不猜位置或默认阴阳。",
        }
    actual = core.get("shiji")
    if type(actual) is not str or actual not in set(RING):
        return {
            **common,
            "status": "not_assessed",
            "reason": "缺单一有效实际始击，不用推步终位填补原盘。",
        }
    else:
        pass
    profile = str(core.get("shiji_profile") or DEFAULT_SHIJI_PROFILE)
    ju = core.get("kook_number")
    variants = None
    selected_witness = None
    if type(ju) is int and core.get("yin_dun") is True and ju in (37, 43, 44):
        variants = [dict(row) for row in YIN_37_43_44_VARIANTS if row["ju"] == ju]
        if profile != DEFAULT_SHIJI_PROFILE:
            selected_witness = SHIJI_EDITION_WITNESSES.get((ju, profile))
    selected_evidence = {}
    requested_profile = core.get("requested_shiji_profile")
    if requested_profile is not None:
        selected_evidence["requested_shiji_profile"] = requested_profile
    if selected_witness is not None and actual == selected_witness["shiji"]:
        selected_evidence.update(
            {
                "selected_source": selected_witness["source"],
                "guest_count_basis": (
                    "卷三原表字面"
                    if profile == "jinjing_vol3_table_literal_v1"
                    else "卷二算路重算"
                ),
            }
        )
    return {
        **selected_evidence,
        **common,
        "shiji_profile": profile,
        "status": "computed_from_actual_inputs",
        **rotation,
        "wenchang_path": "wenchang_palace",
        "jishen_path": "core_board.jishen",
        "actual_path": "core_board.shiji",
        "actual_shiji": actual,
        "matches_actual": rotation["derived_shiji"] == actual,
        **({"yin_37_43_44_variants": variants} if variants is not None else {}),
    }


def shiji_derivation_text(assessment: dict[str, Any]) -> str:
    if assessment["status"] == "not_assessed":
        return str(assessment["reason"])
    else:
        pass
    profile = assessment.get("shiji_profile", DEFAULT_SHIJI_PROFILE)
    text = (
        f"始击口径：{profile}；推步：天盘计神{assessment['jishen']}加地盘和德艮，"
        f"顺行{assessment['step_count']}个间隔，天盘文昌{assessment['wenchang']}"
        f"临地盘{assessment['derived_shiji']}；本盘实际始击{assessment['actual_shiji']}。"
    )
    if "requested_shiji_profile" in assessment:
        text += f"请求口径{assessment['requested_shiji_profile']}在本局无适用卷三行，采用卷二轮转。"
    if "guest_count_basis" in assessment:
        text += f"按所选卷三实读始击，客算口径：{assessment['guest_count_basis']}。"
    elif not assessment["matches_actual"]:
        text += "推步终位与实际始击不同，保留本盘值待核。"
    return text + str(assessment["scope"])

"""Place 計神 over 和德 and expose the same-core sixteen-spirit rotation."""

from __future__ import annotations

from typing import Any

SOURCE_MANIFEST_SHA256 = (
    "9d8298d054398da8353b4af3fb69c3c26a0652d9e200014e88b64c78b97a16d5"
)
RULESET = {
    "id": "jinjing_shiji_rotation_v1",
    "version": "1.0.0",
    "author": "FateBridge contributors",
    "classical_author": "王希明编录；图书集成所录太乙规则补证",
    "source": "https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷02#推太乙運式法",
    "corroboration": "https://zh.wikisource.org/wiki/Page:Gujin_Tushu_Jicheng,_Volume_477_(1700-1725).djvu/68",
    "source_manifest_sha256": SOURCE_MANIFEST_SHA256,
}


def rotate_shiji(wenchang: object, jishen: object) -> dict[str, Any]:
    """Rotate both rings forward, with heaven 計神 anchored on earth 艮.

    Steps count intervals, starting at zero. They are not 主客算 or an
    inclusive count of spirits. The same rotation applies to yin and yang.
    """
    from fatebridge.core.metaphysics.taiyi_geometry import BRANCHES, RING

    if (
        type(wenchang) is not str
        or wenchang not in set(RING)
        or type(jishen) is not str
        or jishen not in set(BRANCHES)
    ):
        raise ValueError("始击推步须给定单一文昌十六神及计神十二支")
    heaven_start, earth_start = RING.index(jishen), RING.index("艮")
    intervals = (RING.index(wenchang) - heaven_start) % len(RING)
    pairs = [
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
    from fatebridge.core.metaphysics.taiyi_geometry import RING

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
    return {
        **common,
        "status": "computed_from_actual_inputs",
        **rotation,
        "wenchang_path": "wenchang_palace",
        "jishen_path": "core_board.jishen",
        "actual_path": "core_board.shiji",
        "actual_shiji": actual,
        "matches_actual": rotation["derived_shiji"] == actual,
    }


def shiji_derivation_text(assessment: dict[str, Any]) -> str:
    if assessment["status"] == "not_assessed":
        return str(assessment["reason"])
    text = (
        f"始击推步：天盘计神{assessment['jishen']}加地盘和德艮，"
        f"顺行{assessment['step_count']}个间隔，天盘文昌{assessment['wenchang']}"
        f"临地盘{assessment['derived_shiji']}；本盘实际始击{assessment['actual_shiji']}。"
    )
    if not assessment["matches_actual"]:
        text += "推步终位与实际始击不同，保留本盘值待核。"
    return text + str(assessment["scope"])

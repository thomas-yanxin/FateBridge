"""Moira sign-pattern compatibility subset, not an edition-certified engine.

Originally ported from horosa guolaoMoira.js. Compatibility is intentionally
broken when a legacy rule treated missing data as a fact (missing purple clouds
in isolated-Moon counting, or missing nobles wrapped into valid sign indices).
Day/night and winter must be supplied explicitly; mansion proximity must come
from the caller's declared boundary model. No equal-28 placeholder is used.

The purple-cloud point remains a fit to four horosa software fixtures. It is
NOT an astronomical body or a calibration to the Tohoku printed edition, whose
volume 1 states an approximately 29-year revolution rather than this fit's 28.
The legacy god helper retains the Sanming Tonghui convention for old callers.
Native Guolao instead uses the collated Lu Wei table in core.guolao_classical.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

PATTERN_MODEL_ID = "moira_compatibility_conditions_v2"

# --- 数据表（verbatim from guolaoMoira.js / SZConst.js）-----------------------

# LIST_SIGNS index (0=Aries … 11=Pisces) → 地支（七政四余 戌将盘；SZConst.SignZi）。
_SIGN_ZI = ["戌", "酉", "申", "未", "午", "巳", "辰", "卯", "寅", "丑", "子", "亥"]

# 行星中文 → 喜用名（guolaoMoira MOIRA_PLANET_CN_TO_ID 的中文键）。
# 在本端口中 facts["planet_signidx"] 直接以中文键给出星座序号。
_MOIRA_PLANET_ORDER = ["日", "月", "金", "木", "水", "火", "土", "计", "罗", "炁", "孛"]

# MOIRA_RULER_BY_SIGN：星座序号 → 庙主行星中文（Aries…Pisces）。
_RULER_BY_SIGN_IDX = [
    "火",
    "金",
    "水",
    "月",
    "日",
    "水",
    "金",
    "火",
    "木",
    "土",
    "土",
    "木",
]

# MOIRA_OVERCOMING：兼容软件的失垣查表，不是五星相克表。
# 本底本的方向性五星生克单独维护在 core.guolao.relation。
_OVERCOMING = {
    "日": "月",
    "月": "日",
    "金": "火",
    "木": "金",
    "水": "土",
    "火": "水",
    "土": "木",
    "炁": "金",
    "孛": "土",
    "罗": "水",
    "计": "木",
}

# 地支 → 星座序号（七政四余 戌将盘；SZConst.ZiSign 之逆）。
_ZI_TO_SIGNIDX = {
    "子": 10,
    "丑": 9,
    "寅": 8,
    "卯": 7,
    "辰": 6,
    "巳": 5,
    "午": 4,
    "未": 3,
    "申": 2,
    "酉": 1,
    "戌": 0,
    "亥": 11,
}

# 七政四余 神煞 起例（键以年干/年支起例）。无 horosa 字节对照，且 贵人 之阳/阴
# (昼/夜) 定向流派有别（《三命通会》与《三历会同》互异，FateBridge 既有 rules.py 日贵格亦为
# 混用）；本旧兼容助手保留《三命通会》口径，不作为原生陆位本的回退：
#   阳贵(昼/天贵)：甲加丑「逆行」—— 甲丑 乙子 丙亥 丁酉 戊丑 己申 庚未 辛午 壬巳 癸卯
#   阴贵(夜/玉贵)：甲加未「顺行」—— 甲未 乙申 丙酉 丁亥 戊未 己子 庚丑 辛寅 壬卯 癸巳
# 戊从甲（戊土寄宫）。十干两贵地支对仍与既有 TIAN_YI_TARGETS（天乙贵人）逐干同对，仅此处
# 明确昼/夜定向。注：与 rules.py 日贵格(丁亥昼/丁酉夜)在丁干上不同口径——后者为独立 BaZi
# 格局、流派混用，不在本段统一范围内。岁驾=太岁=年支本位。
_TIANGUI_BY_YEAR_STEM = {  # 阳贵（昼/天贵）——《三命通会》甲加丑逆行
    "甲": "丑",
    "乙": "子",
    "丙": "亥",
    "丁": "酉",
    "戊": "丑",
    "己": "申",
    "庚": "未",
    "辛": "午",
    "壬": "巳",
    "癸": "卯",
}
_YUGUI_BY_YEAR_STEM = {  # 阴贵（夜/玉贵）——《三命通会》甲加未顺行
    "甲": "未",
    "乙": "申",
    "丙": "酉",
    "丁": "亥",
    "戊": "未",
    "己": "子",
    "庚": "丑",
    "辛": "寅",
    "壬": "卯",
    "癸": "巳",
}


# 步紫气（紫炁/木余）—— 七政四余「四余」之一，无 swisseph 天体对应。以 horosa 后端 4 张
# 七政四余盘 fixture（1985-03-21 / 1998 / 2026，chart_guolao·1998_predictive·liureng·traditional）
# 作最小二乘线性标定：周期 ≈ 27.9994 年（软件拟合，非原典历元），4 点残差 < 1e-5°。
# 锚点取 horosa chart_guolao fixture（1985-03-21 10:00 +08，JD_UT 2446145.5833）。横向移植故
# 直接锚定 horosa 值（紫炁为均行虚点，黄经随时间严格线性）。
_PURPLE_CLOUDS_ANCHOR_JD = 2446145.583333333
_PURPLE_CLOUDS_ANCHOR_LON = 358.66910331920116
_PURPLE_CLOUDS_RATE_DEG_PER_DAY = 0.035201691530618556


def purple_clouds_longitude(julian_day: float) -> float:
    """紫炁（木余）黄经（度，0–360）。horosa 标定的线性步紫气，见上方常量注释。"""
    lon = _PURPLE_CLOUDS_ANCHOR_LON + _PURPLE_CLOUDS_RATE_DEG_PER_DAY * (
        julian_day - _PURPLE_CLOUDS_ANCHOR_JD
    )
    return lon % 360.0


def compute_god_signidx(year_stem: str, year_branch: str) -> Dict[str, int]:
    """Legacy 三命通会 compatibility table, not the native Guolao edition.

    Native Guolao uses core.guolao_classical.year_god_branches after collation
    with Lu Wei bundle vols. 1-2 images 33-34. Keep this explicitly different legacy
    helper for old callers and software oracles, never as an edition fallback.

    依《三命通会》起例，由年柱干支算出 天贵、玉贵、岁驾三神煞的星座序号。

    天贵(昼/阳贵)、玉贵(夜/阴贵) 以年干起例（旧兼容约定为甲加丑逆/甲加未顺，
    见上方常量注释）；岁驾(太岁) 即年支本位。地支经 戌将盘 ``_ZI_TO_SIGNIDX`` 映射为
    星座序号。缺值回退 -1（对应格局自然失效）。
    """
    gods: Dict[str, int] = {}
    tian = _TIANGUI_BY_YEAR_STEM.get(year_stem)
    yu = _YUGUI_BY_YEAR_STEM.get(year_stem)
    gods["天贵"] = _ZI_TO_SIGNIDX.get(tian, -1) if tian else -1
    gods["玉贵"] = _ZI_TO_SIGNIDX.get(yu, -1) if yu else -1
    gods["岁驾"] = _ZI_TO_SIGNIDX.get(year_branch, -1)
    return gods


# 命宫起十二宫的次序偏移（localMoiraHouseSign）。
_HOUSE_OFFSET = {
    "命": 0,
    "命宫": 0,
    "财": 1,
    "财帛": 1,
    "兄弟": 2,
    "田": 3,
    "田宅": 3,
    "嗣": 4,
    "男女": 4,
    "奴": 5,
    "奴仆": 5,
    "妻": 6,
    "夫妻": 6,
    "疾": 7,
    "疾厄": 7,
    "迁": 8,
    "迁移": 8,
    "官": 9,
    "官禄": 9,
    "福": 10,
    "福德": 10,
    "相": 11,
    "相貌": 11,
}


# --- 工具函数 ----------------------------------------------------------------


def _sign_zi(sign_idx: int) -> str:
    if sign_idx < 0:
        return ""
    return _SIGN_ZI[(sign_idx + 12) % 12]


def _same(a: int, b: int) -> bool:
    return a >= 0 and b >= 0 and a == b


def _rel(base: int, offset: int) -> int:
    return -1 if base < 0 else (base + offset + 12) % 12


def _house_sign(life_sign_idx: int, offset: int) -> int:
    return -1 if life_sign_idx < 0 else (life_sign_idx + offset + 12) % 12


# --- Pattern record ----------------------------------------------------------


def _add(
    patterns: List[Dict[str, Any]],
    name: str,
    level: str,
    score: str,
    detail: str,
    dsl: str,
    *,
    rule_id: str,
    inputs: Dict[str, Any],
    granularity: str = "palace_index",
) -> None:
    patterns.append(
        {
            "name": name,
            "level": level,
            "score": score,
            "source": "moira_s.prop-local",
            "dsl": dsl,
            "detail": detail,
            "rule_id": rule_id,
            "evidence": {
                "model_id": PATTERN_MODEL_ID,
                "granularity": granularity,
                "inputs": inputs,
                "condition_satisfied": True,
                "classical_acceptance": False,
                "event_probability_estimated": False,
            },
        }
    )


class _Resolver:
    """localSignOfCn：把宫名/行星/地支/神煞名解析为星座序号（与 JS 同序）。"""

    def __init__(
        self,
        planet_signidx: Dict[str, int],
        life_sign_idx: int,
        self_sign_idx: int,
        god_signidx: Dict[str, int],
    ) -> None:
        self._planets = planet_signidx
        self._life = life_sign_idx
        self._self = self_sign_idx
        self._gods = god_signidx

    def __call__(self, name: str) -> int:
        if name in _HOUSE_OFFSET:
            return _house_sign(self._life, _HOUSE_OFFSET[name])
        if name == "身":
            return self._self
        if name in self._gods and self._gods[name] >= 0:
            return self._gods[name]
        if name in self._planets:
            return self._planets[name]
        try:
            return _SIGN_ZI.index(name)
        except ValueError:
            return -1


def _lost_rulership(signof: _Resolver, subject: str) -> bool:
    """localMoiraLostRulership 的软件兼容条件，尚未通过本底本校勘。"""
    sign_idx = signof(subject)
    if sign_idx < 0:
        return False
    ruler_cn = _RULER_BY_SIGN_IDX[sign_idx]
    ruler_sign = signof(ruler_cn)
    if ruler_sign < 0:
        return False
    ruler_of_ruler = _RULER_BY_SIGN_IDX[ruler_sign]
    return ruler_of_ruler == _OVERCOMING.get(ruler_cn)


def _sign_boundary_distance(lon: float) -> float:
    # Preserve exact integers too; converting an unwrapped integer to float
    # first can move it across the threshold above the binary precision limit.
    if isinstance(lon, int):
        remainder = lon % 30
        return min(remainder, 30 - remainder)
    return abs(math.remainder(lon, 30))


def _near_sign_boundary(lon: Optional[float]) -> bool:
    if lon is None:
        return False
    return _sign_boundary_distance(lon) <= 1


def _indices(value: Any, label: str, allowed: set[str]) -> Dict[str, int]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError(f"{label}须为具名宫位索引映射")
    for key, index in value.items():
        if key not in allowed:
            raise ValueError(
                f"{label}包含未声明的对象{key}，不能跨行星和神煞角色补位置"
            )
        if type(index) is not int:
            raise TypeError(f"{label}.{key}须为整数索引，不能以布尔、浮点或空值冒充")
        if not -1 <= index < 12:
            raise ValueError(f"{label}.{key}须为0至11；未知仅可显式用-1或省略")
    return dict(value)


def _finite_optional(value: Any, label: str) -> None:
    try:
        valid = value is None or (
            not isinstance(value, bool)
            and isinstance(value, (int, float))
            and math.isfinite(value)
        )
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(f"{label}须为有限数值或未提供，不能以布尔或非有限值制造条件")


def _rulership_inputs(signof: _Resolver, subject: str) -> Dict[str, Any]:
    """Operands of an already satisfied compatibility lost-rulership rule."""
    index = signof(subject)
    ruler = _RULER_BY_SIGN_IDX[index]
    ruler_index = signof(ruler)
    return {
        "palace_index": index,
        "palace_ruler": ruler,
        "ruler_palace_index": ruler_index,
        "ruler_of_ruler_palace": _RULER_BY_SIGN_IDX[ruler_index],
        "compatibility_opposing_ruler": _OVERCOMING[ruler],
    }


# --- 主入口 ------------------------------------------------------------------


def calculate(facts: Dict[str, Any]) -> List[Dict[str, Any]]:
    """buildLocalMoiraPatterns 的 Python 端口。

    ``facts`` 形如::

        {
          "life_sign_idx": int,                 # 显式离散命宫，优先于旧ASC推宫
          "asc_lon": float,                     # 旧兼容参考经度，不是原典命度
          "planet_signidx": {"日": int, "月": int, "金": int, "水": int,
                              "火": int, "木": int, "土": int,
                              "孛": int, "罗": int, "计": int, "炁": int},  # 缺省 -1
          "god_signidx": {"天贵": int, "玉贵": int, "岁驾": int},  # 神煞星座序号，缺省 -1
          "is_day": bool,                       # 按调用方明示的昼夜口径
          "is_winter": bool,                    # 按调用方明示的节气口径
          "mansion_boundary_distance": float,     # 已声明宿界模型下的角距离，可缺省
        }

    ``god_signidx`` 由 :func:`compute_god_signidx` 依年柱算出（天贵/玉贵/岁驾）；
    留空则相应神煞格局（日月拱贵人/命登岁驾）失效，与 horosa 离线版一致。

    保留兼容格局名、等级及排序（good 在前、bad 在后），附实际条件证据；
    不宣称新增证据结构与旧JS逐字段相同，也不以兼容测试认证原典或预测效力。
    """
    planet_signidx = _indices(
        facts.get("planet_signidx"), "planet_signidx", set(_MOIRA_PLANET_ORDER)
    )
    god_signidx = _indices(
        facts.get("god_signidx"), "god_signidx", {"天贵", "玉贵", "岁驾"}
    )
    asc_lon = facts.get("asc_lon")
    _finite_optional(asc_lon, "asc_lon")
    distance = facts.get("mansion_boundary_distance")
    _finite_optional(distance, "mansion_boundary_distance")
    if distance is not None and distance < 0:
        raise ValueError("宿界距离须非负；缺失不能用负值当有效数据")
    if "life_sign_idx" in facts:
        life_sign_idx = facts["life_sign_idx"]
        if type(life_sign_idx) is not int or not 0 <= life_sign_idx < 12:
            raise ValueError("显式命宫索引须为0至11的整数")
    else:
        life_sign_idx = -1 if asc_lon is None else int(asc_lon // 30) % 12
    self_sign_idx = planet_signidx.get("月", -1)
    is_day = facts.get("is_day")
    is_winter = facts.get("is_winter")
    for name, value in [("is_day", is_day), ("is_winter", is_winter)]:
        if value is not None and type(value) is not bool:
            raise TypeError(f"{name}须为明确布尔或未提供，不能以数值代替条件")

    signof = _Resolver(planet_signidx, life_sign_idx, self_sign_idx, god_signidx)

    sun = signof("日")
    moon = signof("月")
    venus = signof("金")
    mercury = signof("水")
    dark_moon = signof("孛")
    north_node = signof("罗")
    guan = signof("官")

    patterns: List[Dict[str, Any]] = []
    life_zi = _sign_zi(life_sign_idx) if life_sign_idx >= 0 else ""

    # 八杀朝天（喜）：疾厄宫主入命，且命临戌亥。
    if life_sign_idx >= 0 and life_zi and life_zi in "戌亥":
        disease_ruler_cn = _RULER_BY_SIGN_IDX[signof("疾")]
        if _same(signof(disease_ruler_cn), life_sign_idx):
            _add(
                patterns,
                "八杀朝天",
                "good",
                "3.2.0",
                "政余喜格：疾厄宫主入命，且命临戌亥。",
                "@{@{疾厄}[1]}=@命",
                rule_id="moira_disease_lord_in_life_palace_v2",
                inputs={
                    "life_palace_index": life_sign_idx,
                    "life_palace_branch": life_zi,
                    "disease_palace_index": signof("疾"),
                    "disease_palace_lord": disease_ruler_cn,
                    "disease_lord_palace_index": signof(disease_ruler_cn),
                },
            )

    # 孤月独明（喜）：夜生月曜独居一方。
    if moon >= 0:
        same_moon = sum(
            1 for cn in _MOIRA_PLANET_ORDER if planet_signidx.get(cn, -1) == moon
        )
        complete = all(
            0 <= planet_signidx.get(cn, -1) < 12 for cn in _MOIRA_PLANET_ORDER
        )
        if is_day is False and complete and same_moon == 1:
            _add(
                patterns,
                "孤月独明",
                "good",
                "2.3.0",
                "政余喜格：夜生，月在本次十一曜位置中单独居一宫。",
                "?{孤月} & ?夜",
                rule_id="moira_moon_alone_in_one_palace_at_night_v2",
                inputs={
                    "is_day": is_day,
                    "moon_palace_index": moon,
                    "eleven_positions": {
                        cn: planet_signidx[cn] for cn in _MOIRA_PLANET_ORDER
                    },
                    "same_palace_count": same_moon,
                },
            )

    # 日月拱官（喜）：日月分拱官禄。
    if (_same(sun, _rel(guan, 4)) and _same(moon, _rel(guan, -4))) or (
        _same(sun, _rel(guan, -4)) and _same(moon, _rel(guan, 4))
    ):
        _add(
            patterns,
            "日月拱官",
            "good",
            "2.3.0",
            "政余喜格：日月分居官禄宫前后四宫，按宫位索引比较。",
            "@日=@官禄+4 & @月=@官禄-4",
            rule_id="moira_sun_moon_four_palaces_from_career_v2",
            inputs={"sun_index": sun, "moon_index": moon, "career_index": guan},
        )

    # 金水相涵（喜）：金水同宫，且不以冬令破格。
    if _same(venus, mercury) and is_winter is False:
        _add(
            patterns,
            "金水相涵",
            "good",
            "2.3.0",
            "政余喜格：金水同宫，且不以冬令破格。",
            "?{金水会} & !?冬",
            rule_id="moira_venus_mercury_same_palace_not_winter_v2",
            inputs={
                "venus_index": venus,
                "mercury_index": mercury,
                "is_winter": is_winter,
            },
        )

    # 日月拱贵人（喜）：分别按昼夜取已计算的天贵／玉贵。
    noble = signof("天贵" if is_day else "玉贵") if isinstance(is_day, bool) else -1
    if (_same(sun, _rel(noble, 4)) and _same(moon, _rel(noble, -4))) or (
        _same(sun, _rel(noble, -4)) and _same(moon, _rel(noble, 4))
    ):
        _add(
            patterns,
            "日月拱贵人",
            "good",
            "2.2.0",
            f"政余喜格：{'昼取天贵' if is_day else '夜取玉贵'}，日月分拱。",
            "?昼/夜 & 日月拱贵人",
            rule_id="moira_sun_moon_four_palaces_from_selected_noble_v2",
            inputs={
                "is_day": is_day,
                "selected_noble": "天贵" if is_day else "玉贵",
                "noble_index": noble,
                "sun_index": sun,
                "moon_index": moon,
            },
        )

    # 命登岁驾（兼容喜格）：只比较命宫与岁驾的离散宫位，不计算命度。
    if _same(life_sign_idx, signof("岁驾")):
        _add(
            patterns,
            "命登岁驾",
            "good",
            "2.0.3",
            "政余喜格：命宫与岁驾同宫，仅作宫位比较。",
            "@命=@{岁驾}",
            rule_id="moira_life_and_suijia_same_palace_v2",
            inputs={"life_palace_index": life_sign_idx, "suijia_index": signof("岁驾")},
        )

    # 日月失所（忌）：日居西北、月居东南。
    if sun >= 0 and moon >= 0:
        sun_zi = _sign_zi(sun)
        moon_zi = _sign_zi(moon)
        if sun_zi in "申酉戌亥子丑" and moon_zi in "寅卯辰巳午未":
            _add(
                patterns,
                "日月失所",
                "bad",
                "2.3.0",
                "政余忌格：日居申至丑六宫、月居寅至未六宫，按宫支分组。",
                "(?{日西}|?{日北}) & (?{月东}|?{月南})",
                rule_id="moira_sun_moon_branch_groups_v2",
                inputs={
                    "sun_index": sun,
                    "moon_index": moon,
                    "sun_branch": sun_zi,
                    "moon_branch": moon_zi,
                },
            )

    # 官福失垣（忌）：官禄、福德主失垣。
    if _lost_rulership(signof, "官") and _lost_rulership(signof, "福"):
        _add(
            patterns,
            "官福失垣",
            "bad",
            "2.2.0",
            "政余忌格：按兼容失垣查表，官禄与福德两项条件均成立。",
            "?{官失垣} & ?{福失垣}",
            rule_id="moira_career_and_fortune_lord_chains_v2",
            inputs={
                "career": _rulership_inputs(signof, "官"),
                "fortune": _rulership_inputs(signof, "福"),
            },
        )

    # 孛犯太阳（忌）：孛与太阳同宫。
    if _same(dark_moon, sun):
        _add(
            patterns,
            "孛犯太阳",
            "bad",
            "2.2.0",
            "政余忌格：孛与太阳同宫。",
            "?{日孛遇}",
            rule_id="moira_apogee_sun_same_palace_v2",
            inputs={"sun_index": sun, "apogee_index": dark_moon},
        )

    # 罗犯太阳（忌）：罗与太阳同宫。
    if _same(north_node, sun):
        _add(
            patterns,
            "罗犯太阳",
            "bad",
            "2.2.0",
            "政余忌格：罗与太阳同宫。",
            "?{日罗遇}",
            rule_id="moira_node_sun_same_palace_v2",
            inputs={"sun_index": sun, "node_index": north_node},
        )

    # 孛罗交战（忌）：罗孛同宫。
    if _same(north_node, dark_moon):
        _add(
            patterns,
            "孛罗交战",
            "bad",
            "2.2.0",
            "政余忌格：罗孛同宫。",
            "?{罗孛遇}",
            rule_id="moira_node_apogee_same_palace_v2",
            inputs={"node_index": north_node, "apogee_index": dark_moon},
        )

    # 命坐两歧（兼容规则）：1度阈值来自软件约定，不声称原典阈值。
    near_mansion = distance is not None and distance <= 1
    if _near_sign_boundary(asc_lon) or near_mansion:
        _add(
            patterns,
            "命坐两歧",
            "bad",
            "2.0.4",
            "政余忌格：给定兼容参考经度距30度分宫界不超过1度，或所给宿界距离不超过1度；不证明原典命度。",
            "?{命宫歧} | ?{命宿歧}",
            rule_id="moira_given_reference_near_boundary_v2",
            inputs={
                "reference_longitude": asc_lon,
                "reference_longitude_basis": "legacy_asc_argument_not_classical_life_degree",
                "palace_boundary_distance": (
                    _sign_boundary_distance(asc_lon) if asc_lon is not None else None
                ),
                "declared_mansion_boundary_distance": distance,
                "threshold_modern_degrees": 1,
            },
            granularity="declared_modern_angular_distance",
        )

    def _level_rank(level: str) -> int:
        return 0 if level == "good" else (1 if level == "bad" else 2)

    patterns.sort(key=lambda p: _level_rank(p["level"]))
    return patterns


def build_section_text(patterns: List[Dict[str, Any]]) -> str:
    """runGuolaoMoira 的输出格式：喜格/忌格/察看 三行。"""

    def fmt(items: List[Dict[str, Any]]) -> str:
        return "；".join(
            f"{it['name']}（{it.get('detail') or it.get('dsl') or ''}）" for it in items
        )

    good = [p for p in patterns if p["level"] == "good"]
    bad = [p for p in patterns if p["level"] == "bad"]
    other = [p for p in patterns if p["level"] not in ("good", "bad")]

    lines = [
        f"喜格：{fmt(good) if good else '（无）'}",
        f"忌格：{fmt(bad) if bad else '（无）'}",
    ]
    if other:
        lines.append(f"察看：{fmt(other)}")
    return "\n".join(lines)

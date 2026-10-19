"""七政四余 政余格局 (Moira DSL) — native-Python port of horosa ``guolaoMoira.js``.

Ported verbatim (structure-preserving) from horosa-skill
``horosa-core-js/src/vendor/guolao/guolaoMoira.js`` (星阙 v2.6.x, 抽取自
GuoLaoChartMain.js). The JS reads a fully-computed 七政四余 chart and emits 喜格/忌格
pattern lines; this module reproduces the **盘面物象格局** subset that runs on data
FateBridge can supply (planet sign positions + ASC + 孛/罗 + 昼夜/季节).

Scope and precision notes (overview: ``docs/algorithm-coverage.md``):

* **神煞**：天贵/玉贵/岁驾 三神煞由 :func:`compute_god_signidx` 依年柱算出，
  驱动 日月拱贵人 / 命登岁驾 两格局。贵人阳/阴(昼/夜)定向流派有别，故以单一权威源
  《三命通会》为准（见常量注释）；岁驾=太岁=年支。无 horosa 字节对照 → golden 锁定。其余
  64+36 神煞（per-宫 显示表）未覆盖。``god_signidx`` 缺省时两格局自然失效。
* **紫炁 (木余)**：由 :func:`purple_clouds_longitude` 以 horosa 标定的线性步紫气
  算出（4 张 horosa fixture 最小二乘，残差 <1e-5°，周期≈28年）。补齐后 ``孤月独明`` 的同宫
  计数覆盖全 11 体（含炁）。
* **命坐两歧**：近宫界 + 近宿界 均已实现。宿界以 FB 等分宿口径（360/28，与
  ``core.astro.geometry._su28`` 同源）判定——内部自洽，但非 horosa 后端真实（不等）宿度，故
  近宿界临界判定不与 horosa 字节对照（近宫界仍与 JS 逐字一致）。

The remaining patterns (八杀朝天/日月拱官/金水相涵/日月失所/官福失垣/孛犯太阳/罗犯太阳/
孛罗交战) match ``guolaoMoira.js`` byte-for-byte given identical chart inputs, and are
locked by the saved Node-oracle fixture in ``tests/test_guolao_moira_tool.py``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

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

# MOIRA_OVERCOMING：克制关系（行星中文 → 被其克的行星中文）。
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

# 七政四余 神煞 起例（Phase 2a，键以年干/年支起例）。无 horosa 字节对照，且 贵人 之阳/阴
# (昼/夜) 定向流派有别（《三命通会》与《三历会同》互异，FateBridge 既有 rules.py 日贵格亦为
# 混用），故统一以 **单一权威源《三命通会》** 为准：
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
# 作最小二乘线性标定：周期 ≈ 27.9994 年（古典「紫气二十八年一周天」），4 点残差 < 1e-5°。
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
    """依《三命通会》起例，由年柱干支算出 Phase 2a 三神煞的星座序号。

    天贵(昼/阳贵)、玉贵(夜/阴贵) 以年干起例（《三命通会》甲加丑逆/甲加未顺，单一权威源，
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
    return (base + offset + 12) % 12


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
) -> None:
    patterns.append(
        {
            "name": name,
            "level": level,
            "score": score,
            "source": "moira_s.prop-local",
            "dsl": dsl,
            "detail": detail,
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
    """localMoiraLostRulership：宫主落于被其克之星所主之宫（失垣）。"""
    sign_idx = signof(subject)
    if sign_idx < 0:
        return False
    ruler_cn = _RULER_BY_SIGN_IDX[sign_idx]
    ruler_sign = signof(ruler_cn)
    if ruler_sign < 0:
        return False
    ruler_of_ruler = _RULER_BY_SIGN_IDX[ruler_sign]
    return ruler_of_ruler == _OVERCOMING.get(ruler_cn)


def _near_sign_boundary(lon: Optional[float]) -> bool:
    if lon is None:
        return False
    val = ((lon % 30) + 30) % 30
    return val <= 1 or val >= 29


# 二十八宿等分步长（与 core.astro.geometry._su28 同口径：360/28）。FateBridge 以等分宿度
# 标注星曜所在宿，故 命坐两歧 的「近宿界」亦以同一等分口径判定——内部自洽，但非 horosa
# 后端的真实（不等）宿度，两者在宿界附近的临界判定可能不同。
_SU28_STEP = 360.0 / 28.0


def _near_su_boundary(lon: Optional[float]) -> bool:
    """命度是否近二十八宿界（FB 等分宿口径，距宿界 <= 1°）。"""
    if lon is None:
        return False
    offset = ((lon % _SU28_STEP) + _SU28_STEP) % _SU28_STEP
    return offset <= 1 or offset >= _SU28_STEP - 1


# --- 主入口 ------------------------------------------------------------------


def calculate(facts: Dict[str, Any]) -> List[Dict[str, Any]]:
    """buildLocalMoiraPatterns 的 Python 端口。

    ``facts`` 形如::

        {
          "asc_lon": float,                     # 命度（默认命主=ASC）
          "planet_signidx": {"日": int, "月": int, "金": int, "水": int,
                              "火": int, "木": int, "土": int,
                              "孛": int, "罗": int, "计": int, "炁": int},  # 缺省 -1
          "god_signidx": {"天贵": int, "玉贵": int, "岁驾": int},  # 神煞星座序号，缺省 -1
          "is_day": bool,                       # 昼生（6<=hour<18）
          "is_winter": bool,                    # 冬令（月 ∈ {11,12,1}）
        }

    ``god_signidx`` 由 :func:`compute_god_signidx` 依年柱算出（Phase 2a 起 天贵/玉贵/岁驾）；
    留空则相应神煞格局（日月拱贵人/命登岁驾）失效，与 horosa 离线版一致。

    返回排序后的格局列表（good 在前、bad 在后），结构与 JS 一致。
    """
    planet_signidx = {k: v for k, v in (facts.get("planet_signidx") or {}).items()}
    god_signidx = {k: v for k, v in (facts.get("god_signidx") or {}).items()}
    asc_lon = facts.get("asc_lon")
    life_sign_idx = -1 if asc_lon is None else int(asc_lon // 30) % 12
    self_sign_idx = planet_signidx.get("月", -1)
    is_day = bool(facts.get("is_day", True))
    is_winter = bool(facts.get("is_winter", False))

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
            )

    # 孤月独明（喜）：夜生月曜独居一方。
    if moon >= 0:
        same_moon = sum(
            1 for cn in _MOIRA_PLANET_ORDER if planet_signidx.get(cn, -1) == moon
        )
        if not is_day and same_moon == 1:
            _add(
                patterns,
                "孤月独明",
                "good",
                "2.3.0",
                "政余喜格：夜生月曜独居一方。",
                "?{孤月} & ?夜",
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
            "政余喜格：日月分拱官禄。",
            "@日=@官禄+4 & @月=@官禄-4",
        )

    # 金水相涵（喜）：金水同宫，且不以冬令破格。
    if _same(venus, mercury) and not is_winter:
        _add(
            patterns,
            "金水相涵",
            "good",
            "2.3.0",
            "政余喜格：金水同宫，且不以冬令破格。",
            "?{金水会} & !?冬",
        )

    # 日月拱贵人（喜）：神煞依赖，Phase 1 恒空（天贵/玉贵 未供）。
    noble = signof("天贵" if is_day else "玉贵")
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
        )

    # 命登岁驾（喜）：神煞依赖，Phase 1 恒空（岁驾 未供）。
    if _same(life_sign_idx, signof("岁驾")):
        _add(
            patterns,
            "命登岁驾",
            "good",
            "2.0.3",
            "政余喜格：命度临岁驾。",
            "@命=@{岁驾}",
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
                "政余忌格：日居西北、月居东南。",
                "(?{日西}|?{日北}) & (?{月东}|?{月南})",
            )

    # 官福失垣（忌）：官禄、福德主失垣。
    if _lost_rulership(signof, "官") and _lost_rulership(signof, "福"):
        _add(
            patterns,
            "官福失垣",
            "bad",
            "2.2.0",
            "政余忌格：官禄、福德主失垣。",
            "?{官失垣} & ?{福失垣}",
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
        )

    # 孛罗交战（忌）：罗孛同宫。
    if _same(north_node, dark_moon):
        _add(patterns, "孛罗交战", "bad", "2.2.0", "政余忌格：罗孛同宫。", "?{罗孛遇}")

    # 命坐两歧（忌）：命度近宫界 或 近宿界（宿界以 FB 等分宿口径判定，见 _near_su_boundary）。
    if _near_sign_boundary(asc_lon) or _near_su_boundary(asc_lon):
        _add(
            patterns,
            "命坐两歧",
            "bad",
            "2.0.4",
            "政余忌格：命度近宫界或宿界。",
            "?{命宫歧} | ?{命宿歧}",
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

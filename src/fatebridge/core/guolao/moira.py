"""Compatibility Guolao/Moira discrete-palace pattern evaluator."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

PATTERN_MODEL_ID = "moira_conditions_with_seasonal_moon_v3"
SIGN_ZI = ["戌", "酉", "申", "未", "午", "巳", "辰", "卯", "寅", "丑", "子", "亥"]
MOIRA_PLANET_ORDER = ["日", "月", "金", "木", "水", "火", "土", "计", "罗", "炁", "孛"]
RULER_BY_SIGN_IDX = [
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
OVERCOMING = {
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

PURPLE_CLOUDS_SOURCE_COMMIT = "10fb75de980bb0a6e0d1f50c7ee93cc97a88d7de"
PURPLE_CLOUDS_MODEL_ID = "horosa_mean_purple_clouds_10fb75de_v1"
PURPLE_CLOUDS_EPOCH_JD = 2451543.5
PURPLE_CLOUDS_EPOCH_LONGITUDE = 188.6849
PURPLE_CLOUDS_PERIOD_DAYS = 10226.78132
PURPLE_CLOUDS_RATE_DEG_PER_DAY = 360.0 / PURPLE_CLOUDS_PERIOD_DAYS


def purple_clouds_longitude(julian_day: float) -> float:
    return (
        PURPLE_CLOUDS_EPOCH_LONGITUDE
        + 360 * (julian_day - PURPLE_CLOUDS_EPOCH_JD) / PURPLE_CLOUDS_PERIOD_DAYS
    ) % 360.0


HOUSE_OFFSET = {
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


def _sign_zi(sign_idx: int) -> str:
    return "" if sign_idx < 0 else SIGN_ZI[(sign_idx + 12) % 12]


def _same(a: int, b: int) -> bool:
    return a >= 0 and b >= 0 and a == b


def _offset_palace_index(palace_index: int, offset_palaces: int) -> int:
    return -1 if palace_index < 0 else (palace_index + offset_palaces + 12) % 12


def _add(
    patterns: list[dict[str, Any]],
    name: str,
    level: str,
    detail: str,
    dsl: str,
    *,
    rule_id: str,
    inputs: dict[str, Any],
) -> None:
    patterns.append(
        {
            "name": name,
            "level": level,
            "source": "moira_s.prop-local",
            "dsl": dsl,
            "detail": detail,
            "rule_id": rule_id,
            "evidence": {
                "model_id": PATTERN_MODEL_ID,
                "granularity": "palace_index",
                "inputs": inputs,
                "condition_satisfied": True,
            },
        }
    )


class _Resolver:
    def __init__(
        self,
        planet_signidx: dict[str, int],
        life_sign_idx: int,
        self_sign_idx: int,
        god_signidx: dict[str, int],
    ) -> None:
        self._planets = planet_signidx
        self._life = life_sign_idx
        self._self = self_sign_idx
        self._gods = god_signidx

    def __call__(self, name: str) -> int:
        if name in HOUSE_OFFSET:
            return _offset_palace_index(self._life, HOUSE_OFFSET[name])
        if name == "身":
            return self._self
        if name in self._gods and self._gods[name] >= 0:
            return self._gods[name]
        if name in self._planets:
            return self._planets[name]
        try:
            return SIGN_ZI.index(name)
        except ValueError:
            return -1


def _lost_rulership(signof: _Resolver, subject: str) -> bool:
    sign_idx = signof(subject)
    if sign_idx < 0:
        return False
    ruler_cn = RULER_BY_SIGN_IDX[sign_idx]
    ruler_sign = signof(ruler_cn)
    if ruler_sign < 0:
        return False
    return RULER_BY_SIGN_IDX[ruler_sign] == OVERCOMING.get(ruler_cn)


def _indices(value: object, label: str, allowed: set[str]) -> dict[str, int]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError(f"{label}须为具名宫位索引映射")
    for key, index in value.items():
        if key not in allowed:
            raise ValueError(f"{label}包含未声明的对象{key}")
        if type(index) is not int or not -1 <= index < 12:
            raise ValueError(f"{label}.{key}须为0至11整数")
    return dict(value)


def _rulership_inputs(signof: _Resolver, subject: str) -> dict[str, Any]:
    index = signof(subject)
    ruler = RULER_BY_SIGN_IDX[index]
    ruler_index = signof(ruler)
    return {
        "palace_index": index,
        "palace_ruler": ruler,
        "ruler_palace_index": ruler_index,
        "ruler_of_ruler_palace": RULER_BY_SIGN_IDX[ruler_index],
        "compatibility_opposing_ruler": OVERCOMING[ruler],
    }


def calculate(facts: Mapping[str, object]) -> list[dict[str, Any]]:
    planet_signidx = _indices(
        facts.get("planet_signidx"), "planet_signidx", set(MOIRA_PLANET_ORDER)
    )
    god_signidx = _indices(
        facts.get("god_signidx"),
        "god_signidx",
        {
            "天贵",
            "玉贵",
            "紫微",
            "禄勋",
            "驿马",
            "岁驾",
            "岁殿",
            "斗杓",
            "唐符",
            "国印",
            "卦气",
            "长生",
            "帝旺",
            "临官",
            "阳刃",
            "天雄",
            "的杀",
            "劫杀",
            "飞廉",
            "剑锋",
            "大耗",
            "天耗",
            "地耗",
            "死符",
            "病符",
            "孤辰",
            "寡宿",
            "三刑",
            "六害",
            "地雌",
            "天狗",
            "空亡",
            "飞刃",
        },
    )
    life_sign_idx = facts.get("life_sign_idx", -1)
    if type(life_sign_idx) is not int or not -1 <= life_sign_idx < 12:
        raise ValueError("显式命宫索引须为0至11的整数")
    self_sign_idx = planet_signidx.get("月", -1)
    is_day = facts.get("is_day")
    is_winter = facts.get("is_winter")
    for name, value in (("is_day", is_day), ("is_winter", is_winter)):
        if value is not None and type(value) is not bool:
            raise TypeError(f"{name}须为布尔值")

    signof = _Resolver(planet_signidx, life_sign_idx, self_sign_idx, god_signidx)
    sun = signof("日")
    moon = signof("月")
    venus = signof("金")
    mercury = signof("水")
    dark_moon = signof("孛")
    north_node = signof("罗")
    guan = signof("官")
    patterns: list[dict[str, Any]] = []
    life_zi = _sign_zi(life_sign_idx)

    if life_sign_idx >= 0 and life_zi in "戌亥":
        disease_ruler_cn = RULER_BY_SIGN_IDX[signof("疾")]
        if _same(signof(disease_ruler_cn), life_sign_idx):
            _add(
                patterns,
                "八杀朝天",
                "good",
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

    if moon >= 0:
        same_moon = sum(
            1 for cn in MOIRA_PLANET_ORDER if planet_signidx.get(cn, -1) == moon
        )
        complete = all(
            0 <= planet_signidx.get(cn, -1) < 12 for cn in MOIRA_PLANET_ORDER
        )
        if complete and same_moon == 1 and is_day is not None and is_winter is not None:
            if is_winter:
                _add(
                    patterns,
                    "寒月单行",
                    "good" if is_day else "bad",
                    "冬令月曜独居一宫，昼喜夜忌。",
                    "?冬 & ?{孤月} & ?昼" if is_day else "?冬 & ?{孤月} & ?夜",
                    rule_id=(
                        "moira_cold_moon_alone_day_v1"
                        if is_day
                        else "moira_cold_moon_alone_night_v1"
                    ),
                    inputs={
                        "moon_palace_index": moon,
                        "is_day": is_day,
                        "is_winter": True,
                    },
                )
            elif not is_day:
                _add(
                    patterns,
                    "孤月独明",
                    "good",
                    "非冬令、夜生，月在十一曜中单独居一宫。",
                    "!?冬 & ?{孤月} & ?夜",
                    rule_id="moira_moon_alone_night_nonwinter_v3",
                    inputs={
                        "moon_palace_index": moon,
                        "same_palace_count": 1,
                        "is_winter": False,
                    },
                )

    if (
        sun >= 0
        and moon >= 0
        and guan >= 0
        and (
            _same(_offset_palace_index(sun, -4), guan)
            or _same(_offset_palace_index(sun, 4), guan)
        )
        and (
            _same(_offset_palace_index(moon, -4), guan)
            or _same(_offset_palace_index(moon, 4), guan)
        )
    ):
        _add(
            patterns,
            "日月拱官",
            "good",
            "政余喜格：日月俱在官禄三合方位。",
            "?{日拱官} & ?{月拱官}",
            rule_id="moira_sun_moon_trine_career_v2",
            inputs={"sun_index": sun, "moon_index": moon, "career_index": guan},
        )

    if venus >= 0 and mercury >= 0 and _same(venus, mercury) and is_winter is False:
        _add(
            patterns,
            "金水相涵",
            "good",
            "金星、水星同宫，且非冬令。",
            "@金=@水 & !?冬",
            rule_id="moira_venus_mercury_conjunct_nonwinter_v2",
            inputs={"venus_index": venus, "mercury_index": mercury, "is_winter": False},
        )

    if sun >= 0 and moon >= 0 and is_day is not None:
        noble_name = "天贵" if is_day else "玉贵"
        noble = signof(noble_name)
        if (
            noble >= 0
            and (
                _same(_offset_palace_index(sun, -4), noble)
                or _same(_offset_palace_index(sun, 4), noble)
            )
            and (
                _same(_offset_palace_index(moon, -4), noble)
                or _same(_offset_palace_index(moon, 4), noble)
            )
        ):
            _add(
                patterns,
                "日月拱贵人",
                "good",
                f"昼看天贵、夜看玉贵，日月同拱{noble_name}。",
                "?昼 ? 日拱天贵 : 日拱玉贵",
                rule_id="moira_sun_moon_trine_noble_v2",
                inputs={"selected_noble": noble_name, "noble_index": noble},
            )

    suijia = signof("岁驾")
    if life_sign_idx >= 0 and suijia >= 0 and _same(life_sign_idx, suijia):
        _add(
            patterns,
            "命登岁驾",
            "good",
            "命宫与岁驾同宫。",
            "@命=@岁驾",
            rule_id="moira_life_on_suijia_v2",
            inputs={"life_palace_index": life_sign_idx, "suijia_index": suijia},
        )

    if (
        sun >= 0
        and moon >= 0
        and _sign_zi(sun) in "子丑寅戌亥"
        and _sign_zi(moon) in "午巳辰申酉"
    ):
        _add(
            patterns,
            "日月失所",
            "bad",
            "日在子丑寅戌亥，月在午巳辰申酉。",
            "@日=@{子丑寅戌亥} & @月=@{午巳辰申酉}",
            rule_id="moira_sun_moon_misplaced_v2",
            inputs={"sun_branch": _sign_zi(sun), "moon_branch": _sign_zi(moon)},
        )

    if (
        life_sign_idx >= 0
        and _lost_rulership(signof, "官")
        and _lost_rulership(signof, "福")
    ):
        _add(
            patterns,
            "官福失垣",
            "bad",
            "官禄宫与福德宫主星俱入所克敌宫。",
            "?{官失垣} & ?{福失垣}",
            rule_id="moira_career_fortune_lost_rulership_v2",
            inputs={
                "career": _rulership_inputs(signof, "官"),
                "fortune": _rulership_inputs(signof, "福"),
            },
        )

    if sun >= 0 and dark_moon >= 0 and _same(sun, dark_moon):
        _add(
            patterns,
            "孛犯太阳",
            "bad",
            "月孛与太阳同宫。",
            "@孛=@日",
            rule_id="moira_apogee_sun_conjunct_v2",
            inputs={"sun_index": sun, "apogee_index": dark_moon},
        )

    if sun >= 0 and north_node >= 0 and _same(sun, north_node):
        _add(
            patterns,
            "罗犯太阳",
            "bad",
            "罗睺与太阳同宫。",
            "@罗=@日",
            rule_id="moira_node_sun_conjunct_v2",
            inputs={"sun_index": sun, "node_index": north_node},
        )

    if north_node >= 0 and dark_moon >= 0 and _same(north_node, dark_moon):
        _add(
            patterns,
            "孛罗交战",
            "bad",
            "月孛与罗睺同宫。",
            "@孛=@罗",
            rule_id="moira_apogee_node_conjunct_v2",
            inputs={"node_index": north_node, "apogee_index": dark_moon},
        )

    return patterns

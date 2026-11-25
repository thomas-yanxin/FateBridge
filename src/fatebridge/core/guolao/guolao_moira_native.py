"""Native fact projection for an explicitly supplied Moira style profile.

The source provider is Moira1.50Final EvalRule.setBirthInfo/setBirthSign/setSign,
At Home Projects2004–2015, commit9bb126fd84997aa26fed6e91b4bdf438fceb0e38.
Its source is GPLv2-or-later; this independently written projection bundles no
authored style catalogue or Java runtime. Distribution provenance is separate
from this function's conditional rule-fact semantics.

Coordinates are the caller's retained, selected-zodiac values, with float inputs
meaning their exact IEEE values. This exact-input convention is distinct from
the original Java binary64 input calculation. No coordinate, calendar, god,
historical placement or predictive qualification is inferred here.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Mapping

from fatebridge.core.guolao.guolao_moira_provider import (
    MoiraCalendarFacts,
    MoiraProviderProfile,
    MoiraProviderResolution,
)
from fatebridge.core.guolao.guolao_moira_rules import MoiraSourceFacts

NATIVE_FACTS_POLICY_ID = "guolao_native_moira_exact_facts_v1"


@dataclass(frozen=True)
class MoiraNativeProvider:
    profile: MoiraProviderProfile
    calendar: MoiraCalendarFacts | None = None


# The original signs array order after excluding the three modern planets.
# It also defines stable ties in EvalRule.setSign's longitude-only comparator.
_SOURCE_PLANETS = tuple("日月金木水火土计罗炁孛")
_FULL_PALACES = (
    "戌火",
    "酉金",
    "申水",
    "未月",
    "午日",
    "巳水",
    "辰金",
    "卯火",
    "寅木",
    "丑土",
    "子土",
    "亥木",
)
_YEAR_PALACES = (
    "命宫",
    "相貌",
    "福德",
    "官禄",
    "迁移",
    "疾厄",
    "夫妻",
    "奴仆",
    "男女",
    "田宅",
    "兄弟",
    "财帛",
)
_SOURCE_GODS = (
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
)


def native_source_facts(
    *,
    longitudes: Mapping[str, float | Fraction],
    palace_indices: Mapping[str, int],
    life_sign_index: int,
    god_sign_indices: Mapping[str, int],
    is_day: bool,
    season: str,
    source_provider: MoiraProviderResolution | None = None,
) -> MoiraSourceFacts:
    """Project same-run typed producer values without evaluating any rule.

    The caller owns coordinate/frame and ordinal-palace decisions. Complete
    eleven-body cohorts are required for solitude, neighbours and cyclic
    special patterns; an omitted body never becomes an empty source position.
    Source self_mode0 is fixed: 身 uses the supplied Moon, not another body
    palace algorithm. Life degree/mansion and unprovided calendar/gods stay
    explicitly unavailable.

    A supplied source-provider result owns its namespaces: explicit unknowns
    and known absences replace earlier research values before known facts are
    overlaid. It never mutates the caller's printed-edition god positions.
    """
    palaces: dict[str, str] = {}
    mansions: dict[str, str] = {}
    strings: dict[str, str | tuple[str, ...]] = {
        "e": (),
        "宫位": _FULL_PALACES,
    }
    booleans = {"t": True, "昼": is_day, "夜": not is_day}
    unavailable: dict[str, str] = {}
    coordinates = {
        name: Fraction(longitudes[name])
        for name in _SOURCE_PLANETS
        if name in longitudes
    }
    for name in _SOURCE_PLANETS:
        if name in palace_indices:
            index = palace_indices[name]
            palaces[name] = _FULL_PALACES[index]
            for direction_index, direction in enumerate("西南东北"):
                booleans[name + direction] = index // 3 == direction_index
        else:
            unavailable["@" + name] = "The native producer did not supply this palace"
            for direction in "西南东北":
                unavailable["?" + name + direction] = "Planet palace unavailable"
        if name in coordinates:
            remainder = coordinates[name] % 30
            booleans[name + "宫歧"] = remainder < 1 or remainder > 29
        else:
            unavailable["?" + name + "宫歧"] = "Retained longitude unavailable"
        unavailable["%" + name] = (
            "Original Moira mansion-frame input is not supplied by this adapter"
        )
        unavailable["?" + name + "宿歧"] = "Source mansion boundaries unavailable"

    for offset, name in enumerate(_YEAR_PALACES):
        palace = _FULL_PALACES[(life_sign_index - offset) % 12]
        palaces[name] = palace
        strings[palace[0] + "宫"] = name
    palaces["命"] = palaces["命宫"]
    if "月" in palaces:
        palaces["身"] = palaces["月"]
    else:
        unavailable["@身"] = "Source self_mode0 requires the Moon palace"
    if "月" in coordinates:
        booleans["身宫歧"] = booleans["月宫歧"]
    else:
        unavailable["?身宫歧"] = "Source self_mode0 requires the Moon longitude"
    unavailable.update(
        {
            "%命": "Ordinal life palace does not supply a life mansion",
            "%身": "Source self_mode0 mansion-frame input is not supplied",
            "?命宫歧": "Ordinal life palace does not supply a life degree",
            "?命宿歧": "Life degree and source mansion boundaries are unresolved",
            "?身宿歧": "Source mansion boundaries unavailable",
            "$月柱": "The native producer does not supply a Moira month pillar",
            "?晦朔": "Source lunar-calendar day26..5 is not supplied",
            "?弦望": "Source lunar-calendar day11..20 is not supplied",
        }
    )
    for name, index in god_sign_indices.items():
        palaces[name] = _FULL_PALACES[index]
    for name in _SOURCE_GODS:
        if name not in god_sign_indices:
            unavailable["@" + name] = "No selected source god position supplied"
        else:
            pass
    for source_season in "春夏秋冬":
        booleans[source_season] = season == source_season

    complete_palaces = all(name in palace_indices for name in _SOURCE_PLANETS)
    if complete_palaces:
        for index, palace in enumerate(_FULL_PALACES):
            strings[palace[0] + "宫星"] = tuple(
                name for name in _SOURCE_PLANETS if palace_indices[name] == index
            )
        for name in _SOURCE_PLANETS:
            booleans["孤" + name] = all(
                other == name or palace_indices[other] != palace_indices[name]
                for other in _SOURCE_PLANETS
            )
    else:
        for palace in _FULL_PALACES:
            unavailable["$" + palace[0] + "宫星"] = (
                "Complete eleven-body palaces required"
            )
        for name in _SOURCE_PLANETS:
            unavailable["?孤" + name] = "Complete eleven-body palaces required"

    complete_coordinates = len(coordinates) == len(_SOURCE_PLANETS)
    if complete_coordinates:
        # sorted() is stable; iteration starts in the original source body order.
        ordered = sorted(_SOURCE_PLANETS, key=coordinates.__getitem__)
        if complete_palaces:
            for index, name in enumerate(ordered):
                previous = ordered[(index - 1) % 11]
                following = ordered[(index + 1) % 11]
                backward_gap = (palace_indices[name] - palace_indices[previous]) % 12
                forward_gap = (palace_indices[following] - palace_indices[name]) % 12
                strings[name + "后"] = previous if backward_gap < 2 else "无"
                strings[name + "前"] = following if forward_gap < 2 else "无"
        else:
            pass

        for number in range(1, 7):
            booleans["__sp" + str(number)] = False
        five = "金木水火土"
        lower = ordered.index("金")
        while ordered[(lower - 1) % 11] in "日" + five:
            lower -= 1
        upper = lower + 5
        around_sun = False
        while lower < upper:
            name = ordered[lower % 11]
            if name not in five:
                if name == "日":
                    around_sun = True
                    upper += 1
                else:
                    break
            else:
                pass
            lower += 1
        if lower == upper:
            booleans["__sp5" if around_sun else "__sp4"] = True
            if not around_sun:
                # Retain the source's lower-1 observation, not an intuitive
                # replacement by the following Sun/Moon. With a unique complete
                # cohort this last scanned body is one of the five planets.
                last = ordered[(lower - 1) % 11]
                if last == "日":
                    booleans["__sp2"] = True
                elif last == "月":
                    booleans["__sp3"] = True
                else:
                    pass
            else:
                pass
        else:
            pass

        lower = ordered.index("日")
        while ordered[(lower - 1) % 11] in "日月" + five:
            lower -= 1
        upper = lower + 7
        while lower < upper and ordered[lower % 11] in "日月" + five:
            lower += 1
        booleans["__sp1"] = lower == upper

        lower = ordered.index("计")
        while ordered[(lower - 1) % 11] in "月计罗炁孛":
            lower -= 1
        upper = lower + 5
        while lower < upper and ordered[lower % 11] in "月计罗炁孛":
            lower += 1
        booleans["__sp6"] = lower == upper
    else:
        for number in range(1, 7):
            unavailable["?__sp" + str(number)] = (
                "Complete eleven-body longitudes required"
            )
    if not (complete_coordinates and complete_palaces):
        for name in _SOURCE_PLANETS:
            unavailable["$" + name + "前"] = (
                "Complete eleven-body coordinates and palaces required"
            )
            unavailable["$" + name + "后"] = (
                "Complete eleven-body coordinates and palaces required"
            )
    else:
        pass

    provenance = {
        "provider_id": NATIVE_FACTS_POLICY_ID,
        "coordinates": "same-run selected zodiac; exact supplied float/Fraction values",
        "source_order": "日月金木水火土计罗炁孛; stable equal-coordinate ties",
        "source_self_mode": "0: Moon supplies 身 palace only; no life-degree substitution",
        "palace_basis": "producer's source-hour-count research life and reverse palaces",
        "day_season": "explicit caller solar geometry and northern solar-term season",
        "gods": "explicit supplied positions; remaining source calendar gods unavailable",
        "mansions": "original Moira mansion frame unavailable in this adapter",
        "source_operator": "EvalRule1.50Final provider semantics; original Java float mode distinct",
    }
    if source_provider is not None:
        supplied = source_provider.facts
        # The source owner can replace a research fact by explicit unknown or
        # known absence. Remove the old value before overlaying its result.
        for key in (*source_provider.known_absent, *supplied.unavailable):
            name = key[1:]
            if key[0] == "@":
                palaces.pop(name, None)
            elif key[0] == "%":
                mansions.pop(name, None)
            elif key[0] == "$":
                strings.pop(name, None)
            elif key[0] == "?":
                booleans.pop(name, None)
            else:
                pass
            unavailable.pop(key, None)
        for prefix, names in (
            ("@", supplied.palaces),
            ("%", supplied.mansions),
            ("$", supplied.strings),
            ("?", supplied.booleans),
        ):
            for name in names:
                unavailable.pop(prefix + name, None)
        palaces.update(supplied.palaces)
        mansions.update(supplied.mansions)
        strings.update(supplied.strings)
        booleans.update(supplied.booleans)
        unavailable.update(supplied.unavailable)
        provenance.update(supplied.provenance)
        provenance.update(
            gods="Selected Moira provider owns source-graph gods; LuWei evidence is separate",
            day_season="Native solar day/night; source-provider month season or explicit unknown",
            mansions="Selected source-provider mansion facts or explicit unknown; no RA substitution",
        )
    else:
        pass
    return MoiraSourceFacts(
        palaces=palaces,
        mansions=mansions,
        strings=strings,
        booleans=booleans,
        unavailable=unavailable,
        provenance=provenance,
    )

"""Reference cards derived from the same tables used in calculation."""

from pydantic import JsonValue
from typing_extensions import TypedDict

from fatebridge.core.astro.astrology_tables import (
    DOMICILE_RULERS,
    EXALTATION_SIGNS,
    RULER_BY_SIGN,
    SIGN_LABELS_ZH,
)
from fatebridge.core.astro.lilly_houses import house_condition


class KnowledgeCard(TypedDict, total=False):
    title: str
    tips: list[str]
    citation: str
    curation: dict[str, JsonValue]


def astro_rule_cards(labels: dict[str, str]) -> dict[str, dict[str, KnowledgeCard]]:
    from fatebridge.core.classical_western import LOTS

    planets: dict[str, KnowledgeCard] = {}
    for planet, signs in DOMICILE_RULERS.items():
        planets[planet] = {
            "title": labels[planet],
            "tips": [
                "入庙：" + "、".join(SIGN_LABELS_ZH[sign] for sign in signs),
                f"擢升：{SIGN_LABELS_ZH[EXALTATION_SIGNS[planet]]}",
            ],
            "citation": "Ptolemy, Tetrabiblos I.17、I.19（Robbins）",
        }
    signs_table: dict[str, KnowledgeCard] = {}
    for sign, ruler in RULER_BY_SIGN.items():
        signs_table[sign] = {
            "title": SIGN_LABELS_ZH[sign],
            "tips": [
                f"庙主：{labels[ruler]}",
                *[
                    f"擢升：{labels[planet]}"
                    for planet, exaltation in EXALTATION_SIGNS.items()
                    if exaltation == sign
                ],
            ],
            "citation": "Ptolemy, Tetrabiblos I.17、I.19（Robbins）",
        }
    houses: dict[str, KnowledgeCard] = {}
    house_names = {"angular": "角宫", "succedent": "续宫", "cadent": "果宫"}
    for number in range(1, 13):
        house = house_condition(number, None, None)
        houses[f"House{number}"] = {
            "title": f"第{number}宫",
            "tips": [
                f"宫类：{house_names[house['house_class']]}",
                f"其余尊贵相同时的强度顺序：第 {house['p48_strength_rank']} 位",
                f"第 115 页宫位单项：{house['p115_house_points']:+d}",
            ],
            "citation": "William Lilly, Christian Astrology, pp. 48, 50, 115",
        }
    aspects: dict[str, KnowledgeCard] = {}
    classical_angles = {60, 90, 120, 180}
    for angle, title in {
        0: "合相",
        30: "半六合",
        45: "半刑",
        60: "六合",
        90: "刑相",
        120: "拱相",
        135: "倍半刑",
        150: "梅花相",
        180: "对冲",
    }.items():
        aspects[str(angle)] = {
            "title": f"{title}（{angle}°）",
            "tips": [f"相位角：{angle}°"],
            "citation": (
                "Ptolemy, Tetrabiblos I.13（Robbins）"
                if angle in classical_angles
                else "相位名称与标称角度"
            ),
        }
    lots: dict[str, KnowledgeCard] = {}
    operand_labels = {key.lower(): value for key, value in labels.items()}
    operand_labels["asc"] = "上升点"
    for key, lot_id in {
        "Pars Fortuna": "fortune",
        "Pars Spirit": "spirit",
        "Pars Sons": "children",
    }.items():
        definition = LOTS[lot_id]
        descriptions = []
        for sect, label in (("day", "昼盘"), ("night", "夜盘")):
            anchor, addend, subtrahend = (
                operand_labels[point] for point in definition[sect]
            )
            descriptions.append(
                f"{label}：{anchor} + {addend} − {subtrahend}（模 360°）"
            )
        if lot_id == "fortune":
            descriptions.append("托勒密 III.10 单列上升点 + 月亮 − 太阳，夜盘同式。")
        lots[key] = {
            "title": definition["cn"],
            "tips": descriptions,
            "citation": (
                "FateBridge 昼夜反转点表（core/classical_western.py::LOTS）；"
                "Ptolemy, Tetrabiblos III.10（Robbins）"
                if lot_id == "fortune"
                else "FateBridge 昼夜反转点表（core/classical_western.py::LOTS）"
            ),
        }
    return {
        "planet": planets,
        "sign": signs_table,
        "house": houses,
        "lot": lots,
        "aspect": aspects,
    }


def qimen_rule_cards() -> dict[str, dict[str, KnowledgeCard]]:
    from fatebridge.core.qimen import (
        DOOR_ELEMENTS,
        GOD_PROFILES,
        PRINTED_EXAMPLES,
        QIMEN_DOOR_TO_TRIGRAM,
        QIMEN_FUHEAD_HEAVEN_STEM,
        STAR_ELEMENTS,
        god_evidence,
    )

    doors: dict[str, KnowledgeCard] = {}
    for door, element in DOOR_ELEMENTS.items():
        doors[door] = {
            "title": door,
            "tips": [
                f"{door}属{element}，本宫为{QIMEN_DOOR_TO_TRIGRAM[door]}。",
                *[
                    f"卷二例：{door}临{palace}，称{label}。"
                    for (name, palace), label in PRINTED_EXAMPLES.items()
                    if name == door
                ],
            ],
            "citation": "《遁甲演义》卷二·门迫宫迫",
        }
    stars: dict[str, KnowledgeCard] = {
        star: {
            "title": star,
            "tips": [f"{star}属{element}。"],
            "citation": "《遁甲演义》卷三·九星所属及旺衰",
        }
        for star, element in STAR_ELEMENTS.items()
    }
    gods: dict[str, KnowledgeCard] = {}
    for god in GOD_PROFILES["yanyi_text"]["sequence"]:
        evidence = god_evidence(god)
        gods[god] = {
            "title": god,
            "tips": [evidence["traditional_role"]],
            "citation": f"《遁甲演义》{evidence['section']}",
        }
    instruments = list(QIMEN_FUHEAD_HEAVEN_STEM.items())
    stem_citation = "《遁甲演义》卷三·奇遁布局法"
    stems: dict[str, KnowledgeCard] = {
        "甲": {
            "title": "甲",
            "tips": [
                "六甲旬首所藏六仪："
                + "、".join(f"{head}藏{stem}" for head, stem in instruments)
            ],
            "citation": stem_citation,
        },
        **{
            stem: {
                "title": stem,
                "tips": [f"三奇之一，称{label}。"],
                "citation": stem_citation,
            }
            for stem, label in zip("乙丙丁", ("日奇", "月奇", "星奇"), strict=True)
        },
        **{
            stem: {
                "title": stem,
                "tips": [f"六仪之一，藏{head}。"],
                "citation": stem_citation,
            }
            for head, stem in instruments
        },
    }
    return {"stem": stems, "door": doors, "star": stars, "god": gods}

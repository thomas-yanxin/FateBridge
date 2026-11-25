"""Shared definitions, independent of the domain entry point."""

from __future__ import annotations

from typing import Any, Dict, List

SU28_NAMES = list("角亢氐房心尾箕斗牛女虚危室壁奎娄胃昴毕觜参井鬼柳星张翼轸")


SU27_ORDER: List[str] = [s for s in SU28_NAMES if s != "牛"]


RELATION_TEMPLATE = [
    h for head in ("命", "業", "胎") for h in [head, *"栄衰安危成壊友親"]
]


RELATION_PAIR = {
    "命": "命",
    "業": "業胎",
    "胎": "業胎",
    "栄": "栄親",
    "親": "栄親",
    "衰": "友衰",
    "友": "友衰",
    "安": "安壊",
    "壊": "安壊",
    "危": "危成",
    "成": "危成",
}


TEXT_URL = "https://cbetaonline.dila.edu.tw/zh-tw/T1299"


_ALIASES = str.maketrans("虛婁畢參張軫", "虚娄毕参张轸")


_GOOD_CONTACT = set("栄安成友親")


def normalize_mansion(name: str) -> str:
    return name.translate(_ALIASES)


def relation_between_su27(self_su27: str, other_su27: str) -> Dict[str, Any]:
    self_su27, other_su27 = map(normalize_mansion, (self_su27, other_su27))
    if self_su27 not in SU27_ORDER or other_su27 not in SU27_ORDER:
        raise ValueError("双方必须是二十七宿宿名（不含牛）")
    offset = (SU27_ORDER.index(other_su27) - SU27_ORDER.index(self_su27)) % 27
    relation = RELATION_TEMPLATE[offset]
    assessment = "favorable" if relation in _GOOD_CONTACT else "caution"
    meaning = (
        f"按T1299上卷结交规则，{relation}列于"
        f"{'宜结交' if assessment == 'favorable' else '需审慎'}一侧；"
        "这是单向传统判断，不等于双方现实相处结论。"
    )
    return {
        "relation": relation,
        "pair": RELATION_PAIR[relation],
        "distance": None,
        "sequence_group": offset // 9 + 1,
        "offset": offset,
        "meaning": meaning,
        "traditional_assessment": assessment,
        "self_su27": self_su27,
        "other_su27": other_su27,
        "rule_trace": [
            {
                "rule_id": "t1299_sanjiu_sequence",
                "offset": offset,
                "output": relation,
                "source": TEXT_URL,
                "locator": "T21n1299_p0391b06-18",
            }
        ],
    }

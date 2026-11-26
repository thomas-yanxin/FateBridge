"""Source-scoped month-use witnesses; membership never establishes formation."""

from copy import deepcopy
from typing import Literal, Mapping, Sequence, TypedDict

from fatebridge.utils.data import (
    BRANCH_HIDDEN_STEMS,
    BRANCH_TRIPLE_COMBINATIONS,
    STEM_ELEMENTS,
    get_ten_god,
)

Pillars = Mapping[str, tuple[str, str]]
MonthUseKind = Literal[
    "revealed_month_stem",
    "revealed_month_store_stem",
    "complete_month_triad",
    "selected_month_rule",
    "original_main_qi_reference",
]
MonthUseStatus = Literal["matched", "requires_identity_adjudication", "not_observed"]

FAMILIES = {
    "比肩": "比劫",
    "劫财": "比劫",
    "食神": "食伤",
    "伤官": "食伤",
    "正财": "财",
    "偏财": "财",
    "正官": "官杀",
    "七杀": "官杀",
    "正印": "印",
    "偏印": "印",
}


class MonthUseClaim(TypedDict):
    pdf_pages: list[int]
    text: str
    permission: str


class MonthUseSource(TypedDict):
    id: str
    author: str
    title: str
    edition: str
    url: str
    source_sha256: str
    claims: dict[str, MonthUseClaim]


SOURCE: MonthUseSource = {
    "id": "ziping_month_use_text_v1",
    "author": "沈孝瞻（所选著录）",
    "title": "秘本子平真诠·杂气及既有有限月令取用",
    "edition": ("国家图书馆藏NLC416-11jh010455-35296，上海世界图书馆发行"),
    "url": (
        "https://upload.wikimedia.org/wikipedia/commons/f/fe/"
        "NLC416-11jh010455-35296_"
        "%E5%AD%90%E5%B9%B3%E7%9C%9F%E8%A9%AE.pdf"
    ),
    "source_sha256": (
        "71402a780b0351b54edf121a51bc4a4a4ce5896496c35b954563ee06f1a6f620"
    ),
    "claims": {
        "Q03": {
            "pdf_pages": [41],
            "text": ("如甲生辰月。透戊则用偏财。透癸则用正印。" "透乙则用月刃是也。"),
            "permission": ("透干身份；原页月刃异字照存，不更改实际阳刃资格。"),
        },
        "Q04": {
            "pdf_pages": [41],
            "text": "如甲生辰月。逢申与子会局。则用水印是也。",
            "permission": ("完整会支可独立参与；仅水印类，不认证唯一化干或正偏。"),
        },
        "Q05": {
            "pdf_pages": [41],
            "text": ("一透则一用。兼透则兼用。" "透而又会。则透与会并用。"),
            "permission": ("并存资格，非都为喜用或成格；质量及救应见PDF41–43。"),
        },
        "existing_finite_month_rule": {
            "pdf_pages": [31, 32, 65, 66],
            "text": ("既有有限月令选择及本气参考；" "本轮不扩为通用成格裁定。"),
            "permission": ("复用原已披露的非杂气方法，" "非新逐页通过或新Qclaim。"),
        },
    },
}

_CHEN_REN_CLAIMS: dict[str, MonthUseClaim] = {
    "甲": {
        "pdf_pages": [42, 43, 44],
        "text": "论杂气与论墓库刑冲均列甲日辰月明壬为印。",
        "permission": "明壬见印。辰戌冲时原文另论难通月令，不能由字位判断印格。",
    },
    "丙": {
        "pdf_pages": [43],
        "text": "论杂气列丙日辰月明戊为食、明壬为煞。",
        "permission": "明壬见煞。食煞同透时的力量与制化仍待裁定。",
    },
    "丁": {
        "pdf_pages": [44, 45],
        "text": "论墓库刑冲列丁日辰月明壬为官，以库内之壬说明其身份。",
        "permission": "明壬见官。辰戌冲可伤官用，成格与根力须另审。",
    },
    "己": {
        "pdf_pages": [44],
        "text": "论墓库刑冲列己日辰月明壬为财。",
        "permission": "明壬见财。辰戌冲另有劫动之论，财用成败须另审。",
    },
}


class MonthUseWitness(TypedDict):
    id: str
    kind: MonthUseKind
    element: str
    role_family: str
    stem: str | None
    ten_god: str | None
    possible_ten_gods: list[str]
    month_hidden_stems: list[str]
    visible_positions: list[str]
    branches: list[str]
    branch_positions: dict[str, list[str]]
    label: str
    source_pdf_pages: list[int]
    source_claim_ids: list[str]


class MonthUseResolution(TypedDict):
    method_id: str
    month_branch: str
    policy_scope: Literal["miscellaneous_qi_source", "existing_month_rule"]
    witnesses: list[MonthUseWitness]
    source: MonthUseSource
    formation_status: Literal["not_adjudicated"]
    scope: str


class MonthUseMatch(TypedDict):
    status: MonthUseStatus
    witness_ids: list[str]
    pending_witness_ids: list[str]


def build_month_use_resolution(
    pillars: Pillars, selected_stem: str, original_stem: str
) -> MonthUseResolution:
    """Retain every revealed/complete-meeting use in the miscellaneous text.

    Outside 辰戌丑未, preserve the existing finite selected-month method.
    Its original-main-qi reference remains available to the candidate reader,
    without adding it to the route eligibility of that older method.
    """
    day = pillars["day"][0]
    month = pillars["month"][1]
    witnesses: list[MonthUseWitness] = []
    source = deepcopy(SOURCE)
    miscellaneous = month in "辰戌丑未"
    if miscellaneous:
        revelations: list[tuple[str, MonthUseClaim | None]] = [
            (stem, None) for stem in BRANCH_HIDDEN_STEMS[month]
        ]
        if month == "辰" and day in _CHEN_REN_CLAIMS:
            revelations.append(("壬", _CHEN_REN_CLAIMS[day]))
        for stem, store_claim in revelations:
            positions = [p for p in ("year", "month", "hour") if pillars[p][0] == stem]
            if not positions:
                continue
            god = get_ten_god(day, stem).value
            kind: MonthUseKind
            if store_claim is None:
                kind = "revealed_month_stem"
                witness_id = f"month:revealed:{stem}"
                hidden = [stem]
                label = f"透{stem}（{god}）"
                pages = [41, 42, 43]
                claim_ids = ["Q03", "Q05"]
            else:
                kind = "revealed_month_store_stem"
                witness_id = f"month:store_revealed:{stem}"
                hidden = []
                label = f"辰库见明{stem}（{god}）"
                claim_id = f"chen_store_ren:{day}"
                pages = list(store_claim["pdf_pages"])
                claim_ids = [claim_id]
                source["claims"][claim_id] = deepcopy(store_claim)
            witnesses.append(
                {
                    "id": witness_id,
                    "kind": kind,
                    "element": STEM_ELEMENTS[stem][0].value,
                    "role_family": FAMILIES[god],
                    "stem": stem,
                    "ten_god": god,
                    "possible_ten_gods": [god],
                    "month_hidden_stems": hidden,
                    "visible_positions": positions,
                    "branches": [month],
                    "branch_positions": {month: ["month"]},
                    "label": label,
                    "source_pdf_pages": pages,
                    "source_claim_ids": claim_ids,
                }
            )
        actual = {branch for _, branch in pillars.values()}
        for group, bureau in BRANCH_TRIPLE_COMBINATIONS.items():
            if month not in group or not set(group).issubset(actual):
                continue
            element = bureau[0]
            possible = list(
                dict.fromkeys(
                    get_ten_god(day, stem).value
                    for stem, (stem_element, _) in STEM_ELEMENTS.items()
                    if stem_element.value == element
                )
            )
            family = FAMILIES[possible[0]]
            witnesses.append(
                {
                    "id": f"month:complete_triad:{group}",
                    "kind": "complete_month_triad",
                    "element": element,
                    "role_family": family,
                    "stem": None,
                    "ten_god": None,
                    "possible_ten_gods": possible,
                    "month_hidden_stems": [
                        s
                        for s in BRANCH_HIDDEN_STEMS[month]
                        if STEM_ELEMENTS[s][0].value == element
                    ],
                    "visible_positions": [],
                    "branches": list(group),
                    "branch_positions": {
                        b: [p for p, (_, value) in pillars.items() if value == b]
                        for b in group
                    },
                    "label": (f"{group}会{element}（{family}类，具体十神未定）"),
                    "source_pdf_pages": [41, 42, 43],
                    "source_claim_ids": ["Q04", "Q05"],
                }
            )
    else:
        references: tuple[tuple[MonthUseKind, str], ...] = (
            ("selected_month_rule", selected_stem),
            ("original_main_qi_reference", original_stem),
        )
        for kind, stem in references:
            god = get_ten_god(day, stem).value
            label = (
                f"月令有限选择{stem}（{god}）"
                if kind == "selected_month_rule"
                else f"原月令本气{stem}（{god}，参考）"
            )
            witnesses.append(
                {
                    "id": "month:" + kind,
                    "kind": kind,
                    "element": STEM_ELEMENTS[stem][0].value,
                    "role_family": FAMILIES[god],
                    "stem": stem,
                    "ten_god": god,
                    "possible_ten_gods": [god],
                    "month_hidden_stems": [stem],
                    "visible_positions": [
                        p for p in ("year", "month", "hour") if pillars[p][0] == stem
                    ],
                    "branches": [month],
                    "branch_positions": {month: ["month"]},
                    "label": label,
                    "source_pdf_pages": [31, 32, 65, 66],
                    "source_claim_ids": ["existing_finite_month_rule"],
                }
            )
    return {
        "method_id": "ziping_month_use_witnesses_v1",
        "month_branch": month,
        "policy_scope": (
            "miscellaneous_qi_source" if miscellaneous else "existing_month_rule"
        ),
        "witnesses": witnesses,
        "source": source,
        "formation_status": "not_adjudicated",
        "scope": (
            "杂气按透干、完整三合及兼透/透会并存；"
            "会支只授五行十神类，不强指定正偏或化干。"
            "其余月保既有有限方法。月藏干、禄刃资格、原选择与有效力量分开；"
            "不裁合化、成格、喜忌。"
        ),
    }


def match_month_uses(
    resolution: MonthUseResolution,
    allowed_gods: Sequence[str],
    *,
    include_original_reference: bool = False,
) -> MonthUseMatch:
    """Match source identity at its actual precision, without picking a polarity."""
    allowed = set(allowed_gods)
    matched: list[str] = []
    pending: list[str] = []
    for witness in resolution["witnesses"]:
        if (
            witness["kind"] == "original_main_qi_reference"
            and not include_original_reference
        ):
            continue
        possible = set(witness["possible_ten_gods"])
        if possible.issubset(allowed):
            matched.append(witness["id"])
        elif possible.intersection(allowed):
            pending.append(witness["id"])
    return {
        "status": (
            "matched"
            if matched
            else "requires_identity_adjudication" if pending else "not_observed"
        ),
        "witness_ids": matched,
        "pending_witness_ids": pending,
    }

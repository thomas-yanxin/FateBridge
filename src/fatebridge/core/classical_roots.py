"""Source-specific root categories, separate from weighted strength and root loss.

《秘本子平真诠》PDF22–23 distinguishes 长生禄刃, 墓库, 余气,
and 阴长生. It does not supply numeric coefficients or a universal strong label.
"""

from copy import deepcopy
from typing import Any, Dict, Literal, Tuple, TypedDict

from fatebridge.core.classical_stages import (
    LU_SEATS,
    YANG_BLADE_SEATS,
    life_stage_profile,
    twelve_life_stage,
)
from fatebridge.utils.data import BRANCH_CONFLICTS, BRANCH_HIDDEN_STEMS, STEM_ELEMENTS

PillarMap = Dict[str, Tuple[str, str]]
SOURCE_ID = "ziping_root_categories_v1"


class RootSource(TypedDict):
    id: str
    author: str
    title: str
    edition: str
    url: str
    pdf_pages: list[int]
    printed_pages: list[int]
    source_sha256: str


SOURCE: RootSource = {
    "id": SOURCE_ID,
    "author": "沈孝瞻",
    "title": "秘本子平真诠·论十干得时不旺失时不弱",
    "edition": "国家图书馆藏本，上海世界图书馆发行",
    "url": "https://upload.wikimedia.org/wikipedia/commons/f/fe/NLC416-11jh010455-35296_%E5%AD%90%E5%B9%B3%E7%9C%9F%E8%A9%AE.pdf",
    "pdf_pages": [22, 23],
    "printed_pages": [13, 14],
    "source_sha256": "71402a780b0351b54edf121a51bc4a4a4ce5896496c35b954563ee06f1a6f620",
}

LABELS = {
    "lu_root": "禄根",
    "yang_blade_root": "阳刃根",
    "yang_growth_root": "阳长生根",
    "prosperity_root": "帝旺同气根",
    "storage_root": "同五行墓库根",
    "residual_root": "同五行余气根",
    "principal_element_root": "同五行本气根",
    "other_hidden_root": "其他同五行藏干根",
    "yin_growth_reference": "阴长生原典参考",
    "no_root_in_this_profile": "此规则未见根",
}
_STORAGE = {"木": "未", "火": "戌", "金": "丑", "水": "辰"}
_RESIDUAL = {"木": "辰", "火": "未", "金": "戌", "水": "丑"}
_POSITIONS = ("year", "month", "day", "hour")


class RootClassification(TypedDict):
    stem: str
    branch: str
    life_stage: str
    kind: str
    label: str
    matching_hidden_stems: list[str]
    hidden_element_present: bool
    source_weight_class: str
    effect_status: Literal["root_effect_not_adjudicated"]
    source_ref: str


def classify_classical_root(stem: str, branch: str) -> RootClassification:
    """Classify one explicit stem/branch without inventing a complete chart."""
    element = STEM_ELEMENTS[stem][0]
    hidden = [s for s in BRANCH_HIDDEN_STEMS[branch] if STEM_ELEMENTS[s][0] == element]
    phase = twelve_life_stage(stem, branch)
    is_yang = stem in YANG_BLADE_SEATS
    if branch == LU_SEATS[stem]:
        kind = "lu_root"
    elif branch == YANG_BLADE_SEATS.get(stem):
        kind = "yang_blade_root"
    elif phase == "帝旺" and hidden:
        # A yin stem's 旺地 root is not a qualification for 阳刃格.
        kind = "prosperity_root"
    elif is_yang and phase == "长生" and hidden:
        kind = "yang_growth_root"
    elif branch == _STORAGE.get(element.value) and hidden:
        kind = "storage_root"
    elif branch == _RESIDUAL.get(element.value) and hidden:
        kind = "residual_root"
    elif hidden and STEM_ELEMENTS[BRANCH_HIDDEN_STEMS[branch][0]][0] == element:
        kind = "principal_element_root"
    elif hidden:
        kind = "other_hidden_root"
    elif not is_yang and phase == "长生":
        # The selected text compares 阴长生 to a light root, even where the
        # hidden-stem table contains none. Preserve both observations explicitly.
        kind = "yin_growth_reference"
    else:
        kind = "no_root_in_this_profile"
    return {
        "stem": stem,
        "branch": branch,
        "life_stage": phase,
        "kind": kind,
        "label": LABELS[kind],
        "matching_hidden_stems": hidden,
        "hidden_element_present": bool(hidden),
        "source_weight_class": (
            "heavy"
            if kind
            in {"lu_root", "yang_blade_root", "yang_growth_root", "prosperity_root"}
            else (
                "light"
                if kind in {"storage_root", "residual_root"}
                else (
                    "light_textual_reference"
                    if kind == "yin_growth_reference"
                    else "not_ranked_by_this_rule"
                )
            )
        ),
        "effect_status": "root_effect_not_adjudicated",
        "source_ref": SOURCE_ID,
    }


def build_classical_root_profile(pillars: PillarMap) -> Dict[str, Any]:
    """Retain physical root positions and the chosen text's distinct root views."""
    stem = pillars["day"][0]
    rows: list[Dict[str, Any]] = []
    for name in _POSITIONS:
        branch = pillars[name][1]
        rows.append(
            {
                "pillar": name,
                **classify_classical_root(stem, branch),
                "clash_partners": [
                    other
                    for other in _POSITIONS
                    if other != name and BRANCH_CONFLICTS[branch] == pillars[other][1]
                ],
            }
        )
    return {
        "method_id": "ziping_root_categories_v1",
        "day_stem": stem,
        "life_stage_profile": life_stage_profile(),
        "roots": rows,
        "heavy_root_positions": [
            r["pillar"] for r in rows if r["source_weight_class"] == "heavy"
        ],
        "light_hidden_root_positions": [
            r["pillar"] for r in rows if r["source_weight_class"] == "light"
        ],
        "yin_growth_reference_positions": [
            r["pillar"] for r in rows if r["kind"] == "yin_growth_reference"
        ],
        "global_strength_status": "not_adjudicated",
        "source": deepcopy(SOURCE),
        "scope": "根类是所选原典的有限形式化；阴干帝旺同气根与阳刃格资格分开。不把有根直接改判强，不把阴长生补造成藏干，不以余气顺序换算强根倍数。冲只列候选，未判根损、合化或救应。",
    }

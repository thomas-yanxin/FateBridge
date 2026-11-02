"""Selected literal Heluo line conditions, separate from generic parity."""

import json
from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from typing import Any

from fatebridge.utils.errors import NumerologySourceError

SOURCE_PATH = Path(__file__).resolve().parents[1] / "data/heluo/line-rules-v1.json"
RULESET_ID = "heluo_wenming_line_conditions_v1"


@lru_cache(maxsize=1)
def _source() -> dict[str, Any]:
    try:
        raw = SOURCE_PATH.read_bytes()
        data: dict[str, Any] = json.loads(raw)
        support = data["clauses"]["support"]
        if (
            data["ruleset_id"] != RULESET_ID
            or support["rule_id"] != "wenming_yin_yuantang_yang_corresponding_v1"
            or support["required_selected_yang"] is not False
            or support["required_corresponding_yang"] is not True
            or support["note"] != "元堂坐陰爻位應爻在陽爻是也"
            or support["reading_policy"]
            != "wenming_primary_yin_line_reading; counterpart_yin_position_wording_retained; no_outcome_selection"
        ):
            raise ValueError("河洛爻位规则来源身份或所选有援读法不一致。")
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise NumerologySourceError("invalid_line_condition_source_data") from exc
    data["loaded_sha256"] = sha256(raw).hexdigest()
    return data


def line_conditions(chart: dict[str, Any]) -> dict[str, Any]:
    """Use each phase's actual six lines and selected Yuantang.

    The source's fifth/second preference is an ordinal position rule, not an
    outcome score. Zhongzong requires both a 5:1 pattern and its unique line
    selected. Failure of either positive clause is not a negative omen.
    """
    source = _source()
    support = source["clauses"]["support"]
    rows = []
    for phase in ("xian", "hou"):
        selected = chart[phase]
        bits, pos = selected["lines"], selected["yuan"]
        if (
            not isinstance(bits, list)
            or len(bits) != 6
            or any(type(bit) is not int or bit not in (0, 1) for bit in bits)
            or type(pos) is not int
            or pos not in range(1, 7)
        ):
            raise ValueError("河洛爻位规则需要六个明确阴阳爻与1至6的实际元堂。")
        yang_count = sum(bits)
        minority = 1 if yang_count == 1 else 0 if yang_count == 5 else None
        minority_pos = bits.index(minority) + 1 if minority is not None else None
        order = 1 if pos == 5 else 2 if pos == 2 else 3 if pos in (3, 4) else 4
        corresponding_pos = pos + 3 if pos <= 3 else pos - 3
        selected_yang = bool(bits[pos - 1])
        corresponding_yang = bool(bits[corresponding_pos - 1])
        rows.append(
            {
                "phase": phase,
                "gua": selected["name"],
                "lines": bits[:],
                "pos": pos,
                "yang": bool(bits[pos - 1]),
                "position_polarity_match": (pos % 2 == 1) == bool(bits[pos - 1]),
                "position_preference_order": order,
                "ruler_minister_seat": {
                    "source_pdf_page": 46,
                    "positions": [2, 5],
                    "match": pos in (2, 5),
                    "scope": "named_two_five_position_clause_only; not_complete_line_omen",
                },
                "zhongzong": {
                    "source_pdf_page": 46,
                    "yang_count": yang_count,
                    "yin_count": 6 - yang_count,
                    "minority_polarity": (
                        "yang" if minority == 1 else "yin" if minority == 0 else None
                    ),
                    "minority_pos": minority_pos,
                    "match": minority_pos is not None and pos == minority_pos,
                },
                "source_youyuan": {
                    "rule_id": support["rule_id"],
                    "source_pdf_page": support["pdf_page"],
                    "selected_pos": pos,
                    "selected_yang": selected_yang,
                    "corresponding_pos": corresponding_pos,
                    "corresponding_yang": corresponding_yang,
                    "polarity_opposed": selected_yang != corresponding_yang,
                    "required_selected_yang": support["required_selected_yang"],
                    "required_corresponding_yang": support[
                        "required_corresponding_yang"
                    ],
                    "clause_match": (
                        selected_yang is support["required_selected_yang"]
                        and corresponding_yang is support["required_corresponding_yang"]
                    ),
                    "scope": "named_primary_yin_line_yang_corresponding_clause_only; not_full_ten_condition_verdict",
                },
            }
        )
    return {
        "ruleset_id": RULESET_ID,
        "version": source["version"],
        "source_url": source["source_url"],
        "source_pdf_sha256": source["source_pdf_sha256"],
        "collation_sha256": source["loaded_sha256"],
        "source_pdf_pages": source["source_pdf_pages"][:],
        "review_status": source["review_status"],
        "literal_clauses": deepcopy(source["clauses"]),
        "position_preference_policy": "fifth_then_second_then_third_fourth_then_first_sixth; ordinal_only",
        "phases": rows,
        "source_dangwei": {
            "source_pdf_page": 46,
            "literal_condition": source["clauses"]["dangwei"]["note"],
            "status": "yinyue_definition_pending",
            "month_polarity": None,
            "match": None,
            "line_index_parity_substituted": False,
            "solstice_half_year_substituted": False,
        },
        "complete_assessment": False,
        "ten_condition_score": None,
        "scope": source["scope"],
        "constraints": [
            "逐阶段使用实际元堂；五同一异但未取唯一异爻，不满足所核众宗式。",
            "爻位次序不是成功概率、综合吉凶分数或现实身份等级。",
            "未中二五位或众宗正面条件，不自动推出爻位凶、众疾或其余反面条件。",
            "原文当位小注涉及阴月；未定月阴阳口径，不能以位序奇偶或至点半年代填。",
            "source_youyuan按主本阴爻读法逐阶段核阴元堂、阳应爻；别本阴位字面另存，不改作位序阴阳规则。",
            "yuanTang.youYing只表示先天元堂与应爻阴阳相反；反向相应不等同本段主本有援原句命中，未中原句不推出无援或现实孤立。",
        ],
    }


def line_snapshot(evidence: dict[str, Any]) -> str:
    lines = [
        "[爻位条文条件]",
        "原文爻位次序：五、二、三四、初上；仅为位序，不是综合吉凶评分。",
    ]
    for row in evidence["phases"]:
        phase = "先天" if row["phase"] == "xian" else "后天"
        z = row["zhongzong"]
        minority = (
            f"唯一异爻在{z['minority_pos']}位"
            if z["minority_pos"]
            else "无五同一异结构"
        )
        lines.append(
            f"{phase}·{row['gua']}元堂{row['pos']}位：二五君臣位{'匹配' if row['ruler_minister_seat']['match'] else '未匹配'}；"
            f"{z['yang_count']}阳{z['yin_count']}阴，{minority}，众宗式{'匹配' if z['match'] else '未匹配'}。"
        )
        aid = row["source_youyuan"]
        lines.append(
            f"{phase}有援原句（主本阴爻读法）：元堂{aid['selected_pos']}位{'阳' if aid['selected_yang'] else '阴'}，"
            f"应爻{aid['corresponding_pos']}位{'阳' if aid['corresponding_yang'] else '阴'}；"
            f"阴元堂、阳应爻式{'匹配' if aid['clause_match'] else '未匹配'}。"
        )
    lines.append(
        "原典当位的阴月口径未定；位序阴阳比较不代替此条。上述正面条件未匹配，不推出反面断语；十体综合未裁定。"
    )
    return "\n".join(lines)

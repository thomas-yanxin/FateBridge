"""Source-separated natal Nayin/body relations; no automatic full deTi verdict."""

from typing import Any

from fatebridge.core.heluo_seasonal import SOURCE_SHA256, SOURCE_URL
from fatebridge.utils.data import get_nayin

RULESET_ID = "heluo_wenming_nayin_body_relations_v1"
ELEMENTS = {
    "乾": "金",
    "兌": "金",
    "離": "火",
    "震": "木",
    "巽": "木",
    "坎": "水",
    "艮": "土",
    "坤": "土",
}
GENERATES = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
CONTROLS = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
BODY_POSITIONS = (
    ("lower", [1, 2, 3]),
    ("lower_nuclear", [2, 3, 4]),
    ("upper_nuclear", [3, 4, 5]),
    ("upper", [4, 5, 6]),
)


def element_relation(body: str, natal: str) -> str:
    """Directed relation; a reverse generating edge is never called support."""
    if body not in GENERATES or natal not in GENERATES:
        raise ValueError("卦体与纳音五行必须明确。")
    if body == natal:
        return "same_element"
    if GENERATES[body] == natal:
        return "body_generates_nayin"
    if GENERATES[natal] == body:
        return "nayin_generates_body"
    if CONTROLS[body] == natal:
        return "body_controls_nayin"
    return "nayin_controls_body"


def body_evidence(
    year_ganzhi: str,
    phases: dict[str, dict[str, Any]],
    yuan_trigrams: dict[str, str],
) -> dict[str, Any]:
    """Receive actual lower/nuclear/upper trigrams from the shared calculator.

    Year Nayin is a named input convention supported by the born-year context
    on page 32. It does not settle every use of 金人/土人 elsewhere in the book.
    """
    if not isinstance(year_ganzhi, str) or len(year_ganzhi) != 2:
        raise ValueError("纳音关系需要完整年干支。")
    nayin = get_nayin(year_ganzhi[0], year_ganzhi[1])
    if nayin == "未知纳音" or nayin[-1] not in GENERATES:
        raise ValueError("纳音关系需要有效六十甲子年干支。")
    if set(yuan_trigrams) != {"tian", "di"} or any(
        t not in ELEMENTS for t in yuan_trigrams.values()
    ):
        raise ValueError("纳音关系需要明确的年命天地元气卦。")
    rows = []
    for phase in ("xian", "hou"):
        trigrams = phases[phase]["trigrams"]
        if len(trigrams) != 4 or any(t not in ELEMENTS for t in trigrams):
            raise ValueError("纳音关系需要本卦实际上下体与两互体。")
        for (kind, positions), trigram in zip(BODY_POSITIONS, trigrams):
            relation = element_relation(ELEMENTS[trigram], nayin[-1])
            rows.append(
                {
                    "body_id": f"{phase}.{kind}",
                    "phase": phase,
                    "gua": phases[phase]["gua"],
                    "kind": kind,
                    "line_positions": list(positions),
                    "trigram": trigram,
                    "element": ELEMENTS[trigram],
                    "relation": relation,
                    "yuanqi_kinds": [
                        k for k, t in yuan_trigrams.items() if t == trigram
                    ],
                }
            )
    absence = not any(r["yuanqi_kinds"] for r in rows)
    generating = [r["body_id"] for r in rows if r["relation"] == "body_generates_nayin"]
    reverse = [r["body_id"] for r in rows if r["relation"] == "nayin_generates_body"]
    return {
        "ruleset_id": RULESET_ID,
        "version": "1.0.0",
        "source_url": SOURCE_URL,
        "source_pdf_sha256": SOURCE_SHA256,
        "source_pdf_pages": [32, 46, 51, 87],
        "assessment_status": "partial_nayin_body_relations",
        "year_ganzhi": year_ganzhi,
        "nayin": nayin,
        "nayin_element": nayin[-1],
        "nayin_policy": "birth_year_pillar_nayin; not_day_stem_element",
        "body_scope_policy": "actual_lower_upper_and_two_nuclear_bodies_in_both_phases",
        "bodies": rows,
        "same_element_body_ids": [
            r["body_id"] for r in rows if r["relation"] == "same_element"
        ],
        "yuanqi_absent": absence,
        "generating_qi": {
            "source_pdf_page": 51,
            "direction": "body_generates_nayin",
            "body_ids": generating,
            "relation_present": bool(generating),
            "yuanqi_absence_required": True,
            "condition_match": absence and bool(generating),
        },
        "mutual_generation": {
            "source_pdf_page": 87,
            "body_generates_nayin_ids": generating,
            "nayin_generates_body_ids": reverse,
            "relation_present": bool(generating or reverse),
            "scope": "bidirectional_relation_facts_only; not_the_page_51_equivalent_qi_verdict",
        },
        "present": None,
        "complete_assessment": False,
        "review_status": "single_visual_review; independent_second_review_pending",
        "unresolved": [
            "第46页得体与合理分列；其中金人、土人的五行口径未由年纳音规则统一取代。",
            "第51页卦体生纳音且无元气的条件，与第87页彼此相生的双向关系分列，不互相覆盖。",
            "年纳音同五行、相生及相克均为关系事实，不单独判定完整得体、合理、葉否或现实吉凶。",
        ],
    }


def body_snapshot(evidence: dict[str, Any]) -> str:
    lines = [
        "[年纳音与卦体关系]",
        f"年柱{evidence['year_ganzhi']}，纳音{evidence['nayin']}；按实际上下体和两互体分列。",
    ]
    labels = {
        "same_element": "同五行",
        "body_generates_nayin": "卦体生纳音",
        "nayin_generates_body": "纳音生卦体",
        "body_controls_nayin": "卦体克纳音",
        "nayin_controls_body": "纳音克卦体",
    }
    kinds = {
        "lower": "下体",
        "lower_nuclear": "下互体",
        "upper_nuclear": "上互体",
        "upper": "上体",
    }
    for row in evidence["bodies"]:
        lines.append(
            f"{row['gua']}·{kinds[row['kind']]}{row['trigram']}{row['element']}：{labels[row['relation']]}。"
        )
    qi = evidence["generating_qi"]
    lines.append(
        f"第51页无元气且卦体生纳音条件：{'匹配' if qi['condition_match'] else '未匹配'}；无元气前提{'成立' if evidence['yuanqi_absent'] else '不成立'}。"
    )
    lines.append(
        "第87页双向相生另列，不能反向套用第51页规则；完整得体、合理与葉否尚未裁定。"
    )
    return "\n".join(lines)

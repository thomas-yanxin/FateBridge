"""Generic structured-result -> sectioned ``snapshot_text`` renderer.

Several analysis tools (the nine BaZi dimensions, two-person compatibility, the
relationship/relative chart) return structured JSON and historically carried no
``snapshot_text``. That forced every consumer to special-case "does this tool
have a snapshot or not". This module flattens any such result into the same
``[Section]`` block format the snapshot contract uses elsewhere
(``fatebridge.core.export_parser`` splits on those headers), so every tool can
expose a uniform, readable text rendering plus a parseable ``snapshot_export``.

The values in these dicts already carry the domain's Chinese content; only the
structural keys are English, so a light label map plus the raw key as fallback
is enough.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

_KEY_LABELS: Dict[str, str] = {
    "summary": "小结",
    "overview": "概览",
    "notes": "说明",
    "note": "说明",
    "score": "评分",
    "score_basis": "计分依据",
    "level": "层级",
    "pattern": "格局",
    "patterns": "格局",
    "visibility": "显隐",
    "strength": "强弱",
    "recommendations": "建议",
    "suggestions": "建议",
    "strengths": "优势",
    "advantages": "优势",
    "challenges": "挑战",
    "risks": "风险",
    "risk": "风险",
    "timing": "时机",
    "timing_context": "当前大运流年",
    # 大运 / 流年时间字段：dayun_age 是"起运至今累计年数"，易被误读为起运岁数，
    # 故给明确中文标签（结构化键名不变）。
    "analysis_date": "分析日期",
    "analysis_age": "分析年龄",
    "start_age": "起运年龄",
    "dayun_age": "累计行运年数(起运至今)",
    "years_in_period": "本运已行年数",
    "dayun_pillar": "大运",
    "liunian_pillar": "流年",
    "liuyue_pillar": "流月",
    "liuri_pillar": "流日",
    "liushi_pillar": "流时",
    "overridden": "是否手动覆盖",
    "positions": "落点",
    "findings": "要点",
    "elements": "五行",
    "element": "五行",
    "direction": "方位",
    "overall_score": "综合分",
    "compatibility_level": "配合层级",
    "element_balance": "五行互补",
    "favorable_synergy": "共同喜用",
    "relationship_profile": "关系画像",
    "synastry_aspects": "互动相位",
    "compatibility": "配合度",
    "compatibility_evidence": "自定义评分依据",
    # 八字核心结构键：未覆盖时会以英文原文漏进中文快照（_label 回退到原 key）。
    "day_master": "日主",
    "day_master_strength": "日主强弱",
    "favorable_elements": "喜用神",
    "unfavorable_elements": "忌神",
    "ten_gods": "十神",
    "hidden_stems": "藏干",
    "element_distribution": "五行分布",
    "five_elements": "五行",
}

# Envelope/structural keys never rendered as content.
_SKIP_ALWAYS = {"snapshot_text", "snapshot_export", "run_metadata", "analysis_type"}


def _label(key: str) -> str:
    return _KEY_LABELS.get(key, key)


def _scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "是" if value else "否"
    return f"{value}"


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


# Keep snapshots readable: stop recursing past this depth, and cap list length.
_MAX_DEPTH = 4
_MAX_ITEMS = 12


def _flatten(value: Any, indent: int = 0, depth: int = 0) -> List[str]:
    """Render a nested structure into indented ``key：value`` / bullet lines.

    Bounded by ``_MAX_DEPTH`` / ``_MAX_ITEMS`` so deeply nested or very long
    sub-results (e.g. relationship-chart aspect dumps) degrade to a short
    summary instead of flooding the snapshot.
    """
    pad = "  " * indent
    lines: List[str] = []
    if isinstance(value, dict):
        if depth >= _MAX_DEPTH:
            lines.append(f"{pad}（{len(value)} 项，略）")
            return lines
        for key, sub in value.items():
            label = _label(str(key))
            if isinstance(sub, (dict, list)) and not _is_empty(sub):
                lines.append(f"{pad}{label}：")
                lines.extend(_flatten(sub, indent + 1, depth + 1))
            elif not isinstance(sub, (dict, list)):
                lines.append(f"{pad}{label}：{_scalar(sub)}")
    elif isinstance(value, list):
        if depth >= _MAX_DEPTH:
            lines.append(f"{pad}（{len(value)} 条，略）")
            return lines
        for item in value[:_MAX_ITEMS]:
            if isinstance(item, dict):
                inline = "，".join(
                    f"{_label(str(k))}={_scalar(v)}"
                    for k, v in item.items()
                    if not isinstance(v, (dict, list))
                )
                lines.append(f"{pad}- {inline}" if inline else f"{pad}-")
                for k, v in item.items():
                    if isinstance(v, (dict, list)) and not _is_empty(v):
                        lines.append(f"{pad}  {_label(str(k))}：")
                        lines.extend(_flatten(v, indent + 2, depth + 1))
            else:
                lines.append(f"{pad}- {_scalar(item)}")
        if len(value) > _MAX_ITEMS:
            lines.append(f"{pad}…（共 {len(value)} 条，余略）")
    else:
        lines.append(f"{pad}{_scalar(value)}")
    return lines


def build_structured_snapshot_sections(
    data: Dict[str, Any],
    *,
    title: Optional[str] = None,
    skip_keys: Optional[set[str]] = None,
) -> List[Tuple[str, List[str]]]:
    """Turn a structured result dict into ``(section_title, lines)`` pairs.

    Scalars are gathered into a leading 概要 section; each dict/list-valued key
    becomes its own section. ``skip_keys`` drops bulky sub-results (e.g. raw
    inner/outer charts) a caller does not want flattened into the snapshot.
    """
    skip = _SKIP_ALWAYS | (skip_keys or set())
    overview: List[str] = []
    if title:
        overview.append(f"类型：{title}")
    detail_sections: List[Tuple[str, List[str]]] = []
    for key, value in data.items():
        if key in skip:
            continue
        if isinstance(value, (dict, list)):
            if _is_empty(value):
                continue
            detail_sections.append((_label(str(key)), _flatten(value)))
        else:
            overview.append(f"{_label(str(key))}：{_scalar(value)}")

    sections: List[Tuple[str, List[str]]] = []
    if overview:
        sections.append(("概要", overview))
    sections.extend(detail_sections)
    return sections


def render_structured_snapshot_text(
    data: Dict[str, Any],
    *,
    title: Optional[str] = None,
    skip_keys: Optional[set[str]] = None,
) -> str:
    sections = build_structured_snapshot_sections(
        data, title=title, skip_keys=skip_keys
    )
    blocks: List[str] = []
    for section_title, lines in sections:
        body = "\n".join(line for line in lines if line is not None).strip()
        blocks.append(f"[{section_title}]\n{body}" if body else f"[{section_title}]")
    return "\n\n".join(blocks).strip()

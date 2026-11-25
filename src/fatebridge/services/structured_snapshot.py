"""Render public structured facts as titled snapshot sections."""

from typing import NamedTuple

from pydantic import JsonValue

from fatebridge.application.tool_spec import ServiceResult
from fatebridge.core.public_output import public_payload
from fatebridge.services.snapshot_builders import render_snapshot_lines

FIELD_LABELS: dict[str, str] = {
    "summary": "小结",
    "overview": "概览",
    "notes": "说明",
    "note": "说明",
    "score": "评分",
    "level": "层级",
    "pattern": "格局",
    "patterns": "格局",
    "visibility": "显隐",
    "strength": "强弱",
    "suggestions": "建议",
    "strengths": "强度",
    "challenges": "挑战",
    "risks": "风险",
    "risk": "风险",
    "timing": "时机",
    "timing_context": "当前大运流年",
    "analysis_date": "分析日期",
    "analysis_age": "分析年龄",
    "start_age": "起运年龄",
    # note (age): This measures elapsed years since the first luck period began.
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
    "element_balance": "元素分布",
    "relationship_profile": "关系盘设定",
    "synastry_aspects": "互动相位",
    "cross_chart_relations": "跨盘干支关系",
    "directional_ten_gods": "双向十神",
    "day_master": "日主",
    "day_master_strength": "日主强弱",
    "engineering_index": "工程旺衰指数",
    "classical_adjudication": "原典力量裁定",
    "engineering_reference": "工程参考方向",
    "favorable_elements_status": "喜忌裁定状态",
    "favorable_elements": "喜用神",
    "unfavorable_elements": "忌神",
    "ten_gods": "十神",
    "hidden_stems": "藏干",
    "element_distribution": "五行分布",
    "five_elements": "五行",
}

SNAPSHOT_ENVELOPE_FIELDS = {
    "snapshot_text",
    "snapshot_export",
    "run_metadata",
    "analysis_type",
}


def field_label(field_name: str) -> str:
    return FIELD_LABELS.get(field_name, field_name)


def render_scalar(value: JsonValue) -> str:
    if isinstance(value, bool):
        return "是" if value else "否"
    return f"{value}"


def is_empty_snapshot_value(value: JsonValue) -> bool:
    return value is None or value == "" or value == [] or value == {}


MAX_SNAPSHOT_DEPTH = 4
MAX_SNAPSHOT_LIST_ENTRIES = 12


def flatten_snapshot_value(
    value: JsonValue, indent: int = 0, depth: int = 0
) -> list[str]:
    """Indent nested facts, summarizing values past the depth or list limit."""
    indentation = "  " * indent
    lines: list[str] = []
    if isinstance(value, dict):
        if depth >= MAX_SNAPSHOT_DEPTH:
            lines.append(f"{indentation}（{len(value)} 项，略）")
            return lines
        for field_name, field_value in value.items():
            label = field_label(field_name)
            if isinstance(field_value, (dict, list)) and not is_empty_snapshot_value(
                field_value
            ):
                lines.append(f"{indentation}{label}：")
                lines.extend(flatten_snapshot_value(field_value, indent + 1, depth + 1))
            elif not isinstance(field_value, (dict, list)):
                lines.append(f"{indentation}{label}：{render_scalar(field_value)}")
    elif isinstance(value, list):
        if depth >= MAX_SNAPSHOT_DEPTH:
            lines.append(f"{indentation}（{len(value)} 条，略）")
            return lines
        for entry in value[:MAX_SNAPSHOT_LIST_ENTRIES]:
            if isinstance(entry, dict):
                inline = "，".join(
                    f"{field_label(field_name)}={render_scalar(field_value)}"
                    for field_name, field_value in entry.items()
                    if not isinstance(field_value, (dict, list))
                )
                lines.append(
                    f"{indentation}- {inline}" if inline else f"{indentation}-"
                )
                for field_name, field_value in entry.items():
                    if isinstance(
                        field_value, (dict, list)
                    ) and not is_empty_snapshot_value(field_value):
                        lines.append(f"{indentation}  {field_label(field_name)}：")
                        lines.extend(
                            flatten_snapshot_value(field_value, indent + 2, depth + 1)
                        )
            else:
                lines.append(f"{indentation}- {render_scalar(entry)}")
        if len(value) > MAX_SNAPSHOT_LIST_ENTRIES:
            lines.append(f"{indentation}…（共 {len(value)} 条，余略）")
    else:
        lines.append(f"{indentation}{render_scalar(value)}")
    return lines


class SnapshotSectionLines(NamedTuple):
    title: str
    lines: list[str]


def build_structured_snapshot_sections(
    data: ServiceResult,
    *,
    title: str | None = None,
    skip_keys: set[str] | None = None,
) -> list[SnapshotSectionLines]:
    """Group scalars into an overview and give nested facts their own sections."""
    skip = SNAPSHOT_ENVELOPE_FIELDS | (skip_keys or set())
    overview: list[str] = []
    if title:
        overview.append(f"类型：{title}")
    detail_sections: list[SnapshotSectionLines] = []
    for field_name, value in public_payload(data).items():
        if field_name in skip:
            continue
        if isinstance(value, (dict, list)):
            if is_empty_snapshot_value(value):
                continue
            detail_sections.append(
                SnapshotSectionLines(
                    field_label(field_name), flatten_snapshot_value(value)
                )
            )
        else:
            overview.append(f"{field_label(field_name)}：{render_scalar(value)}")

    sections: list[SnapshotSectionLines] = []
    if overview:
        sections.append(SnapshotSectionLines("概要", overview))
    sections.extend(detail_sections)
    return sections


def render_structured_snapshot_text(
    data: ServiceResult,
    *,
    title: str | None = None,
    skip_keys: set[str] | None = None,
) -> str:
    return render_snapshot_lines(
        build_structured_snapshot_sections(data, title=title, skip_keys=skip_keys)
    )

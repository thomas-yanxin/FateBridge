"""将服务结果分节渲染为快照文本，并构造对应的导出结构。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from fatebridge.core.export_parser import parse_export_content

__all__ = [
    "render_snapshot_text",
    "render_snapshot_lines",
    "build_snapshot_export",
]


def render_snapshot_text(sections: Sequence[Tuple[str, str]]) -> str:
    """把 ``(标题, 正文字符串)`` 块渲染为 ``[标题]`` + 正文，块与块之间空一行。

    正文为空（``strip()`` 后无内容）时只输出标题行。
    """
    blocks: List[str] = []
    for title, body in sections:
        blocks.append(f"[{title}]")
        if body.strip():
            blocks.append(body)
        blocks.append("")
    return "\n".join(blocks).strip()


def render_snapshot_lines(sections: Sequence[Tuple[str, Sequence[str]]]) -> str:
    """把 ``(标题, 正文行列表)`` 块渲染为快照文本，块间以空行分隔。

    会丢弃 ``None`` 行；正文整体为空时只保留标题。
    """
    blocks: List[str] = []
    for title, lines in sections:
        body = "\n".join(line for line in lines if line is not None).strip()
        if body:
            blocks.append(f"[{title}]\n{body}")
        else:
            blocks.append(f"[{title}]")
    return "\n\n".join(blocks).strip()


def build_snapshot_export(
    *,
    technique: str,
    snapshot_text: str,
    selected_sections: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """``parse_export_content`` 的轻量包装，统一 service 层的调用形态。"""
    return parse_export_content(
        technique=technique,
        content=snapshot_text,
        selected_sections=selected_sections,
    )

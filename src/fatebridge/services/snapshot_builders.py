"""将服务结果分节渲染为快照文本，并构造对应的导出结构。"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import JsonValue

from fatebridge.core.export_parser import ParsedExport, parse_export_content
from fatebridge.core.public_output import public_value
from fatebridge.utils.formatting import format_json_response

__all__ = [
    "format_snapshot_json",
    "render_snapshot_text",
    "render_snapshot_lines",
    "build_snapshot_export",
]


def format_snapshot_json(value: JsonValue, *, compact: bool = False) -> str:
    """Render structured public facts before they become opaque snapshot text."""
    return format_json_response(public_value(value), compact=compact)


def render_snapshot_text(sections: Sequence[tuple[str, str]]) -> str:
    """Render titled text blocks separated by a blank line."""
    blocks: list[str] = []
    for title, body in sections:
        blocks.append(f"[{title}]")
        if body.strip():
            blocks.append(body)
        else:
            pass
        blocks.append("")
    return "\n".join(blocks).strip()


def render_snapshot_lines(sections: Sequence[tuple[str, Sequence[str | None]]]) -> str:
    """Render titled blocks while omitting absent lines."""
    return render_snapshot_text(
        [
            (title, "\n".join(line for line in lines if line is not None).strip())
            for title, lines in sections
        ]
    )


def build_snapshot_export(
    *,
    technique: str,
    snapshot_text: str,
    selected_sections: list[str] | None = None,
) -> ParsedExport:
    """Build the structured export of an existing snapshot."""
    return parse_export_content(
        technique=technique,
        content=snapshot_text,
        selected_sections=selected_sections,
    )

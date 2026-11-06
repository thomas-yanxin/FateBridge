"""Text rendering shared by local divination techniques."""

from typing import List, Tuple


def join_lines(lines: List[str]) -> str:
    return "\n".join(line for line in lines if line).strip()


def render_snapshot_text(sections: List[Tuple[str, str]]) -> str:
    blocks: List[str] = []
    for title, body in sections:
        blocks.append(f"[{title}]")
        if body:
            blocks.append(body.strip())
        blocks.append("")
    return "\n".join(blocks).strip()

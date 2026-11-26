"""Text rendering shared by local divination techniques."""


def join_lines(lines: list[str]) -> str:
    return "\n".join(line for line in lines if line).strip()


def render_snapshot_text(sections: list[tuple[str, str]]) -> str:
    blocks: list[str] = []
    for title, body in sections:
        blocks.append(f"[{title}]")
        if body:
            blocks.append(body.strip())
        blocks.append("")
    return "\n".join(blocks).strip()

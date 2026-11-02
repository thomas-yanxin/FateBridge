"""Remove only verified additions for offline comparison with unchanged old facts."""

from __future__ import annotations

import copy
import json
from typing import Any


def without_branch_breaks(value: dict[str, Any]) -> dict[str, Any]:
    from fatebridge.core.metaphysics.jinkou_branch_breaks import (
        RULE,
        branch_breaks,
        branch_breaks_trace,
    )

    result = copy.deepcopy(value)
    version_lines: set[tuple[str, str]] = set()

    def canonical(obj: Any) -> str:
        return json.dumps(obj, sort_keys=True, ensure_ascii=False)

    def visit(obj: Any) -> None:
        if isinstance(obj, list):
            for child in obj:
                visit(child)
        elif isinstance(obj, dict):
            if obj.get("ruleset", {}).get("id") == "jinkou_guben_excerpt_v1":
                rows = obj["rows"]
                expected = branch_breaks(*(r["content"] for r in rows[1:]))
                traces = obj["rule_trace"]
                selected = [t for t in traces if t.get("rule_id") == RULE]
                if (
                    canonical(obj.get("branch_breaks")) != canonical(expected)
                    or canonical(selected) != canonical([branch_breaks_trace(expected)])
                    or obj["ruleset"]["version"] != "1.16.0"
                ):
                    raise ValueError(
                        "Offline comparison cannot hide wrong break-pair facts"
                    )
                del obj["branch_breaks"]
                obj["rule_trace"] = [t for t in traces if t.get("rule_id") != RULE]
                title = obj["ruleset"]["source_title"]
                prefix = f"规则来源：{title}；jinkou_guben_excerpt_v1 / "
                version_lines.add((prefix + "1.16.0", prefix + "1.15.0"))
                obj["ruleset"]["version"] = "1.15.0"
            for child in list(obj.values()):
                visit(child)

    visit(result)

    # Only the renderer's exact metadata line, only at its declared text paths.
    # Never replace version-like strings in calculation facts or arbitrary prose.
    def previous_version_line(text: str) -> str:
        lines = text.splitlines(keepends=True)
        for new, old in version_lines:
            lines = [
                old + line[len(new) :] if line.rstrip("\r\n") == new else line
                for line in lines
            ]
        return "".join(lines)

    if isinstance(result.get("snapshot_text"), str):
        result["snapshot_text"] = previous_version_line(result["snapshot_text"])
    for section in result.get("snapshot_export", {}).get("sections", []):
        if isinstance(section.get("content"), str):
            section["content"] = previous_version_line(section["content"])
    return result

"""Remove only verified witness additions for an offline, exact prior-result diff."""

from __future__ import annotations

import json
from typing import Any


def without_break_witnesses(
    value: dict[str, Any], expected: dict[str, Any]
) -> dict[str, Any]:
    # JSON round-trip prevents a shared result/trace dict from being removed twice.
    result = json.loads(json.dumps(value, ensure_ascii=False))

    def visit(obj: Any) -> None:
        if isinstance(obj, list):
            for child in obj:
                visit(child)
        elif isinstance(obj, dict):
            if obj.get("ruleset", {}).get("id") == "jinkou_guben_excerpt_v1":
                block = obj.get("branch_breaks")
                traces = [
                    t
                    for t in obj.get("rule_trace", [])
                    if t.get("rule_id") == "jinkou.printed_break_pairs"
                ]
                if (
                    not isinstance(block, dict)
                    or block.get("witness_evidence") != expected
                    or len(traces) != 1
                    or traces[0].get("result") != block
                ):
                    raise ValueError(
                        "Offline comparison cannot hide wrong witness facts"
                    )
                del block["witness_evidence"]
                del traces[0]["result"]["witness_evidence"]
            for child in obj.values():
                visit(child)

    visit(result)
    return result

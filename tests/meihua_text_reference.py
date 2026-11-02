"""Reverse only v46 display additions against unchanged literal source references."""

import json
from copy import deepcopy
from pathlib import Path

_ROWS = json.loads(
    (
        Path(__file__).parent / "fixtures/meihua_text_variants_v1/reference.json"
    ).read_bytes()
)["rows"]
_LITERAL = {row["raw_text"]: row["expected_display_text"] for row in _ROWS}


def restore_pre_v46_text_display(result):
    result = deepcopy(result)
    replacements = {}

    def remove(value):
        if isinstance(value, list):
            for item in value:
                remove(item)
        elif isinstance(value, dict):
            for key, source in [
                ("classical_yaoci_rendering", "classical_yaoci"),
                ("moving_yaoci_rendering", "moving_yaoci"),
            ]:
                if key not in value:
                    continue
                rendering = value.pop(key)
                raw = value[source]["text"]
                assert rendering["raw_text"] == raw
                assert rendering["display_text"] == _LITERAL[raw]
                assert rendering["status"] == "rendered_literal_transcription"
                display = rendering["display_text"]
                if display != raw:
                    assert replacements.get(display, raw) == raw
                    replacements[display] = raw
            for item in value.values():
                remove(item)

    remove(result)

    def reverse(value, path=()):
        if isinstance(value, dict):
            return {key: reverse(item, (*path, key)) for key, item in value.items()}
        if isinstance(value, list):
            return [reverse(item, (*path, i)) for i, item in enumerate(value)]
        allowed = (
            path == ("summary",)
            or path == ("interpretation", "comprehensive_judgement")
            or path[:2] == ("interpretation", "judgement_outline")
            or (
                path[:2] == ("interpretation", "line_oracles")
                and path[-1] in {"judgement", "summary"}
            )
            or (
                path[:2] == ("interpretation", "moving_line_oracle")
                and path[-1] in {"judgement", "summary"}
            )
        )
        if isinstance(value, str) and allowed:
            for display, raw in sorted(
                replacements.items(), key=lambda row: len(row[0]), reverse=True
            ):
                value = value.replace(display, raw)
        return value

    return reverse(result)

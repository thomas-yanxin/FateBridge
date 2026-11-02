"""Literal Zhouyi texts from a frozen, attributed public-domain transcription."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from importlib.resources import files
from typing import Any


@lru_cache(maxsize=1)
def _corpus() -> dict[str, Any]:
    resource = files("fatebridge.data").joinpath("classical/zhouyi.json")
    corpus: dict[str, Any] = json.loads(resource.read_text(encoding="utf-8"))
    return corpus


def classical_hexagram(code: str) -> dict[str, Any]:
    """Return a fresh copy; caller mutations cannot alter cached source text."""
    corpus = _corpus()
    for chapter in corpus["chapters"]:
        if chapter["code"] == code:
            return {
                "corpus_id": corpus["corpus_id"],
                "source_kind": corpus["source_kind"],
                "edition_status": corpus["edition_status"],
                **deepcopy(chapter),
            }
    raise ValueError("周易卦码必须为初爻至上爻的六位 0/1 字符串")


def moving_text_evidence(current_code: str, changed_code: str) -> dict[str, Any]:
    base = classical_hexagram(current_code)
    changed = classical_hexagram(changed_code)
    positions = [
        i + 1 for i, (a, b) in enumerate(zip(current_code, changed_code)) if a != b
    ]
    return {
        "selection_policy": "all_actual_moving_lines_reference_only",
        "base_guaci": base["guaci"],
        "changed_guaci": changed["guaci"] if positions else None,
        "moving_yaoci": [
            verse for verse in base["yaoci"] if verse["position"] in positions
        ],
        "all_moving_special": base["special"] if len(positions) == 6 else None,
        "base_source_url": base["source_url"],
        "changed_source_url": changed["source_url"],
        "scope": "按实际动爻列原文供参照；纳甲六爻不以通用爻位模板替代爻辞，未自动套用其他流派的多爻变占法。",
    }

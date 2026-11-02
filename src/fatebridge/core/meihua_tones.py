"""Tone-input evidence distinguishes source examples from declared phonology."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def _profile() -> dict[str, Any]:
    profile: dict[str, Any] = json.loads(
        (
            Path(__file__).resolve().parents[1] / "data/meihua/tone-basis-v1.json"
        ).read_text(encoding="utf-8")
    )
    if profile["id"] != "meihua_tone_input_v1" or profile["version"] != "1.0.0":
        raise ValueError("Unknown Meihua tone input evidence profile")
    return profile


def build_text_tone_basis(parameters: dict[str, Any]) -> dict[str, Any]:
    """Keep reported categories; never assign tones from a character or source name."""
    profile = _profile()
    text, tones = parameters["text"], parameters["tones"]
    example = profile["selected_worked_example"]
    # These two graphic aliases identify the cited phrase only. They do not
    # replace the input text, its category values or the casting arithmetic.
    comparison_text = (
        text.translate(str.maketrans({"动": "動", "静": "靜"})) if text else None
    )
    differences = []
    if comparison_text == example["text"]:
        differences = [
            i + 1
            for i, (actual, expected) in enumerate(zip(tones, example["tones"]))
            if actual != expected
        ]
        status = (
            "differs_from_selected_example_categories"
            if differences
            else "matches_selected_example_categories"
        )
    else:
        status = "text_not_supplied" if text is None else "different_text_not_compared"
    reference = parameters["tone_reference"]
    return {
        "ruleset_id": profile["id"],
        "version": profile["version"],
        "ruleset": deepcopy(profile),
        "encoding": "ping_shang_qu_ru_1_2_3_4",
        "reported_tones": list(tones),
        "characters": [
            {
                "index": i + 1,
                "character": text[i] if text is not None else None,
                "reported_value": tone,
                "tone_category": "平上去入"[tone - 1],
                "fact_path": f"meihua.seed.parameters.tones.{i}",
            }
            for i, tone in enumerate(tones)
        ],
        "reference": deepcopy(reference),
        "reference_status": (
            "caller_declared_unverified" if reference is not None else "not_supplied"
        ),
        "reference_independently_verified": False,
        "phonological_system_automatically_identified": False,
        "unique_classical_pronunciation_established": False,
        "selected_example_comparison": {
            "status": status,
            "difference_positions": differences,
            "example_id": example["id"],
            "source_id": example["source_id"],
            "original_pdf_index": example["original_pdf_index"],
            "matching_categories_establish_same_original_sound_system": False,
            "different_categories_prove_source_example_wrong": False,
        },
    }

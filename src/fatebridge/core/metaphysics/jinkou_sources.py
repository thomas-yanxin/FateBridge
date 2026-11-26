"""Witness identity and unresolved readings, separate from computed strength."""

import json
from pathlib import Path
from typing import Any

STRENGTH_NOTE = (
    "课内旺衰采用网上转录十二例归纳的唯一不受克规则；"
    "京本PDF130天乙例图式末位为木，转录为水，书影判语仍为土旺。"
    "早稻田第五册PDF54–59同章十二例中，天乙例明确作水，为所选推导提供原书旁证。"
    "京本原样11/12与异文仍保留，不据另本改判京本；同组十二例不算新增独立占验，日下五态与综合取用仍未裁。"
)


def strength_sources() -> dict[str, Any]:
    asset = Path(__file__).resolve().parents[2] / "data/jinkou_waseda_strength.json"
    corroboration: dict[str, Any] = json.loads(asset.read_text(encoding="utf-8"))
    return {
        "selected_witness": "online_transcription",
        "derivation": "sufficient_condition_inferred_from_examples",
        "source_section": "贵神休旺所主",
        "scan_pdf_pages": [129, 130],
        "scan_collation_status": "unresolved_diagram_prose_difference",
        "daily_five_states_adjudicated": False,
        "complete_classical_acceptance": False,
        "note": STRENGTH_NOTE,
        **corroboration,
    }


def use_sources() -> dict[str, Any]:
    return {
        "no_control_pdf_page": 18,
        "no_control_footer_page": 17,
        "polarity_pdf_pages": [45, 46],
        "combined_priority_status": "not_adjudicated",
    }

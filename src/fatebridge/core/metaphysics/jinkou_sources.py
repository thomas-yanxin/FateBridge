"""Witness identity and unresolved readings, separate from computed strength."""

import json
from pathlib import Path
from typing import Any

SCAN_URL = "https://upload.wikimedia.org/wikipedia/commons/e/e1/CNTS-00047981961_1_六壬神課金口訣.pdf"
SCAN_SHA256 = "dfa4b039f30100eb75a8fe21904256bc4e47c04538c8602d08aec9e7f7646364"
STRENGTH_NOTE = (
    "课内旺衰采用网上转录十二例归纳的唯一不受克规则；"
    "京本PDF130天乙例图式末位为木，转录为水，书影判语仍为土旺。"
    "早稻田第五册PDF54–59同章十二例中，天乙例明确作水，为所选推导提供原书旁证。"
    "京本原样11/12与异文仍保留，不据另本改判京本；同组十二例不算新增独立占验，日下五态与综合取用仍未裁。"
)


def strength_sources() -> dict[str, Any]:
    from fatebridge.core.metaphysics.ren_sources import JINKOU_SOURCE

    asset = Path(__file__).resolve().parents[2] / "data/jinkou_waseda_strength.json"
    corroboration: dict[str, Any] = json.loads(asset.read_text(encoding="utf-8"))
    return {
        "selected_witness": "online_transcription",
        "derivation": "sufficient_condition_inferred_from_examples",
        "source_url": JINKOU_SOURCE,
        "source_section": "贵神休旺所主",
        "scan_source_url": SCAN_URL,
        "scan_source_sha256": SCAN_SHA256,
        "scan_pdf_pages": [129, 130],
        "scan_collation_status": "unresolved_diagram_prose_difference",
        "daily_five_states_adjudicated": False,
        "complete_classical_acceptance": False,
        "note": STRENGTH_NOTE,
        **corroboration,
    }


def use_sources() -> dict[str, Any]:
    return {
        "scan_source_url": SCAN_URL,
        "scan_source_sha256": SCAN_SHA256,
        "no_control_pdf_page": 18,
        "no_control_footer_page": 17,
        "polarity_pdf_pages": [45, 46],
        "combined_priority_status": "not_adjudicated",
    }

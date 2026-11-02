"""Selected direct manuscript readings, kept separate from calendar policy."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_hinoo_catalog import catalogue_reference
from fatebridge.core.sukuyo_hinoo_context import context_reference
from fatebridge.core.sukuyo_hinoo_meanings import calendar_clause_meanings
from fatebridge.core.sukuyo_hinoo_natal_scope import natal_scope_reference
from fatebridge.core.sukuyo_kyoto_layers import qualify_kyoto_reference
from fatebridge.core.sukuyo_seibunkan import seibunkan_reference
from fatebridge.core.sukuyo_sources import load_source
from fatebridge.core.sukuyo_witness_research import (
    native_completion_reference,
    native_followup_reference,
    research_reference,
)
from fatebridge.core.sukuyo_zentsuji_later import later_reading_reference

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_t2465_critical.json"
ZENTSUJI_SOURCE = (
    Path(__file__).resolve().parents[1] / "data/sukuyo_t2465_zentsuji.json"
)
_ALIASES = str.maketrans("虛", "虚")


def critical_calendar_reference(
    hinoo_source: dict[str, Any], host_examples: list[dict[str, Any]]
) -> dict[str, Any]:
    """Compare three named examples; never choose a new manuscript algorithm.

    Bind the companion reference to the actual Taisho quotations supplied by
    this profile, so a later source update cannot silently inherit old findings.
    The loaded data and its digest are captured together.
    """
    loaded = load_source(SOURCE)
    bundle = loaded.data
    taisho = hinoo_source["downloaded_primary_edition"]
    if (
        taisho["publisher_html_response_sha256"]
        != bundle["taisho_publisher_html_sha256"]
        or taisho["downloaded_calendar_windows"] != bundle["taisho_calendar_windows"]
    ):
        raise ValueError("桧尾校勘参考与本次所用大正原文不一致，须重新核验")
    examples = {(row["lunar_month"], row["lunar_day"]): row for row in host_examples}
    controls = bundle["taisho_selected_controls"]
    manuscript_rows = [
        row for row in bundle["selected_primary"]["observations"] if "month" in row
    ]
    manuscript = {(row["month"], row["day"]): row for row in manuscript_rows}
    control_keys = {(row["month"], row["day"]) for row in controls}
    if (
        set(examples) != set(manuscript)
        or set(examples) != control_keys
        or len(examples) != len(host_examples)
        or len(controls) != len(examples)
        or len(manuscript_rows) != len(manuscript)
    ):
        raise ValueError("桧尾所选原文例题的计算上下文不完整或重复")
    comparisons = []
    for control in controls:
        key = (control["month"], control["day"])
        calculation = examples[key]
        observed = manuscript[key]
        calculated = calculation["direct_mansion"]
        comparisons.append(
            {
                "lunar_month": key[0],
                "lunar_day": key[1],
                "taisho_literal_mansion": control["mansion"],
                "kyoto_manuscript_mansion": observed["mansion"],
                "host_calculated_mansion": calculated,
                "manuscript_matches_host": observed["mansion"].translate(_ALIASES)
                == calculated,
                "taisho_literal_matches_host": control["mansion"].translate(_ALIASES)
                == calculated,
                "calculation": deepcopy(calculation),
                "manuscript_location": observed["location"],
                "source_example_applied_as_calendar_override": False,
            }
        )
    supplemental = load_source(ZENTSUJI_SOURCE)
    witness = supplemental.data
    witness_rows = [row for row in witness["observations"] if "month" in row]
    witness_examples = {(row["month"], row["day"]): row for row in witness_rows}
    if len(witness_rows) != len(witness_examples) or set(witness_examples) != set(
        examples
    ):
        raise ValueError("善通寺桧尾所选原文例题不完整或重复")
    supplemental_comparisons = []
    for control in controls:
        key = control["month"], control["day"]
        observed = witness_examples[key]
        calculation = examples[key]
        calculated = calculation["direct_mansion"]
        supplemental_comparisons.append(
            {
                "lunar_month": key[0],
                "lunar_day": key[1],
                "taisho_literal_mansion": control["mansion"],
                "witness_literal_mansion": observed["mansion"],
                "host_calculated_mansion": calculated,
                "witness_matches_host": observed["mansion"].translate(_ALIASES)
                == calculated,
                "taisho_literal_matches_host": control["mansion"].translate(_ALIASES)
                == calculated,
                "calculation": deepcopy(calculation),
                "witness_location": observed["location"],
                "source_example_applied_as_calendar_override": False,
            }
        )
    research = research_reference(taisho)
    native_followup = native_followup_reference(research)
    native_completed = native_completion_reference(native_followup)
    meanings = calendar_clause_meanings(taisho)
    primary, span = qualify_kyoto_reference(
        bundle["selected_primary"], bundle["apparatus_span_reference"], loaded.sha256
    )
    return {
        **deepcopy(bundle),
        "source_bundle_sha256": loaded.sha256,
        "selected_primary": primary,
        "apparatus_span_reference": span,
        "witness_catalogue_candidates": catalogue_reference(
            taisho["edition_witness_note_html"]
        ),
        "image_witness_research": research,
        "image_witness_native_followup": native_followup,
        "image_witness_native_completion": native_completed,
        "image_witness_context_followup": context_reference(native_completed, taisho),
        "calendar_clause_meanings": meanings,
        "natal_half_application": natal_scope_reference(meanings, taisho),
        "later_seibunkan_comparison": seibunkan_reference(meanings, taisho),
        "selected_example_comparisons": comparisons,
        "supplemental_witnesses": [
            {
                **witness,
                "source_bundle_sha256": supplemental.sha256,
                "selected_example_comparisons": supplemental_comparisons,
                "later_reading_followup": later_reading_reference(
                    witness, supplemental.sha256
                ),
            }
        ],
        "complete_critical_edition_accepted": False,
    }

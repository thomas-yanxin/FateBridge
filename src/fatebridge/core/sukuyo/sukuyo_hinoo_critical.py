"""Selected direct manuscript readings, kept separate from calendar policy."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[2] / "data/sukuyo_t2465_critical.json"
ZENTSUJI_SOURCE = (
    Path(__file__).resolve().parents[2] / "data/sukuyo_t2465_zentsuji.json"
)
ALIASES = str.maketrans("虛", "虚")


def critical_calendar_reference(
    hinoo_source: dict[str, Any], host_examples: list[dict[str, Any]]
) -> dict[str, Any]:
    """Compare three named examples; never choose a new manuscript algorithm."""
    bundle = load_source(SOURCE)
    taisho = hinoo_source["downloaded_primary_edition"]
    if taisho["downloaded_calendar_windows"] != bundle["taisho_calendar_windows"]:
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
                "manuscript_matches_host": observed["mansion"].translate(ALIASES)
                == calculated,
                "taisho_literal_matches_host": control["mansion"].translate(ALIASES)
                == calculated,
                "calculation": deepcopy(calculation),
                "manuscript_location": observed["location"],
                "source_example_applied_as_calendar_override": False,
            }
        )
    witness = load_source(ZENTSUJI_SOURCE)
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
                "witness_matches_host": observed["mansion"].translate(ALIASES)
                == calculated,
                "taisho_literal_matches_host": control["mansion"].translate(ALIASES)
                == calculated,
                "calculation": deepcopy(calculation),
                "witness_location": observed["location"],
                "source_example_applied_as_calendar_override": False,
            }
        )
    return {
        **deepcopy(bundle),
        "selected_example_comparisons": comparisons,
        "supplemental_witnesses": [
            {
                **witness,
                "selected_example_comparisons": supplemental_comparisons,
            }
        ],
        "complete_critical_edition_accepted": False,
    }

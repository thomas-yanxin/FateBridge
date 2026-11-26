"""Consolidated gate-2/context-clause invariants for Human Design knowledge."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core.human_design import knowledge as hd
from fatebridge.services.knowledge import calculate_knowledge_read
from fatebridge.utils.errors import EphemerisSourceError


def test_gate2_condition_stays_reference_only() -> None:
    result = calculate_knowledge_read(domain="human_design", key="2.3")
    row = result["reference_details"]["record"]
    (condition,) = row["source_conditions"]
    assert condition["source_condition"] == {
        "relation": "permanent_channel_connection",
        "channel_gates": [2, 14],
    }
    assert condition["polarity"] == "exaltation"
    assert condition["personal_condition_satisfied"] is None
    assert condition["automatic_application"] is False
    assert row["actual_fixing_state"] is row["selected_polarity"] is None
    assert "永久" in result["rendered_text"] and "不自动应用" in result["rendered_text"]
    assert result["provenance"]["real_world_efficacy_validated"] is False


def test_context_annotations_attached_on_exact_five_keys() -> None:
    annotated = []
    for gate in range(1, 65):
        for line in range(1, 7):
            key = f"{gate}.{line}"
            row = hd.read_reference(category="lines", key=key)["reference_details"][
                "record"
            ]
            if row.get("source_context_annotations"):
                annotated.append(key)
    assert annotated == ["2.3", "6.3", "7.2", "12.6", "42.1"]


def test_missing_or_invalid_context_clauses_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad = tmp_path / "missing.json"
    monkeypatch.setattr(hd, "CONTEXT_CLAUSES_PATH", bad)
    with pytest.raises(EphemerisSourceError):
        hd.build_registry()
    bad.write_text("{}")
    result = calculate_knowledge_read(domain="human_design", key="1.1")
    assert result["status_code"] == 503 and result["retryable"] is False


def test_returned_condition_mutation_does_not_change_next_read() -> None:
    result = hd.read_reference(category=None, key="2.3")
    prior = deepcopy(result["reference_details"]["record"]["source_conditions"])
    result["reference_details"]["record"]["source_conditions"][0][
        "automatic_application"
    ] = True
    assert (
        hd.read_reference(category=None, key="2.3")["reference_details"]["record"][
            "source_conditions"
        ]
        == prior
    )

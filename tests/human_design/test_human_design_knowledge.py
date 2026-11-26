"""Consolidated Human Design 384-line knowledge catalogue tests."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core.contracts.output_reference import HumanDesignKnowledgeDetails
from fatebridge.core.human_design import depth
from fatebridge.core.human_design import knowledge as hd
from fatebridge.services.knowledge import (
    calculate_knowledge_read,
    calculate_knowledge_registry,
)
from fatebridge.utils.errors import EphemerisSourceError


def test_all384_keys_retain_source_poles_and_curated_gates_1_to_6() -> None:
    seen = []
    curated = []
    ref = depth.depth_reference()
    for gate in range(1, 65):
        for line in range(1, 7):
            key = f"{gate}.{line}"
            entry = hd.read_reference(category="lines", key=key)
            row = entry["reference_details"]["record"]
            seen.append(row["key"])
            assert (
                row["catalogue_glyph_polarity"]
                == ref["gates"][gate - 1]["line_polarities"][line - 1]
            )
            assert row["source_pdf_page_one_based"] == 7 + 2 * (gate - 1)
            assert row["personal_applicability_assessed"] is False
            assert row["actual_fixing_state"] is row["selected_polarity"] is None
            assert row["complete_line_meaning_accepted"] is False
            assert row["independent_semantic_review_completed"] is False
            if row["editorial_paraphrase"] is not None:
                curated.append(key)
                assert (
                    row["meaning_status"]
                    == "local_editorial_paraphrase_pending_independent_review"
                )
            else:
                assert row["meaning_status"] == "not_yet_curated"
                assert "爻义" in entry["title"] and "待整理" in entry["title"]
    assert len(seen) == len(set(seen)) == 384
    assert len(curated) == 36
    assert curated == [f"{g}.{l}" for g in range(1, 7) for l in range(1, 7)]


@pytest.mark.parametrize(
    "key,expected", [("11.4", ["Moon", "Venus"]), ("25.4", ["Venus", "Jupiter"])]
)
def test_untriggered_additional_source_planets_are_visible_but_not_applied(
    key: str, expected: list[str]
) -> None:
    entry = calculate_knowledge_read(domain="human_design", key=key)
    record = entry["reference_details"]["record"]
    assert record["source_polarity_planets"]["exaltation"] == expected
    assert record["actual_fixing_state"] is None
    assert record["editorial_paraphrase"] is None


def test_gate1_source_ambiguity_and_both_poles_survive_summary() -> None:
    entry = calculate_knowledge_read(domain="human_design", key="1.4")
    row = entry["reference_details"]["record"]
    assert row["source_reading_notes"] and "重复措辞" in entry["rendered_text"]
    assert entry["provenance"]["independent_whole_corpus_review_completed"] is False
    assert "不排除另一极性" in row["selection_policy"]
    assert row["fixing_reading_rule_source"]["author"] == "Lynda Bunnell"


@pytest.mark.parametrize(
    "key",
    [
        None,
        "0.1",
        "65.1",
        "1.0",
        "1.7",
        "01.1",
        "1.01",
        "１.１",
        "6/3",
        "1.1.1",
        "../../1.1",
    ],
)
def test_invalid_keys_do_not_guess_or_use_profile_lines(key: str | None) -> None:
    result = calculate_knowledge_read(domain="human_design", key=key)
    assert result["status_code"] == 400
    assert result["error_code"] == "knowledge.human_design.unknown_key"


def test_unknown_category_and_irrelevant_foreign_query_fields_are_user_errors() -> None:
    result = calculate_knowledge_read(
        domain="human_design", category="lines_v3", key="1.1"
    )
    assert result["status_code"] == 400
    result = calculate_knowledge_read(domain="human_design", key="1.1", object_a="Sun")
    assert result["status_code"] == 400
    assert result["error_code"] == "knowledge.human_design.irrelevant_fields"


@pytest.mark.parametrize("fault", ["delete", "certify", "unknown_to_curated"])
def test_changed_reference_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    value = json.loads(hd.CATALOGUE_PATH.read_bytes())
    if fault == "delete":
        value["rows"].pop()
    elif fault == "certify":
        value["complete384_line_meanings_accepted"] = True
    else:
        value["rows"][6]["editorial_paraphrase"] = deepcopy(
            value["rows"][0]["editorial_paraphrase"]
        )
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(value))
    monkeypatch.setattr(hd, "CATALOGUE_PATH", path)
    with pytest.raises(EphemerisSourceError):
        hd.read_reference(category="lines", key="1.1")
    result = calculate_knowledge_read(domain="human_design", key="1.1")
    assert result["status_code"] == 503 and result["retryable"] is False


def test_returned_mutation_cannot_change_subsequent_source_lookup() -> None:
    first = hd.read_reference(category="lines", key="1.1")
    first["reference_details"]["record"]["editorial_paraphrase"][
        "exaltation"
    ] = "modified"
    assert (
        hd.read_reference(category=None, key="1.1")["reference_details"]["record"][
            "editorial_paraphrase"
        ]["exaltation"]
        != "modified"
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("reference_only", False),
        ("reference_only", 1),
        ("personal_applicability_assessed", True),
        ("personal_applicability_assessed", 0),
    ],
)
def test_public_reference_contract_cannot_become_personal_applicability(
    field: str, value: bool | int
) -> None:
    from pydantic import ValidationError

    details = {
        "policy_id": hd.POLICY_ID,
        "reference_only": True,
        "personal_applicability_assessed": False,
        "record": {},
    }
    details[field] = value
    with pytest.raises(ValidationError):
        HumanDesignKnowledgeDetails.model_validate(details)


def test_consolidated_registry_exposes_single_lines_category() -> None:
    registry = calculate_knowledge_registry(domain="human_design")
    human = registry["domains"][0]
    assert human["source"] == hd.SOURCE
    assert [c["name"] for c in human["categories"]] == ["lines"]
    assert human["categories"][0]["coverage"] == {
        "line_locators": 384,
        "local_editorial_paraphrases": 36,
        "meanings_pending": 348,
        "independently_accepted_line_meanings": 0,
        "full_source_meanings_accepted": False,
    }

"""Complete line keyspace, honest unknowns and immutable editorial provenance."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core import human_design_knowledge as hd
from fatebridge.core import human_design_line_catalogue as catalogue
from fatebridge.core.human_design_depth import depth_reference
from fatebridge.core.output_reference import HumanDesignKnowledgeDetails
from fatebridge.services.knowledge import (
    calculate_knowledge_read,
    calculate_knowledge_registry,
)
from fatebridge.utils.errors import EphemerisSourceError

ROOT = Path(__file__).resolve().parents[2]


def test_all384_keys_retain_source_poles_and_unknown_meanings():
    seen = []
    curated = []
    for gate in range(1, 65):
        for line in range(1, 7):
            key = f"{gate}.{line}"
            entry = hd.read_reference(category="lines", key=key)
            row = entry["reference_details"]["record"]
            seen.append(row["key"])
            assert (
                row["catalogue_glyph_polarity"]
                == depth_reference()["gates"][gate - 1]["line_polarities"][line - 1]
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
    assert curated[:6] == [f"1.{line}" for line in range(1, 7)]
    assert curated[6:] == [f"2.{line}" for line in range(1, 7)]


@pytest.mark.parametrize(
    "key,expected", [("11.4", ["Moon", "Venus"]), ("25.4", ["Venus", "Jupiter"])]
)
def test_untriggered_additional_source_planets_are_visible_but_not_applied(
    key, expected
):
    entry = calculate_knowledge_read(domain="human_design", key=key)
    record = entry["reference_details"]["record"]
    assert record["source_polarity_planets"]["exaltation"] == expected
    assert record["actual_fixing_state"] is None
    assert record["editorial_paraphrase"] is None
    assert "含明文附加星体" in entry["snapshot_text"]


def test_gate1_source_ambiguity_and_both_poles_survive_summary():
    entry = calculate_knowledge_read(domain="human_design", key="1.4")
    row = entry["reference_details"]["record"]
    assert row["source_reading_notes"] and "重复措辞" in entry["snapshot_text"]
    assert "上升极性简述" in entry["snapshot_text"]
    assert "下降极性简述" in entry["snapshot_text"]
    assert "尚待独立复核" in entry["snapshot_text"]
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
def test_invalid_keys_do_not_guess_or_use_profile_lines(key):
    result = calculate_knowledge_read(domain="human_design", key=key)
    assert result["status_code"] == 400
    assert result["error_code"] == "knowledge.human_design.unknown_key"


def test_unknown_category_and_irrelevant_foreign_query_fields_are_user_errors():
    result = calculate_knowledge_read(
        domain="human_design", category="profile", key="1.1"
    )
    assert result["status_code"] == 400
    result = calculate_knowledge_read(domain="human_design", key="1.1", object_a="Sun")
    assert result["status_code"] == 400
    assert result["error_code"] == "knowledge.human_design.irrelevant_fields"


@pytest.mark.parametrize(
    "fault", ["delete", "replace", "certify", "unknown_to_curated"]
)
def test_changed_reference_is_rejected_before_partial_read(
    tmp_path, monkeypatch, fault
):
    value = json.loads(catalogue.CATALOGUE_PATH.read_bytes())
    if fault == "delete":
        value["rows"].pop()
    elif fault == "replace":
        value["rows"][0]["editorial_paraphrase"]["exaltation"] = "guaranteed success"
    elif fault == "certify":
        value["complete384_line_meanings_accepted"] = True
    else:
        value["rows"][6]["editorial_paraphrase"] = deepcopy(
            value["rows"][0]["editorial_paraphrase"]
        )
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(value))
    from fatebridge.core import human_design_line_catalogue

    monkeypatch.setattr(human_design_line_catalogue, "CATALOGUE_PATH", path)
    with pytest.raises(EphemerisSourceError):
        hd.read_reference(category="lines", key="1.1")
    result = calculate_knowledge_read(domain="human_design", key="1.1")
    assert result["status_code"] == 503 and result["retryable"] is False


def test_returned_mutation_cannot_change_subsequent_source_lookup():
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
def test_public_reference_contract_cannot_become_personal_applicability(field, value):
    from pydantic import ValidationError

    details = {
        "policy_id": catalogue.POLICY_ID,
        "reference_only": True,
        "personal_applicability_assessed": False,
        "record": {},
    }
    details[field] = value
    with pytest.raises(ValidationError):
        HumanDesignKnowledgeDetails.model_validate(details)


def test_current_public_registry_preserves_all_explicit_human_design_categories():
    registry = calculate_knowledge_registry(domain="human_design")
    human = registry["domains"][0]
    assert human["source"] == hd.SOURCE
    assert [c["name"] for c in human["categories"]] == [
        "lines",
        "lines_v3",
        "lines_v4",
        "lines_v5",
        "lines_v6",
        "lines_v7",
    ]
    for category, curated in zip(
        human["categories"], [12, 18, 18, 24, 30, 36], strict=True
    ):
        assert category["coverage"] == {
            "line_locators": 384,
            "local_editorial_paraphrases": curated,
            "meanings_pending": 384 - curated,
            "independently_accepted_line_meanings": 0,
            "full_source_meanings_accepted": False,
        }

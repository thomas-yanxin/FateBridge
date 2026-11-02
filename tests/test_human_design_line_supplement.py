"""Additive source binding, retained old rows and explicitly unknown conditions."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core import human_design_knowledge as hd
from fatebridge.core import human_design_line_catalogue as catalogue
from fatebridge.services.knowledge import calculate_knowledge_read
from fatebridge.utils.errors import EphemerisSourceError

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "docs/validation/human-design-line-knowledge-v2"


def test_frozen_v1_and_every_prior_locator_polarity_and_gate1_field_survive():
    before = json.loads((BASE / "evidence/before-384.json").read_bytes())
    assert (
        hashlib.sha256(hd.CATALOGUE_PATH.read_bytes()).hexdigest()
        == hd.CATALOGUE_SHA256
    )
    assert (
        hd.CATALOGUE_PATH.read_bytes()
        == (
            BASE
            / "before-source/src/fatebridge/data/human_design/line-knowledge-v1.json"
        ).read_bytes()
    )
    for old in before:
        key = old["key"]
        prior = old["reference_details"]["record"]
        current = hd.read_reference(category="lines", key=key)["reference_details"][
            "record"
        ]
        for field in [
            "key",
            "gate",
            "line",
            "source_pdf_page_one_based",
            "source_layout_block_sha256",
            "catalogue_glyph_polarity",
            "source_polarity_planets",
            "additional_polarity_facts",
        ]:
            assert current[field] == prior[field], (key, field)
        if not key.startswith("2."):
            for field, value in prior.items():
                assert current[field] == value, (key, field)


def test_gate2_condition_stays_reference_only_and_is_not_a_material_forecast():
    result = calculate_knowledge_read(domain="human_design", key="2.3")
    row = result["reference_details"]["record"]
    (condition,) = row["source_conditions"]
    assert condition["source_condition"] == {
        "relation": "permanent_channel_connection",
        "channel_gates": [2, 14],
    }
    assert condition["polarity"] == "exaltation"
    assert (
        condition["source_clause_sha256"]
        == "8e412f58a60749b2a85a3a77720181610af084d0038564de3afa7d0776823d3a"
    )
    assert condition["personal_condition_satisfied"] is None
    assert condition["automatic_application"] is False
    assert condition["evidence_required"] == [
        "same_run_actual_2_3_activation_and_fixing_state",
        "same_run_permanent_2_14_channel_evidence",
    ]
    assert (
        row["condition_review_status"]
        == "one_explicit_clause_locally_recorded_not_exhaustive"
    )
    assert row["actual_fixing_state"] is row["selected_polarity"] is None
    assert "永久" in result["snapshot_text"] and "不自动应用" in result["snapshot_text"]
    assert "逆命题" in result["snapshot_text"]
    assert result["provenance"]["real_world_efficacy_validated"] is False


def test_unknown_conditions_are_not_an_empty_fully_reviewed_set():
    for key in ["1.1", "2.1", "2.6", "11.4", "64.6"]:
        result = hd.read_reference(category="lines", key=key)
        row = result["reference_details"]["record"]
        assert row["source_conditions"] is None
        assert row["condition_review_status"] == "not_assessed"
        assert "未记录不表示无条件" in result["provenance"]["scope"]


def test_exaltation_does_not_turn_narrow_receptivity_into_a_positive_trait():
    result = hd.read_reference(category="lines", key="2.6")
    row = result["reference_details"]["record"]
    assert "狭窄" in row["editorial_paraphrase"]["exaltation"]
    assert "上升一概改写为正面能力" in result["rendered_text"]
    assert row["complete_line_meaning_accepted"] is False


@pytest.mark.parametrize("component", ["MANIFEST_PATH", "SUPPLEMENT_PATH"])
def test_missing_or_changed_composite_component_never_falls_back(
    tmp_path, monkeypatch, component
):
    path = tmp_path / "missing.json"
    monkeypatch.setattr(catalogue, component, path)
    with pytest.raises(EphemerisSourceError):
        hd.read_reference(category="lines", key="1.1")
    path.write_text("{}")
    result = calculate_knowledge_read(domain="human_design", key="1.1")
    assert result["status_code"] == 503 and result["retryable"] is False


@pytest.mark.parametrize(
    "fault",
    [
        "certify",
        "overwrite_gate1",
        "apply_condition",
        "erase_condition",
        "locator",
        "coverage",
        "manifest_certify",
        "path",
    ],
)
def test_semantic_invariants_survive_even_a_rebound_component_hash(
    tmp_path, monkeypatch, fault
):
    manifest = json.loads(hd.MANIFEST_PATH.read_bytes())
    supplement = json.loads(hd.SUPPLEMENT_PATH.read_bytes())
    if fault == "certify":
        supplement["rows"][0]["independent_semantic_review_completed"] = True
    elif fault == "overwrite_gate1":
        supplement["rows"][0]["key"] = "1.1"
        manifest["supplements"][0]["keys"][0] = "1.1"
    elif fault == "apply_condition":
        supplement["rows"][2]["source_conditions"][0][
            "personal_condition_satisfied"
        ] = True
    elif fault == "erase_condition":
        del supplement["rows"][2]["source_conditions"]
    elif fault == "locator":
        supplement["rows"][0]["source_layout_block_sha256"] = "0" * 64
    elif fault == "coverage":
        manifest["expected_local_paraphrase_count"] = 384
    elif fault == "manifest_certify":
        manifest["complete384_line_meanings_accepted"] = True
    else:
        manifest["supplements"][0]["file"] = "../line-knowledge-gate2-v1.json"
    raw = json.dumps(supplement).encode()
    supplement_path = tmp_path / "supplement.json"
    supplement_path.write_bytes(raw)
    manifest["supplements"][0]["sha256"] = hashlib.sha256(raw).hexdigest()
    raw = json.dumps(manifest).encode()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_bytes(raw)
    monkeypatch.setattr(catalogue, "SUPPLEMENT_PATH", supplement_path)
    monkeypatch.setattr(catalogue, "MANIFEST_PATH", manifest_path)
    monkeypatch.setattr(catalogue, "MANIFEST_SHA256", hashlib.sha256(raw).hexdigest())
    with pytest.raises(EphemerisSourceError):
        hd.build_registry()


@pytest.mark.parametrize(
    "component", ["CATALOGUE_PATH", "MANIFEST_PATH", "SUPPLEMENT_PATH"]
)
@pytest.mark.parametrize("operation", ["read", "registry"])
def test_every_loaded_component_is_rechecked_after_response_construction(
    tmp_path, monkeypatch, component, operation
):
    path = tmp_path / getattr(hd, component).name
    path.write_bytes(getattr(hd, component).read_bytes())
    monkeypatch.setattr(catalogue, component, path)
    original = hd._provenance

    def change_after_load(data, snapshot):
        result = original(data, snapshot)
        path.write_bytes(path.read_bytes() + b" ")
        return result

    monkeypatch.setattr(
        hd if operation == "registry" else catalogue, "_provenance", change_after_load
    )
    with pytest.raises(EphemerisSourceError, match="changed after loading"):
        if operation == "registry":
            hd.build_registry()
        else:
            hd.read_reference(category="lines", key="2.3")


def test_returned_condition_mutation_does_not_change_next_read():
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

"""Gate6 drafts retain source roles, original calculations and earlier editions."""

import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest

from fatebridge.core import human_design_knowledge as base
from fatebridge.core import human_design_knowledge_v7 as hd
from fatebridge.core.human_design_mechanics import CHANNELS, GATE_CENTER
from fatebridge.core.human_design_source_context import bind_source_context
from fatebridge.services.human_design_context_lines import (
    build_human_design_context_packet,
)
from fatebridge.utils.errors import EphemerisSourceError
from fatebridge.validation.human_design_context_lines import (
    verify_human_design_context_packet,
)
from tests.reference_data import read, sha
from tests.test_agentic_nested_outputs import SPECS, business
from tests.test_agentic_nested_outputs import rest as shared_rest
from tests.test_heluo_poem_transports import run_three

ROOT = Path(__file__).resolve().parents[1]
E = ROOT / "tests/data/human_design/gate6"
rest = shared_rest
LOCATOR_SHA = "f49c6a9ea3b8e394615c44babe50a06ff3c38367d3c22cf6f8829af4650a0b46"


def test_all384_references_preserve_inherited_poles_annotations_and_other_meanings():
    for gate in range(1, 65):
        for line in range(1, 7):
            key = f"{gate}.{line}"
            old = base.read_reference(category="lines_v6", key=key)[
                "reference_details"
            ]["record"]
            new = hd.read_reference(key=key)["reference_details"]["record"]
            for name in (
                "source_polarity_planets",
                "source_available_polarities",
                "source_context_annotations",
            ):
                assert new[name] == old[name]
            assert new["actual_fixing_state"] is new["selected_polarity"] is None
            if gate != 6:
                assert new == old


@pytest.mark.parametrize(
    "line,up,down",
    [
        (1, "Pluto", "Mercury"),
        (2, "Venus", "Mars"),
        (3, "Neptune", "Pluto"),
        (4, "Sun", "Pluto"),
        (5, "Venus", "Moon"),
        (6, "Mercury", "Venus"),
    ],
)
def test_six_lines_match_frozen_independent_locators_and_do_not_decide_applicability(
    line, up, down
):
    path = E / "gate6-independent-source-locators.json"
    assert sha(path) == LOCATOR_SHA
    fact = read(path)["rows"][line - 1]
    record = hd.read_reference(key=f"6.{line}")["reference_details"]["record"]
    assert (
        record["source_pdf_page_one_based"] == fact["source_pdf_page_one_based"] == 17
    )
    for name in ("source_layout_block_sha256", "source_line_heading"):
        assert record[name] == fact[name]
    assert fact["visually_observed_exaltation_planet"] == up
    assert fact["visually_observed_detriment_planet"] == down
    assert record["source_polarity_planets"] == {
        "exaltation": [up],
        "detriment": [down],
    }
    assert record["source_available_polarities"] == ["exaltation", "detriment"]
    assert record["source_conditions"] is None
    assert record["source_qualifiers"][0]["personal_condition_satisfied"] is None
    assert record["complete_line_meaning_accepted"] is False
    if line == 3:
        annotation = record["source_context_annotations"][0]
        assert annotation["source_role"] == "line_intro"
        assert annotation["scope"] == "named_clause_only_not_whole_line_or_pole"
        assert annotation["source_interpretation_resolved"] is False
    if line == 5:
        assert any("内在权威" in n for n in record["source_reading_notes"])


@pytest.mark.parametrize(
    "key", ["6.1", "6.2", "6.3", "6.4", "6.5", "6.6", "5.6", "2.3"]
)
def test_actual_rest_mcp_cli_keep_complete_bound_reference_values(
    key, rest, tmp_path, capsys
):
    response, code, cli, mcp = run_three(
        SPECS["knowledge_read"],
        {"domain": "human_design", "category": "lines_v7", "key": key},
        ["category", "key", "reference_details", "provenance", "snapshot_text"],
        rest,
        tmp_path,
        capsys,
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    assert (
        business(response.json()) == business(cli) == business(mcp.structured_content)
    )
    assert cli["provenance"]["source_catalogue_version"] == 7
    if key == "5.6":
        assert (
            cli["reference_details"]["record"]["editorial_paraphrase"]["detriment"]
            is None
        )


@pytest.mark.parametrize(
    "fault",
    [
        "inherited_override",
        "extra_qualifier",
        "personal_true",
        "mechanical_predicate",
        "claimed_acceptance",
        "changed_glyph",
        "notes_wrong_type",
        "empty_note",
        "resolved_note",
    ],
)
def test_deliberately_rehashed_invalid_supplement_cannot_override_inherited_clauses(
    fault, tmp_path, monkeypatch
):
    data = json.loads(hd.CATALOGUE_PATH.read_text())
    row = data["rows"][2]
    if fault == "inherited_override":
        ann = deepcopy(
            hd.read_reference(key="6.3")["reference_details"]["record"][
                "source_context_annotations"
            ]
        )
        ann[0]["source_role"] = "exaltation"
        row["source_context_annotations"] = ann
    elif fault == "extra_qualifier":
        row["source_qualifiers"][0]["biological_effect_assessed"] = True
    elif fault == "personal_true":
        row["source_qualifiers"][0]["personal_condition_satisfied"] = True
    elif fault == "mechanical_predicate":
        row["source_qualifiers"][0]["mechanical_predicate"] = "channel_6_59"
    elif fault == "claimed_acceptance":
        row["complete_line_meaning_accepted"] = True
    elif fault == "changed_glyph":
        row["source_polarity_planets"]["exaltation"] = ["Jupiter"]
    elif fault == "notes_wrong_type":
        row["source_reading_notes"] = {"biological_effect_assessed": True}
    elif fault == "empty_note":
        row["source_reading_notes"] = [""]
    else:
        row["source_polarity_text_note"] = {"independently_resolved": True}
    path = tmp_path / "repinned-test-draft.json"
    path.write_text(json.dumps(data))
    monkeypatch.setattr(hd, "CATALOGUE_PATH", path)
    monkeypatch.setattr(hd, "CATALOGUE_SHA256", sha(path))
    with pytest.raises(EphemerisSourceError):
        hd.read_reference(key="6.3")


@pytest.fixture(scope="module")
def packet63():
    from tests.human_design_current import semantic_sources

    source = semantic_sources("gate6")["gate6"]
    with patch(
        "fatebridge.core.astro.runtime.ephemeris_call",
        side_effect=AssertionError("native sky forbidden during assembly"),
    ):
        packet = build_human_design_context_packet(
            source, reference_category="lines_v7"
        )
    return source, packet


def rows63(packet):
    return [
        r
        for g in packet["line_reading_groups"].values()
        for r in g["rows"]
        if r["reference_key"] == "6.3"
    ]


def test_actual63_interpretation_binds_intro_observation_without_biological_conclusion(
    packet63,
):
    source, packet = packet63
    assert packet["packet_version"] == 7
    assert (
        verify_human_design_context_packet(
            packet, source, reference_category="lines_v7"
        )["status"]
        == "verified_original_bound_context_line_packet"
    )
    rows = rows63(packet)
    assert rows
    for row in rows:
        for bound in row["bound_source_context_annotations"]:
            assert bound["source_annotation"]["source_role"] == "line_intro"
            assert bound["fixing_emphasizes_clause_polarity"] is None
            assert bound["biological_effect_assessed"] is False
            assert bound["source_applicability_satisfied"] is None
            assert bound["actual_fixing_state"] == row["actual_fixing_state"]
    assert packet["nominal_packet_v1"]["original_result"] == source


@pytest.mark.parametrize(
    "fault",
    ["role", "biology", "outcome", "drop_annotation", "condition", "wrong_version"],
)
def test_complete_context_replay_rejects_role_outcome_and_version_forgery(
    packet63, fault
):
    source, original = packet63
    packet = deepcopy(original)
    row = rows63(packet)[0]
    bound = row["bound_source_context_annotations"][0]
    if fault == "role":
        bound["source_annotation"]["source_role"] = "exaltation"
    elif fault == "biology":
        bound["biological_effect_assessed"] = True
    elif fault == "outcome":
        bound["outcome_guaranteed"] = True
    elif fault == "drop_annotation":
        row["bound_source_context_annotations"] = []
    elif fault == "condition":
        bound["source_applicability_satisfied"] = True
    else:
        packet["reference_category"] = "lines_v6"
    assert (
        verify_human_design_context_packet(
            packet, source, reference_category="lines_v7"
        )["status"]
        == "rejected"
    )


@pytest.mark.parametrize("connected", [True, False])
@pytest.mark.parametrize(
    "state", ["unfixed", "exaltation", "detriment", "juxtaposition"]
)
def test_synthetic_graph_controls_keep_intro_separate_from_fixing_and_world_outcomes(
    connected, state
):
    # Pure graph controls are not astronomical cases or predictive samples.
    gates = [6, 59] if connected else [6, 1]
    acts = [{"body": str(i), "gate": gates[i % 2], "line": 3} for i in range(13)]
    active = set(gates)
    channels = [
        {"gates": [a, b], "centers": [GATE_CENTER[a], GATE_CENTER[b]]}
        for a, b, _ in CHANNELS
        if {a, b} <= active
    ]
    chart = {
        "activations": {"personality": acts, "design": deepcopy(acts)},
        "bodygraph": {"channels": channels},
    }
    ann = hd.read_reference(key="6.3")["reference_details"]["record"][
        "source_context_annotations"
    ][0]
    bound = bind_source_context(
        ann, chart, {"gate": 6, "line": 3, "fixing_state": state}
    )
    assert bound["observations"][0]["observed_in_this_chart"] is connected
    assert bound["source_annotation"]["source_role"] == "line_intro"
    assert bound["fixing_emphasizes_clause_polarity"] is None
    assert bound["biological_effect_assessed"] is bound["outcome_guaranteed"] is False
    assert bound["source_applicability_satisfied"] is None
    assert bound["actual_fixing_state"] == state

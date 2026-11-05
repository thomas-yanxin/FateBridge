"""Clause role, graph alternatives, immutable old outputs and adapter rejection."""

import gzip
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

import fatebridge.application.execution as execution
from fatebridge.core import human_design_knowledge as base
from fatebridge.core import human_design_knowledge_v4 as hd
from fatebridge.core.human_design import bodygraph
from fatebridge.core.human_design_source_context import bind_source_context
from fatebridge.services.knowledge import calculate_knowledge_read
from fatebridge.utils.errors import EphemerisSourceError
from tests.evaluation.test_agentic_nested_outputs import SPECS, business
from tests.evaluation.test_agentic_nested_outputs import rest as shared_rest
from tests.numerology.test_heluo_poem_transports import run_three

ROOT = Path(__file__).resolve().parents[2]
rest = shared_rest


def read(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def annotation(key):
    return hd.read_reference(key=key)["reference_details"]["record"][
        "source_context_annotations"
    ][0]


def chart(personality, design):
    return {
        "activations": {
            s: [
                {"body": "Sun" if i == 0 else "Moon", "gate": g, "line": 1}
                for i, g in enumerate(gs)
            ]
            for s, gs in (("personality", personality), ("design", design))
        },
        "bodygraph": bodygraph(personality, design),
    }


def fixing(key, state="unfixed"):
    gate, line = map(int, key.split("."))
    return {"gate": gate, "line": line, "fixing_state": state}


def test_all_384_v4_rows_preserve_v3_meanings_and_honest_coverage():
    registry = base.build_registry()["domains"][0]["categories"]
    assert registry[2]["coverage"] == registry[1]["coverage"]
    assert registry[2]["coverage"]["local_editorial_paraphrases"] == 18
    assert registry[2]["coverage"]["independently_accepted_line_meanings"] == 0
    selected = []
    for gate in range(1, 65):
        for line in range(1, 7):
            key = f"{gate}.{line}"
            record = hd.read_reference(key=key)["reference_details"]["record"]
            parent = base.read_reference(category="lines_v3", key=key)[
                "reference_details"
            ]["record"]
            extra = record.pop("source_context_annotations")
            assert record == parent
            if extra:
                selected.append(key)
                assert len(extra) == 1
                assert extra[0]["personal_condition_satisfied"] is None
                assert extra[0]["source_interpretation_resolved"] is False
    assert selected == ["2.3", "6.3", "7.2", "12.6", "42.1"]


@pytest.mark.parametrize(
    "key,gates,role,permanent",
    [
        ("2.3", [2, 14], "exaltation", True),
        ("6.3", [6, 59], "line_intro", False),
        ("7.2", [7, 31], "exaltation", False),
        ("12.6", [12, 22], "exaltation", False),
    ],
)
@pytest.mark.parametrize("split", ["personality", "design", "mixed", "absent"])
def test_literal_named_channels_roles_and_absence_are_separate_from_fixing(
    key, gates, role, permanent, split
):
    a, b = gates
    p, d = {
        "personality": ([a, b], []),
        "design": ([], [a, b]),
        "mixed": ([a], [b]),
        "absent": ([a], []),
    }[split]
    ann = annotation(key)
    result = bind_source_context(ann, chart(p, d), fixing(key, "detriment"))
    assert ann["source_role"] == role
    assert ann["source_explicitly_says_permanent"] is permanent
    observed = result["observations"][0]
    assert observed["observed_in_this_chart"] is (split != "absent")
    assert {a["gate"] for a in observed["gate_activation_witnesses"]} == set(p + d)
    assert result["actual_fixing_state"] == "detriment"
    assert result["fixing_emphasizes_clause_polarity"] is (
        None if role == "line_intro" else False
    )
    assert result["source_applicability_satisfied"] is None
    assert result["outcome_guaranteed"] is result["converse_inferred"] is False
    assert result["biological_effect_assessed"] is False


@pytest.mark.parametrize(
    "gates,direct,connected",
    [
        ([42, 53], True, True),
        ([42, 3, 60], False, True),
        ([42, 5, 15, 18, 58], False, False),
        ([42], False, False),
        # Indirect multi-edge Sacral-G-Ego-Root path, with no 42-53 channel.
        ([42, 5, 15, 25, 51, 19, 49, 37, 40], False, True),
    ],
)
def test_root_models_remain_distinct_and_particular_is_not_necessary(
    gates, direct, connected
):
    ann = annotation("42.1")
    result = bind_source_context(ann, chart(gates, []), fixing("42.1", "exaltation"))
    assert ann["source_force"] == "particular_emphasis_not_necessity"
    assert [o["observed_in_this_chart"] for o in result["observations"]] == [
        direct,
        connected,
    ]
    assert (
        result["selected_source_interpretation"]
        is result["source_applicability_satisfied"]
        is None
    )
    assert "surplus_resources_not_assessed" in ann["unassessed_qualifiers"]
    assert result["world_qualifiers_assessed"] is False
    assert result["fixing_emphasizes_clause_polarity"] is True
    if gates == [42, 5, 15, 18, 58]:
        assert chart(gates, [])["bodygraph"]["centers"]["root"]["status"] == "defined"
        assert result["observations"][1]["channel_witnesses"] == []


@pytest.mark.parametrize("fault", ["drop", "extra", "wrong_center", "wrong_key"])
def test_contradictory_structural_witnesses_fail(fault):
    value = chart([7], [31])
    fixed = fixing("7.2")
    if fault == "drop":
        value["bodygraph"]["channels"] = []
    if fault == "extra":
        value["bodygraph"]["channels"].append(
            deepcopy(value["bodygraph"]["channels"][0])
        )
    if fault == "wrong_center":
        value["bodygraph"]["channels"][0]["centers"][0] = "root"
    if fault == "wrong_key":
        fixed["line"] = 3
    with pytest.raises(ValueError):
        bind_source_context(annotation("7.2"), value, fixed)


@pytest.mark.parametrize("key", ["2.3", "6.3", "7.2", "12.6", "42.1", "3.4", "64.6"])
def test_actual_reference_content_on_three_adapters(key, rest, tmp_path, capsys):
    response, code, cli, mcp = run_three(
        SPECS["knowledge_read"],
        {"domain": "human_design", "category": "lines_v4", "key": key},
        ["category", "key", "reference_details", "provenance", "snapshot_text"],
        rest,
        tmp_path,
        capsys,
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    assert (
        business(response.json()) == business(cli) == business(mcp.structured_content)
    )
    assert cli["provenance"]["source_catalogue_version"] == 4
    assert cli["reference_details"]["record"]["actual_fixing_state"] is None


@pytest.mark.parametrize(
    "fault",
    [
        "version",
        "personal_true",
        "choose_root",
        "drop_intro",
        "new_meaning",
        "drop_qualifier",
    ],
)
def test_adapters_reject_forged_annotations_even_if_projecting_unrelated_field(
    fault, monkeypatch, rest, tmp_path, capsys
):
    key = "6.3" if fault == "drop_intro" else "42.1"
    result = calculate_knowledge_read(
        domain="human_design", category="lines_v4", key=key
    )
    record = result["reference_details"]["record"]
    ann = record["source_context_annotations"][0]
    if fault == "version":
        result["category"] = "lines_v3"
    if fault == "personal_true":
        ann["personal_condition_satisfied"] = True
    if fault == "choose_root":
        ann["selected_source_interpretation"] = "direct_named_channel"
    if fault == "drop_intro":
        ann["source_role"] = "exaltation"
    if fault == "new_meaning":
        record["complete_line_meaning_accepted"] = True
    if fault == "drop_qualifier":
        ann["unassessed_qualifiers"] = []
    execute = execution.execute_spec

    def forged(spec, request):
        if spec.key == "knowledge_read":
            spec = replace(spec, bind=lambda _: (lambda: deepcopy(result), (), {}))
        return execute(spec, request)

    monkeypatch.setattr(execution, "execute_spec", forged)
    response, code, _, mcp = run_three(
        SPECS["knowledge_read"],
        {"domain": "human_design", "category": "lines_v4", "key": key},
        ["source"],
        rest,
        tmp_path,
        capsys,
    )
    assert response.status_code == 503 and code != 0 and mcp.is_error


@pytest.mark.parametrize("mode", ["read", "registry"])
def test_context_bytes_changed_after_load_are_rejected(mode, monkeypatch, tmp_path):
    path = tmp_path / hd.CATALOGUE_PATH.name
    path.write_bytes(hd.CATALOGUE_PATH.read_bytes())
    monkeypatch.setattr(hd, "CATALOGUE_PATH", path)
    method = "_catalogue" if mode == "read" else "_registry_category"
    original = getattr(hd, method)

    def changed():
        result = original()
        path.write_bytes(path.read_bytes() + b" ")
        return result

    monkeypatch.setattr(hd, method, changed)
    with pytest.raises(EphemerisSourceError) as caught:
        (hd.read_reference(key="7.2") if mode == "read" else base.build_registry())
    assert caught.value.reason == "human_design_reference_changed"


def test_source_replaced_before_lookup_is_invalid(monkeypatch, tmp_path):
    path = tmp_path / hd.CATALOGUE_PATH.name
    path.write_bytes(hd.CATALOGUE_PATH.read_bytes() + b" ")
    monkeypatch.setattr(hd, "CATALOGUE_PATH", path)
    with pytest.raises(EphemerisSourceError) as caught:
        hd.read_reference(key="7.2")
    assert caught.value.reason == "human_design_reference_invalid"

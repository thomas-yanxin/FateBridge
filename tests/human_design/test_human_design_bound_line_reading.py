"""Full original binding, all nominal activations and honest semantic gaps."""

import gzip
import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core import human_design_knowledge as knowledge
from fatebridge.core.human_design_line_catalogue import _canonical
from fatebridge.core.human_design_line_reading import _condition
from fatebridge.core.human_design_mechanics import CHANNELS
from fatebridge.services.human_design_line_reading import (
    LineReadingInputError,
    build_human_design_line_packet,
)
from fatebridge.validation.human_design_line_reading import (
    verify_human_design_line_packet,
)

ROOT = Path(__file__).resolve().parents[2]
# Reading contract: the teaching describes emphasis, not exclusive access.
# These expectations are independent of the implementation's lookup table.
EXPECTED_EMPHASIS = {
    "exaltation": ["exaltation"],
    "detriment": ["detriment"],
    "juxtaposition": ["exaltation", "detriment"],
    "unfixed": [],
    "not_applicable_no_planet_polarity": [],
}


@pytest.fixture(scope="module")
def cases():
    from tests.support.human_design_current import semantic_sources

    return semantic_sources("bound")


@pytest.fixture(scope="module")
def packets(cases):
    return {key: build_human_design_line_packet(value) for key, value in cases.items()}


def test_every_original_activation_and_all_unknown_meanings_survive(cases, packets):
    for key, packet in packets.items():
        source = cases[key]
        assert packet["original_result"] == source
        assert packet["source_identity"]["run_id"] == source["run_metadata"]["run_id"]
        reading = packet["line_reading"]
        assert reading["activation_scope"] == "selected_nominal_personality_and_design"
        assert reading["other_context_line_meanings"] == {
            "alternative_node_or_backend_charts": "not_assembled",
            "birth_time_interval_samples": "not_assembled",
            "cycle_contacts": "not_assembled",
        }
        expected_paths = [
            f"activations.{s}.{i}" for s in ("personality", "design") for i in range(13)
        ]
        assert [r["activation_path"] for r in reading["rows"]] == expected_paths
        assert len(reading["rows"]) == 26
        assert reading["coverage"]["independently_accepted_full_line_meanings"] == 0
        assert reading["coverage"]["source_conditions_exhaustively_reviewed"] is False
        pending = 0
        for i, row in enumerate(reading["rows"]):
            fixing = source["depth_evidence"]["line_fixings"][i]
            assert (row["side"], row["body"], row["gate"], row["line"]) == tuple(
                fixing[k] for k in ("side", "body", "gate", "line")
            )
            assert row["fixing_planets"] == fixing["fixing_planets"]
            assert row["actual_fixing_state"] == fixing["fixing_state"]
            assert (
                row["emphasized_polarities"]
                == EXPECTED_EMPHASIS[fixing["fixing_state"]]
            )
            ref = reading["source_references"][row["reference_key"]][
                "reference_details"
            ]["record"]
            assert ref["actual_fixing_state"] is ref["selected_polarity"] is None
            assert row["editorial_paraphrase"] == ref["editorial_paraphrase"]
            assert row["source_polarity_planets"] == ref["source_polarity_planets"]
            if row["editorial_paraphrase"] is None:
                pending += 1
                assert "尚未整理" in row["reading"]
            else:
                assert "上升为" in row["reading"] and "下降为" in row["reading"]
            assert row["complete_line_meaning_accepted"] is False
            if ref.get("source_conditions") is None:
                assert row["bound_source_conditions"] is None
                assert row["condition_review_status"] == "not_assessed"
        assert pending == reading["coverage"]["activations_without_curated_meaning"]
        assert (
            packet["complete384_line_semantics_accepted"]
            is packet["arbitrary_model_free_text_accepted"]
            is False
        )


@pytest.mark.parametrize(
    "key,state,truth",
    [
        ("may6_2030_synthetic", "exaltation", True),
        ("may6_2023_synthetic", "detriment", True),
        ("j2000_control_synthetic", "unfixed", False),
        ("may6_1988_early_synthetic", "exaltation", False),
    ],
)
def test_named_condition_and_actual_fixing_are_independent_facts(
    packets, key, state, truth
):
    rows = [
        r for r in packets[key]["line_reading"]["rows"] if r["reference_key"] == "2.3"
    ]
    assert rows
    for row in rows:
        assert row["actual_fixing_state"] == state
        (condition,) = row["bound_source_conditions"]
        assert condition["calculation_condition_satisfied"] is truth
        assert condition["fixing_emphasizes_clause_polarity"] is (state == "exaltation")
        assert bool(condition["channel_witnesses"]) is truth
        assert condition["source_condition"]["personal_condition_satisfied"] is None
        assert condition["scope_is_named_clause_only"] is True
        assert condition["source_condition_semantics_independently_accepted"] is False
        assert (
            condition["converse_inferred"] is condition["outcome_guaranteed"] is False
        )
        assert "原文上升段限定句" in row["reading"]
        assert "条件判定不改变实际固定状态" in row["reading"]
        if not truth:
            assert "也不反推没有回报" in row["reading"]


def test_gate1_ambiguity_and_whole_chart_context_are_not_lost(packets, cases):
    packet = packets["may6_1988_synthetic"]
    row = next(r for r in packet["line_reading"]["rows"] if r["reference_key"] == "1.4")
    assert row["source_reading_notes"] and "重复措辞" in row["reading"]
    context = packet["line_reading"]["whole_chart_context"]
    assert context["profile"] == cases["may6_1988_synthetic"]["profile"]
    assert (
        context["incarnation_cross"]
        == cases["may6_1988_synthetic"]["incarnation_cross"]
    )
    assert (
        context["authority"] == cases["may6_1988_synthetic"]["bodygraph"]["authority"]
    )


@pytest.mark.parametrize("a,b,_circuit", CHANNELS)
def test_channel_predicate_supports_every_declared_pair_as_mechanical_probe(
    a, b, _circuit
):
    source = {
        "polarity": "exaltation",
        "source_condition": {
            "relation": "permanent_channel_connection",
            "channel_gates": [a, b],
        },
    }
    chart = {
        "bodygraph": {"channels": [{"id": f"{a}-{b}", "gates": [a, b]}]},
        "activations": {
            "personality": [{"body": "Sun", "gate": a, "line": 1}],
            "design": [{"body": "Moon", "gate": b, "line": 6}],
        },
    }
    result = _condition(source, chart, {"fixing_state": "unfixed"})
    assert result["calculation_condition_satisfied"] is True
    assert result["fixing_emphasizes_clause_polarity"] is False
    assert len(result["gate_activation_witnesses"]) == 2
    chart["bodygraph"]["channels"] = []
    with pytest.raises(ValueError):
        _condition(source, chart, {"fixing_state": "unfixed"})
    chart["activations"]["design"] = []
    assert (
        _condition(source, chart, {"fixing_state": "exaltation"})[
            "calculation_condition_satisfied"
        ]
        is False
    )


@pytest.mark.parametrize(
    "descriptor",
    [
        None,
        {},
        {"relation": "weather", "channel_gates": [2, 14]},
        {"relation": "permanent_channel_connection", "channel_gates": [True, 14]},
        {"relation": "permanent_channel_connection", "channel_gates": [2, 3]},
    ],
)
def test_unknown_or_invalid_source_conditions_remain_unknown(descriptor):
    value = _condition(
        {"polarity": "exaltation", "source_condition": descriptor},
        {},
        {"fixing_state": "exaltation"},
    )
    assert value["calculation_condition_satisfied"] is None
    assert value["evaluation_status"] == "unsupported_condition_rule"
    assert value["outcome_guaranteed"] is False


@pytest.mark.parametrize(
    "fault",
    [
        "delete_row",
        "wrong_key",
        "wrong_fixing",
        "drop_pole",
        "erase_condition",
        "claim_condition",
        "claim_review",
        "invent_text",
        "extra_field",
        "donor_path",
        "hide_unknown",
        "context",
    ],
)
def test_every_forged_packet_field_is_rejected_even_with_extra_rehash_claims(
    cases, packets, fault
):
    key = "may6_1988_early_synthetic"
    packet = deepcopy(packets[key])
    reading = packet["line_reading"]
    target = next(r for r in reading["rows"] if r["reference_key"] == "2.3")
    if fault == "delete_row":
        reading["rows"].pop()
    elif fault == "wrong_key":
        target["reference_key"] = "1.1"
    elif fault == "wrong_fixing":
        target["actual_fixing_state"] = "detriment"
    elif fault == "drop_pole":
        target["editorial_paraphrase"]["detriment"] = None
    elif fault == "erase_condition":
        target["bound_source_conditions"] = []
    elif fault == "claim_condition":
        target["bound_source_conditions"][0]["calculation_condition_satisfied"] = True
    elif fault == "claim_review":
        packet["complete384_line_semantics_accepted"] = True
    elif fault == "invent_text":
        target["reading"] += "This guarantees wealth."
    elif fault == "extra_field":
        packet["model_advice"] = "guaranteed"
    elif fault == "donor_path":
        target["fixing_planets"]["exaltation"][0][
            "calculation_path"
        ] = "activations.design.12"
    elif fault == "hide_unknown":
        reading["rows"] = [
            r for r in reading["rows"] if r["editorial_paraphrase"] is not None
        ]
    else:
        reading["whole_chart_context"]["authority"] = "invented"
    # Keep the separately bound source digest correct. A reading fault must be
    # rejected for its own field, not masked by an intentionally invalid hash.
    packet["source_identity"]["original_result_sha256"] = hashlib.sha256(
        _canonical(packet["original_result"])
    ).hexdigest()
    assert packet["source_identity"] == packets[key]["source_identity"]
    check = verify_human_design_line_packet(packet, cases[key])
    assert check["status"] == "rejected" and check["errors"]
    expected_path = (
        "model_advice"
        if fault == "extra_field"
        else (
            "complete384_line_semantics_accepted"
            if fault == "claim_review"
            else "line_reading"
        )
    )
    assert any(e.get("path") == expected_path for e in check["errors"])


def test_a_whole_other_valid_run_cannot_replace_the_trusted_original(cases, packets):
    good = verify_human_design_line_packet(
        packets["may6_2030_synthetic"], cases["may6_2030_synthetic"]
    )
    assert good["status"] == "verified_original_bound_line_reference_packet"
    wrong = verify_human_design_line_packet(
        packets["may6_2023_synthetic"], cases["may6_2030_synthetic"]
    )
    assert (
        wrong["status"] == "rejected" and not wrong["trusted_original_binding_matches"]
    )
    assert any(e["code"] == "external_original_run_mismatch" for e in wrong["errors"])


@pytest.mark.parametrize("fault", ["partial", "changed_activation", "fake_fixing"])
def test_unverified_original_cannot_be_used_even_after_rehash(cases, fault):
    value = deepcopy(cases["may6_2030_synthetic"])
    if fault == "partial":
        value = {"activations": value["activations"], "bodygraph": value["bodygraph"]}
    elif fault == "changed_activation":
        value["activations"]["personality"][0]["line"] = 6
    else:
        value["depth_evidence"]["line_fixings"][0]["fixing_state"] = "unfixed"
    with pytest.raises(LineReadingInputError):
        build_human_design_line_packet(value)


def test_no_native_recomputation_and_no_mutation_of_the_callers_run(cases, monkeypatch):
    from fatebridge.core.astro import runtime
    from fatebridge.services import human_design_line_reading as service

    value = deepcopy(cases["may6_2030_synthetic"])
    original = deepcopy(value)

    def forbidden(*args, **kwargs):
        raise AssertionError("Line packet recalculated a native position")

    monkeypatch.setattr(runtime, "ephemeris_call", forbidden)
    packet = build_human_design_line_packet(value)
    assert value == original
    assert (
        verify_human_design_line_packet(packet, value)["status"]
        == "verified_original_bound_line_reference_packet"
    )
    read = knowledge.read_reference

    def mutate_caller_after_snapshot(*args, **kwargs):
        value["profile"] = "changed-by-caller"
        return read(*args, **kwargs)

    monkeypatch.setattr(
        service.knowledge, "read_reference", mutate_caller_after_snapshot
    )
    assert build_human_design_line_packet(value)["original_result"] == original


def test_actual_module_cli_matches_library_and_requires_external_source(
    cases, packets, tmp_path
):
    key = "may6_2030_synthetic"
    source = tmp_path / "source.json.gz"
    source.write_bytes(gzip.compress(json.dumps(cases[key]).encode()))
    wrong_source = tmp_path / "wrong-source.json.gz"
    wrong_source.write_bytes(
        gzip.compress(json.dumps(cases["may6_2023_synthetic"]).encode())
    )
    packet_path = tmp_path / "packet.json.gz"
    command = [
        sys.executable,
        "-m",
        "fatebridge.validation.human_design_line_packet_cli",
    ]
    result = subprocess.run(
        [*command, "build", str(source), "--output", str(packet_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(gzip.decompress(packet_path.read_bytes())) == packets[key]
    result = subprocess.run(
        [*command, "verify", str(source), str(packet_path)],
        capture_output=True,
        text=True,
    )
    assert (
        result.returncode == 0
        and json.loads(result.stdout)["checked_activation_count"] == 26
    )
    result = subprocess.run(
        [*command, "verify", str(wrong_source), str(packet_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1 and json.loads(result.stdout)["status"] == "rejected"
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"activations": {}, "activations": {}}')
    result = subprocess.run(
        [*command, "build", str(duplicate), "--output", str(tmp_path / "invalid.json")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1 and not (tmp_path / "invalid.json").exists()

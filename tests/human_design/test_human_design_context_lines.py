"""Whole-context binding, retained failures and tamper rejection, without astronomy replay."""

import gzip
import hashlib
import json
import subprocess
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core.human_design_depth import line_fixings
from fatebridge.core.human_design_line_catalogue import _canonical
from fatebridge.core.human_design_source_variants import line_variant_impact
from fatebridge.services.human_design_context_lines import (
    build_human_design_context_packet,
)
from fatebridge.services.human_design_line_reading import LineReadingInputError
from fatebridge.services.replay_metadata import digest
from fatebridge.validation.human_design_context_lines import (
    verify_human_design_context_packet,
)

ROOT = Path(__file__).resolve().parents[2]
NAMES = [
    "1971_backend_base_interval",
    "mean_j2000_interval",
    "strict_jpl_j2000",
    "gate14_transition_interval",
    "retained_root_family_control",
    "moshier_root_family_control",
]


def read(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


@pytest.fixture(scope="module")
def cases():
    from tests.support.human_design_current import semantic_sources

    return semantic_sources("context")


def forbidden(*args, **kwargs):
    raise AssertionError("Context replay invoked a native calculation")


@pytest.fixture(scope="module")
def packets(cases):
    from unittest.mock import patch

    with (
        patch("fatebridge.core.astro.runtime.ephemeris_call", forbidden),
        patch("fatebridge.core.astro.native_execution.calculate", forbidden),
    ):
        return {
            name: build_human_design_context_packet(source)
            for name, source in cases.items()
        }


def _at(source, path):
    value = source
    for part in path.removeprefix("$.").split(".") if path != "$" else []:
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


@pytest.mark.parametrize("name", NAMES)
def test_every_context_and_all_raw_coordinates_are_retained(name, cases, packets):
    source, packet = cases[name], packets[name]
    assert packet["nominal_packet_v1"]["original_result"] == source
    contexts = packet["contexts"]
    assert len({c["source_path"] for c in contexts}) == len(contexts)
    expected_paths = {"$", "$.node_convention_comparison.reference_node_positions"}
    if source["node_backend_comparison"].get("reference_node_positions") is not None:
        expected_paths.add("$.node_backend_comparison.reference_node_positions")
    parents = [("$", source)]
    backend = source["ephemeris_backend_comparison"]
    if backend["status"] == "full_backend_compared":
        path = "$.ephemeris_backend_comparison.reference_chart"
        parents.append((path, backend["reference_chart"]))
        expected_paths.add(path)
    witnesses = source["time_sensitivity"]["evaluation_witnesses"]
    if witnesses is not None:
        for i, sample in enumerate(witnesses["samples"]):
            path = f"$.time_sensitivity.evaluation_witnesses.samples.{i}"
            parents.append((path, sample))
            expected_paths.add(path)
    for path, parent in parents:
        precision = parent["design_solver"]["numerical_precision"]
        stem = path + ".design_solver.numerical_precision"
        expected_paths.update(
            f"{stem}.design_body_endpoint_assessment.evaluations.{i}"
            for i in range(
                len(precision["design_body_endpoint_assessment"]["evaluations"])
            )
        )
        if precision["local_root_family"] is not None:
            expected_paths.update(
                f"{stem}.local_root_family.candidates.{i}"
                for i in range(len(precision["local_root_family"]["candidates"]))
            )
    assert {c["source_path"] for c in contexts} == expected_paths
    counts = Counter(c["kind"] for c in contexts)
    witness = source["time_sensitivity"]["evaluation_witnesses"]
    assert counts["birth_interval_sample"] == (
        len(witness["samples"]) if witness else 0
    )
    for c in contexts:
        chart = c["chart"]
        assert c["chart_sha256"] == hashlib.sha256(_canonical(chart)).hexdigest()
        assert all(
            len(chart["activations"][s]) == 13 for s in ("personality", "design")
        )
        assert chart["depth_evidence"]["line_fixings"] == line_fixings(
            chart["activations"]
        )
        assert c["source_numeric_line_impacts"] == line_variant_impact(chart)
        group = packet["line_reading_groups"][c["line_reading_group_id"]]
        assert [r["activation_path"] for r in group["rows"]] == [
            f"activations.{s}.{i}" for s in ("personality", "design") for i in range(13)
        ]
        for row, fixing in zip(
            group["rows"], chart["depth_evidence"]["line_fixings"], strict=True
        ):
            actual = _at(chart, row["activation_path"])
            assert (row["body"], row["gate"], row["line"]) == tuple(
                actual[k] for k in ("body", "gate", "line")
            )
            assert row["actual_fixing_state"] == fixing["fixing_state"]
            assert row["fixing_planets"] == fixing["fixing_planets"]
            assert "当前所选名义盘" not in row["reading"]
        if c["kind"] in {
            "birth_interval_sample",
            "numeric_design_endpoint",
            "numeric_design_root_candidate",
        }:
            original = _at(source, c["source_path"])
            raw = original["native_positions"]
            direct = chart["activations"]["design"]
            if c["kind"] == "birth_interval_sample":
                assert c["epoch_tt"] == {
                    s: original["time_scales"][s]["jd_tt"]
                    for s in ("personality", "design")
                }
                for s in ("personality", "design"):
                    assert [
                        [r[k] for k in ("longitude", "longitude_speed", "return_flags")]
                        for r in chart["activations"][s]
                        if r["body"] not in {"Earth", "SouthNode"}
                    ] == raw[s]
            else:
                assert c["epoch_tt"]["design"] == original["jd_tt"]
                assert [
                    [r[k] for k in ("longitude", "longitude_speed", "return_flags")]
                    for r in direct
                    if r["body"] not in {"Earth", "SouthNode"}
                ] == raw
                assert c["numerical_candidate_is_physical_uncertainty_bound"] is False
    assert packet["coverage"]["activation_context_bindings"] == 26 * len(contexts)
    assert packet["coverage"]["contexts_by_kind"] == dict(counts)
    assert (
        packet["coverage"]["repeated_source_roles_count_as_independent_evidence"]
        is False
    )


def test_actual_birth_interval_channel_condition_cannot_borrow_nominal(packets):
    packet = packets["gate14_transition_interval"]
    observed = []
    for c in packet["contexts"]:
        if c["kind"] not in {"selected_nominal", "birth_interval_sample"}:
            continue
        group = packet["line_reading_groups"][c["line_reading_group_id"]]
        row = next(
            r
            for r in group["rows"]
            if r["side"] == "personality" and r["body"] == "Sun"
        )
        assert (
            row["reference_key"] == "2.3" and row["actual_fixing_state"] == "detriment"
        )
        (condition,) = row["bound_source_conditions"]
        truth = condition["calculation_condition_satisfied"]
        actual_gates = {
            a["gate"] for rows in c["chart"]["activations"].values() for a in rows
        }
        assert truth is ({2, 14} <= actual_gates)
        assert condition["fixing_emphasizes_clause_polarity"] is False
        assert condition["source_condition_semantics_independently_accepted"] is False
        observed.append((c["kind"], truth, c["line_reading_group_id"]))
    assert observed[0][1] is True
    assert {truth for _, truth, _ in observed[1:]} == {True, False}
    false_groups = {g for _, truth, g in observed if not truth}
    true_groups = {g for _, truth, g in observed if truth}
    assert false_groups.isdisjoint(true_groups)


def test_fine_backend_base_change_survives_shared_line_reading(packets):
    packet = packets["1971_backend_base_interval"]
    (nominal,) = [c for c in packet["contexts"] if c["kind"] == "selected_nominal"]
    (reference,) = [
        c for c in packet["contexts"] if c["kind"] == "full_backend_reference"
    ]
    moon = next(
        r
        for r in reference["subdivision_changes_from_nominal"]
        if r["body"] == "Moon"
        and r["activation_path"].startswith("activations.personality")
    )
    assert moon["changed_levels"] == ["base"]
    assert moon["nominal"]["base"] != moon["context"]["base"]
    assert nominal["line_reading_group_id"] == reference["line_reading_group_id"]
    assert nominal["chart_sha256"] != reference["chart_sha256"]


def test_no_full_backend_or_interval_chart_is_invented(packets):
    jpl = packets["strict_jpl_j2000"]
    assert {c["kind"] for c in jpl["contexts"]} == {
        "selected_nominal",
        "numeric_design_endpoint",
        "alternative_node_convention",
    }
    absent = {r["source_path"]: r for r in jpl["unassembled_contexts"]}
    for key in ("node_backend_comparison", "ephemeris_backend_comparison"):
        assert absent["$." + key]["status"] == "reference_disabled_by_strict_jpl_policy"
        assert absent["$." + key]["complete_chart_assembled"] is False
    mean = packets["mean_j2000_interval"]
    assert any(
        r["status"] == "analytic_mean_node_not_cross_validated"
        for r in mean["unassembled_contexts"]
    )
    assert packets["retained_root_family_control"]["contexts"]
    family = packets["moshier_root_family_control"]
    assert any(c["kind"] == "numeric_design_root_candidate" for c in family["contexts"])
    assert any(
        r["status"] == "same_backend_not_independent"
        for r in family["unassembled_contexts"]
    )


@pytest.mark.parametrize(
    "fault",
    [
        "omit_context",
        "swap_contexts",
        "wrong_group",
        "delete_group_row",
        "nominal_condition",
        "invent_text",
        "wrong_donor",
        "wrong_fine_coordinate",
        "wrong_source_impact",
        "hide_conflict",
        "fake_master",
        "fake_full_semantics",
        "fake_stability",
        "extra_field",
        "bool_as_count",
        "omit_unavailable",
    ],
)
def test_every_forged_context_or_explanation_is_rejected(cases, packets, fault):
    name = "gate14_transition_interval"
    packet = deepcopy(packets[name])
    c = next(c for c in packet["contexts"] if c["kind"] == "birth_interval_sample")
    group = packet["line_reading_groups"][c["line_reading_group_id"]]
    row = next(r for r in group["rows"] if r["reference_key"] == "2.3")
    if fault == "omit_context":
        packet["contexts"].pop()
    elif fault == "swap_contexts":
        packet["contexts"][1:3] = packet["contexts"][1:3][::-1]
    elif fault == "wrong_group":
        c["line_reading_group_id"] = packet["contexts"][0]["line_reading_group_id"]
    elif fault == "delete_group_row":
        group["rows"].pop()
    elif fault == "nominal_condition":
        row["bound_source_conditions"][0]["calculation_condition_satisfied"] = True
    elif fault == "invent_text":
        row["reading"] += " гарантированное богатство"
    elif fault == "wrong_donor":
        row["fixing_planets"] = {"exaltation": [], "detriment": []}
    elif fault == "wrong_fine_coordinate":
        c["chart"]["activations"]["design"][0]["base"] += 1
    elif fault == "wrong_source_impact":
        c["source_numeric_line_impacts"]["differences"] = ["invented"]
    elif fault == "hide_conflict":
        c["source_context"]["historical_polarity_comparison"][
            "source_conflict_resolved"
        ] = True
    elif fault == "fake_master":
        packet["publisher_master_authenticated"] = True
    elif fault == "fake_full_semantics":
        packet["complete384_line_semantics_accepted"] = True
    elif fault == "fake_stability":
        packet["continuous_interval_stability_certified"] = True
    elif fault == "extra_field":
        packet["new_prediction"] = "guaranteed"
    elif fault == "bool_as_count":
        c["context_index"] = bool(c["context_index"])
    elif fault == "omit_unavailable":
        packet["unassembled_contexts"] = []
    # Keep a locally updated chart digest: a hash is not semantic validation.
    c["chart_sha256"] = hashlib.sha256(_canonical(c["chart"])).hexdigest()
    receipt = verify_human_design_context_packet(packet, cases[name])
    assert receipt["status"] == "rejected" and receipt["errors"]
    assert receipt["checked_activation_context_bindings"] == 0


def test_external_original_and_bad_original_are_rejected(cases, packets):
    assert (
        verify_human_design_context_packet(packets[NAMES[0]], cases[NAMES[1]])[
            "trusted_original_binding_matches"
        ]
        is False
    )
    source = deepcopy(cases[NAMES[0]])
    source["depth_evidence"]["line_fixings"][0]["fixing_state"] = "invented"
    source["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in source.items() if k != "run_metadata"}
    )
    with pytest.raises(LineReadingInputError):
        build_human_design_context_packet(source)
    with pytest.raises(LineReadingInputError):
        build_human_design_context_packet({"activations": source["activations"]})


def test_native_calls_forbidden_and_inputs_unchanged(cases, packets, monkeypatch):
    from fatebridge.core.astro import native_execution, runtime

    monkeypatch.setattr(runtime, "ephemeris_call", forbidden)
    monkeypatch.setattr(native_execution, "calculate", forbidden)
    source = deepcopy(cases[NAMES[0]])
    before = deepcopy(source)
    packet = build_human_design_context_packet(source)
    assert source == before
    assert (
        verify_human_design_context_packet(packet, source)["status"]
        == "verified_original_bound_context_line_packet"
    )
    for name in NAMES:
        assert packets[name]["complete384_line_semantics_accepted"] is False
        assert (
            packets[name]["coverage"]["independently_accepted_full_line_meanings"] == 0
        )


def test_real_module_cli_roundtrip_wrong_original_and_no_overwrite(tmp_path, cases):
    source = tmp_path / "source.json.gz"
    source.write_bytes(
        gzip.compress(json.dumps(cases["gate14_transition_interval"]).encode())
    )
    wrong_source = tmp_path / "wrong-source.json.gz"
    wrong_source.write_bytes(
        gzip.compress(json.dumps(cases["strict_jpl_j2000"]).encode())
    )
    target = tmp_path / "packet.json.gz"
    prefix = [
        sys.executable,
        "-m",
        "fatebridge.validation.human_design_context_lines_cli",
    ]
    result = subprocess.run(
        [*prefix, "build", str(source), "--output", str(target)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (
        subprocess.run(
            [*prefix, "verify", str(source), str(target)], capture_output=True
        ).returncode
        == 0
    )
    assert (
        subprocess.run(
            [*prefix, "verify", str(wrong_source), str(target)],
            capture_output=True,
        ).returncode
        == 1
    )
    before = target.read_bytes()
    assert (
        subprocess.run(
            [*prefix, "build", str(source), "--output", str(target)],
            capture_output=True,
        ).returncode
        == 1
    )
    assert before == target.read_bytes()

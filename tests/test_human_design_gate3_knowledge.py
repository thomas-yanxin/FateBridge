"""Bounded Gate3 source content, explicit versions and real adapter binding."""

import gzip
import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

import fatebridge.application.execution as execution
from fatebridge.core import human_design_knowledge as old
from fatebridge.core import human_design_knowledge_v3 as hd
from fatebridge.services.human_design_context_lines import (
    build_human_design_context_packet,
)
from fatebridge.services.knowledge import calculate_knowledge_read
from fatebridge.utils.errors import EphemerisSourceError
from fatebridge.validation.human_design_context_lines import (
    verify_human_design_context_packet,
)
from tests.test_agentic_nested_outputs import SPECS, business
from tests.test_agentic_nested_outputs import rest as shared_rest
from tests.test_heluo_poem_transports import run_three

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "docs/validation/human-design-gate3-knowledge-v3"
E = BASE / "evidence"
PREVIOUS = ROOT / "docs/validation/human-design-context-line-reading-v2"
rest = shared_rest


def read(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


@pytest.fixture(scope="module")
def source():
    value = read(E / "gate3_april1988_synthetic.json.gz")
    expected = read(E / "gate3-original-capture.json")["gzip_sha256"]
    assert (
        hashlib.sha256(
            (E / "gate3_april1988_synthetic.json.gz").read_bytes()
        ).hexdigest()
        == expected
    )
    return value


@pytest.fixture(scope="module")
def packet(source):
    from unittest.mock import patch

    with (
        patch(
            "fatebridge.core.astro.runtime.ephemeris_call",
            side_effect=AssertionError("native replay"),
        ),
        patch(
            "fatebridge.core.astro.native_execution.calculate",
            side_effect=AssertionError("native dispatch"),
        ),
    ):
        return build_human_design_context_packet(source, reference_category="lines_v3")


def test_all_default384_outputs_and_all_previous_v2_context_packets_unchanged():
    expected = read(E / "before-384-canonical-hashes.json")
    for key, digest in expected.items():
        assert (
            hashlib.sha256(
                old._canonical(old.read_reference(category="lines", key=key))
            ).hexdigest()
            == digest
        )
    rows = read(PREVIOUS / "evidence/packet-delivery.json")["rows"]
    for row in rows:
        source = read(ROOT / row["source_path"])
        expected = read(PREVIOUS / "packets" / (row["id"] + ".json.gz"))
        assert old._canonical(
            build_human_design_context_packet(source)
        ) == old._canonical(expected)


def test_versions_have_separate_honest_coverage_and_keep_unknowns():
    categories = old.build_registry()["domains"][0]["categories"]
    # Preserve the original version prefix and require the additive category.
    assert [c["name"] for c in categories[:3]] == ["lines", "lines_v3", "lines_v4"]
    assert [c["name"] for c in categories] == [
        "lines",
        "lines_v3",
        "lines_v4",
        "lines_v5",
        "lines_v6",
        "lines_v7",
    ]
    assert (
        categories[0]
        == read(E / "before-registry.json.gz")["domains"][0]["categories"][0]
    )
    assert categories[0]["coverage"]["local_editorial_paraphrases"] == 12
    assert categories[1]["coverage"] == {
        "line_locators": 384,
        "local_editorial_paraphrases": 18,
        "meanings_pending": 366,
        "independently_accepted_line_meanings": 0,
        "full_source_meanings_accepted": False,
    }
    for g in range(1, 65):
        for n in range(1, 7):
            key = f"{g}.{n}"
            record = hd.read_reference(key=key)["reference_details"]["record"]
            if g != 3:
                assert (
                    record
                    == old.read_reference(category="lines", key=key)[
                        "reference_details"
                    ]["record"]
                )
            assert record["complete_line_meaning_accepted"] is False
            assert record["actual_fixing_state"] is record["selected_polarity"] is None


@pytest.mark.parametrize(
    "line,heading,up,down",
    [
        (1, "Synthesis", "Earth", "Mercury"),
        (2, "Immaturity", "Mars", "Uranus"),
        (3, "Survival", "Venus", "Pluto"),
        (4, "Charisma", "Neptune", "Mars"),
        (5, "Victimization", "Mars", "Earth"),
        (6, "Surrender", "Sun", "Pluto"),
    ],
)
def test_actual_specific_line_is_not_a_generic_role_theme(line, heading, up, down):
    record = hd.read_reference(key=f"3.{line}")["reference_details"]["record"]
    assert record["source_line_heading"] == heading
    assert record["source_polarity_planets"] == {
        "exaltation": [up],
        "detriment": [down],
    }
    (qualifier,) = record["source_qualifiers"]
    assert (
        qualifier["personal_condition_satisfied"]
        is qualifier["mechanical_predicate"]
        is None
    )
    assert qualifier["automatic_application"] is False
    assert qualifier["editorial_summary_zh"] in record["source_reading_notes"][0]
    corroboration = record["heading_corroboration"]
    assert corroboration["literal_heading_matches"] is True
    assert corroboration["full_line_body_available_in_sample"] is False
    assert corroboration["full_line_semantics_corroborated"] is False


def test_public_publisher_sample_supports_headings_only():
    path = BASE / "sources/ra-1-6-gate3-public-sample.pdf"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == hd.SAMPLE_SHA256
    # Frozen independent extraction, also visually checked; test consumers need
    # no system Poppler dependency and do not use the current knowledge producer.
    raw = (BASE / "sources/publisher-contents.txt").read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == "8ac3fc180ac1eda2743ac8b58b8a001107a8c7e5f34ae1e98071df93e52cfaa8"
    )
    witness = read(E / "publisher-extraction.json")
    assert witness["pdf_sha256"] == hd.SAMPLE_SHA256
    assert witness["extracted_text_sha256"] == hashlib.sha256(raw).hexdigest()
    text = raw.decode()
    for heading in [
        "Synthesis",
        "Immaturity",
        "Survival",
        "Charisma",
        "Victimization",
        "Surrender",
    ]:
        assert heading in text
    assert "TABLE OF CONTENTS" in text
    record = hd.read_reference(key="3.4")["reference_details"]["record"]
    assert any("Physic" in n and "psychic" in n for n in record["source_reading_notes"])
    assert (
        "生物性"
        in hd.read_reference(key="3.3")["reference_details"]["record"][
            "editorial_paraphrase"
        ]["exaltation"]
    )


@pytest.mark.parametrize("key", ["3.1", "3.2", "3.3", "3.4", "3.5", "3.6", "64.6"])
def test_actual_versioned_reference_on_three_adapters(key, rest, tmp_path, capsys):
    response, code, cli, mcp = run_three(
        SPECS["knowledge_read"],
        {"domain": "human_design", "category": "lines_v3", "key": key},
        ["category", "key", "reference_details", "provenance", "snapshot_text"],
        rest,
        tmp_path,
        capsys,
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    assert (
        business(response.json()) == business(cli) == business(mcp.structured_content)
    )
    assert (
        cli["category"] == "lines_v3"
        and cli["provenance"]["source_catalogue_version"] == 3
    )
    if key.startswith("3."):
        assert (
            "引导语" in cli["snapshot_text"]
            and cli["reference_details"]["record"]["editorial_paraphrase"]
        )
    else:
        assert cli["reference_details"]["record"]["editorial_paraphrase"] is None


@pytest.mark.parametrize(
    "fault",
    [
        "wrong_version",
        "full_body_claim",
        "qualifier",
        "personal_true",
        "drop_pole",
        "hide_ambiguity",
    ],
)
def test_actual_adapters_reject_forged_content_before_unrelated_projection(
    fault, monkeypatch, rest, tmp_path, capsys
):
    result = calculate_knowledge_read(
        domain="human_design", category="lines_v3", key="3.4"
    )
    record = result["reference_details"]["record"]
    if fault == "wrong_version":
        result = calculate_knowledge_read(
            domain="human_design", category="lines", key="3.4"
        )
    elif fault == "full_body_claim":
        record["heading_corroboration"]["full_line_body_available_in_sample"] = True
    elif fault == "qualifier":
        record["source_qualifiers"][0]["editorial_summary_zh"] = "invented"
    elif fault == "personal_true":
        record["source_qualifiers"][0]["personal_condition_satisfied"] = True
    elif fault == "drop_pole":
        record["editorial_paraphrase"]["detriment"] = None
    elif fault == "hide_ambiguity":
        record["source_reading_notes"] = []
    execute = execution.execute_spec

    def forged(spec, request):
        if spec.key == "knowledge_read":
            spec = replace(spec, bind=lambda _: (lambda: deepcopy(result), (), {}))
        return execute(spec, request)

    monkeypatch.setattr(execution, "execute_spec", forged)
    response, code, _, mcp = run_three(
        SPECS["knowledge_read"],
        {"domain": "human_design", "category": "lines_v3", "key": "3.4"},
        ["source"],
        rest,
        tmp_path,
        capsys,
    )
    assert response.status_code == 503 and code != 0 and mcp.is_error


@pytest.mark.parametrize("component", ["MANIFEST_PATH", "SUPPLEMENT_PATH"])
def test_late_source_change_is_rejected(component, monkeypatch, tmp_path):
    original = getattr(hd, component)
    path = tmp_path / original.name
    path.write_bytes(original.read_bytes())
    monkeypatch.setattr(hd, component, path)
    catalogue = hd._catalogue

    def changed():
        data = catalogue()
        path.write_bytes(path.read_bytes() + b" ")
        return data

    monkeypatch.setattr(hd, "_catalogue", changed)
    with pytest.raises(EphemerisSourceError) as caught:
        hd.read_reference(key="3.4")
    assert caught.value.reason == "human_design_reference_changed"


@pytest.mark.parametrize("component", ["MANIFEST_PATH", "SUPPLEMENT_PATH"])
def test_registry_rechecks_versioned_bytes_after_nested_composition(
    component, monkeypatch, tmp_path
):
    original = getattr(hd, component)
    path = tmp_path / original.name
    path.write_bytes(original.read_bytes())
    monkeypatch.setattr(hd, component, path)
    category = hd._registry_category

    def changed():
        result = category()
        path.write_bytes(path.read_bytes() + b" ")
        return result

    monkeypatch.setattr(hd, "_registry_category", changed)
    with pytest.raises(EphemerisSourceError) as caught:
        old.build_registry()
    assert caught.value.reason == "human_design_reference_changed"


def test_v3_context_uses_actual_chart_and_keeps_unassessed_qualifiers(source, packet):
    baseline = build_human_design_context_packet(source)
    assert packet["packet_version"] == 3 and packet["reference_category"] == "lines_v3"
    assert packet["nominal_packet_v1"] == baseline["nominal_packet_v1"]
    assert packet["line_reference_provenance"]["source_catalogue_version"] == 3
    seen = set()
    for c, old_c in zip(packet["contexts"], baseline["contexts"], strict=True):
        assert c["chart"] == old_c["chart"] and c["epoch_tt"] == old_c["epoch_tt"]
        group = packet["line_reading_groups"][c["line_reading_group_id"]]
        assert len(group["rows"]) == 26
        for r in group["rows"]:
            if r["gate"] == 3:
                seen.add(r["reference_key"])
                assert (
                    r["editorial_paraphrase"]
                    and r["source_qualifiers"][0]["personal_condition_satisfied"]
                    is None
                )
                assert "引导语" in r["reading"]
    assert {"3.3", "3.4"} <= seen
    assert (
        verify_human_design_context_packet(
            packet, source, reference_category="lines_v3"
        )["status"]
        == "verified_original_bound_context_line_packet"
    )
    assert verify_human_design_context_packet(packet, source)["status"] == "rejected"
    assert (
        verify_human_design_context_packet(
            baseline, source, reference_category="lines_v3"
        )["status"]
        == "rejected"
    )


@pytest.mark.parametrize(
    "fault",
    ["qualifier_true", "drop_qualifier", "heading_proves_body", "wrong_version"],
)
def test_v3_packet_forgery_is_rejected_with_correct_original(source, packet, fault):
    altered = deepcopy(packet)
    row = next(
        r
        for g in altered["line_reading_groups"].values()
        for r in g["rows"]
        if r["gate"] == 3
    )
    if fault == "qualifier_true":
        row["source_qualifiers"][0]["personal_condition_satisfied"] = True
    elif fault == "drop_qualifier":
        row["source_qualifiers"] = []
    elif fault == "heading_proves_body":
        row["heading_corroboration"]["full_line_semantics_corroborated"] = True
    else:
        altered["reference_category"] = "lines"
    assert (
        verify_human_design_context_packet(
            altered, source, reference_category="lines_v3"
        )["status"]
        == "rejected"
    )


def test_module_cli_requires_explicit_reference_category(tmp_path):
    source = E / "gate3_april1988_synthetic.json.gz"
    target = tmp_path / "v3.json.gz"
    prefix = [
        sys.executable,
        "-m",
        "fatebridge.validation.human_design_context_lines_cli",
    ]
    assert (
        subprocess.run(
            [
                *prefix,
                "build",
                str(source),
                "--output",
                str(target),
                "--reference-category",
                "lines_v3",
            ],
            capture_output=True,
        ).returncode
        == 0
    )
    assert (
        subprocess.run(
            [
                *prefix,
                "verify",
                str(source),
                str(target),
                "--reference-category",
                "lines_v3",
            ],
            capture_output=True,
        ).returncode
        == 0
    )
    assert (
        subprocess.run(
            [*prefix, "verify", str(source), str(target)], capture_output=True
        ).returncode
        == 1
    )

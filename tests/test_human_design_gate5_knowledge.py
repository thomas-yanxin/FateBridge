"""Gate5 source facts, absent poles and untouched historical editions."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest

from fatebridge.core import human_design_knowledge as base
from fatebridge.core import human_design_knowledge_v6 as hd
from fatebridge.services.human_design_context_lines import (
    build_human_design_context_packet,
)
from fatebridge.utils.errors import EphemerisSourceError
from fatebridge.validation.human_design_context_lines import (
    verify_human_design_context_packet,
)
from scripts.gen_human_design_timezone_history import read, sha
from tests.test_agentic_nested_outputs import SPECS, business
from tests.test_agentic_nested_outputs import rest as shared_rest
from tests.test_heluo_poem_transports import run_three

ROOT = Path(__file__).resolve().parents[1]
E = ROOT / "docs/validation/human-design-gate5-knowledge-v6/evidence"
rest = shared_rest
LOCATOR_SHA = "6efc0b43f31b16ee7923c239fea686a150c2dd61597aebf65fdaec998c53baca"


def test_all384_v6_source_inventories_preserve_previous_facts_and_non_gate5_meanings():
    for gate in range(1, 65):
        for line in range(1, 7):
            key = f"{gate}.{line}"
            old = base.read_reference(category="lines_v5", key=key)[
                "reference_details"
            ]["record"]
            new = hd.read_reference(key=key)["reference_details"]["record"]
            available = [
                p
                for p in ("exaltation", "detriment")
                if old["source_polarity_planets"][p]
            ]
            assert new["source_available_polarities"] == available
            assert new["source_polarity_planets"] == old["source_polarity_planets"]
            assert (
                new["source_context_annotations"] == old["source_context_annotations"]
            )
            assert new["actual_fixing_state"] is new["selected_polarity"] is None
            if len(available) != 2:
                assert "另一极性" not in new["selection_policy"]
            if gate != 5:
                new = deepcopy(new)
                new.pop("source_available_polarities")
                new["selection_policy"] = old["selection_policy"]
                assert new == old


def test_all1536_existing_reference_outputs_and_registry_prefix_are_unchanged():
    for category, keys in read(E / "before-1536-canonical-hashes.json").items():
        assert len(keys) == 384
        for key, expected in keys.items():
            assert (
                hashlib.sha256(
                    base._canonical(base.read_reference(category=category, key=key))
                ).hexdigest()
                == expected
            )
    registry = base.build_registry()
    newer = registry["domains"][0]["categories"].pop()
    assert newer["name"] == "lines_v7"
    assert newer["coverage"] == {
        "line_locators": 384,
        "local_editorial_paraphrases": 36,
        "meanings_pending": 348,
        "independently_accepted_line_meanings": 0,
        "full_source_meanings_accepted": False,
    }
    category = registry["domains"][0]["categories"].pop()
    assert category["name"] == "lines_v6"
    assert category["coverage"] == {
        "line_locators": 384,
        "local_editorial_paraphrases": 30,
        "meanings_pending": 354,
        "independently_accepted_line_meanings": 0,
        "full_source_meanings_accepted": False,
    }
    assert registry == read(E / "before-registry.json")


@pytest.mark.parametrize(
    "line,up,down",
    [
        (1, "Mars", "Earth"),
        (2, "Venus", "Pluto"),
        (3, "Neptune", "Moon"),
        (4, "Uranus", "Sun"),
        (5, "Venus", "Pluto"),
        (6, "Neptune", None),
    ],
)
def test_six_lines_match_independent_page_locators_and_available_poles(line, up, down):
    p = E / "gate5-independent-source-locators-v2.json"
    assert sha(p) == LOCATOR_SHA
    fact = read(p)["rows"][line - 1]
    record = hd.read_reference(key=f"5.{line}")["reference_details"]["record"]
    assert (
        record["source_pdf_page_one_based"] == fact["source_pdf_page_one_based"] == 15
    )
    assert record["source_layout_block_sha256"] == fact["source_layout_block_sha256"]
    assert record["source_line_heading"] == fact["source_line_heading"]
    assert fact["visually_observed_exaltation_planet"] == up
    assert fact["visually_observed_detriment_planet"] == down
    assert record["source_polarity_planets"] == {
        "exaltation": [up],
        "detriment": [] if down is None else [down],
    }
    assert record["source_available_polarities"] == (
        ["exaltation"] if down is None else ["exaltation", "detriment"]
    )
    assert (record["editorial_paraphrase"]["detriment"] is None) == (down is None)
    assert record["source_conditions"] is None
    assert record["source_qualifiers"][0]["personal_condition_satisfied"] is None
    assert record["complete_line_meaning_accepted"] is False
    if line == 6:
        assert record["source_polarity_text_note"]["printed_no_polarity"] is True
        assert record["source_polarity_text_note"]["mechanical_rule_changed"] is False
        assert "另一极性" not in record["selection_policy"]


@pytest.mark.parametrize(
    "key", ["5.1", "5.2", "5.3", "5.4", "5.5", "5.6", "2.3", "64.6"]
)
def test_real_rest_mcp_cli_reading_with_nullable_missing_pole(
    key, rest, tmp_path, capsys
):
    response, code, cli, mcp = run_three(
        SPECS["knowledge_read"],
        {"domain": "human_design", "category": "lines_v6", "key": key},
        ["category", "key", "reference_details", "provenance", "snapshot_text"],
        rest,
        tmp_path,
        capsys,
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    assert (
        business(response.json()) == business(cli) == business(mcp.structured_content)
    )
    assert cli["provenance"]["source_catalogue_version"] == 6


@pytest.mark.parametrize(
    "fault",
    [
        "invented_detriment",
        "changed_glyph",
        "personal_true",
        "claimed_acceptance",
        "resolved_note",
    ],
)
def test_rehashed_invalid_catalogue_cannot_invent_poles_or_acceptance(
    fault, tmp_path, monkeypatch
):
    data = json.loads(hd.CATALOGUE_PATH.read_text())
    row = data["rows"][-1]
    if fault == "invented_detriment":
        row["editorial_paraphrase"]["detriment"] = "Invented opposite meaning"
    elif fault == "changed_glyph":
        data["rows"][3]["source_polarity_planets"]["exaltation"] = ["Jupiter"]
    elif fault == "personal_true":
        row["source_qualifiers"][0]["personal_condition_satisfied"] = True
    elif fault == "claimed_acceptance":
        row["complete_line_meaning_accepted"] = True
    else:
        row["source_polarity_text_note"][
            "glyph_text_convention_independently_resolved"
        ] = True
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(data))
    monkeypatch.setattr(hd, "CATALOGUE_PATH", path)
    monkeypatch.setattr(hd, "CATALOGUE_SHA256", sha(path))
    with pytest.raises(EphemerisSourceError):
        hd.read_reference(key="5.6")


@pytest.fixture(scope="module")
def packet56():
    source = read(E / "before-1976-12-08.json.gz")
    with patch(
        "fatebridge.core.astro.runtime.ephemeris_call",
        side_effect=AssertionError("native sky forbidden"),
    ):
        packet = build_human_design_context_packet(
            source, reference_category="lines_v6"
        )
    return source, packet


def test_actual_fixed56_has_no_invented_detriment_or_changed_mechanics(packet56):
    source, packet = packet56
    assert (
        verify_human_design_context_packet(
            packet, source, reference_category="lines_v6"
        )["status"]
        == "verified_original_bound_context_line_packet"
    )
    rows = [
        r
        for g in packet["line_reading_groups"].values()
        for r in g["rows"]
        if r["reference_key"] == "5.6"
    ]
    assert rows and any(r["actual_fixing_state"] == "exaltation" for r in rows)
    for row in rows:
        assert row["editorial_paraphrase"]["detriment"] is None
        assert row["source_available_polarities"] == ["exaltation"]
        assert "下降为" not in row["reading"] and "另一极性" not in row["reading"]
    assert packet["nominal_packet_v1"]["original_result"] == source


@pytest.mark.parametrize(
    "fault",
    ["invented_text", "invented_pole", "wrong_fixing", "drop_note", "wrong_version"],
)
def test_complete_context_replay_rejects_new_pole_and_text_forgery(packet56, fault):
    source, original = packet56
    packet = deepcopy(original)
    row = next(
        r
        for g in packet["line_reading_groups"].values()
        for r in g["rows"]
        if r["reference_key"] == "5.6"
    )
    if fault == "invented_text":
        row["reading"] += "另一极性必定出现。"
    elif fault == "invented_pole":
        row["source_available_polarities"].append("detriment")
    elif fault == "wrong_fixing":
        row["actual_fixing_state"] = "detriment"
    elif fault == "drop_note":
        row["source_reading_notes"] = []
    else:
        packet["reference_category"] = "lines_v5"
    proof = verify_human_design_context_packet(
        packet, source, reference_category="lines_v6"
    )
    assert proof["status"] == "rejected"

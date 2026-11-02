"""Keep literal source counterevidence separate from formula computation."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from fatebridge.core.jyotish_balas import PLANETS, aspect_strength
from fatebridge.core.jyotish_evidence import strength_context
from fatebridge.core.output_jyotish import ConditionalDrik
from scripts.audit_jyotish_drik_primary import build_report
from tests.fixtures.surface_payloads import astro_payload
from tests.test_jyotish_sources import data18, restore_runtime  # noqa: F401
from tests.test_jyotish_transports import call_surfaces

ROOT = Path(__file__).resolve().parents[1]
PRIMARY = ROOT / "tests/fixtures/jyotish-drik-primary.json"


def test_source_seal_and_literal_arithmetic_failures_are_not_silently_corrected():
    raw = PRIMARY.read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == "6937c48aacf4317bfe5455047fe9c3e7b148cd48d446d9c7fbcea8455c389961"
    )
    report = build_report(json.loads(raw))
    assert report["status"] == "source_internal_conflicts"
    assert report["complete_single_original_accepted"] is False
    assert len(report["decimal_relations"]) == 35
    assert len(report["decimal_conflicts"]) == 4
    assert all(
        abs(float(row["difference"])) == 0.7 for row in report["decimal_conflicts"]
    )
    assert len(report["literal_angle_disagreements"]) == 13
    outside = [
        r
        for r in report["literal_angle_disagreements"]
        if r["exceeds_three_display_quanta"]
    ]
    assert [
        (r["aspector"], r["target"], r["difference_arcminutes"]) for r in outside
    ] == [("Jupiter", "Mars", "-10")]
    # The seven printed Example55 quarter sums cohere under this declared
    # rounding comparison; contradictions elsewhere do not invalidate them.
    assert all(
        r["equal"]
        for r in report["decimal_relations"]
        if r["relation"] == "example55_net_to_drik_half_up"
    )


def test_source_gate_exits_one_and_cannot_overwrite_its_reference(tmp_path):
    command = [
        sys.executable,
        str(ROOT / "scripts/audit_jyotish_drik_primary.py"),
        "--report",
    ]
    completed = subprocess.run(
        [*command, str(tmp_path / "report.json")], capture_output=True
    )
    assert completed.returncode == 1
    before = PRIMARY.read_bytes()
    rejected = subprocess.run([*command, str(PRIMARY)], capture_output=True)
    assert rejected.returncode == 2
    assert PRIMARY.read_bytes() == before


def test_numeric_consensus_never_erases_source_conflicts_or_selects_mercury_orb():
    drik = aspect_strength(dict.fromkeys(PLANETS, 0.0))
    assert drik["summary"] == dict.fromkeys(PLANETS, 0.0)
    assert drik["source_witness"]["complete_single_original_accepted"] is False
    assert len(drik["source_reading_conflicts"]) == 3
    assert (
        drik["nature_context"]["mercury_status"]
        == "association_predicate_not_adjudicated"
    )
    ConditionalDrik.model_validate(drik)
    context = strength_context("drik_bala", "Sun", drik)
    assert context["value_status"] == "computed_consensus"
    assert (
        "india.strengths.drik_bala.source_reading_conflicts" in context["context_paths"]
    )
    assert {
        "fact_path": "india.strengths.drik_bala.source_witness.complete_single_original_accepted",
        "value": False,
    } in context["constraints"]


@pytest.mark.parametrize("key", ["astro_india", "astro_chart", "astro_vimshottari"])
def test_primary_witness_survives_strict_projection_on_three_surfaces(
    data18, monkeypatch, capsys, key
):
    monkeypatch.setenv("SE_EPHE_PATH", str(data18[1]))
    payload = astro_payload()
    if key == "astro_chart":
        payload["chart_variant"] = "india_chart"
    if key == "astro_vimshottari":
        payload["analysis_year"] = 2026
    result = call_surfaces(
        monkeypatch,
        capsys,
        key,
        payload,
        [
            "india.strengths.drik_bala.source_witness",
            "india.strengths.drik_bala.source_reading_conflicts",
            "india.strengths.drik_bala.nature_context.mercury_status",
        ],
    )
    drik = result["india"]["strengths"]["drik_bala"]
    assert (
        drik["source_witness"]["sha256"]
        == "727c8063f64816a0c1c7f6bc577c249629854e980bf860bf4cfd8de16ec9bab2"
    )
    assert drik["source_witness"]["complete_single_original_accepted"] is False
    assert len(drik["source_reading_conflicts"]) == 3
    assert (
        drik["nature_context"]["mercury_status"]
        == "association_predicate_not_adjudicated"
    )

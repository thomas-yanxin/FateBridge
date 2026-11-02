"""Keep all negative anchors while tracing force, monthly duty and passage."""

import gzip
import json
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest

from fatebridge.utils.data import DESTRUCTION_CYCLE, GENERATION_CYCLE, Element
from scripts.audit_bazi_focus import receipt_totals

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/validation/bazi-focus-first-v1.json.gz"


def report():
    assert (
        sha256(REPORT.read_bytes()).hexdigest()
        == Path(str(REPORT) + ".sha256").read_text().strip()
    )
    return json.loads(gzip.decompress(REPORT.read_bytes()))


def test_all_original_labels_remain_and_source_days_are_not_invented():
    result = report()
    source = json.loads(
        (ROOT / "tests/fixtures/bazi_disagreement_review_v1/review.json").read_text()
    )
    assert [
        (r["id"], r["pillars"], r["expected_strength"]) for r in result["rows"]
    ] == [(r["id"], r["pillars"], r["expected_strength"]) for r in source["cases"]]
    assert len(result["unresolved"]) == 19
    assert result["resolved_under_original_labels"] == []
    assert result["explicit_source_relative_days"] == 1
    assert result["unknown_source_relative_days"] == 18
    assert result["absolute_source_birth_instants"] == 0
    assert not result["candidate_adopted"] and not result["classical_acceptance_passed"]
    assert result["real_world_efficacy"] == "not_tested"


def test_heavy_seal_does_not_get_promoted_to_a_classical_body_verdict():
    row = next(r for r in report()["rows"] if r["id"] == "ZP-PROSPECTIVE-18-MA-LIGHT")
    assert row["expected_strength"] == "弱" and row["actual_strength"] == "强"
    assert row["body_seal"]["seal_energy"] > row["body_seal"]["body_energy"]
    assert any(r["stem"] == "壬" for r in row["body_seal"]["body_physical_roots"])
    assert set(row["body_seal"]["classical_adjudication"].values()) == {
        "not_adjudicated"
    }
    changed = deepcopy(row["raw_same_calculation"]["assessment"])
    changed["effective_elements_unrounded"]["水"] += 1
    with pytest.raises(ValueError, match="fails to reconcile"):
        receipt_totals(changed)


def test_month_branch_phase_does_not_overwrite_the_authors_day_duty_or_body_label():
    row = next(r for r in report()["rows"] if r["id"] == "ML-02")
    month = row["month_command"]
    assert month["source_relative_day"] == 6 and month["source_duty_stem"] == "戊"
    assert month["branch_phase"]["phase"] == "囚"
    assert month["intra_month_duty"]["selected_stem"] is None
    assert row["expected_strength"] == "强" and row["actual_strength"] == "弱"


def test_every_retained_path_obeys_its_actual_nodes_without_exempting_clashes():
    result = report()
    for row in result["rows"]:
        passage = row["raw_same_calculation"]["evidence"]["classical_passage"]
        nodes = {n["id"]: n for n in passage["nodes"]}
        for name in ["visible_paths", "all_hidden_paths", "mixed_paths"]:
            for path in passage[name]:
                a, m, b = (nodes[path[k]] for k in ("from_node", "via_node", "to_node"))
                ea, em, eb = (Element(n["element"]) for n in (a, m, b))
                assert DESTRUCTION_CYCLE[ea] == eb
                assert GENERATION_CYCLE[ea] == em and GENERATION_CYCLE[em] == eb
                assert path["effective_passage"] == "not_adjudicated"
        assert row["passage"]["clash_exemptions_added"] is False
    tg = next(r for r in result["rows"] if r["id"] == "DTCW1947-TG-01")
    assert tg["passage"]["principal_hidden_paths"]["observed"] == 2
    assert tg["actual_strength"] == "弱" and tg["expected_strength"] == "强"
    gs = next(r for r in result["rows"] if r["id"] == "DTCW1947-GS-03")
    assert gs["passage"]["mixed_paths"]["shared_pillar_paths"] > 0

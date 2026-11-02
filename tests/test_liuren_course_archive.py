"""Offline new annotations preserve exact old facts and never relax live gates."""

import copy
import json
import shutil
from pathlib import Path

import pytest

from fatebridge.core.output_ren_anchors import require_complete_ren_anchors
from scripts.jinkou_archive_proofs import ARCHIVE_SNAPSHOTS, historical_pattern_proofs
from scripts.liuren_course_archive import historical_course_conditions
from scripts.liuren_cross_harmony_archive import historical_cross_harmony
from tests.ren_archive_contract import assert_historical_contract_gap
from tests.test_agentic_nested_outputs import SPECS
from tests.test_liuren_ordered_patterns import raw

ROOT = Path(__file__).resolve().parents[1]
SLUGS = {
    "api_cn_liureng_gods": "liureng_gods",
    "api_cn_liureng_runyear": "liureng_runyear",
    "api_cn_jinkou": "jinkou",
    "api_divination_sanshiunited": "sanshiunited",
}


def archived(slug="api_cn_liureng_gods"):
    path = ARCHIVE_SNAPSHOTS / (slug + ".json")
    return json.loads(path.read_text()), path


@pytest.mark.parametrize("slug", SLUGS)
def test_all_old_fields_and_file_bytes_survive_new_annotations(slug):
    value, path = archived(slug)
    before = path.read_bytes()
    original = copy.deepcopy(value)
    augmented, receipt = historical_course_conditions(value)
    assert receipt["existing_fields_unchanged"] and receipt["supplement_computed_now"]
    assert (
        receipt["not_a_historical_or_live_receipt"]
        and not receipt["golden_files_written"]
    )
    assert value == original and path.read_bytes() == before
    assert augmented["liureng"]["ruleset"] == value["liureng"]["ruleset"]
    assert augmented["snapshot_text"] == value["snapshot_text"]
    restored, _ = historical_course_conditions(augmented, mode="strip")
    assert restored == value
    twice, second = historical_course_conditions(augmented)
    assert twice == augmented and not second["changes"]
    current, _ = historical_pattern_proofs(augmented)
    from scripts.liuren_ordered_archive import historical_ordered_patterns

    current, _ = historical_ordered_patterns(current)
    from scripts.liuren_day_placement_archive import historical_day_placements

    current, _ = historical_day_placements(current)
    current, cross_supplement = historical_cross_harmony(current)
    assert cross_supplement["original_restored_exactly"]
    assert_historical_contract_gap(
        SPECS[SLUGS[slug]], {k: v for k, v in current.items() if k != "run_metadata"}
    )


@pytest.mark.parametrize(
    "fault",
    [
        "missing_block",
        "missing_trace",
        "duplicate",
        "branches",
        "match",
        "source",
        "numeric_bool",
        "scope",
    ],
)
def test_supplied_wrong_annotations_never_vanish_in_add_or_strip(fault):
    value, _ = archived()
    value, _ = historical_course_conditions(value)
    board = value["liureng"]
    evidence = board["transmission_relations"]["course_conditions"]
    trace = next(
        t for t in board["rule_trace"] if t["rule_id"] == "liuren.course_conditions"
    )
    if fault == "missing_block":
        board["transmission_relations"].pop("course_conditions")
    elif fault == "missing_trace":
        board["rule_trace"].remove(trace)
    elif fault == "duplicate":
        board["rule_trace"].append(copy.deepcopy(trace))
    elif fault == "branches":
        board["three_transmissions"]["initial"]["branch"] = (
            "子" if evidence["branches"][0] != "子" else "丑"
        )
    elif fault == "match":
        evidence["stage_god_patterns"][0]["matched"] = not evidence[
            "stage_god_patterns"
        ][0]["matched"]
    elif fault == "source":
        evidence["source_sha256"] = "fake"
    elif fault == "numeric_bool":
        evidence["complete_classical_conformance"] = 0
    else:
        evidence["scope"] = "old prophecy confirmed"
    for mode in ["add", "strip"]:
        with pytest.raises(ValueError):
            historical_course_conditions(value, mode=mode)


@pytest.mark.parametrize("fault", ["manifest", "bytes", "missing", "extra"])
def test_archive_protocol_is_fixed_before_adapter(fault, tmp_path, monkeypatch):
    import scripts.liuren_course_archive as adapter

    path = tmp_path / "protocol"
    shutil.copytree(adapter.CORPUS, path)
    if fault == "manifest":
        (path / "freeze.json").write_text("{}")
    elif fault == "bytes":
        (path / "protocol.json").write_text("{}")
    elif fault == "missing":
        (path / "protocol.json").unlink()
    else:
        (path / "extra").write_text("")
    monkeypatch.setattr(adapter, "CORPUS", path)
    with pytest.raises((ValueError, FileNotFoundError)):
        adapter.reference()


def test_legacy_version_cannot_bypass_the_live_complete_gate():
    value = raw("liureng_gods")
    value["liureng"]["ruleset"]["version"] = "1.11.0"
    value["liureng"]["transmission_relations"].pop("course_conditions")
    with pytest.raises(ValueError):
        require_complete_ren_anchors("liureng_gods", value)

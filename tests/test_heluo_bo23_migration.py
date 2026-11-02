"""Keep old failures and reject opportunistic weakening of the R101 successor."""

import copy
import gzip
import hashlib
import json
import shutil

import pytest

from fatebridge.core import heluo_texts
from fatebridge.core.heluo import yao_text
from fatebridge.services.knowledge import (
    calculate_knowledge_read,
    calculate_knowledge_registry,
)
from tests.heluo_bo23_revision_reference import (
    CURRENT_CATALOGUE,
    ENVELOPE,
    FOOTER_ADDENDUM,
    KNOWLEDGE,
    REFERENCE,
    ROOT,
    F,
    assert_r101_source_edge,
    canonical,
    rebind_r101_business,
    rebind_r101_metadata,
    rebind_r101_record,
    rebind_r101_registry,
    rebind_r101_render_row,
)
from tests.heluo_current_source_reference import (
    HEADER_COUNT,
)
from tests.heluo_current_source_reference import REFERENCE as CURRENT_REFERENCE
from tests.heluo_current_source_reference import F as CURRENT_F
from tests.heluo_current_source_reference import (
    advance_current_record,
    advance_current_registry,
)


def test_reference_is_sealed_before_old_tests_and_has_no_prediction_or_reader_credit():
    freeze = json.loads((F / "freeze.json").read_bytes())
    assert freeze["before_any_old_test_edits"]
    assert freeze["original_failures_preserved"] == 120
    assert freeze["no_current_producer_used_for_expected_results"]
    for name, digest in freeze["files"].items():
        assert hashlib.sha256((F / name).read_bytes()).hexdigest() == digest, name
    assert (
        REFERENCE["new_independent_reviews"]
        == REFERENCE["new_real_world_outcomes"]
        == 0
    )
    assert REFERENCE["goal_complete"] is REFERENCE["authority_certified"] is False
    assert len(REFERENCE["business_edges"]) == 34


def test_complete384_records_and_statuses_match_the_before_code_source_reference():
    assert len(REFERENCE["records"]) == 384
    for key, edge in REFERENCE["records"].items():
        gua, line = key.rsplit(":", 1)
        expected = rebind_r101_record(edge["before"], key)
        current = advance_current_record(expected, key)
        assert yao_text(gua, int(line)) == current
        assert (
            heluo_texts.text_status_snapshot(current)
            == CURRENT_REFERENCE["statuses_after"][key]
        )
        if not key.startswith("山地剝:"):
            assert {k: v for k, v in expected.items() if k != "text_provenance"} == {
                k: v for k, v in edge["before"].items() if k != "text_provenance"
            }
    from scripts.audit_numerology import bo23_source_checks

    audit = bo23_source_checks()
    assert audit["checks_passed"] and audit["failures"] == []
    assert (
        audit["current_headers"]
        == audit["current_complete_commentaries"]
        == HEADER_COUNT
    )
    assert audit["independent_reviews_added"] == audit["new_real_world_outcomes"] == 0


@pytest.mark.parametrize("domain,count", [("heluo", 384), ("canping", 1170)])
def test_entire_knowledge_domain_matches_old_gateway_with_fixed_source_inputs(
    domain, count
):
    rows = json.loads(gzip.decompress((F / "after1554.json.gz").read_bytes()))
    keys = [key for key in KNOWLEDGE["keys"] if key.startswith(domain + ":")]
    assert len(keys) == count
    current_rows = json.loads(
        gzip.decompress(
            (CURRENT_F / "migration-reference-v1/after1554.json.gz").read_bytes()
        )
    )
    for qualified in keys:
        expected = rows[qualified]
        assert canonical(expected) == KNOWLEDGE["after_sha256"][qualified]
        assert (
            calculate_knowledge_read(domain=domain, key=qualified.split(":", 1)[1])
            == current_rows[qualified]
        )
    assert (
        rebind_r101_registry(KNOWLEDGE["registry_before"][domain], domain)
        == CURRENT_REFERENCE["registry_before"][domain]
    )
    assert advance_current_registry(
        CURRENT_REFERENCE["registry_before"][domain], domain
    ) == calculate_knowledge_registry(domain=domain)


@pytest.mark.parametrize(
    "field", ["yaoci", "detail", "shige", "verdict", "provenance", "repeated"]
)
def test_record_edge_rejects_unbound_literals_metadata_and_repeated_application(field):
    key = "山地剝:5"
    value = copy.deepcopy(REFERENCE["records"][key]["before"])
    if field == "repeated":
        value = rebind_r101_record(value, key)
    elif field == "provenance":
        value["text_provenance"]["commentary_content_sha256"] = "forged"
    else:
        value[field] += "forged"
    with pytest.raises(AssertionError):
        rebind_r101_record(value, key)


@pytest.mark.parametrize(
    "field", ["chart", "four_pillars", "calendar_context", "snapshot_text", "repeated"]
)
def test_business_edge_rejects_numerical_and_snapshot_changes(field):
    rows = json.loads(gzip.decompress((F / "before-business.json.gz").read_bytes()))
    key = "business22:0"
    value = copy.deepcopy(rows[key])
    value["snapshot_text"] = REFERENCE["business_edges"][key][
        "accepted_before_snapshot"
    ]
    if field == "repeated":
        value = rebind_r101_business(value, "business22", 0)
    elif field == "snapshot_text":
        value[field] += "forged"
    else:
        value[field]["forged"] = True
    with pytest.raises(AssertionError):
        rebind_r101_business(value, "business22", 0)


def test_render_edge_rejects_changed_notes_and_repeated_additions():
    value = copy.deepcopy(REFERENCE["render_rows"]["山地剝:5"]["before"])
    changed = rebind_r101_render_row(value)
    assert changed != value
    with pytest.raises(AssertionError):
        rebind_r101_render_row(changed)
    value["commentary_notes"].append("forged")
    with pytest.raises(AssertionError):
        rebind_r101_render_row(value)


def test_metadata_edge_leaves_words_and_numbers_exact_and_refuses_new_or_unknown_identity():
    for name in [
        "record",
        "lines",
        "tips",
        "text",
        "answer",
        "notes",
        "number",
        "chart",
        "four_pillars",
        "calendar_context",
        "dayun",
        "judge",
    ]:
        value = {name: {"source_catalogue_version": 11, "word": "132条"}}
        assert rebind_r101_metadata(value) == value
    for name, (before, after) in KNOWLEDGE["provenance_pairs"].items():
        assert rebind_r101_metadata({"provenance": {name: before}}) == {
            "provenance": {name: after}
        }
        for bad in [after, "forged"]:
            with pytest.raises(AssertionError):
                rebind_r101_metadata({"provenance": {name: bad}})
    old, new = FOOTER_ADDENDUM["exact_metadata_footer_pairs"][0]
    assert rebind_r101_metadata({"snapshot_text": old}) == {"snapshot_text": new}
    assert rebind_r101_metadata({"snapshot_text": "prefix " + old}) == {
        "snapshot_text": "prefix " + old
    }
    for name in ["text", "answer", "notes", "record"]:
        assert rebind_r101_metadata({name: old}) == {name: old}


@pytest.mark.parametrize(
    "fault",
    [
        "none",
        "header",
        "commentary",
        "catalogue",
        "gateway",
        "renderer",
        "missing",
        "rebound_source",
    ],
)
def test_complete_current_source_edge_accepts_exact_graph_and_rejects_mutations(
    fault, tmp_path
):
    from tests.heluo_current_source_reference import ENVELOPE as current_envelope

    paths = list(current_envelope["data"]) + list(current_envelope["code"])
    paths += [
        "src/fatebridge/data/" + source["source_path"]
        for source in CURRENT_CATALOGUE["sources"]
    ]
    for name in set(paths):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    assert assert_r101_source_edge(tmp_path)
    if fault == "none":
        return
    if fault in ["gateway", "renderer"]:
        name = "src/fatebridge/core/" + (
            "numerology_knowledge.py" if fault == "gateway" else "heluo_texts.py"
        )
        path = tmp_path / name
        path.write_text(path.read_text() + "\nauthority_certified = True\n")
    elif fault == "missing":
        (tmp_path / paths[-1]).unlink()
    else:
        name = list(ENVELOPE["data"])[
            {"header": 0, "commentary": 1, "catalogue": 2, "rebound_source": 0}[fault]
        ]
        path = tmp_path / name
        data = json.loads(path.read_bytes())
        data["scope"] = str(data.get("scope")) + "forged"
        path.write_text(json.dumps(data, ensure_ascii=False))
        if fault == "rebound_source":
            catalogue = tmp_path / list(ENVELOPE["data"])[2]
            cat = json.loads(catalogue.read_bytes())
            next(s for s in cat["sources"] if s["key"] == "yaoci_collation")[
                "canonical_content_sha256"
            ] = canonical(data)
            catalogue.write_text(json.dumps(cat, ensure_ascii=False))
    with pytest.raises((AssertionError, FileNotFoundError)):
        assert_r101_source_edge(tmp_path)

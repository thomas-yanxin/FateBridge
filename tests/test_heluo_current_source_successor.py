"""Fixed source transitions reject altered facts, repeated use and changed code."""

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
from tests.heluo_current_source_reference import (
    CURRENT_CATALOGUE,
    ENVELOPE,
    REFERENCE,
    ROOT,
    F,
    advance_current_business,
    advance_current_metadata,
    advance_current_record,
    advance_current_registry,
    advance_current_render_row,
    advance_source_identity,
    assert_current_source_edge,
    canonical,
)


def test_all_frozen_inputs_precede_consumer_edits_and_no_independent_credit_is_created():
    freeze = json.loads((F / "pre-consumer-freeze.json").read_bytes())
    assert freeze["before_any_existing_test_or_shared_runtime_edits"]
    for name, digest in freeze["files"].items():
        assert hashlib.sha256((F / name).read_bytes()).hexdigest() == digest, name
    assert freeze["independent_readers_added"] == freeze["new_real_world_outcomes"] == 0
    assert freeze["goal_complete"] is False
    assert assert_current_source_edge(ROOT)


def test_complete384_records_statuses_and_all1554_knowledge_outputs_are_fixed():
    for key, edge in REFERENCE["records"].items():
        gua, pos = key.rsplit(":", 1)
        expected = advance_current_record(edge["before"], key)
        assert yao_text(gua, int(pos)) == expected
        assert (
            heluo_texts.text_status_snapshot(expected)
            == REFERENCE["statuses_after"][key]
        )
    rows = json.loads(
        gzip.decompress((F / "migration-reference-v1/after1554.json.gz").read_bytes())
    )
    assert len(rows) == 1554
    for qualified, expected in rows.items():
        domain, key = qualified.split(":", 1)
        assert calculate_knowledge_read(domain=domain, key=key) == expected, qualified
    for domain in ["heluo", "canping"]:
        assert advance_current_registry(
            REFERENCE["registry_before"][domain], domain
        ) == calculate_knowledge_registry(domain=domain)


@pytest.mark.parametrize(
    "field", ["yaoci", "detail", "shige", "verdict", "provenance", "repeated"]
)
def test_record_edge_rejects_unreviewed_words_metadata_and_repeated_application(field):
    key = "地雷復:3"
    value = copy.deepcopy(REFERENCE["records"][key]["before"])
    if field == "repeated":
        value = advance_current_record(value, key)
    elif field == "provenance":
        value["text_provenance"]["commentary_content_sha256"] = "forged"
    else:
        value[field] += "forged"
    with pytest.raises(AssertionError):
        advance_current_record(value, key)


@pytest.mark.parametrize(
    "field", ["chart", "four_pillars", "calendar_context", "snapshot_text", "repeated"]
)
def test_business_transition_rejects_changes_to_math_or_the_frozen_snapshot(field):
    rows = json.loads(
        gzip.decompress(
            (F / "migration-reference-v1/before-business.json.gz").read_bytes()
        )
    )
    value = copy.deepcopy(rows["business22:0"])
    value["snapshot_text"] = REFERENCE["business_edges"]["business22:0"][
        "accepted_before_snapshot"
    ]
    if field == "repeated":
        value = advance_current_business(value, "business22", 0)
    elif field == "snapshot_text":
        value[field] += "forged"
    else:
        value[field]["forged"] = True
    with pytest.raises(AssertionError):
        advance_current_business(value, "business22", 0)


def test_metadata_does_not_replace_literal_words_numbers_or_partial_footer_lines():
    for field in [
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
        value = {
            field: {
                "provenance": {"source_catalogue_version": 13},
                "text": "None 138条",
            }
        }
        assert advance_current_metadata(value) == value
    old, new = REFERENCE["exact_metadata_footer_pairs"][0]
    assert advance_current_metadata({"snapshot_text": old}) == {"snapshot_text": new}
    assert advance_current_metadata({"snapshot_text": "prefix " + old}) == {
        "snapshot_text": "prefix " + old
    }
    for field, (before, after) in REFERENCE["provenance_pairs"].items():
        assert advance_current_metadata({"provenance": {field: before}}) == {
            "provenance": {field: after}
        }
        for bad in [after, "forged"]:
            with pytest.raises(AssertionError):
                advance_current_metadata({"provenance": {field: bad}})


def test_render_and_identity_edges_reject_changed_or_repeated_preimages():
    row = copy.deepcopy(REFERENCE["render_rows"]["地雷復:3"]["before"])
    changed = advance_current_render_row(row)
    with pytest.raises(AssertionError):
        advance_current_render_row(changed)
    row["lines"][0] = 1 - row["lines"][0]
    with pytest.raises(AssertionError):
        advance_current_render_row(row)
    for name, edge in ENVELOPE["data"].items():
        assert advance_source_identity(
            name, edge["before_raw_sha256"], edge["before_identity"]
        ) == (edge["after_raw_sha256"], edge["after_identity"])
        with pytest.raises(AssertionError):
            advance_source_identity(
                name, edge["after_raw_sha256"], edge["after_identity"]
            )


@pytest.mark.parametrize(
    "fault",
    [
        "none",
        "header",
        "commentary",
        "catalogue",
        "renderer",
        "gateway",
        "knowledge",
        "missing",
        "rebound",
    ],
)
def test_complete_source_graph_has_a_passing_positive_and_rejects_every_mutation(
    fault, tmp_path
):
    paths = set(ENVELOPE["data"]) | set(ENVELOPE["code"])
    paths |= {
        "src/fatebridge/data/" + s["source_path"] for s in CURRENT_CATALOGUE["sources"]
    }
    for name in paths:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    assert assert_current_source_edge(tmp_path)
    if fault == "none":
        return
    if fault in ["renderer", "gateway", "knowledge"]:
        name = {
            "renderer": "src/fatebridge/core/heluo_texts.py",
            "gateway": "src/fatebridge/core/numerology_knowledge.py",
            "knowledge": "src/fatebridge/services/knowledge.py",
        }[fault]
        p = tmp_path / name
        p.write_text(p.read_text() + "\nauthority_certified = True\n")
    elif fault == "missing":
        (tmp_path / "src/fatebridge/services/knowledge.py").unlink()
    else:
        name = list(ENVELOPE["data"])[
            (
                ["header", "commentary", "catalogue"].index(fault)
                if fault != "rebound"
                else 0
            )
        ]
        p = tmp_path / name
        value = json.loads(p.read_bytes())
        value["scope"] = str(value.get("scope")) + "forged"
        p.write_text(json.dumps(value, ensure_ascii=False))
        if fault == "rebound":
            p = tmp_path / list(ENVELOPE["data"])[2]
            cat = json.loads(p.read_bytes())
            next(s for s in cat["sources"] if s["key"] == "yaoci_collation")[
                "canonical_content_sha256"
            ] = canonical(value)
            p.write_text(json.dumps(cat, ensure_ascii=False))
    with pytest.raises((AssertionError, FileNotFoundError)):
        assert_current_source_edge(tmp_path)


def test_all46_complete_calculations_match_the_before_code_reference_without_numerical_tolerance(
    monkeypatch,
):
    from fatebridge.core.local_techniques.heluo import build_heluo_result
    from tests.heluo_current_source_reference import MATH_FIELDS

    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    before = json.loads(
        gzip.decompress(
            (F / "migration-reference-v1/before-business.json.gz").read_bytes()
        )
    )
    after = json.loads(
        gzip.decompress(
            (F / "migration-reference-v1/after-business.json.gz").read_bytes()
        )
    )
    groups = [
        ("business22", ROOT / "tests/fixtures/heluo_reading_delivery_v1/cases.json"),
        ("ben6", ROOT / "tests/fixtures/heluo_ben22_v1/case-search/cases.json"),
        ("bo6", ROOT / "tests/fixtures/heluo_bo23_v1/case-search/cases.json"),
        (
            "fuwuwang12",
            ROOT / "tests/fixtures/heluo_fu24_wuwang25_v1/case-search/cases.json",
        ),
    ]
    seen = set()
    for kind, path in groups:
        for index, case in enumerate(json.loads(path.read_bytes())["cases"]):
            label = (
                str(index)
                if kind == "business22"
                else case["label"] if kind == "fuwuwang12" else str(case["line"])
            )
            key = kind + ":" + label
            prior = copy.deepcopy(before[key])
            prior["snapshot_text"] = REFERENCE["business_edges"][key][
                "accepted_before_snapshot"
            ]
            assert advance_current_business(prior, kind, label) == after[key], key
            actual = build_heluo_result(**case["payload"])
            assert actual == after[key], key
            for field in MATH_FIELDS:
                assert actual[field] == before[key][field], (key, field)
            seen.add(key)
    assert seen == set(before) == set(after) and len(seen) == 46


def test_new_audit_checks_do_not_inflate_source_review_or_outcome_counts():
    from scripts.audit_numerology import fu24_wuwang25_source_checks

    result = fu24_wuwang25_source_checks()
    assert result["checks_passed"] and result["failures"] == []
    assert result["new_headers"] == result["new_complete_commentaries"] == 12
    assert result["new_parent_sections"] == 48
    assert result["source_pdf_pages"] == [175, 176, 177, 178, 179]
    assert result["extraction_only_pages"] == [180, 181, 182]
    assert (
        result["independent_reviews_added"]
        == result["new_model_evaluations"]
        == result["new_real_world_outcomes"]
        == 0
    )
    assert result["authority_certified"] is False

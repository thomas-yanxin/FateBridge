"""Association coverage: preserve source-first windows and full returned blocks."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "data/sukuyo-apparatus-before-production-v77.json"


def collector():
    path = Path(__file__).parents[1] / "scripts/check_sukuyo_apparatus_scope.py"
    spec = importlib.util.spec_from_file_location("apparatus_scope_checker", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.collect_apparatus_scope


def document(body, back):
    return (
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>'
        + body
        + "</body><back>"
        + back
        + "</back></text></TEI>"
    ).encode()


def test_entire_frozen_scope_is_delivered_with_distinct_base_and_coverage_hashes():
    from fatebridge.core.sukuyo_upstream_dawn import upstream_reference

    value = upstream_reference()
    expected = json.loads(FIXTURE.read_bytes())["source_data"]
    assert value["apparatus_coverage"]["source_data"] == expected
    assert (
        value["apparatus_coverage"]["source_bundle_sha256"]
        != value["source_bundle_sha256"]
    )
    assert value["source_bundle_hash_scope"] == "source_data_only_v76"
    assert expected["counts"]["all_selected_direct_record_nodes"] == 198
    assert expected["counts"]["context_only_added_record_nodes"] == 108
    assert expected["counts"]["additional_window_record_nodes"] == 0
    assert (
        len(value["source_data"]["sources"][1]["all_selected_linked_postposed_records"])
        == 22
    )


def test_actual_source_scope_keeps_inline_and_nested_evidence_and_endpoint_lines():
    from fatebridge.core.sukuyo_apparatus_scope import apparatus_reference

    data = apparatus_reference()["source_data"]
    src = next(s for s in data["sources"] if s["source_id"] == "T1435")
    rows = src["all_associated"]
    row = next(r for r in rows if r["attributes"].get("from") == "#beg0059007a")
    assert row["resolved_endpoints"]["from"][0]["start_line"] == "0059a22"
    assert row["resolved_endpoints"]["to"][0]["end_line"] == "0059a24"
    row = next(r for r in rows if r["attributes"].get("from") == "#beg0308002")
    assert row["resolved_endpoints"]["from"][0]["inside_note"]
    assert not row["window_associations"] and row["context_block_associations"]
    row = next(r for r in rows if r["attributes"].get("from") == "#beg0032b1101")
    assert "Q20_p0516a07" in row["xml_element"]
    assert "K21n0890_p0525a09" in row["xml_element"]
    assert len(src["embedded_unlinked_records_inside_selected_parents"]) == 17
    assert not data["claims"]["leap_short_month_priority_established"]


def test_non_anchor_element_endpoints_cover_an_intervening_window():
    raw = document(
        '<lb ed="T" n="a"/><p xml:id="first">甲</p>'
        '<lb ed="T" n="b"/><p xml:id="middle">乙</p>'
        '<lb ed="T" n="c"/><p xml:id="last">丙</p>',
        '<app from="#first" to="#last"><lem>甲乙丙</lem></app>',
    )
    observed = collector()(raw, "T", {"middle": ("b", "b")}, [], set())
    row = observed["all_associated"][0]
    assert row["window_associations"] == [
        {"window": "middle", "association": "from_to"}
    ]
    assert row["resolved_endpoints"]["to"][0]["tag"] == "p"


def test_from_without_to_includes_entire_element_not_only_start():
    raw = document(
        '<lb ed="T" n="a"/><p xml:id="span">甲<lb ed="T" n="b"/>乙</p>',
        '<app from="#span"><lem>甲乙</lem></app>',
    )
    observed = collector()(raw, "T", {"middle": ("b", "b")}, [], set())
    assert observed["all_associated"][0]["window_associations"] == [
        {"window": "middle", "association": "from_element"}
    ]


def test_inline_note_target_and_window_external_context_are_retained():
    raw = document(
        '<lb ed="T" n="a"/><p xml:id="context">甲<lb ed="T" n="b"/>'
        '<note place="inline"><seg xml:id="inside">乙</seg></note></p>',
        '<note target="#inside">校注</note>',
    )
    observed = collector()(raw, "T", {"selected": ("a", "a")}, ["context"], set())
    row = observed["all_associated"][0]
    assert not row["window_associations"]
    assert row["context_block_associations"]
    assert row["resolved_endpoints"]["target"][0]["inside_note"]
    assert len(observed["context_only_new"]) == 1


@pytest.mark.parametrize(
    "body,back,windows,contexts",
    [
        (
            '<lb ed="T" n="a"/><p xml:id="x">甲</p>',
            '<app from="#x" to="#missing"/>',
            {"w": ("a", "a")},
            [],
        ),
        (
            '<lb ed="T" n="a"/><p xml:id="x">甲</p>',
            '<note target="other.xml#x"/>',
            {"w": ("a", "a")},
            [],
        ),
        (
            '<lb ed="T" n="a"/><p xml:id="x">甲</p><p xml:id="x"/>',
            "",
            {"w": ("a", "a")},
            [],
        ),
        (
            '<lb ed="T" n="a"/><p xml:id="x"/><p xml:id="y"/>',
            '<app from="#y" to="#x"/>',
            {"w": ("a", "a")},
            [],
        ),
        ('<lb ed="T" n="a"/><p xml:id="x"/>', '<app to="#x"/>', {"w": ("a", "a")}, []),
        ('<lb ed="T" n="a"/><p xml:id="x"/>', "", {}, []),
        ('<lb ed="T" n="a"/><p xml:id="x"/>', "", {"w": ("missing", "missing")}, []),
        ('<lb ed="T" n="a"/><p xml:id="x"/>', "", {"w": ("a", "a")}, ["absent"]),
        (
            '<lb ed="T" n="a"/><p xml:id="x"/>',
            "<note>detached</note>",
            {"w": ("a", "a")},
            [],
        ),
    ],
)
def test_invalid_or_empty_association_inputs_fail_closed(body, back, windows, contexts):
    with pytest.raises(ValueError):
        collector()(document(body, back), "T", windows, contexts, set())


def test_nested_app_is_preserved_inside_parent_not_counted_as_another_direct_record():
    raw = document(
        '<lb ed="T" n="a"/><p xml:id="x">甲</p>',
        '<app from="#x"><lem>甲<note type="cf1">ref</note></lem>'
        '<rdg>乙<app n="nested"><lem>丙</lem></app></rdg></app>',
    )
    observed = collector()(raw, "T", {"w": ("a", "a")}, [], set())
    assert len(observed["all_associated"]) == 1
    assert len(observed["embedded_unlinked_records_inside_selected_parents"]) == 2
    assert (
        '<ns0:note type="cf1">ref</ns0:note>'
        in observed["all_associated"][0]["xml_element"]
    )


def test_changed_coverage_or_false_authority_needs_fresh_review():
    from fatebridge.core.sukuyo_apparatus_scope import validate_apparatus_reference

    for key in ("context_only_added_record_nodes", "all_selected_direct_record_nodes"):
        data = copy.deepcopy(json.loads(FIXTURE.read_bytes())["source_data"])
        data["counts"][key] = 0
        with pytest.raises(ValueError):
            validate_apparatus_reference(data)
    data = copy.deepcopy(json.loads(FIXTURE.read_bytes())["source_data"])
    data["claims"]["leap_short_month_priority_established"] = True
    with pytest.raises(ValueError):
        validate_apparatus_reference(data)

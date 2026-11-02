"""Frozen Lin19/Song6 sources keep wording, conditions and unresolved evidence."""

import hashlib
import json
import runpy
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core import heluo_poems as hp
from fatebridge.core import heluo_texts as ht
from fatebridge.core.heluo import _tiaowen, yao_text
from fatebridge.services.knowledge import calculate_knowledge_read
from tests.heluo_ben22_revision_reference import REVISION as R96_REVISION
from tests.heluo_current_source_reference import HEADER_COUNT, PENDING_COUNT
from tests.heluo_guan_shi_revision_reference import NEW_POEMS as R84_NEW_POEMS
from tests.heluo_guan_shi_revision_reference import PROPOSAL as R84_PROPOSAL
from tests.heluo_lin19_song6_revision_reference import (
    ADDENDUM,
    REVISION,
    rebind_r81_counts,
    rebind_r81_metadata,
)
from tests.heluo_shike_bi_revision_reference import REVISION as R92_REVISION
from tests.heluo_song_glyph_revision_reference import PROPOSAL as GLYPH_PROPOSAL
from tests.heluo_song_glyph_revision_reference import REVISION as GLYPH_REVISION
from tests.heluo_song_glyph_revision_reference import (
    rebind_r82_metadata,
    rebind_reviewed_song_readings,
)
from tests.test_agentic_nested_outputs import SPECS

F = Path(__file__).parent / "fixtures/heluo_lin19_song6_v1"
HISTORICAL_READINGS = json.loads((F / "final-accepted-readings.json").read_bytes())
READINGS = rebind_reviewed_song_readings(HISTORICAL_READINGS)
REFERENCE = json.loads((F / "source-adoption-reference.json").read_bytes())
UNCERTAIN = [(1, 1), (2, 2), (4, 2), (5, 3), (6, 1)]
FAULTS = [
    "header_word",
    "commentary_parent",
    "commentary_quote",
    "poem_negation",
    "poem_count_heading",
    "poem_count_deletion",
    "poem_uncertainty_note",
    "poem_clause_boundary",
    "poem_page",
    "poem_order",
]


@pytest.fixture(autouse=True)
def source_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path / "empty-ephe"))
    for fn in [ht._collation, ht._commentary_collation, hp._collation]:
        fn.cache_clear()
    yield
    for fn in [ht._collation, ht._commentary_collation, hp._collation]:
        fn.cache_clear()


def canonical(value):
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def test_reviewed_reference_binding_uses_frozen_source_objects_and_original_controls():
    assert REVISION["before_reference_adapter_edits"] is True
    assert REVISION["before_production_edits"] is False
    root = Path(__file__).parents[1]
    for name, digest in REVISION["reference_sha256"].items():
        assert hashlib.sha256((F / name).read_bytes()).hexdigest() == digest
    for name, binding in REVISION["source_bindings"].items():
        data = (root / name).read_bytes()
        edge_sha = binding["after_sha256"]
        edge_canonical = binding["after_canonical_sha256"]
        if name in GLYPH_PROPOSAL["proposed_file_sha256"]:
            assert edge_sha == GLYPH_PROPOSAL["before_source_sha256"][name]
            assert edge_canonical == GLYPH_PROPOSAL["before_canonical_sha256"][name]
            edge_sha = GLYPH_PROPOSAL["proposed_file_sha256"][name]
            edge_canonical = GLYPH_PROPOSAL["proposed_canonical_sha256"][name]
        if name in R84_PROPOSAL["proposed_file_sha256"]:
            assert edge_sha == R84_PROPOSAL["before_source_sha256"][name]
            assert edge_canonical == R84_PROPOSAL["before_canonical_sha256"][name]
            edge_sha = R84_PROPOSAL["proposed_file_sha256"][name]
            edge_canonical = R84_PROPOSAL["proposed_canonical_sha256"][name]
        if name in R92_REVISION["source_after_canonical"]:
            assert edge_sha == R92_REVISION["source_files_before_sha256"][name]
            assert edge_canonical == R92_REVISION["source_before_canonical"][name]
            edge_sha = R92_REVISION["source_files_after_sha256"][name]
            edge_canonical = R92_REVISION["source_after_canonical"][name]
        if name in R96_REVISION["source_files_after_sha256"]:
            assert edge_sha == R96_REVISION["source_files_before_sha256"][name]
            old_data = json.loads(
                (
                    Path(__file__).parent
                    / "fixtures/heluo_ben22_v1/before-source"
                    / name
                ).read_bytes()
            )
            assert edge_canonical == canonical(old_data)
            edge_sha = R96_REVISION["source_files_after_sha256"][name]
            edge_canonical = canonical(
                json.loads(
                    (
                        Path(__file__).parent
                        / "fixtures/heluo_ben22_v1/proposed"
                        / name
                    ).read_bytes()
                )
            )
        from tests.canping_witness_knowledge_revision import REVISION as r99
        from tests.canping_witness_source_edge import ENVELOPE

        if name == ENVELOPE["catalogue_path"]:
            assert edge_sha == ENVELOPE["before_catalogue_raw_sha256"]
            assert (
                edge_canonical
                == r99["provenance_pairs"]["source_catalogue_content_sha256"][0]
            )
            edge_sha = ENVELOPE["after_catalogue_raw_sha256"]
            edge_canonical = r99["provenance_pairs"]["source_catalogue_content_sha256"][
                1
            ]
        from tests.heluo_bo23_revision_reference import ENVELOPE as r101_envelope

        if name in r101_envelope["data"]:
            edge = r101_envelope["data"][name]
            assert edge_sha == edge["before_raw_sha256"]
            assert edge_canonical == edge["before_identity"]
            edge_sha = edge["after_raw_sha256"]
            edge_canonical = edge["after_identity"]
        from tests.heluo_current_source_reference import advance_source_identity

        edge_sha, edge_canonical = advance_source_identity(
            name, edge_sha, edge_canonical
        )
        assert hashlib.sha256(data).hexdigest() == edge_sha
        assert canonical(json.loads(data)) == edge_canonical
    assert GLYPH_REVISION["before_existing_test_or_auditor_edits"] is True
    assert GLYPH_REVISION["before_root_production_edits"] is True
    assert GLYPH_REVISION["coverage_changes"] == []
    legacy = "tests/heluo_source_revision_reference.py"
    assert (
        hashlib.sha256((root / legacy).read_bytes()).hexdigest()
        == REVISION["pre_edit_sha256"][legacy]
    )
    assert len(REVISION["changed_record_fields"]) == 24
    assert REVISION["expected_changed_summary_records"] == 120
    assert ADDENDUM["original_wrong_predicted_count"] == 120
    assert ADDENDUM["corrected_expected_changed_summary_records"] == 114
    assert (
        hashlib.sha256(
            (F / "reference-metadata-migration-v1.json").read_bytes()
        ).hexdigest()
        == ADDENDUM["original_migration_sha256"]
    )
    assert set(ADDENDUM["reviewed_poem_record_keys"]) <= set(
        ADDENDUM["reviewed_main_record_keys"]
    )


@pytest.mark.parametrize(
    "parent,key,owner",
    [
        ("text_provenance", "header_content_sha256", None),
        ("text_provenance", "commentary_corpus_id", None),
        ("text_provenance", "poem_transcription_policy", None),
        ("provenance", "source_catalogue_version", None),
        ("provenance", "source_catalogue_content_sha256", None),
        ("source_records", "loaded_file_sha256", "yaoci_collation"),
        ("source_records", "source_revision", "commentary_collation"),
        ("source_records", "review_status", "poem_collation"),
    ],
)
def test_reference_binding_rejects_unreviewed_metadata(parent, key, owner):
    value = {key: "forged source identity"}
    if owner:
        value["key"] = owner
    with pytest.raises(AssertionError):
        rebind_r81_metadata(value, parent)
    for owner82, pairs in GLYPH_REVISION["source_record_pairs"].items():
        for field82 in pairs:
            with pytest.raises(AssertionError):
                rebind_r82_metadata(
                    {"key": owner82, field82: "forged"}, "source_records"
                )
    for parent82 in ["text_provenance", "provenance"]:
        for field82 in GLYPH_REVISION[parent82 + "_pairs"]:
            with pytest.raises(AssertionError):
                rebind_r82_metadata({field82: "forged"}, parent82)


@pytest.mark.parametrize("field", ["detail", "reading_notes", "verdict", "number"])
def test_reference_binding_cannot_rewrite_body_notes_or_numeric_values(field):
    old_hash = REVISION["text_provenance_pairs"]["header_content_sha256"][0]
    old_footer = REVISION["exact_metadata_footer_pairs"][0][0]
    value = {field: ["篡改正文", old_hash, old_footer, 114, "10.0.0"]}
    assert rebind_r81_metadata(value) == value
    footer82 = GLYPH_REVISION["exact_metadata_footer_pairs"][0][0]
    assert rebind_r82_metadata({field: [footer82, 6, "2.4.1"]}) == {
        field: [footer82, 6, "2.4.1"]
    }
    assert rebind_r82_metadata({"snapshot_text": "prefix " + footer82}) == {
        "snapshot_text": "prefix " + footer82
    }
    assert rebind_r81_counts({field: 108}) == {field: 108}
    with pytest.raises(AssertionError):
        rebind_r81_counts({"coverage": {"header_collated": 109}})


def test_first_readings_all_amendments_and_primary_identities_are_preserved():
    freeze = json.loads((F / "source-reading-freeze.json").read_bytes())
    for name, digest in freeze["files"].items():
        assert hashlib.sha256((F / name).read_bytes()).hexdigest() == digest
    assert freeze["frozen_before_production_edits"] is True
    assert freeze["frozen_before_inherited_target_text_exposure"] is False
    first = json.loads((F / "source-only-verified-freeze.json").read_bytes())
    assert first["frozen_before_inherited_target_text_exposure"] is True
    assert freeze["original_correct_readings_restored_not_product_fixes"] == [
        "Song2王事",
        "Song3狂謀",
    ]
    assert freeze["unresolved_count"] == 5
    protocol = json.loads((F / "protocol.json").read_bytes())
    for row in protocol["primary_sources"]:
        assert (
            hashlib.sha256(
                (F / "primary" / (row["kind"] + ".pdf")).read_bytes()
            ).hexdigest()
            == row["sha256"]
        )
    assert (
        protocol["primary_sources"][0]["sha256"]
        != protocol["primary_sources"][1]["sha256"]
    )


@pytest.mark.parametrize("key", ["headers", "commentaries", "poems"])
def test_every_previous_source_entry_is_exact_and_totals_keep_their_units(key):
    data = {
        "headers": ht._collation,
        "commentaries": ht._commentary_collation,
        "poems": hp._collation,
    }[key]()
    before = REFERENCE["prefixes_preserved"][key]
    assert canonical(data["entries"][: before["count"]]) == before["canonical_sha256"]
    assert data["entries"][before["count"] : before["count"] + 6] == READINGS[key]
    assert ht.collation_summary()["collated_line_headers"] == HEADER_COUNT
    assert (
        ht.commentary_collation_summary()["pending_line_commentaries"] == PENDING_COUNT
    )
    poems = hp.collation_summary()
    assert (
        poems["collated_line_poem_groups"],
        poems["pending_line_poem_groups"],
        poems["collated_individual_poems"],
        poems["total_individual_poems"],
    ) == (48, 336, 117, None)


@pytest.mark.parametrize(
    "entry", READINGS["commentaries"], ids=lambda e: str(e["line"])
)
def test_all_six_complete_lin_commentaries_preserve_their_original_parents(entry):
    text = yao_text("地澤臨", entry["line"])
    assert text["commentary_sections"] == [
        dict(s, applicability=None) for s in entry["sections"]
    ]
    assert text["detail"] == "".join(s["text"] for s in entry["sections"])
    assert text["text_provenance"]["commentary_pdf_pages"] == entry["pdf_pages"]
    assert text["commentary_branch_selection"]["selected_section_ids"] == []
    assert text["text_provenance"]["automatic_branch_selection"] is False
    assert text["verdict"] == _tiaowen()["地澤臨"]["yao"][str(entry["line"])]["verdict"]
    assert text["shige"] == _tiaowen()["地澤臨"]["yao"][str(entry["line"])]["shige"]
    assert text["text_provenance"]["poem_status"] == "inherited_poem_source_unverified"


@pytest.mark.parametrize("entry", READINGS["poems"], ids=lambda e: str(e["line"]))
def test_every_song_poem_and_printed_clause_is_retained_without_selecting_one(entry):
    text = yao_text("天水訟", entry["line"])
    assert text["poem_sections"] == [
        dict(p, applicability=None) for p in entry["poems"]
    ]
    assert text["shige"] == "\n".join(p["text"] for p in entry["poems"])
    assert text["poem_selection"]["selected_poem_indices"] == []
    assert text["poem_selection"]["automatic_selection"] is False
    assert text["text_provenance"]["poem_heading_text"] == entry["heading_text"]
    assert text["text_provenance"]["poem_pdf_pages"] == entry["pdf_pages"]
    assert (
        text["text_provenance"]["inherited_shige"]
        == _tiaowen()["天水訟"]["yao"][str(entry["line"])]["shige"]
    )
    assert text["inherited_xiang_reference"]["status"].endswith(
        "unverified_by_poem_witness"
    )


@pytest.mark.parametrize(
    "expected", REFERENCE["cross_references"], ids=lambda r: str(r["source_line"])
)
def test_lin_references_keep_parent_conditions_and_no_printed_target_line(expected):
    text = yao_text("地澤臨", expected["source_line"])
    assert text["commentary_cross_references"] == [expected]
    assert (
        expected["target_line"] is None
        and expected["target_line_source_status"] == "not_printed"
    )
    assert (
        expected["applicability"] is None and expected["automatic_application"] is False
    )
    assert expected["replaces_chart"] is False
    summary = "\n".join(
        calculate_knowledge_read(
            domain="heluo", key=f"地澤臨:{expected['source_line']}"
        )["lines"]
    )
    assert expected["source_condition_label"] in summary
    assert "原文未印目标爻位" in summary and "不替代正式卦盘" in summary


def test_source_negation_crosspage_tail_and_count_conflict_stay_visible_in_summary():
    second = yao_text("天水訟", 2)
    assert (
        "時間理未明" in second["shige"]
        and "時聞理義明" in second["text_provenance"]["inherited_shige"]
    )
    three = yao_text("天水訟", 3)
    assert three["text_provenance"]["poem_heading_text"] == "訟卦三爻訣一首"
    assert len(three["poem_sections"]) == 3
    summary = "\n".join(
        calculate_knowledge_read(domain="heluo", key="天水訟:3")["lines"]
    )
    assert "原题訟卦三爻訣一首" in summary and "保留三首和原题" in summary
    six = yao_text("天水訟", 6)
    assert six["poem_sections"][1]["pdf_pages"] == [13]
    assert six["shige"].endswith("心戚戚。恍惚兩三頭。")


def test_late_dictionary_comparison_discloses_meaning_risk_without_claiming_glyph_resolution():
    late = json.loads((F / "late-qualification-reference.json").read_bytes())
    assert late["before_initial_production_edits"] is False
    assert late["before_late_qualification_source_edits"] is True
    assert late["old87_poem_texts_unchanged"] is True
    assert late["unresolved_reading_choicepoints"] == 6
    assert late["uncertain_poem_locations"] == 5
    assert late["newly_resolved_glyphs"] == 0
    old = json.loads((F / "accepted-readings.json").read_bytes())
    assert [p["text"] for e in HISTORICAL_READINGS["poems"] for p in e["poems"]] == [
        p["text"] for e in old["poems"] for p in e["poems"]
    ]
    summary = "\n".join(
        calculate_knowledge_read(domain="heluo", key="天水訟:6")["lines"]
    )
    # These late R81 qualifications remain in the historical record. R82 then
    # selected a glyph from the complete embedded pixels, still by one reader.
    prior_notes = HISTORICAL_READINGS["poems"][-1]["poems"][0]["reading_notes"]
    assert any("懼／懽" in note for note in prior_notes)
    assert all(note in summary for note in GLYPH_PROPOSAL["reading_notes"]["6:1"])
    assert "不能再释为无需畏惧" in summary
    assert "独立复核未完成" in summary


def test_auditor_keeps_unreviewed_poems_distinct_from_read_commentary_and_preserves_conflict(
    monkeypatch,
):
    script = Path(__file__).parents[1] / "scripts/audit_numerology.py"
    monkeypatch.syspath_prepend(str(script.parent))
    audit = runpy.run_path(str(script))
    poem_audit = audit["poem_collation_checks"]()
    assert poem_audit["checks_passed"] is True
    assert poem_audit["pending_poem_controls_checked"] == 336
    original_control = yao_text("地水師", 1)
    assert (
        original_control["text_provenance"]["commentary_status"]
        == "source_commentary_visually_collated"
    )
    assert (
        original_control["text_provenance"]["poem_status"]
        == "source_poems_visually_collated"
    )
    frozen = next(
        e
        for e in R84_NEW_POEMS["entries"]
        if (e["hexagram"], e["line"]) == ("地水師", 1)
    )
    assert original_control["poem_sections"] == [
        dict(p, applicability=None) for p in frozen["poems"]
    ]
    assert (
        original_control["text_provenance"]["inherited_shige"]
        == _tiaowen()["地水師"]["yao"]["1"]["shige"]
    )
    source = audit["lin19_song6_source_checks"]()
    assert source["checks_passed"] is True
    assert source["all_new_literal_heading_counts_agree"] is False
    assert source["source_heading_count_conflicts"] == [
        REFERENCE["source_count_conflict"]
    ]


@pytest.mark.parametrize("line,index", UNCERTAIN)
def test_each_unresolved_reading_remains_qualified_in_summary(line, index):
    text = yao_text("天水訟", line)
    poem = text["poem_sections"][index - 1]
    historical = HISTORICAL_READINGS["poems"][line - 1]["poems"][index - 1]
    assert "glyph_choice_unresolved" in historical["review_status"]
    assert any("暂" in note or "未定" in note for note in historical["reading_notes"])
    assert (
        poem["review_status"]
        == "single_reader_embedded_pixel_recheck; independent_second_review_pending"
    )
    assert poem["reading_notes"] == GLYPH_PROPOSAL["reading_notes"][f"{line}:{index}"]
    summary = "\n".join(
        calculate_knowledge_read(domain="heluo", key=f"天水訟:{line}")["lines"]
    )
    assert all(note in summary for note in poem["reading_notes"])


def corrupt_source(kind, monkeypatch, tmp_path):
    module, attr = (
        (ht, "COLLATION_PATH")
        if kind == "header_word"
        else (
            (ht, "COMMENTARY_PATH")
            if kind.startswith("commentary")
            else (hp, "COLLATION_PATH")
        )
    )
    data = json.loads(getattr(module, attr).read_bytes())
    gua = "地澤臨" if module is ht else "天水訟"
    pos = (
        2
        if kind in {"header_word", "poem_negation"}
        else (
            5
            if kind.startswith("commentary")
            else 4 if kind == "poem_uncertainty_note" else 3
        )
    )
    entry = next(
        e for e in data["entries"] if e["hexagram"] == gua and e["line"] == pos
    )
    if kind == "header_word":
        entry["yaoci"] = entry["yaoci"].replace("无", "無")
    elif kind == "commentary_parent":
        entry["sections"][1], entry["sections"][2] = (
            entry["sections"][2],
            entry["sections"][1],
        )
    elif kind == "commentary_quote":
        entry["sections"][2]["text"] = entry["sections"][2]["text"].replace(
            "節", "歸妹"
        )
    elif kind == "poem_negation":
        entry["poems"][0]["text"] = entry["poems"][0]["text"].replace("未明", "義明")
    elif kind == "poem_count_heading":
        entry["heading_text"] = entry["heading_text"].replace("一首", "三首")
    elif kind == "poem_count_deletion":
        entry["poems"] = entry["poems"][:1]
    elif kind == "poem_uncertainty_note":
        entry["poems"][1]["reading_notes"] = []
    elif kind == "poem_clause_boundary":
        entry["poems"][0]["printed_clauses"][0] += "字"
    elif kind == "poem_page":
        entry["pdf_pages"] = [11]
    elif kind == "poem_order":
        entry["poems"].reverse()
    else:
        raise AssertionError(kind)
    dest = tmp_path / (kind + ".json")
    dest.write_text(json.dumps(data, ensure_ascii=False))
    monkeypatch.setattr(module, attr, dest)
    return gua + ":" + str(pos)


@pytest.mark.parametrize("kind", FAULTS)
def test_changed_words_parents_count_or_uncertainty_are_source503(
    kind, monkeypatch, tmp_path
):
    key = corrupt_source(kind, monkeypatch, tmp_path)
    spec = SPECS["knowledge_read"]
    result = execute_tool(
        spec, spec.request_model.model_validate(dict(domain="heluo", key=key))
    )
    assert result["status_code"] == 503 and result["retryable"] is False

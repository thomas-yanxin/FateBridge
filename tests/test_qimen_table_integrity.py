"""Source-internal counterexamples must survive an engine that mimics a typo."""

import json
import shutil
from pathlib import Path

import pytest

from fatebridge.validation import qimen as engine_audit
from fatebridge.validation.qimen_table_integrity import (
    audit_printed_table_integrity,
    audit_table_source_context,
    unrepresented_walk_anomalies,
)

TABLES = Path(__file__).parent / "fixtures/qimen_classical_v3"
CONTEXT = Path(__file__).parent / "fixtures/qimen_classical_v12"


@pytest.fixture
def copied_tables(tmp_path):
    manifest = json.loads((TABLES / "sources-and-tables.json").read_text())
    shutil.copy2(TABLES / manifest["excerpt_file"], tmp_path / manifest["excerpt_file"])
    (tmp_path / "sources-and-tables.json").write_text(json.dumps(manifest))
    return tmp_path


@pytest.fixture
def copied_context(tmp_path):
    shutil.copytree(CONTEXT, tmp_path / "context")
    return tmp_path / "context"


def mutate(directory, filename, change):
    p = directory / filename
    data = json.loads(p.read_text())
    change(data)
    p.write_text(json.dumps(data, ensure_ascii=False))


def test_two_source_sequences_are_checked_without_calling_production_engine(
    monkeypatch,
):
    def forbidden(*args, **kwargs):
        raise AssertionError(
            "Source-internal diagnostic must not call production leaders"
        )

    monkeypatch.setattr(engine_audit, "_qimen_zhifu_zhishi", forbidden)
    r = audit_printed_table_integrity(TABLES)
    assert [
        (d["dun"], d["ju"], d["hour"], d["printed_number"], d["walk_implied_number"])
        for d in r["anomalous_cells"]
    ] == [("阴遁", 9, "庚辰", 1, 2), ("阴遁", 4, "癸亥", 9, 8)]
    assert r["printed_column_count"] == 108 and r["printed_hour_rows"] == 1080
    assert (
        r["adjacent_transition_checks"] == 972
        and len(r["adjacent_transition_defects"]) == 3
    )
    assert (
        r["nine_step_closure_checks"] == 108
        and len(r["nine_step_closure_defects"]) == 1
    )
    assert r["nine_step_closure_defects"][0]["last_hour"] == "癸亥"
    assert not r["production_engine_used"] and not r["emendation_adopted"]
    assert (
        not r["printing_error_established"]
        and not r["whole_book_conformance_established"]
    )
    assert r["independent_new_reference_cases"] == 0


def test_original_sources_and_known_disagreements_are_not_rewritten():
    before = (TABLES / "sources-and-tables.json").read_bytes()
    r = audit_printed_table_integrity(TABLES)
    engine = engine_audit.audit_numeric_tables(TABLES)
    assert unrepresented_walk_anomalies(r, engine["disagreements"]) == []
    assert len(engine["disagreements"]) == 2 and engine["matched_case_count"] == 1078
    assert (TABLES / "sources-and-tables.json").read_bytes() == before


def test_engine_forced_to_mimic_printed_numbers_cannot_erase_source_anomalies():
    r = audit_printed_table_integrity(TABLES)
    assert len(unrepresented_walk_anomalies(r, [])) == 2
    first = r["anomalous_cells"][0]
    assert len(unrepresented_walk_anomalies(r, [first])) == 1
    unrelated = {**first, "field": "star"}
    assert len(unrepresented_walk_anomalies(r, [unrelated])) == 2


def test_deleting_the_manifest_unresolved_list_does_not_hide_defects(copied_tables):
    mutate(copied_tables, "sources-and-tables.json", lambda d: d.update(unresolved=[]))
    assert len(audit_printed_table_integrity(copied_tables)["anomalous_cells"]) == 2


def test_new_synthetic_bad_cell_is_detected_without_a_hardcoded_case_list(
    copied_tables,
):
    def change(d):
        tokens = d["tables"][0]["palace_pairs"][0].split()
        assert tokens[2] == "83"
        tokens[2] = "87"
        d["tables"][0]["palace_pairs"][0] = " ".join(tokens)

    mutate(copied_tables, "sources-and-tables.json", change)
    r = audit_printed_table_integrity(copied_tables)
    assert len(r["anomalous_cells"]) == 3
    d = next(d for d in r["anomalous_cells"] if d["dun"] == "阳遁")
    assert (d["hour"], d["printed_number"], d["walk_implied_number"]) == ("丙寅", 7, 3)


def test_raw_centre_five_is_never_replaced_with_hosted_two(copied_tables):
    def change(d):
        tokens = d["tables"][0]["palace_pairs"][3].split()
        assert tokens[1] == "95"
        tokens[1] = "92"
        d["tables"][0]["palace_pairs"][3] = " ".join(tokens)

    mutate(copied_tables, "sources-and-tables.json", change)
    r = audit_printed_table_integrity(copied_tables)
    d = next(d for d in r["anomalous_cells"] if d["dun"] == "阳遁")
    assert (d["hour"], d["printed_number"], d["walk_implied_number"]) == ("乙未", 2, 5)


def test_a_self_consistent_shift_does_not_certify_absolute_head_placement(
    copied_tables,
):
    def change(d):
        tokens = d["tables"][0]["palace_pairs"][0].split()
        d["tables"][0]["palace_pairs"][0] = " ".join(
            t[0] + str(int(t[1]) % 9 + 1) for t in tokens
        )

    mutate(copied_tables, "sources-and-tables.json", change)
    r = audit_printed_table_integrity(copied_tables)
    assert len(r["anomalous_cells"]) == 2
    assert (
        not r["absolute_head_placement_validated"] and not r["star_numbers_validated"]
    )


@pytest.mark.parametrize("part", ["table", "column", "row", "invalid_digit"])
def test_incomplete_or_malformed_corpus_is_rejected(copied_tables, part):
    def change(d):
        if part == "table":
            d["tables"].pop()
        elif part == "column":
            d["tables"][0]["palace_pairs"].pop()
        elif part == "row":
            d["tables"][0]["palace_pairs"][0] = "11 92"
        else:
            d["tables"][0]["palace_pairs"][0] = (
                "00 " + d["tables"][0]["palace_pairs"][0].split(" ", 1)[1]
            )

    mutate(copied_tables, "sources-and-tables.json", change)
    with pytest.raises(ValueError):
        audit_printed_table_integrity(copied_tables)


@pytest.mark.parametrize("kind", ["path", "bytes"])
def test_source_pointer_and_bytes_are_checked(copied_tables, kind):
    if kind == "path":
        mutate(
            copied_tables,
            "sources-and-tables.json",
            lambda d: d.update(excerpt_file="../outside.pdf"),
        )
    else:
        p = copied_tables / "siku-pages-62-71.pdf"
        p.write_bytes(p.read_bytes() + b"changed")
    with pytest.raises(ValueError):
        audit_printed_table_integrity(copied_tables)


def test_catalogue_title_match_is_not_scan_authentication():
    r = audit_table_source_context(CONTEXT)
    assert len(r["catalogue_observations"]) == 3
    assert (
        r["bibliographic_binding_fields_conflict"]
        and not r["binding_priority_resolved"]
    )
    assert r["institutional_rule_pages_read"] == 0
    assert not r["selected_scan_lineage_authenticated"]
    assert not r["catalogue_observations_live_rechecked_by_this_function"]
    assert "尚未數位化" in r["catalogue_observations"][0]["digitization_message"]
    assert all(r["publication_year"] == "不詳" for r in r["catalogue_observations"][1:])


@pytest.mark.parametrize("record", range(3))
@pytest.mark.parametrize(
    "field",
    ["readable_rule_images_verified", "selected_third_party_pdf_lineage_authenticated"],
)
def test_catalogue_record_cannot_be_relabelled_as_a_read_rule_image(
    copied_context, record, field
):
    def change(d):
        d["catalogue_observations"][record][field] = True

    mutate(copied_context, "source-diagnostics.json", change)
    with pytest.raises(ValueError, match="不能升级"):
        audit_table_source_context(copied_context)


@pytest.mark.parametrize("index", range(3))
def test_inaccessible_catalogue_entries_cannot_be_silently_deleted(
    copied_context, index
):
    mutate(
        copied_context,
        "source-diagnostics.json",
        lambda d: d["catalogue_observations"].pop(index),
    )
    with pytest.raises(ValueError, match="三条"):
        audit_table_source_context(copied_context)


def test_binding_conflict_is_derived_and_not_a_fixed_label(copied_context):
    def change(d):
        npm = d["catalogue_observations"][0]
        npm["extended_binding"] = npm["main_binding"]

    mutate(copied_context, "source-diagnostics.json", change)
    r = audit_table_source_context(copied_context)
    assert (
        not r["bibliographic_binding_fields_conflict"]
        and r["binding_priority_resolved"]
    )

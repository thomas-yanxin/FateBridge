"""Knowledge access must consume the same reviewed witness source as charts."""

import json
from pathlib import Path

import pytest

from fatebridge.core import canping_texts
from fatebridge.core import numerology_knowledge as gateway
from tests.canping_witness_knowledge_revision import (
    REVISION,
    rebind_r99_knowledge,
    rebind_r99_metadata,
)
from tests.heluo_current_source_reference import CATALOGUE_VERSION


@pytest.mark.parametrize("domain", ["heluo", "canping"])
def test_both_reference_registries_load_the_new_catalogue(domain):
    out = gateway.build_registry(domain)
    assert out["provenance"]["source_catalogue_version"] == CATALOGUE_VERSION
    assert out["provenance"]["whole_books_collated"] is False
    assert out["provenance"]["real_world_efficacy_validated"] is False


def test_all1170_records_retain_actual_primary_and_all_page_bound_occurrences():
    source = canping_texts.source_readings()
    total = 0
    for entry in source["entries"]:
        for kind in entry["cells"]:
            key = f"{entry['element']}.{entry['number']}.{kind}"
            out = gateway.read_reference(
                domain="canping", category="text_cells", key=key
            )
            assert out["reference_details"]["record"] == canping_texts.lookup_record(
                entry["element"], entry["number"], kind
            )
            sources = out["provenance"]["source_records"]
            witness = next(v for v in sources if v["key"] == "text_witnesses")
            assert witness["source_revision"] == "1.2.0"
            assert (
                witness["canonical_content_sha256"]
                == canping_texts.WITNESS_CONTENT_SHA256
            )
            assert out["reference_details"]["personal_applicability_assessed"] is False
            total += 1
    assert total == 1170


@pytest.mark.parametrize("kind", ["male", "female", "luck"])
def test_ambiguous_number_is_disclosed_in_summary_and_both_texts_are_visible(kind):
    out = gateway.read_reference(
        domain="canping", category="text_cells", key=f"金.3322.{kind}"
    )
    rows = out["reference_details"]["record"]["selection"]["witnesses"]
    assert [r["header_pdf_page"] for r in rows] == [87, 94]
    assert len(rows) == 2
    assert all(r["number_occurrence_ambiguous"] is True for r in rows)
    text = "\n".join(out["tips"])
    assert "同一文明書局本同号有多处正文" in text
    assert "号文归属未裁定" in text
    for r in rows:
        assert r["text"] in text
    assert out["tips"] == out["lines"]


def test_unmatched2328_does_not_fill3328_or_resolve_primary_uncertainty():
    out = gateway.read_reference(
        domain="canping", category="text_cells", key="金.3328.male"
    )
    assert "witnesses" not in out["reference_details"]["record"]["selection"]
    uncertain = gateway.read_reference(
        domain="canping", category="text_cells", key="金.2524.male"
    )
    assert uncertain["reference_details"]["record"]["text"].startswith("□")
    assert "□是编辑未定字标记" in "\n".join(uncertain["tips"])


@pytest.mark.parametrize(
    "field",
    ["source_catalogue_version", "source_catalogue_content_sha256", "source_records"],
)
def test_knowledge_version_migration_rejects_unreviewed_old_metadata(field):
    before = {k: pair[0] for k, pair in REVISION["provenance_pairs"].items()}
    before["source_records"] = [
        {
            "key": "text_witnesses",
            **{
                k: pair[0]
                for k, pair in REVISION["source_record_pairs"]["text_witnesses"].items()
            },
        }
    ]
    if field == "source_records":
        before[field][0]["loaded_file_sha256"] = "unreviewed"
    else:
        before[field] = "unreviewed"
    with pytest.raises(AssertionError):
        rebind_r99_metadata({"provenance": before})


def test_knowledge_migration_preserves_literal_body_and_unrelated_fields():
    literal = REVISION["provenance_pairs"]["source_catalogue_content_sha256"][0]
    old = {
        "domain": "heluo",
        "category": "line_texts",
        "provenance": {k: pair[0] for k, pair in REVISION["provenance_pairs"].items()},
        "reference_details": {"record": {"text": literal}},
        "unreviewed_other_field": literal,
    }
    current = rebind_r99_knowledge(old)
    assert current["reference_details"] == old["reference_details"]
    assert current["unreviewed_other_field"] == literal
    assert old["provenance"]["source_catalogue_version"] == 10
    with pytest.raises(AssertionError):
        rebind_r99_knowledge(current)

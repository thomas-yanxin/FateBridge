"""Source binding and reference applicability, without new visual-collation claims."""

import hashlib
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.application.execution import execute_tool
from fatebridge.core import numerology_knowledge as gateway
from fatebridge.core.output_reference import NumerologyKnowledgeDetails
from fatebridge.services.knowledge import (
    calculate_knowledge_read,
    calculate_knowledge_registry,
)
from fatebridge.services.tool_catalog import CATALOG
from tests.heluo_source_facts import CURRENT_CATALOGUE, HEADER_COUNT, PENDING_COUNT

DATA = Path(gateway.__file__).parents[1] / "data"
F = Path(__file__).parent / "fixtures/numerology_knowledge_v1"
SPECS = {s.key: s for s in CATALOG if s.key in ["knowledge_read", "knowledge_registry"]}


@pytest.mark.parametrize("domain", ["heluo", "canping"])
def test_registry_separates_keyspace_review_counts_and_applicability(domain):
    result = calculate_knowledge_registry(domain=domain)
    assert "error" not in result and result["source"] == gateway.SOURCE
    assert result["provenance"]["reference_only"] is True
    assert result["provenance"]["whole_books_collated"] is False
    categories = {c["name"]: c for c in result["domains"][0]["categories"]}
    category = categories["line_texts" if domain == "heluo" else "text_cells"]
    assert category["keys_complete"] is False and "keys" not in category
    assert len(category["keys_sample"]) == 20
    coverage = category["coverage"]
    if domain == "heluo":
        assert category["count"] == 384
        assert (
            coverage["header_collated"]
            == coverage["commentary_collated"]
            == HEADER_COUNT
        )
        assert (
            coverage["header_pending"]
            == coverage["commentary_pending"]
            == PENDING_COUNT
        )
        assert (
            coverage["poem_groups_collated"] == 48
            and coverage["poem_groups_pending"] == 336
        )
    else:
        assert category["count"] == 1170
        assert coverage["clear_reading_cells"] == 1123
        assert coverage["unresolved_reading_cells"] == 47
        assert categories["schedule_profiles"]["count"] == 3
        assert categories["schedule_clauses"]["count"] == 6


def test_global_registry_does_not_attribute_added_domains_to_legacy_hover_source():
    result = calculate_knowledge_registry()
    assert [d["domain"] for d in result["domains"]] == [
        "astro",
        "bazi",
        "liureng",
        "qimen",
        "heluo",
        "canping",
        "human_design",
    ]
    assert (
        result["source"] == "fatebridge_mixed_knowledge"
        and result["bundle_version"] is None
    )
    for domain in result["domains"][:4]:
        assert domain["source"] == "xingque_hover_docs"
        assert calculate_knowledge_registry(domain=domain["domain"])["domains"] == [
            domain
        ]
    assert all(d["source"] == gateway.SOURCE for d in result["domains"][4:6])
    from fatebridge.core.human_design_knowledge import SOURCE as HUMAN_DESIGN_SOURCE

    assert result["domains"][6]["source"] == HUMAN_DESIGN_SOURCE


def test_all1170_bodies_match_version_bound_literal_records_and_columns():
    # Binding to existing records, not an independent reading of their images.
    data = json.loads((DATA / "canping/text-collation-v1.json").read_bytes())
    count = 0
    for entry in data["entries"]:
        for kind, literal in entry["cells"].items():
            key = f"{entry['element']}.{entry['number']}.{kind}"
            result = gateway.read_reference(
                domain="canping", category="text_cells", key=key
            )
            record = result["reference_details"]["record"]
            assert (
                record["text"] == literal and record["selection"]["corpus_key"] == key
            )
            assert (
                record["selection"]["column"]
                == {
                    "male": "upper_male",
                    "female": "middle_female",
                    "luck": "lower_shared_luck",
                }[kind]
            )
            if kind in entry.get("reading_uncertainties", {}):
                assert record["selection"]["cell_status"] == "source_reading_uncertain"
            count += 1
    assert count == 1170


def test_all384_line_references_leave_conditions_and_poems_unselected():
    from fatebridge.core.heluo import _tiaowen

    count = 0
    for gua, value in _tiaowen().items():
        for position in value["yao"]:
            result = gateway.read_reference(
                domain="heluo", category="line_texts", key=f"{gua}:{position}"
            )
            record = result["reference_details"]["record"]
            assert result["reference_only"] is True
            assert (
                result["reference_details"]["personal_applicability_assessed"] is False
            )
            assert record["text_provenance"]["automatic_branch_selection"] is False
            assert all(
                s["applicability"] is None
                for s in record.get("commentary_sections", [])
            )
            assert all(
                s["applicability"] is None for s in record.get("poem_sections", [])
            )
            count += 1
    assert count == 384


@pytest.mark.parametrize(
    "profile", ["bazi_appendix_v1", "bazi_continuous_v1", "legacy_minggong_v1"]
)
def test_policy_reference_preserves_roles_and_has_no_personal_date(profile):
    from fatebridge.core.canping_schedule_basis import APPLIED, clause_role

    result = gateway.read_reference(domain="canping", category=None, key=profile)
    record = result["reference_details"]["record"]
    assert (
        record["actual_start_at"] is None
        and record["personal_applicability_assessed"] is False
    )
    assert record["applied_clause_ids_for_profile"] == list(APPLIED[profile])
    assert all(
        c["role_for_profile"] == clause_role(profile, c) for c in record["clauses"]
    )
    assert (
        record["sources"]["heluo_najda"]["pdf_sha256"]
        != record["sources"]["sanming_nlc"]["pdf_sha256"]
    )


@pytest.mark.parametrize(
    "domain,key",
    [
        ("heluo", "乾為天:1"),
        ("canping", "火.2434.female"),
        ("canping", "appendix_integer_rounding"),
    ],
)
def test_category_omission_resolves_exact_key_without_cross_domain_fallback(
    domain, key
):
    result = gateway.read_reference(domain=domain, category=None, key=key)
    assert result["key"] == key and result["provenance"]["domain"] == domain
    wrong = calculate_knowledge_read(
        domain="canping" if domain == "heluo" else "heluo", key=key
    )
    assert wrong["status_code"] == 400


def test_missing_row_and_unselected_column_do_not_become_printed_blanks():
    missing = gateway.read_reference(
        domain="canping", category=None, key="火.3034.female"
    )["reference_details"]["record"]
    unselected = gateway.read_reference(
        domain="canping", category=None, key="水.3330.unselected"
    )["reference_details"]["record"]
    assert missing["text"] == unselected["text"] == ""
    assert missing["selection"]["cell_status"] == "row_absent_in_local_corpus"
    assert unselected["selection"]["cell_status"] == "not_selected_missing_gender"


@pytest.mark.parametrize(
    "fault", ["citation", "title", "text", "role", "all_copies_wrong_query"]
)
def test_forged_consistent_card_still_binds_to_original_request(fault):
    spec = SPECS["knowledge_read"]
    request = spec.request_model.model_validate(
        dict(domain="canping", key="appendix_integer_rounding")
    )
    output = calculate_knowledge_read(**request.model_dump())
    if fault == "citation":
        output["citation"] = "另一书第1页"
    elif fault == "title":
        output["title"] = "already completely certified"
    elif fault == "text":
        output["reference_details"]["record"]["text"] = "伪造原文"
    elif fault == "role":
        output["reference_details"]["record"]["role_by_profile"][
            "bazi_continuous_v1"
        ] = "applied_rule"
    else:
        output = calculate_knowledge_read(domain="canping", key="appendix_month_order")
    frozen = replace(spec, bind=lambda _: (lambda: deepcopy(output), (), {}))
    actual = execute_tool(frozen, request)
    assert actual["status_code"] == 503 and actual["retryable"] is False
    assert (
        actual["issues"][0]["code"] == "runtime_numerology_knowledge_binding_conflict"
    )


@pytest.mark.parametrize(
    "change",
    [
        {"reference_only": False},
        {"reference_only": 1},
        {"personal_applicability_assessed": True},
    ],
)
def test_partial_reference_cannot_certify_personal_application(change):
    with pytest.raises(ValidationError):
        NumerologyKnowledgeDetails.model_validate(change)


@pytest.mark.parametrize("domain", ["heluo", "canping"])
def test_reference_registry_normalizes_domain_like_reference_read(domain):
    assert calculate_knowledge_registry(domain=f" {domain} ")["domains"] == (
        calculate_knowledge_registry(domain=domain)["domains"]
    )


@pytest.mark.parametrize("attack", ["catalogue", "source", "missing", "malformed"])
def test_source_identity_is_checked_from_actual_bytes(tmp_path, monkeypatch, attack):
    catalogue = json.loads(gateway.CATALOGUE_PATH.read_bytes())
    source = next(e for e in catalogue["sources"] if e["key"] == "schedule_basis")
    target = tmp_path / source["source_path"]
    target.parent.mkdir(parents=True)
    data = json.loads((DATA / source["source_path"]).read_bytes())
    if attack in {"catalogue", "source"}:
        data["clauses"][0]["text"] = "Unreviewed source replacement"
    if attack == "catalogue":
        # Updating only the descriptor hash does not approve a new reading.
        source["canonical_content_sha256"] = hashlib.sha256(
            gateway.canonical_bytes(data)
        ).hexdigest()
    if attack != "missing":
        target.write_bytes(
            b"[" if attack == "malformed" else gateway.canonical_bytes(data)
        )
    manifest = tmp_path / "catalogue.json"
    manifest.write_bytes(gateway.canonical_bytes(catalogue))
    monkeypatch.setattr(gateway, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(gateway, "CATALOGUE_PATH", manifest)
    actual = calculate_knowledge_read(domain="canping", key="appendix_integer_rounding")
    assert actual["status_code"] == 503 and actual["retryable"] is False
    assert actual["issues"][0]["code"] == "invalid_numerology_knowledge_sources"

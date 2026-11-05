"""Related contract regressions with shared imports; original cases retained."""

import copy
import json
from datetime import datetime
from pathlib import Path

import pytest
from pydantic_core import PydanticCustomError

from fatebridge.core import canping_texts
from fatebridge.core import numerology_knowledge as gateway
from fatebridge.services.knowledge import _build_knowledge_snapshot_text
from fatebridge.utils.errors import UNRESOLVED_OFFSET_MESSAGE, handle_calculation_error
from fatebridge.utils.timezones import parse_timezone_name, validate_local_clock
from scripts.numerology import audit_numerology as audit
from tests.support.heluo_source_facts import CATALOGUE_VERSION


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


def test_water_literal_controls_and_expanded_witness_statistics_are_distinct():
    report = audit.canping_text_checks()
    assert report["checks_passed"] and report["failures"] == []
    assert (
        report["comparison_cells_examined"],
        report["comparison_clear_readings"],
        report["comparison_uncertain_readings"],
    ) == (72, 70, 2)
    assert (
        report["comparison_water_cells_examined"],
        report["comparison_water_clear_readings"],
        report["comparison_water_uncertain_readings"],
    ) == (36, 34, 2)
    assert (
        report["comparison_registered_counterpart_cells"],
        report["comparison_registered_counterpart_keys"],
        report["comparison_ambiguous_counterpart_keys"],
        report["comparison_unmatched_observed_cells"],
    ) == (69, 66, 3, 3)
    assert report["collated_cells"] == 1123 and report["unresolved_reading_cells"] == 47
    assert report["comparison_primary_count_increase"] == 0


@pytest.mark.parametrize(
    "field,bad",
    [("cells_examined", 35), ("clear_readings", 35), ("uncertain_readings", 0)],
)
def test_expanded_global_counts_cannot_hide_a_damaged_water_subset(
    field, bad, monkeypatch
):
    original = audit.canping_collation_summary

    def damaged():
        result = copy.deepcopy(original())
        result["comparison_witness"]["part_coverage"]["水"][field] = bad
        return result

    monkeypatch.setattr(audit, "canping_collation_summary", damaged)
    report = audit.canping_text_checks()
    assert report["checks_passed"] is False
    assert {"kind": "canping_witness_coverage"} in report["failures"]


def test_old_global34_false_positive_cannot_override_the_water_fixture(monkeypatch):
    original = audit.canping_collation_summary

    def damaged():
        result = copy.deepcopy(original())
        result["comparison_witness"]["clear_readings"] = 34
        result["comparison_witness"]["part_coverage"]["水"]["clear_readings"] = 33
        return result

    monkeypatch.setattr(audit, "canping_collation_summary", damaged)
    report = audit.canping_text_checks()
    assert report["checks_passed"] is False
    assert {"kind": "canping_witness_coverage"} in report["failures"]


@pytest.mark.parametrize(
    "revision,label", [(None, "未提供"), (0, "0"), ("0", "0"), ("1.2.0", "1.2.0")]
)
def test_missing_and_explicit_source_versions_remain_distinct_without_input_mutation(
    revision, label
):
    entry = {
        "domain": "heluo",
        "category": "source_collections",
        "key": "source",
        "title": "原文None保留",
        "tips": ["正文None保留"],
        "provenance": {
            "reference_policy_id": "numerology_source_reference_v1",
            "source_records": [
                {
                    "key": "source",
                    "source_title": "所選來源",
                    "source_revision": revision,
                    "review_status": "not_assessed",
                    "loaded_file_sha256": "fixed",
                    "canonical_content_sha256": "fixed",
                }
            ],
        },
    }
    before = copy.deepcopy(entry)
    snapshot = _build_knowledge_snapshot_text(entry)
    assert f"修订：{label}；状态：not_assessed" in snapshot
    assert "正文None保留" in snapshot and "原文None保留" in snapshot
    assert (
        entry == before
        and entry["provenance"]["source_records"][0]["source_revision"] == revision
    )


def test_real_tzif_rejection_keeps_its_type_across_domain_guard():
    at = datetime(1900, 1, 1, 12, tzinfo=parse_timezone_name("Antarctica/Casey"))
    with pytest.raises(PydanticCustomError) as caught:
        validate_local_clock(at)
    result = handle_calculation_error(caught.value, "河洛测试")
    assert result == {
        "error": UNRESOLVED_OFFSET_MESSAGE,
        "error_code": "validation_error",
        "status_code": 422,
        "retryable": False,
        "issues": [{"path": "request", "code": "unresolved_timezone_offset"}],
    }


def test_typed_hint_uses_the_canonical_message_without_private_error_text():
    error = PydanticCustomError(
        "unresolved_timezone_offset", "private birthrecord /private/path"
    )
    result = handle_calculation_error(error, "测试")
    assert result["error"] == UNRESOLVED_OFFSET_MESSAGE
    assert result["issues"] == [
        {"path": "request", "code": "unresolved_timezone_offset"}
    ]
    assert "private" not in json.dumps(result)


def test_plain_text_cannot_impersonate_a_typed_timezone_rejection():
    error = ValueError("unresolved_timezone_offset " + UNRESOLVED_OFFSET_MESSAGE)
    result = handle_calculation_error(error, "测试")
    assert result["status_code"] == 400 and result["error_code"] == "validation_error"
    assert "issues" not in result


def test_other_custom_errors_keep_the_existing_domain_input_contract():
    result = handle_calculation_error(
        PydanticCustomError("another_type", "other failure"), "测试"
    )
    assert result == {
        "error": "other failure",
        "error_code": "validation_error",
        "status_code": 400,
        "retryable": False,
    }

"""Whole-corpus source qualifications survive reference summaries and projection."""

import gzip
import hashlib
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.services.knowledge import (
    calculate_knowledge_read,
    calculate_knowledge_registry,
)
from tests.canping_witness_knowledge_revision import rebind_r99_knowledge
from tests.heluo_ben22_revision_reference import REVISION as R96_REVISION
from tests.heluo_ben22_revision_reference import rebind_r96_counts
from tests.heluo_ben22_revision_reference import (
    rebind_r96_metadata as rebind_r96_metadata_before_r99,
)
from tests.heluo_ben22_revision_reference import rebind_r96_record
from tests.heluo_bo23_revision_reference import (
    rebind_r101_metadata,
    rebind_r101_record,
    rebind_r101_registry,
)
from tests.heluo_current_source_reference import (
    HEADER_COUNT,
    LITERAL_CHANGED_KEYS,
    advance_current_metadata,
    advance_current_record,
    advance_current_registry,
)
from tests.heluo_guan_shi_revision_reference import REVISION as R84_REVISION
from tests.heluo_guan_shi_revision_reference import rebind_r84_record
from tests.heluo_lin19_song6_revision_reference import (
    ADDENDUM,
    REVISION,
    rebind_reviewed_registry_counts,
    rebind_reviewed_source_metadata,
)
from tests.heluo_shike_bi_revision_reference import REVISION as R92_REVISION
from tests.heluo_shike_bi_revision_reference import (
    rebind_r92_counts,
    rebind_r92_metadata,
    rebind_r92_record,
)
from tests.test_agentic_nested_outputs import SPECS, business
from tests.test_agentic_nested_outputs import rest as shared_rest
from tests.test_heluo_poem_transports import run_three

rest = shared_rest
F = Path(__file__).parent / "fixtures/numerology_reference_notes_v1"
REFERENCE = json.loads((F / "independent-note-reference.json").read_bytes())["entries"]
QUALIFICATIONS = json.loads(
    (F / "existing-record-qualification-reference.json").read_bytes()
)["entries"]
BEFORE = json.loads(gzip.decompress((F / "whole-corpus-before.json.gz").read_bytes()))


def rebind_r96_metadata(value):
    return rebind_r99_knowledge(rebind_r96_metadata_before_r99(value))


def literal_notes(ref):
    return (
        ref["header_notes"]
        + ref["commentary_notes"]
        + [note for poem in ref["poem_notes"] for note in poem["notes"]]
    )


def test_independent_reference_freeze_and_original_omissions_are_retained():
    freeze = json.loads((F / "before-survey-freeze.json").read_bytes())
    assert freeze["before_production_edits"] is True
    for name, digest in freeze["files_sha256"].items():
        assert hashlib.sha256((F / name).read_bytes()).hexdigest() == digest
    original = json.loads((F / "summary-omissions-before.json").read_bytes())
    assert original["examined_heluo"] == 384 and original["examined_canping"] == 1170
    assert original["heluo_records_with_omitted_notes"] == 82
    assert original["individual_omitted_note_occurrences"] == 160


def test_all384_line_summaries_keep_every_existing_source_note_and_record():
    old = {r["key"]: r["output"] for r in BEFORE if r["domain"] == "heluo"}
    changed = set()
    for ref in REFERENCE:
        out = calculate_knowledge_read(domain="heluo", key=ref["key"])
        prior = old[ref["key"]]
        assert "error" not in out
        # R77 and R81 source additions have separately frozen literal references.
        # Original R76 outputs stay frozen; migrate only reviewed metadata and
        # keep every field outside the named additions exact.
        expected = rebind_reviewed_source_metadata(prior)
        if ref["key"] in R84_REVISION["record_extensions"]:
            expected["reference_details"]["record"] = rebind_r84_record(
                expected["reference_details"]["record"], ref["key"]
            )
        expected = rebind_r92_metadata(expected)
        expected["reference_details"]["record"] = rebind_r92_record(
            expected["reference_details"]["record"], ref["key"]
        )
        expected = rebind_r96_metadata(expected)
        if ref["key"] in R96_REVISION["record_extensions"]:
            expected["reference_details"]["record"] = rebind_r96_record(
                expected["reference_details"]["record"], ref["key"]
            )
        # The earlier 24-record test deliberately keeps its partial historical
        # expectations. R101's separate 384-record control binds those complete
        # before/after records without replacing the historical assertions.
        if ref["key"] not in REVISION["changed_record_fields"]:
            expected["reference_details"]["record"] = rebind_r101_record(
                expected["reference_details"]["record"], ref["key"]
            )
        if ref["key"] not in REVISION["changed_record_fields"]:
            expected["reference_details"]["record"] = advance_current_record(
                expected["reference_details"]["record"], ref["key"]
            )
        expected = advance_current_metadata(rebind_r101_metadata(expected))
        if ref["key"] in R96_REVISION["record_extensions"]:
            assert out["reference_details"] == expected["reference_details"]
        elif ref["key"] in R92_REVISION["record_extensions"]:
            assert out["reference_details"] == expected["reference_details"]
        elif ref["key"] in R84_REVISION["record_extensions"]:
            assert out["reference_details"] == expected["reference_details"]
        elif ref["key"].startswith("山地剝:") or ref["key"] in LITERAL_CHANGED_KEYS:
            assert out["reference_details"] == expected["reference_details"]
        elif ref["key"] not in REVISION["changed_record_fields"]:
            assert out["reference_details"] == expected["reference_details"]
            assert out["lines"][: len(prior["lines"])] == prior["lines"]
        else:
            changing = set(REVISION["changed_record_fields"][ref["key"]])
            record = expected["reference_details"]["record"]
            for k, v in record.items():
                if k not in changing:
                    assert out["reference_details"]["record"][k] == v
            assert out["reference_details"]["record"]["verdict"] == record["verdict"]
        assert out["provenance"] == expected["provenance"]
        assert out["tips"] == out["lines"]
        for note in literal_notes(ref):
            for surface in [
                "\n".join(out["lines"]),
                out["rendered_text"],
                out["snapshot_text"],
            ]:
                assert note in surface, (ref["key"], note)
        if out["lines"] != prior["lines"]:
            changed.add(ref["key"])
        else:
            assert out == expected
    assert (
        ADDENDUM["corrected_expected_changed_summary_records"]
        == R84_REVISION["old_summary_changed_count"]
        == 114
    )
    assert R84_REVISION["expected_summary_changed_count"] == 120
    assert R92_REVISION["current_headers"] == 126
    assert R96_REVISION["current_headers"] == 132
    assert len(changed) == HEADER_COUNT
    assert len(old) == len(REFERENCE) == 384


def test_all1170_canping_references_and_both_registries_stay_exact():
    old = [r for r in BEFORE if r["domain"] == "canping"]
    assert len(old) == 1170
    for row in old:
        assert calculate_knowledge_read(
            domain="canping", key=row["key"]
        ) == advance_current_metadata(
            rebind_r101_metadata(
                rebind_r96_metadata(
                    rebind_r92_metadata(rebind_reviewed_source_metadata(row["output"]))
                )
            )
        )
    registry = json.loads((F / "registry-before.json").read_bytes())
    for domain, expected in registry.items():
        expected_current = rebind_r92_counts(
            rebind_r92_metadata(
                rebind_reviewed_registry_counts(
                    rebind_reviewed_source_metadata(expected)
                )
            )
        )
        assert calculate_knowledge_registry(domain=domain) == advance_current_registry(
            rebind_r101_registry(
                rebind_r96_counts(rebind_r96_metadata(expected_current)), domain
            ),
            domain,
        )


def test_all_existing_selection_reasons_remain_available_without_personal_selection():
    for ref in QUALIFICATIONS:
        out = calculate_knowledge_read(domain="heluo", key=ref["key"])
        lines = "\n".join(out["lines"])
        record = out["reference_details"]["record"]
        for field in ["branch_reason", "poem_reason"]:
            if ref[field]:
                assert ref[field] in lines
        assert out["reference_details"]["personal_applicability_assessed"] is False
        if "commentary_branch_selection" in record:
            assert record["commentary_branch_selection"]["selected_section_ids"] == []
            assert all(
                s["applicability"] is None for s in record["commentary_sections"]
            )
        if "poem_selection" in record:
            assert record["poem_selection"]["selected_poem_indices"] == []
            assert all(s["applicability"] is None for s in record["poem_sections"])


@pytest.mark.parametrize(
    "ref", [r for r in QUALIFICATIONS if r["cross_references"]], ids=lambda r: r["key"]
)
def test_conditional_quotes_retain_their_scope_in_summary(ref):
    out = calculate_knowledge_read(domain="heluo", key=ref["key"])
    quotes = [line for line in out["lines"] if line.startswith("有条件引文说明：")]
    assert len(quotes) == len(ref["cross_references"])
    for original, rendered in zip(ref["cross_references"], quotes, strict=True):
        assert original["source_quote"] in rendered
        assert original["condition_text"] in rendered
        assert original["target_hexagram"] in rendered
        if original["target_quote"] is not None:
            assert original["target_quote"] in rendered
        else:
            assert "所引文字：" not in rendered
        assert "None" not in rendered
        assert "适用性未裁定" in rendered and "不自动应用" in rendered
        assert "不替代正式卦盘" in rendered
        if original.get("source_condition_label"):
            assert original["source_condition_label"] in rendered
        if original.get("source_context_text"):
            assert original["source_context_text"] in rendered
        if original.get("target_line_source_status") == "not_printed":
            assert "原文未印目标爻位" in rendered
        assert "不单独证明目标卦全文" in rendered


@pytest.mark.parametrize(
    "key", ["山水蒙:2", "山水蒙:6", "澤雷隨:5", "風天小畜:3", "火天大有:3", "地山謙:4"]
)
def test_qualified_summary_on_rest_cli_and_mcp(key, rest, tmp_path, capsys):
    spec = SPECS["knowledge_read"]
    response, code, cli, mcp = run_three(
        spec,
        dict(domain="heluo", key=key),
        ["title", "lines", "tips", "rendered_text", "snapshot_text", "reference_only"],
        rest,
        tmp_path,
        capsys,
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    outputs = [response.json(), cli, mcp.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    ref = next(r for r in REFERENCE if r["key"] == key)
    scope = next(r for r in QUALIFICATIONS if r["key"] == key)
    for out in outputs:
        spec.output_model.model_validate(out)
        assert "reference_details" not in out and out["reference_only"] is True
        for note in literal_notes(ref):
            assert note in "\n".join(out["lines"]) and note in out["snapshot_text"]
        if scope["branch_reason"]:
            assert scope["branch_reason"] in "\n".join(out["lines"])


@pytest.mark.parametrize("key", ["山水蒙:6", "澤雷隨:5", "火天大有:3"])
def test_stale_consistent_old_summary_is_rejected_before_narrow_projection(key):
    spec = SPECS["knowledge_read"]
    prior = deepcopy(
        next(r["output"] for r in BEFORE if r["domain"] == "heluo" and r["key"] == key)
    )
    request = spec.request_model.model_validate(dict(domain="heluo", key=key))
    frozen = replace(spec, bind=lambda _: (lambda: prior, (), {}))
    result = execute_tool(frozen, request)
    assert result["status_code"] == 503 and result["retryable"] is False
    assert (
        result["issues"][0]["code"] == "runtime_numerology_knowledge_binding_conflict"
    )


def test_small_budget_rest_pages_retain_notes_from_same_result(rest):
    key = "山水蒙:6"
    response = rest.post(
        SPECS["knowledge_read"].rest_path,
        json=dict(domain="heluo", key=key),
        params=[
            ("fields", "lines"),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "4096"),
        ],
    )
    assert response.status_code == 200
    result = response.json()
    if "result_delivery" in result:
        reference = result["result_delivery"]
        offset = 0
        parts = []
        while True:
            page = rest.get(
                f"/api/results/{reference['result_id']}/pages",
                params={"path": "lines", "offset": offset},
            ).json()
            assert page["result_id"] == reference["result_id"]
            parts.append(page["text"])
            if page["next_offset"] is None:
                break
            offset = page["next_offset"]
        lines = json.loads("".join(parts))
    else:
        lines = result["lines"]
    expected = calculate_knowledge_read(domain="heluo", key=key)["lines"]
    assert lines == expected
    assert "不據此生成具體年齡或日期" in "\n".join(lines)


def test_unselected_year_still_has_a_generated_annual_sequence(monkeypatch, tmp_path):
    from fatebridge.core.local_techniques.heluo import build_heluo_result

    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path / "empty-ephe"))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    diagnostic = json.loads((F / "timing-scope-diagnostic.json").read_bytes())
    assert diagnostic["original45criterion_meanings_changed"] is False
    for case in diagnostic["rows"]:
        result = build_heluo_result(**case["payload"])
        assert result["input_normalized"]["analysis_year"] is None
        assert result["heluo_timing"]["annual_rows"]
        assert result["heluo_timing"]["selected_annual"] is None
        assert result["heluo_timing"]["prediction_validation"] == "not_validated"

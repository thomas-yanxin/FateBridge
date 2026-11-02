"""Selected printing readings, preserved conditions and actual source routing."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from fatebridge.core import heluo_poems as hp
from fatebridge.core import heluo_texts as ht
from fatebridge.core.heluo import _tiaowen, yao_text
from fatebridge.services.knowledge import calculate_knowledge_read
from fatebridge.utils.errors import NumerologySourceError
from tests.heluo_current_source_reference import HEADER_COUNT, PENDING_COUNT
from tests.heluo_current_source_reference import REFERENCE as CURRENT_REFERENCE
from tests.test_agentic_nested_outputs import SPECS, business
from tests.test_agentic_nested_outputs import rest as shared_rest
from tests.test_heluo_poem_transports import run_three

rest = shared_rest
F = Path(__file__).parent / "fixtures/heluo_sui17_meng4_v1"
READINGS = json.loads((F / "verified-readings.json").read_bytes())
ADOPTION = json.loads((F / "source-adoption-reference.json").read_bytes())
CASES = json.loads((F / "cases.json").read_bytes())["cases"]


def test_audit_checks_both_new_source_and_preserved_prefixes():
    from scripts.audit_numerology import (
        poem_collation_checks,
        sui17_meng4_source_checks,
    )

    poems = poem_collation_checks()
    assert poems["checks_passed"] and poems["failures"] == []

    result = sui17_meng4_source_checks()
    assert result["checks_passed"] and result["failures"] == []
    assert result["unresolved_new_prose_glyphs"] == 1
    assert result["independent_second_review_completed"] is False


def canonical(value):
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


@pytest.fixture(autouse=True)
def isolated_native(monkeypatch, tmp_path):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path / "empty-ephe"))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    for loader in [ht._collation, ht._commentary_collation, hp._collation]:
        loader.cache_clear()
    yield
    for loader in [ht._collation, ht._commentary_collation, hp._collation]:
        loader.cache_clear()


def test_source_first_draft_and_all_amendments_are_retained():
    first = json.loads((F / "first-draft-freeze.json").read_bytes())
    assert first["inherited_target_text_exposed"] is False
    for name, digest in first["files"].items():
        assert hashlib.sha256((F / name).read_bytes()).hexdigest() == digest
    source = json.loads((F / "source-only-verified-freeze.json").read_bytes())
    assert source["inherited_target_text_exposed"] is False
    assert source["new_independent_readers"] == 0
    final = json.loads((F / "source-reading-freeze.json").read_bytes())
    assert (
        hashlib.sha256((F / "verified-readings.json").read_bytes()).hexdigest()
        == final["final_verified_sha256"]
    )
    change = json.loads((F / "postcomparison-amendments.json").read_bytes())["changes"]
    assert len(change) == 1 and change[0]["line"] == 4
    assert change[0]["before"].endswith("事權") and change[0]["after"].endswith("專權")
    assert change[0]["inherited_was_correct_here"] is True
    assert change[0]["counts_as_production_correction"] is False


def test_prior_prefixes_and_real_coverage_remain_separate():
    for data, prefix, count in [
        (ht._collation(), "headers", 96),
        (ht._commentary_collation(), "commentaries", 96),
        (hp._collation(), "poems", 18),
    ]:
        assert (
            canonical(data["entries"][:count])
            == ADOPTION["prefixes_preserved"][prefix]["canonical_sha256"]
        )
    assert (
        ht.collation_summary()["collated_line_headers"],
        ht.collation_summary()["pending_line_headers"],
    ) == (HEADER_COUNT, PENDING_COUNT)
    assert (
        ht.commentary_collation_summary()["collated_line_commentaries"],
        ht.commentary_collation_summary()["pending_line_commentaries"],
    ) == (HEADER_COUNT, PENDING_COUNT)
    p = hp.collation_summary()
    assert (
        p["collated_line_poem_groups"],
        p["pending_line_poem_groups"],
        p["collated_individual_poems"],
        p["total_individual_poems"],
    ) == (48, 336, 117, None)
    assert p["automatic_poem_selection"] is False


@pytest.mark.parametrize(
    "entry", READINGS["commentaries"], ids=lambda e: str(e["line"])
)
def test_sui_complete_text_preserves_parent_conditions_and_original_forms(entry):
    text = yao_text("澤雷隨", entry["line"])
    sections = deepcopy(entry["sections"])
    for s in sections:
        s["text"] = s["text"].replace("无", "無")
        s["applicability"] = None
    assert text["yaoci"] == entry["yaoci"]
    assert text["detail"] == "".join(s["text"] for s in sections)
    assert text["commentary_sections"] == sections
    assert sections[1]["condition_label"] == "叶者"
    assert sections[2]["condition_label"] == "不叶者"
    assert text["commentary_branch_selection"]["selected_section_ids"] == []
    old = _tiaowen()["澤雷隨"]["yao"][str(entry["line"])]
    assert (text["shige"], text["verdict"]) == (old["shige"], old["verdict"])
    p = text["text_provenance"]
    assert p["inherited_detail"] == old["detail"]
    assert p["commentary_pdf_pages"] == entry["pdf_pages"]
    assert p["poem_status"] == "inherited_poem_source_unverified"
    if entry["line"] == 2:
        assert "女子元數叶者" in sections[1]["text"]
        assert "female" not in [s["section_id"] for s in sections]
    if entry["line"] == 3:
        assert "成引進名" in sections[1]["text"]
        assert "女命必遭貴夫" in sections[2]["text"]
    if entry["line"] == 5:
        assert "善人吉士" in sections[2]["text"]
    if entry["line"] == 6:
        assert "unresolved" in p["commentary_review_status"]
        assert any(
            "縲" in note and "未定" in note for note in p["commentary_reading_notes"]
        )
        assert "字形未决" in ht.text_status_snapshot(text)


@pytest.mark.parametrize("entry", READINGS["poems"], ids=lambda e: str(e["line"]))
def test_meng_every_printed_poem_and_boundary_is_retained(entry):
    text = yao_text("山水蒙", entry["line"])
    actual = text["poem_sections"]
    assert len(actual) == len(entry["poems"])
    for a, e in zip(actual, entry["poems"], strict=True):
        assert all(
            a[k] == e[k]
            for k in ["index", "printed_label", "text", "pdf_pages", "printed_clauses"]
        )
        assert a["applicability"] is None
    assert text["shige"] == "\n".join(p["text"] for p in entry["poems"])
    assert text["poem_selection"]["selected_poem_indices"] == []
    assert text["poem_selection"]["automatic_selection"] is False
    assert text["text_provenance"]["poem_heading_pdf_page"] == entry["heading_pdf_page"]
    assert (
        text["text_provenance"]["poem_source_pdf_sha256"]
        != text["text_provenance"]["commentary_source_pdf_sha256"]
    )
    old = _tiaowen()["山水蒙"]["yao"][str(entry["line"])]
    assert text["verdict"] == old["verdict"]
    assert text["text_provenance"]["inherited_shige"] == old["shige"]
    assert text["inherited_xiang_reference"]["text"] == old["shige"].splitlines()[0]
    if entry["line"] == 2:
        assert "納婿" in actual[0]["text"] and "納婦" in text["yaoci"]
        assert "牛途" in actual[1]["text"]
        assert actual[0]["reading_notes"] and actual[1]["reading_notes"]
    if entry["line"] == 6:
        assert "四八尋" in actual[0]["text"]
        assert any("具體年齡或日期" in note for note in actual[0]["reading_notes"])


def test_initial_case_search_failure_is_not_relabelled_as_complete():
    initial = json.loads((F / "case-selection-result.json").read_bytes())
    extension = json.loads((F / "case-selection-extension-result.json").read_bytes())
    assert initial["candidates_evaluated"] == 4320
    assert len(initial["all_target_keys_found"]) == 11
    assert ["澤雷隨", 3] not in initial["all_target_keys_found"]
    assert extension["original_failed_plan_retained"] is True
    assert (
        extension["initial_found_cases"] == 11
        and extension["additional_found_cases"] == 1
    )
    assert len(CASES) == 12
    extra = [c for c in CASES if c["selection_origin"] == "extension"]
    assert len(extra) == 1 and (extra[0]["hexagram"], extra[0]["line"]) == ("澤雷隨", 3)


@pytest.mark.parametrize(
    "fault",
    [
        "sui_label",
        "sui_words",
        "sui_status",
        "meng_words",
        "meng_missing_poem",
        "meng_order",
    ],
)
def test_new_source_mutations_cannot_keep_reviewed_identity(
    fault, monkeypatch, tmp_path
):
    poem = fault.startswith("meng")
    path = hp.COLLATION_PATH if poem else ht.COMMENTARY_PATH
    data = json.loads(path.read_bytes())
    entry = next(
        e
        for e in data["entries"]
        if e["hexagram"] == ("山水蒙" if poem else "澤雷隨")
        and e["line"]
        == (
            1
            if fault in {"meng_missing_poem", "meng_order"}
            else 2 if fault == "meng_words" else 5
        )
    )
    if fault == "sui_label":
        entry["sections"][2]["condition_label"] = "葉者"
    elif fault == "sui_words":
        entry["sections"][2]["text"] = "不叶者一律不利。"
    elif fault == "sui_status":
        entry["review_status"] = "independent_expert_certified"
    elif fault == "meng_words":
        entry["poems"][0]["text"] = entry["poems"][0]["text"].replace("納婿", "納婦")
    elif fault == "meng_missing_poem":
        entry["poems"].pop()
    else:
        entry["poems"][0], entry["poems"][1] = entry["poems"][1], entry["poems"][0]
    target = tmp_path / "source.json"
    target.write_text(json.dumps(data, ensure_ascii=False))
    monkeypatch.setattr(
        hp if poem else ht, "COLLATION_PATH" if poem else "COMMENTARY_PATH", target
    )
    with pytest.raises(NumerologySourceError):
        (hp._collation if poem else ht._commentary_collation)()


@pytest.mark.parametrize("case", CASES, ids=lambda c: f"{c['hexagram']}-{c['line']}")
def test_actual_selected_text_and_conditions_match_all_three_adapters(
    case, rest, tmp_path, capsys
):
    spec = SPECS["heluo"]
    fields = [
        "chart",
        "four_pillars",
        "numerology_evidence.selected_texts",
        "numerology_evidence.commentary_collation",
        "numerology_evidence.poem_collation",
        "snapshot_text",
    ]
    response, code, cli, mcp = run_three(
        spec, case["payload"], fields, rest, tmp_path, capsys
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    outputs = [response.json(), cli, mcp.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for out in outputs:
        spec.output_model.model_validate(out)
        Draft202012Validator(spec.output_model.model_json_schema()).validate(out)
        selected = out["numerology_evidence"]["selected_texts"][case["phase"]]
        assert (selected["hexagram"], selected["line"]) == (
            case["hexagram"],
            case["line"],
        )
        expected = yao_text(case["hexagram"], case["line"])
        assert selected["text"] == expected
        assert expected["detail"] in out["snapshot_text"]
        if case["hexagram"] == "山水蒙":
            assert expected["shige"] in out["snapshot_text"]
        if (case["hexagram"], case["line"]) == ("澤雷隨", 6):
            assert "字形未决" in out["snapshot_text"]


@pytest.mark.parametrize("key", ["澤雷隨:5", "澤雷隨:6", "山水蒙:2", "山水蒙:6"])
def test_knowledge_reference_is_same_source_without_personal_application(key):
    result = calculate_knowledge_read(domain="heluo", key=key)
    assert "error" not in result
    details = result["reference_details"]
    gua, _, pos = key.rpartition(":")
    assert details["record"] == yao_text(gua, int(pos))
    assert details["reference_only"] is True
    assert details["personal_applicability_assessed"] is False
    from tests.heluo_guan_shi_revision_reference import REVISION as glyph_revision
    from tests.heluo_shike_bi_revision_reference import REVISION as r92

    assert (
        glyph_revision["provenance_pairs"]["source_catalogue_version"][1]
        == r92["provenance_pairs"]["source_catalogue_version"][0]
    )
    from tests.canping_witness_knowledge_revision import REVISION as r99
    from tests.heluo_ben22_revision_reference import REVISION as r96

    assert (
        r92["provenance_pairs"]["source_catalogue_version"][1]
        == r96["provenance_pairs"]["source_catalogue_version"][0]
    )
    assert (
        r96["provenance_pairs"]["source_catalogue_version"][1]
        == r99["provenance_pairs"]["source_catalogue_version"][0]
    )
    from tests.heluo_bo23_revision_reference import KNOWLEDGE as R101_KNOWLEDGE

    assert (
        r99["provenance_pairs"]["source_catalogue_version"][1]
        == R101_KNOWLEDGE["provenance_pairs"]["source_catalogue_version"][0]
    )
    assert (
        R101_KNOWLEDGE["provenance_pairs"]["source_catalogue_version"][1]
        == CURRENT_REFERENCE["provenance_pairs"]["source_catalogue_version"][0]
    )
    assert (
        result["provenance"]["source_catalogue_version"]
        == CURRENT_REFERENCE["provenance_pairs"]["source_catalogue_version"][1]
    )


@pytest.mark.parametrize("key", ["澤雷隨:6", "山水蒙:2"])
def test_knowledge_actual_three_adapters_retain_notes(key, rest, tmp_path, capsys):
    spec = SPECS["knowledge_read"]
    response, code, cli, mcp = run_three(
        spec,
        dict(domain="heluo", key=key),
        ["title", "reference_details", "provenance"],
        rest,
        tmp_path,
        capsys,
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    results = [response.json(), cli, mcp.structured_content]
    assert business(results[0]) == business(results[1]) == business(results[2])
    assert all(
        r["reference_details"]["personal_applicability_assessed"] is False
        for r in results
    )


@pytest.mark.parametrize(
    "key,label",
    [
        ("雷地豫:2", "注文"),
        ("雷地豫:4", "爻辞"),
        ("澤雷隨:6", "注文"),
        ("澤雷隨:5", None),
    ],
)
def test_summary_only_knowledge_keeps_scoped_glyph_uncertainty(
    key, label, rest, tmp_path, capsys
):
    spec = SPECS["knowledge_read"]
    response, code, cli, mcp = run_three(
        spec,
        dict(domain="heluo", key=key),
        ["title", "lines", "reference_only"],
        rest,
        tmp_path,
        capsys,
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    outputs = [response.json(), cli, mcp.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for out in outputs:
        assert "reference_details" not in out
        summary = "\n".join(out["lines"])
        assert ("字形未决" in summary) is (label is not None)
        if label:
            assert f"{label}字形未决：" in summary
        assert out["reference_only"] is True

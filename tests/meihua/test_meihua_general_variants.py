"""Each retained general cast owns its body, mutuals, season and actual verse."""

import hashlib
import json
import shutil
import unicodedata
from pathlib import Path

import pytest

from fatebridge.services.meihua import calculate_meihua_cast
from fatebridge.validation.meihua_general_variants import audit_general_casting_readings
from tests.support.transports import rest, surface_calls

REFERENCES = Path(__file__).parents[1] / "fixtures/meihua_general_variants_v2"
CASES = json.loads((REFERENCES / "cases.json").read_text())["cases"]


def normalized(text):
    return "".join(
        c
        for c in text
        if unicodedata.category(c)[0] not in {"P", "S", "Z"} and not c.isspace()
    )


def calculate(case):
    return calculate_meihua_cast(
        casting=case["casting"],
        season_month_branch=case["season_month_branch"],
        question="虚构规则核验",
    )


def resolve(output, path):
    value = output
    for key in path.split("."):
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_frozen_candidate_geometry_season_and_actual_verse(case):
    output = calculate(case)
    readings = output["interpretation"]["casting_readings"]
    expected = case["expected"]
    assert len(readings) == expected["candidate_count"]
    assert (
        output["interpretation"]["casting_comparison"]["status"]
        == expected["comparison_status"]
    )
    by_basis = {v["line_sum_basis"]: v for v in readings}
    for reference in expected["candidates"]:
        row = by_basis[reference["basis"]]
        for key in [
            "moving_line",
            "base_code",
            "changed_code",
            "mutual_code",
            "body",
            "use",
        ]:
            assert row[key] == reference[key], (case["id"], reference["basis"], key)
        assert [r["relation"] for r in row["stage_relations"]] == reference["relations"]
        assert [
            row["body"],
            *[r["trigram"] for r in row["stage_relations"]],
        ] == reference["role_trigrams"]
        seasonal = row["seasonal_strength"]
        assert (
            None
            if seasonal is None
            else {r["role"]: r["strength"] for r in seasonal["trigrams"]}
        ) == reference["seasonal_strengths"]
        verse = row["classical_text_reference"]["moving_yaoci"]
        assert verse["position"] == reference["moving_line"]
        assert normalized(verse["text"]) == normalized(reference["yaoci"])
        for relation in row["stage_relations"]:
            actual = resolve(output, relation["fact_path"])
            assert (actual["name"], actual["element"]) == (
                relation["trigram"],
                relation["element"],
            )
            assert relation["body"] == row["body"]
        if seasonal:
            for strength in seasonal["trigrams"]:
                assert (
                    resolve(output, strength["fact_path"])["name"]
                    == strength["trigram"]
                )
    if readings:
        assert sum(r["selected"] for r in readings) == 1
        assert (
            next(r for r in readings if r["selected"])["line_sum_basis"]
            == output["meihua"]["seed"]["line_sum_basis"]
        )
        assert "各候选分列" in output["summary"]


def test_frozen_audit_retains_source_and_acceptance_boundaries():
    report = audit_general_casting_readings(REFERENCES)
    assert report["selected_checks_passed"], report
    assert report["literal_mathematical_probe_count"] == 9
    assert len(report["verse_source_checks"]) == 14
    assert report["independent_human_expert_review"] == "not_performed"
    assert report["actual_model_runs"] == report["prospective_observation_count"] == 0
    assert report["original_worked_example_count_added"] == 0
    assert not report["full_classical_conformance_established"]
    assert not report["predictive_efficacy_established"]


def test_tampered_reference_still_fails_after_manifest_rehash(tmp_path):
    reference = tmp_path / "fixtures/meihua_general_variants_v2"
    shutil.copytree(REFERENCES, reference)
    shutil.copytree(
        REFERENCES.parent / "meihua_v1/sources", reference.parent / "meihua_v1/sources"
    )
    path = reference / "cases.json"
    data = json.loads(path.read_text())
    data["cases"][0]["expected"]["candidates"][0]["body"] = "乾"
    path.write_text(json.dumps(data, ensure_ascii=False))
    with pytest.raises(ValueError, match="source or oracle changed"):
        audit_general_casting_readings(reference)
    manifest = json.loads((reference / "manifest.json").read_text())
    manifest["files"]["cases.json"] = hashlib.sha256(path.read_bytes()).hexdigest()
    (reference / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False))
    report = audit_general_casting_readings(reference)
    assert not report["selected_checks_passed"]
    assert "raw_counts.body" in report["cases"][0]["disagreements"]


def canonical_paths(value, prefix):
    if isinstance(value, str) and value.startswith(prefix):
        return "meihua" + value.removeprefix(prefix)
    if isinstance(value, list):
        return [canonical_paths(row, prefix) for row in value]
    if isinstance(value, dict):
        return {key: canonical_paths(row, prefix) for key, row in value.items()}
    return value


@pytest.mark.parametrize("case", CASES[:7], ids=lambda c: c["id"])
def test_each_candidate_agrees_with_standalone_existing_cast(case):
    # Integration equivalence is separate from the frozen mathematical oracles.
    output = calculate(case)
    for reading in output["interpretation"]["casting_readings"]:
        standalone = calculate_meihua_cast(
            casting={
                "method": "existing",
                "hexagram_code": reading["base_code"],
                "moving_line": reading["moving_line"],
            },
            season_month_branch=case["season_month_branch"],
        )
        assert (
            canonical_paths(reading["stage_relations"], reading["fact_prefix"])
            == standalone["meihua"]["stage_relations"]
        )
        assert (
            canonical_paths(reading["seasonal_strength"], reading["fact_prefix"])
            == standalone["meihua"]["seasonal_strength"]
        )
        assert (
            reading["classical_text_reference"]["moving_yaoci"]
            == standalone["interpretation"]["classical_text_reference"]["moving_yaoci"]
        )
        assert (
            reading["traditional_judgement"]
            == standalone["interpretation"]["traditional_judgement"]
        )
        for field in ("base_fact_path", "moving_line_fact_path"):
            resolve(output, reading["classical_text_reference"][field])


def test_same_initial_relation_does_not_hide_opposite_final_relation():
    output = calculate(CASES[4])
    comparison = output["interpretation"]["casting_comparison"]
    assert "body_use_relation" not in comparison["changed_fields"]
    assert comparison["changed_stage_relation_roles"] == ["changed_use"]
    assert comparison["single_outcome_verdict"] is None
    assert "终应之变用坎对原体震为用生体" in output["summary"]
    assert "终应之变用乾对原体震为用克体" in output["summary"]


def test_readings_do_not_mutate_cast_or_later_calls():
    a = calculate(CASES[0])
    a["interpretation"]["casting_readings"][0]["stage_relations"][0]["body"] = "伪造"
    assert a["meihua"]["counting_variants"][0]["stage_relations"][0]["body"] == "离"
    assert calculate(CASES[0])["interpretation"]["casting_readings"][0]["body"] == "离"


def test_shared_audit_view_keeps_weather_body_readings_inapplicable(surface_calls):
    from fatebridge.application.examples import evidence_views
    from tests.support.transports import SPECS, business, call_cli, native

    spec = SPECS["meihua_cast"]
    fields = evidence_views(spec)["audit"]["fields"]
    payload = {"casting": CASES[0]["casting"], "interpretation_topic": "weather"}
    response, protocol, code, local = surface_calls(
        spec,
        payload,
        projection={
            **{"fields": fields, "strict_fields": True},
            "response_char_limit": 0,
        },
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        assert output["interpretation"]["casting_readings"] is None
        assert output["interpretation"]["casting_comparison"] is None


@pytest.mark.parametrize(
    "case", [CASES[0], CASES[3], CASES[4], CASES[6], CASES[8]], ids=lambda c: c["id"]
)
def test_candidate_reading_view_agrees_on_rest_mcp_cli(case, surface_calls):
    from jsonschema import Draft202012Validator

    from fatebridge.application.examples import evidence_views
    from tests.support.transports import SPECS, business, call_cli, native

    spec = SPECS["meihua_cast"]
    fields = evidence_views(spec)["reading"]["fields"]
    payload = {
        "casting": case["casting"],
        "season_month_branch": case["season_month_branch"],
    }
    response, protocol, code, local = surface_calls(
        spec,
        payload,
        projection={
            **{"fields": fields, "strict_fields": True},
            "response_char_limit": 0,
        },
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        assert (
            len(output["interpretation"]["casting_readings"])
            == case["expected"]["candidate_count"]
        )
        assert (
            "meihua_explicit_casts_v1@1.5.0"
            in output["run_metadata"]["provenance"]["ruleset"]
        )

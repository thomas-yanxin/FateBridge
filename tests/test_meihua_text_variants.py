"""Literal verse references preserve both source readings and every cast fact."""

import asyncio
import copy
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.application.examples import suggested_fields
from fatebridge.core.divination import (
    build_moving_line_oracle,
    detect_question_domain,
    lookup_hexagram_by_code,
)
from fatebridge.services.divination import calculate_meihua_analysis
from fatebridge.services.meihua import calculate_meihua_cast
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest

FIXTURE = Path(__file__).parent / "fixtures/meihua_text_variants_v1"
REFERENCE = json.loads((FIXTURE / "reference.json").read_bytes())
CAST = {
    "method": "sound_groups",
    "first_count": 15,
    "second_count": 8,
    "hour_branch": "子",
}
TIME = {
    "analysis_year": 2026,
    "analysis_month": 2,
    "analysis_day": 16,
    "analysis_hour": 0,
    "analysis_timezone": "Asia/Shanghai",
}
BO = next(row for row in REFERENCE["rows"] if row["id"] == "23-6")


@pytest.mark.parametrize("row", REFERENCE["rows"], ids=lambda row: row["id"])
def test_display_quotes_retain_both_literal_readings(row):
    oracle = build_moving_line_oracle(
        lookup_hexagram_by_code(row["code"]),
        row["position"],
        detect_question_domain(""),
    )
    assert oracle["classical_yaoci"]["text"] == row["raw_text"]
    expected = row["expected_display_text"]
    assert expected in oracle["judgement"]
    assert oracle["summary"].startswith(oracle["judgement"])


@pytest.mark.parametrize("row", REFERENCE["rows"], ids=lambda row: row["id"])
def test_each_verse_rendering_matches_independent_full_text_and_source_spans(row):
    from fatebridge.core.meihua_text_reference import render_yaoci_text

    output = render_yaoci_text(row["raw_text"])
    assert output["display_text"] == row["expected_display_text"]
    assert output["raw_text"] == row["raw_text"]
    assert output["status"] == "rendered_literal_transcription"
    assert not output["critical_edition_adjudicated"]
    assert output["offset_unit"] == "unicode_code_points_zero_based_half_open"
    assert len(output["variants"]) == len(row["variants"])
    restored = output["display_text"]
    for actual, expected in zip(output["variants"], row["variants"], strict=True):
        assert {k: actual[k] for k in expected} == expected
        assert (
            output["raw_text"][actual["raw_start"] : actual["raw_end"]]
            == actual["raw_template"]
        )
        assert (
            output["display_text"][actual["display_start"] : actual["display_end"]]
            == actual["main_reading"]
            + "〔一作「"
            + actual["alternative_reading"]
            + "」〕"
        )
    for span in reversed(output["variants"]):
        restored = (
            restored[: span["display_start"]]
            + span["raw_template"]
            + restored[span["display_end"] :]
        )
    assert restored == row["raw_text"]


@pytest.mark.parametrize("row", REFERENCE["synthetic_cases"], ids=lambda row: row["id"])
def test_unresolved_syntax_remains_visible_without_a_partial_quote(row):
    from fatebridge.core.meihua_text_reference import render_yaoci_text

    out = render_yaoci_text(row["raw_text"])
    assert out["raw_text"] == row["raw_text"]
    assert out["display_text"] == row["expected_display_text"]
    assert (out["status"] == "unresolved_markup") is (
        row["expected_display_text"] is None
    )


def test_reference_and_actual_template_source_are_retained():
    corpus = Path(__file__).parents[1] / "src/fatebridge/data/classical/zhouyi.json"
    assert (
        hashlib.sha256(corpus.read_bytes()).hexdigest()
        == REFERENCE["source_corpus_sha256"]
    )
    witness = json.loads((FIXTURE / "template-source.json").read_bytes())
    assert witness["revision"] == 5438530
    assert hashlib.sha256((FIXTURE / "template.wikitext").read_bytes()).hexdigest() == (
        witness["wikitext_sha256"]
    )
    assert REFERENCE["literal_variant_line_displays"] == 44
    assert sum(len(row["variants"]) for row in REFERENCE["rows"]) == 48


def test_renderer_and_original_corpus_are_not_mutated():
    from fatebridge.core.meihua_text_reference import render_yaoci_text

    raw = "{{另|德車|得輿}}"
    first = render_yaoci_text(raw)
    original = copy.deepcopy(first)
    first["variants"][0]["main_reading"] = "changed"
    assert render_yaoci_text(raw) == original


@pytest.mark.parametrize(
    "topic",
    ["general", "planning", "reputation", "wealth", "transaction", "travel", "meeting"],
)
def test_selected_and_each_count_candidate_keep_their_own_source_verse(topic):
    result = calculate_meihua_cast(casting=CAST, interpretation_topic=topic)
    assert "error" not in result
    interpretation = result["interpretation"]
    selected = interpretation["classical_text_reference"]
    assert selected["moving_yaoci"]["text"] == BO["raw_text"]
    assert (
        selected["moving_yaoci_rendering"]["display_text"]
        == BO["expected_display_text"]
    )
    candidates = interpretation["casting_readings"]
    assert [(row["line_sum_basis"], row["moving_line"]) for row in candidates] == [
        ("raw_counts", 6),
        ("trigram_numbers", 4),
    ]
    for row in candidates:
        line = row["moving_line"]
        assert row["base_code"] == "000001"
        expected = next(r for r in REFERENCE["rows"] if r["id"] == f"23-{line}")
        reference = row["classical_text_reference"]
        assert reference["moving_yaoci"]["position"] == line
        assert (
            reference["moving_yaoci_rendering"]["display_text"]
            == expected["expected_display_text"]
        )
    if topic == "general":
        assert BO["expected_display_text"] in result["summary"]
        assert "{{" not in result["summary"]
        assert "{{" not in interpretation["comprehensive_judgement"]


def test_time_entry_uses_its_actual_verse_and_preserves_calendar_and_cast():
    result = calculate_meihua_analysis(**TIME)
    assert "error" not in result
    assert result["meihua"]["base_hexagram"]["binary_code"] == "000001"
    assert result["meihua"]["seed"]["moving_line"] == 6
    reference = result["interpretation"]["classical_text_reference"]
    assert (
        reference["moving_yaoci_rendering"]["display_text"]
        == BO["expected_display_text"]
    )
    assert BO["expected_display_text"] in result["summary"]


@pytest.mark.parametrize("tool", ["meihua_cast", "meihua_analysis"])
@pytest.mark.parametrize("view", [None, "reading"])
@pytest.mark.parametrize("topic", ["general", "planning", "weather"])
def test_published_reading_fields_agree_on_rest_mcp_and_cli(
    tool, view, topic, rest, tmp_path, capsys
):
    spec = SPECS[tool]
    payload = {"casting": CAST} if tool == "meihua_cast" else dict(TIME)
    payload["interpretation_topic"] = topic
    fields = suggested_fields(spec, view=view)
    assert "interpretation.classical_text_reference" in fields
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", field) for field in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
        ],
    )
    assert response.status_code == 200, response.text
    mcp = asyncio.run(
        native(
            spec,
            payload,
            fields=fields,
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
    assert not mcp.is_error
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    assert code == 0
    assert (
        business(response.json()) == business(mcp.structured_content) == business(cli)
    )
    reference = cli["interpretation"]["classical_text_reference"]
    if topic == "weather":
        assert reference is None
    else:
        assert reference["moving_yaoci"]["text"] == BO["raw_text"]
        assert (
            reference["moving_yaoci_rendering"]["display_text"]
            == BO["expected_display_text"]
        )

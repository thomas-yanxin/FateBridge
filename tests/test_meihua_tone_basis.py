"""Reported tone categories cannot silently certify a historical sound system."""

import asyncio
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.requests.meihua import MeihuaCastRequest
from fatebridge.services.meihua import calculate_meihua_cast
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest

FIXTURE = Path(__file__).parent / "fixtures/meihua_tone_basis_v1"
CASES = json.loads((FIXTURE / "cases.json").read_text())["cases"]
REFERENCE = {
    "system_name": "所选梅花原例取音",
    "source": "NLC1925原PDF索引24",
    "reading_scope": "worked_example",
}


def test_witnesses_and_hand_oracles_precede_the_implementation():
    m = json.loads((FIXTURE / "manifest.json").read_text())
    assert m["precedes_implementation"]
    for group in ["files", "references"]:
        for name, digest in m[group].items():
            p = (FIXTURE / name).resolve()
            assert p.is_relative_to(FIXTURE.parent.resolve())
            assert hashlib.sha256(p.read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
@pytest.mark.parametrize("with_reference", [False, True])
def test_supplied_categories_retain_hand_geometry_without_claiming_an_original(
    case, with_reference
):
    p = {"method": "text_tones", "text": case["text"], "tones": case["tones"]}
    if with_reference:
        p["tone_reference"] = REFERENCE
    out = calculate_meihua_cast(casting=p)
    cast = out["meihua"]
    assert cast["seed"]["upper_number"] == case["upper"]
    assert cast["seed"]["lower_number"] == case["lower"]
    assert cast["seed"]["moving_line"] == case["line"]
    for key, expected in [
        ("base_hexagram", "base"),
        ("changed_hexagram", "changed"),
        ("mutual_hexagram", "mutual"),
    ]:
        assert cast[key]["binary_code"] == case[expected]
    assert cast["body_trigram"]["name"] == case["body"]
    assert cast["use_trigram"]["name"] == case["use"]
    assert cast["body_use_relation"] == case["relation"]
    scope = cast["seed"]["text_tone_basis"]
    assert scope["reported_tones"] == case["tones"]
    assert scope["phonological_system_automatically_identified"] is False
    assert scope["reference_independently_verified"] is False
    assert scope["reference_status"] == (
        "caller_declared_unverified" if with_reference else "not_supplied"
    )
    expected = (
        "matches_selected_example_categories"
        if case["id"] == "selected-source-original"
        else "differs_from_selected_example_categories"
    )
    assert scope["selected_example_comparison"]["status"] == expected
    assert out["interpretation"]["status"] == "conditional_on_reported_tone_categories"
    assert out["meihua"]["evidence_scope"]["text_tone_basis"] == scope
    assert out["interpretation"]["evidence_scope"]["text_tone_basis"] == scope
    assert "按所报平上去入类别计算" in out["summary"]
    assert "hour_branch" not in cast["seed"]


@pytest.mark.parametrize("text", ["今日动静如何", "今日動静如何"])
def test_glyph_aliases_only_identify_the_example_never_change_reported_text(text):
    out = calculate_meihua_cast(
        casting={"method": "text_tones", "text": text, "tones": CASES[0]["tones"]}
    )
    assert out["input_normalized"]["casting"]["text"] == text
    assert (
        out["meihua"]["seed"]["text_tone_basis"]["selected_example_comparison"][
            "status"
        ]
        == "matches_selected_example_categories"
    )


@pytest.mark.parametrize(
    "text,expected",
    [(None, "text_not_supplied"), ("甲乙丙丁", "different_text_not_compared")],
)
def test_categories_without_identified_original_do_not_borrow_the_example(
    text, expected
):
    out = calculate_meihua_cast(
        casting={"method": "text_tones", "text": text, "tones": [1, 2, 3, 4]}
    )
    scope = out["meihua"]["seed"]["text_tone_basis"]
    assert scope["selected_example_comparison"]["status"] == expected
    assert scope["selected_example_comparison"]["difference_positions"] == []
    assert [r["tone_category"] for r in scope["characters"]] == ["平", "上", "去", "入"]


@pytest.mark.parametrize(
    "reference",
    [
        {**REFERENCE, "encoding": "modern_mandarin_tone_numbers"},
        {**REFERENCE, "system_name": " "},
        {**REFERENCE, "source": " "},
        {**REFERENCE, "reading_scope": "automatically_verified"},
        {**REFERENCE, "extra": "unsupported"},
    ],
)
def test_an_invalid_reference_or_explicit_pinyin_encoding_is_rejected(reference):
    with pytest.raises(ValidationError):
        MeihuaCastRequest(
            casting={
                "method": "text_tones",
                "tones": [1, 2, 3, 4],
                "tone_reference": reference,
            }
        )


@pytest.mark.parametrize(
    "casting",
    [
        {"method": "text_count", "character_count": 17},
        {"method": "text_strokes", "strokes": [7, 8]},
    ],
)
def test_other_methods_do_not_accept_tone_evidence(casting):
    with pytest.raises(ValidationError):
        MeihuaCastRequest(casting={**casting, "tone_reference": REFERENCE})


@pytest.mark.parametrize("topic", ["general", "wealth", "weather"])
def test_tone_basis_is_strictly_projectable_on_rest_mcp_cli(
    topic, rest, tmp_path, capsys
):
    spec = SPECS["meihua_cast"]
    p = {
        "casting": {
            "method": "text_tones",
            "text": "今日動靜如何",
            "tones": CASES[0]["tones"],
            "tone_reference": REFERENCE,
        },
        "interpretation_topic": topic,
    }
    fields = [
        "meihua.seed.text_tone_basis",
        "meihua.evidence_scope.text_tone_basis",
        "interpretation.evidence_scope.text_tone_basis",
        "interpretation.status",
        "summary",
    ]
    response = rest.post(
        spec.rest_path,
        json=p,
        params=[
            *(("fields", f) for f in fields),
            ("strict_fields", "true"),
            ("response_char_limit", "0"),
        ],
    )
    code, cli = call_cli(
        spec,
        p,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--response-char-limit",
            "0",
        ],
    )
    mcp = asyncio.run(native(spec, p, fields=fields, strict_fields=True))
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    assert (
        business(response.json()) == business(cli) == business(mcp.structured_content)
    )
    assert (
        cli["meihua"]["seed"]["text_tone_basis"]["reference_independently_verified"]
        is False
    )

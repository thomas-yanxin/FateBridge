"""A later review exposes disagreement without rewriting the frozen witness."""

import asyncio
import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
import fatebridge.mcp_server as mcp
from fatebridge.cli import run as cli_run
from fatebridge.core import heluo_poems as hp
from fatebridge.core.heluo import yao_text
from fatebridge.services.knowledge import calculate_knowledge_read
from fatebridge.services.tool_catalog import CATALOG

F = Path(__file__).parent / "fixtures/heluo_song_independent_v1"
PROPOSAL = json.loads((F / "supplement-proposal.json").read_bytes())
FREEZE = json.loads((F / "proposal-freeze.json").read_bytes())
CASES = PROPOSAL["entries"]
SPEC = next(s for s in CATALOG if s.key == "knowledge_read")


@pytest.fixture(autouse=True)
def clear_source_caches():
    hp._collation.cache_clear()
    if hasattr(hp, "_review_supplement"):
        hp._review_supplement.cache_clear()
    yield
    hp._collation.cache_clear()
    if hasattr(hp, "_review_supplement"):
        hp._review_supplement.cache_clear()


def test_frozen_unexposed_first_reading_and_later_comparison_stay_distinct():
    for name, digest in FREEZE["files"].items():
        assert hashlib.sha256((F / name).read_bytes()).hexdigest() == digest
    first = json.loads((F / "reader-first.json").read_bytes())
    comparison = json.loads((F / "reader-comparison.json").read_bytes())
    assert first["context_disclosure"]["candidate_text_exposure_before_freeze"] is False
    assert comparison["summary"]["first_current_difference_count"] == 5
    assert comparison["summary"]["differences_remaining_unadjudicated"] == 4
    assert comparison["summary"]["changed_to_match_current_after_exposure"] == ["d05"]
    assert len(comparison["unresolved_after_phase2"]) == 7
    assert FREEZE["before_supplement_runtime_edits"] is True
    assert PROPOSAL["whole_corpus_independent_review"] is False
    assert PROPOSAL["external_expert_review"] is False
    assert PROPOSAL["real_world_efficacy_validated"] is False


@pytest.mark.parametrize("case", CASES, ids=lambda c: str(c["line"]))
def test_full_first_transcription_and_unresolved_alternatives_reach_selected_line(case):
    result = yao_text("天水訟", case["line"])
    review = result["poem_review_supplement"]
    assert review["entries"] == [case]
    assert review["content_sha256"] == FREEZE["proposal_canonical_sha256"]
    assert review["unresolved_character_positions"] == 7
    assert (
        result["poem_sections"][case["poem_index"] - 1]["text"] == case["current_text"]
    )
    assert result["poem_selection"]["selected_poem_indices"] == []
    review["entries"][0]["unresolved_readings"].append({"pollution": True})
    assert yao_text("天水訟", case["line"])["poem_review_supplement"]["entries"] == [
        case
    ]


@pytest.mark.parametrize("case", CASES, ids=lambda c: str(c["line"]))
def test_summary_only_reads_cannot_hide_new_disagreements(case):
    result = calculate_knowledge_read(domain="heluo", key=f"天水訟:{case['line']}")
    text = "\n".join(result["lines"])
    assert PROPOSAL["scope_note"] in text
    assert all(note in text for note in case["review_notes"])
    assert result["provenance"]["independent_whole_corpus_review_completed"] is False
    assert result["provenance"]["real_world_efficacy_validated"] is False


@pytest.mark.parametrize("case", CASES, ids=lambda c: str(c["line"]))
def test_review_and_literal_qualifications_on_actual_local_rest_mcp_cli(
    case, monkeypatch, tmp_path, capsys
):
    payload = {"domain": "heluo", "key": f"天水訟:{case['line']}"}
    fields = ["reference_details", "lines"]
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    with TestClient(api.app) as http:
        response = http.post(
            SPEC.rest_path,
            json=payload,
            params=[("fields", x) for x in fields]
            + [("strict_fields", "true"), ("response_char_limit", "0")],
        )
    subject = tmp_path / "subject.json"
    subject.write_text(json.dumps(payload, ensure_ascii=False))
    code = cli_run(
        [
            "knowledge_read",
            "--subject-file",
            str(subject),
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--response-char-limit",
            "0",
        ]
    )
    cli = json.loads(capsys.readouterr().out)

    async def call_mcp():
        async with Client(mcp.app) as client:
            return await client.call_tool(
                "knowledge_read",
                {
                    **payload,
                    "fields": fields,
                    "strict_fields": True,
                    "response_char_limit": 0,
                },
                raise_on_error=False,
            )

    protocol = asyncio.run(call_mcp())
    outputs = [response.json(), cli, protocol.structured_content]
    (tmp_path / "raw-three-adapters.json").write_text(
        json.dumps(
            {
                "HTTP_status": response.status_code,
                "CLI_exit": code,
                "MCP_is_error": protocol.is_error,
                "outputs": outputs,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    for output in outputs:
        assert output["reference_details"]["record"]["poem_review_supplement"][
            "entries"
        ] == [case]
        assert all(note in "\n".join(output["lines"]) for note in case["review_notes"])
    assert [o["reference_details"] for o in outputs] == [
        outputs[0]["reference_details"]
    ] * 3
    assert [o["lines"] for o in outputs] == [outputs[0]["lines"]] * 3


@pytest.mark.parametrize("kind", ["missing", "altered"])
def test_unbound_or_missing_review_cannot_silently_disappear(
    kind, monkeypatch, tmp_path
):
    bad = tmp_path / "review.json"
    if kind == "altered":
        value = json.loads((F / "supplement-proposal.json").read_bytes())
        value["unresolved_character_positions"] = 0
        bad.write_text(json.dumps(value, ensure_ascii=False))
    monkeypatch.setattr(hp, "REVIEW_PATH", bad)
    result = calculate_knowledge_read(domain="heluo", key="天水訟:4")
    assert result["status_code"] == 503
    assert result["error_code"] == "numerology_source_inconsistent"
    assert result["issues"][0]["code"] == "invalid_heluo_poem_collation"

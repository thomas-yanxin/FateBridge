"""All twelve preselected public routes retain charts and source evidence."""

import json
from pathlib import Path

import pytest

from tests.numerology.test_heluo_lin19_song6 import FAULTS, corrupt_source
from tests.numerology.test_heluo_lin19_song6 import source_cache as source_cache
from tests.support.transports import SPECS, business
from tests.support.transports import rest as shared_rest
from tests.support.transports import run_three

rest = shared_rest
cases = json.loads(
    (Path(__file__).parents[1] / "data/heluo/lin_song_routes.json").read_text()
)


@pytest.mark.parametrize("case", cases, ids=lambda c: c["hexagram"] + str(c["line"]))
def test_public_route_selected_source_text_matches_all_transports(
    case, rest, tmp_path, capsys, source_cache
):
    response, code, cli, mcp = run_three(
        SPECS["heluo"],
        case["payload"],
        ["chart", "numerology_evidence.selected_texts", "snapshot_text"],
        rest,
        tmp_path,
        capsys,
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    assert (
        business(response.json()) == business(cli) == business(mcp.structured_content)
    )
    for result in [response.json(), cli, mcp.structured_content]:
        selected = result["numerology_evidence"]["selected_texts"][case["phase"]]
        assert (selected["hexagram"], selected["line"]) == (
            case["hexagram"],
            case["line"],
        )
        text = selected["text"]
        if case["hexagram"] == "地澤臨":
            assert text["commentary_branch_selection"]["selected_section_ids"] == []
            if case["line"] in [4, 5]:
                ref = text["commentary_cross_references"][0]
                assert (
                    ref["target_line"] is None and ref["automatic_application"] is False
                )
        else:
            assert text["poem_selection"]["selected_poem_indices"] == []
            if case["line"] == 3:
                assert len(text["poem_sections"]) == 3
                assert text["text_provenance"]["poem_heading_text"].endswith("一首")


@pytest.mark.parametrize("kind", FAULTS)
def test_source_fault_remains_nonretryable503_on_every_adapter(
    kind, monkeypatch, tmp_path, rest, capsys, source_cache
):
    key = corrupt_source(kind, monkeypatch, tmp_path)
    response, code, cli, mcp = run_three(
        SPECS["knowledge_read"],
        dict(domain="heluo", key=key),
        ["lines"],
        rest,
        tmp_path,
        capsys,
    )
    assert response.status_code == 503 and code != 0 and mcp.is_error
    for result in [response.json(), cli, mcp.structured_content]:
        assert result["error_code"] == "numerology_source_inconsistent"
        assert result["retryable"] is False
    assert cli["status_code"] == mcp.structured_content["status_code"] == 503

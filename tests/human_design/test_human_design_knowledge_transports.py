"""Actual three adapters preserve meanings, unknowns and source rejection."""

from copy import deepcopy
from dataclasses import replace

import pytest

import fatebridge.application.execution as execution
from fatebridge.services.knowledge import calculate_knowledge_read
from tests.numerology.test_heluo_poem_transports import run_three
from tests.support.transports import SPECS, business
from tests.support.transports import rest as shared_rest

rest = shared_rest


@pytest.mark.parametrize("key", ["1.1", "1.4", "2.3", "2.6", "11.4", "64.6"])
def test_actual_line_reference_and_pending_meaning_agree_across_adapters(
    key, rest, tmp_path, capsys
):
    response, code, cli, mcp = run_three(
        SPECS["knowledge_read"],
        {"domain": "human_design", "key": key},
        [
            "domain",
            "category",
            "key",
            "reference_details",
            "provenance",
            "snapshot_text",
        ],
        rest,
        tmp_path,
        capsys,
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    assert (
        business(response.json()) == business(cli) == business(mcp.structured_content)
    )
    for value in [response.json(), cli, mcp.structured_content]:
        record = value["reference_details"]["record"]
        assert record["key"] == key
        assert record["selected_polarity"] is record["actual_fixing_state"] is None
        assert record["complete_line_meaning_accepted"] is False
        if key in {"11.4", "64.6"}:
            assert record["editorial_paraphrase"] is None
        else:
            assert record["editorial_paraphrase"] is not None
        if key == "2.3":
            assert (
                record["source_conditions"][0]["personal_condition_satisfied"] is None
            )
            assert record["source_conditions"][0]["automatic_application"] is False
            assert "永久" in value["snapshot_text"]
        if key == "2.6":
            assert "狭窄" in record["editorial_paraphrase"]["exaltation"]


@pytest.mark.parametrize("domain", ["human_design", None])
def test_registry_coverage_is_honest_on_actual_adapters(domain, rest, tmp_path, capsys):
    payload = {} if domain is None else {"domain": domain}
    response, code, cli, mcp = run_three(
        SPECS["knowledge_registry"],
        payload,
        ["domains", "source", "provenance"],
        rest,
        tmp_path,
        capsys,
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    assert (
        business(response.json()) == business(cli) == business(mcp.structured_content)
    )
    human = next(row for row in cli["domains"] if row["domain"] == "human_design")
    assert human["categories"][0]["count"] == 384
    assert human["categories"][0]["coverage"]["meanings_pending"] == 372
    assert human["categories"][0]["coverage"]["local_editorial_paraphrases"] == 12
    assert (
        human["categories"][0]["coverage"]["independently_accepted_line_meanings"] == 0
    )


@pytest.mark.parametrize("key", ["1.7", "65.1", "6/3"])
def test_invalid_line_keys_stay_user_errors_on_actual_adapters(
    key, rest, tmp_path, capsys
):
    response, code, cli, mcp = run_three(
        SPECS["knowledge_read"],
        {"domain": "human_design", "key": key},
        ["source"],
        rest,
        tmp_path,
        capsys,
    )
    assert response.status_code == 400 and code != 0 and mcp.is_error
    assert (
        response.json()["error_code"]
        == cli["error_code"]
        == mcp.structured_content["error_code"]
        == "knowledge.human_design.unknown_key"
    )


@pytest.mark.parametrize(
    "fault", ["text", "polarity", "certification", "wrong_complete_card"]
)
@pytest.mark.parametrize("unrelated_projection", [False, True])
def test_actual_request_rejects_forged_reference_before_projection(
    fault, unrelated_projection, monkeypatch, rest, tmp_path, capsys
):
    output = calculate_knowledge_read(domain="human_design", key="1.1")
    record = output["reference_details"]["record"]
    if fault == "text":
        record["editorial_paraphrase"]["exaltation"] = "Guaranteed reality prediction"
    elif fault == "polarity":
        record["selected_polarity"] = "exaltation"
        record["actual_fixing_state"] = "exaltation"
    elif fault == "certification":
        record["complete_line_meaning_accepted"] = True
    else:
        output = calculate_knowledge_read(domain="human_design", key="1.2")
    original = execution.execute_spec

    def forged(spec, request):
        if spec.key == "knowledge_read":
            spec = replace(spec, bind=lambda _: (lambda: deepcopy(output), (), {}))
        return original(spec, request)

    monkeypatch.setattr(execution, "execute_spec", forged)
    fields = ["source"] if unrelated_projection else ["reference_details"]
    response, code, cli, mcp = run_three(
        SPECS["knowledge_read"],
        {"domain": "human_design", "key": "1.1"},
        fields,
        rest,
        tmp_path,
        capsys,
    )
    assert response.status_code == 503 and code == 1 and mcp.is_error
    assert all(
        value["retryable"] is False
        for value in [response.json(), cli, mcp.structured_content]
    )


def test_source_conflict_after_metadata_stays_a_source_error(
    monkeypatch, rest, tmp_path, capsys
):
    from fatebridge.services import run_metadata

    original = run_metadata.attach_run_metadata

    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        if kwargs.get("tool_name") == "knowledge_read":
            result["reference_details"]["record"][
                "complete_line_meaning_accepted"
            ] = True
        return result

    monkeypatch.setattr(run_metadata, "attach_run_metadata", changed)
    response, code, cli, mcp = run_three(
        SPECS["knowledge_read"],
        {"domain": "human_design", "key": "1.1"},
        ["source"],
        rest,
        tmp_path,
        capsys,
    )
    assert response.status_code == 503 and code == 1 and mcp.is_error
    for result in [response.json(), cli, mcp.structured_content]:
        assert result["retryable"] is False
        assert result["error_code"] == "ephemeris_source_inconsistent"
        assert result["issues"][0]["code"] == "human_design_reference_changed"


@pytest.mark.parametrize("stage", ["before_projection", "after_metadata"])
@pytest.mark.parametrize(
    "fault",
    [
        "condition_true",
        "condition_erased",
        "automatic_application",
        "exhaustive_review",
    ],
)
def test_forged_source_condition_rejected_on_all_adapters_even_source_only_projection(
    stage, fault, monkeypatch, rest, tmp_path, capsys
):
    from fatebridge.services import run_metadata

    def corrupt(result):
        row = result["reference_details"]["record"]
        if fault == "condition_true":
            row["source_conditions"][0]["personal_condition_satisfied"] = True
        elif fault == "condition_erased":
            row["source_conditions"] = []
        elif fault == "automatic_application":
            row["source_conditions"][0]["automatic_application"] = True
        else:
            row["condition_review_status"] = "exhaustive_independent_review"
        return result

    if stage == "before_projection":
        output = corrupt(calculate_knowledge_read(domain="human_design", key="2.3"))
        original = execution.execute_spec

        def forged(spec, request):
            if spec.key == "knowledge_read":
                spec = replace(spec, bind=lambda _: (lambda: deepcopy(output), (), {}))
            return original(spec, request)

        monkeypatch.setattr(execution, "execute_spec", forged)
    else:
        original_metadata = run_metadata.attach_run_metadata

        def changed(*args, **kwargs):
            result = original_metadata(*args, **kwargs)
            return (
                corrupt(result)
                if kwargs.get("tool_name") == "knowledge_read"
                else result
            )

        monkeypatch.setattr(run_metadata, "attach_run_metadata", changed)
    response, code, cli, mcp = run_three(
        SPECS["knowledge_read"],
        {"domain": "human_design", "key": "2.3"},
        ["source"],
        rest,
        tmp_path,
        capsys,
    )
    assert response.status_code == 503 and code == 1 and mcp.is_error
    for value in [response.json(), cli, mcp.structured_content]:
        assert value["retryable"] is False
        assert value["error_code"] == "ephemeris_source_inconsistent"
        assert value["issues"][0]["code"] == "human_design_reference_changed"

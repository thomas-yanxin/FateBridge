"""Reject ambiguous stdout while recognizing preserved complete model reads."""

import json
from pathlib import Path

import pytest

from scripts.audit_bazi_budget_guide import decode_full_stdout


@pytest.mark.parametrize(
    "stdout",
    [
        'file_sha256 nope\n{"payload":{}}',
        "file_sha256 " + "a" * 64,
        "file_sha256 " + "a" * 64 + '\n{"payload":{}',
        "file_sha256 " + "a" * 64 + '\n{"payload":{}}\nextra',
        'other_prefix\n{"payload":{}}',
        '{"payload": []}',
        '{"selected_field": {}}',
    ],
)
def test_incomplete_or_unknown_stdout_is_rejected(stdout: str) -> None:
    with pytest.raises(ValueError):
        decode_full_stdout(stdout)


@pytest.mark.parametrize("kind", ["comprehensive", "career"])
def test_preserved_prefixed_first_stdout_contains_exact_same_run_payload(
    kind: str,
) -> None:
    folder = (
        Path(__file__).parent
        / "fixtures/bazi_semantic_run_v5"
        / f"bazi_{kind}_fidelity"
    )
    packet = json.loads((folder / "review-payloads-first.json").read_bytes())[0]
    events = [
        json.loads(line) for line in (folder / "events.jsonl").read_text().splitlines()
    ]
    observed = [
        event["item"]["aggregated_output"]
        for event in events
        if event.get("type") == "item.completed"
        and event.get("item", {}).get("exit_code") == 0
        and event["item"].get("command") in packet["model_file_read_commands"]
        and event["item"].get("aggregated_output", "").startswith("file_sha256 ")
    ]
    assert len(observed) == 1
    wrapper, prefixed = decode_full_stdout(observed[0])
    assert prefixed is True
    assert wrapper["payload"] == packet["payload"]
    # The first JSON-only collector observation is preserved, not rewritten.
    assert packet["full_file_stdout_preserved"] is False


def test_plain_complete_stdout_is_still_recognized() -> None:
    wrapper = {"payload": {"run_metadata": {"run_id": "fictional"}}}
    assert decode_full_stdout(json.dumps(wrapper)) == (wrapper, False)

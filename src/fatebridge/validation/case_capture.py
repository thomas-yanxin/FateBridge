"""Incremental evidence for explicitly supplied deterministic evaluation cases.

No production calculation imports this module. A complete local hash chain
detects changed bytes; it does not authenticate inputs or establish efficacy.
"""

from __future__ import annotations

import hashlib
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from fatebridge.validation.agent_capture import CaptureJournal, canonical, read_capture


async def collect_cases(
    path: Path,
    cases: Sequence[Mapping[str, Any]],
    calculate: Callable[[Mapping[str, Any]], Any],
    *,
    context: Mapping[str, Any],
) -> int:
    """Persist every input and result before proceeding; never retry a case."""
    inputs = [deepcopy(dict(case)) for case in cases]
    input_hash = hashlib.sha256(canonical(inputs)).hexdigest()
    # Validate header serializability before creating a private exclusive file.
    header = {
        "event": "batch_started",
        "case_count": len(inputs),
        "inputs_sha256": input_hash,
        "cases": inputs,
        "context": deepcopy(dict(context)),
    }
    canonical(header)
    journal = CaptureJournal(path, sync_to_disk=True)
    try:
        await journal.append(header)
        for index, case in enumerate(inputs):
            await journal.append({"event": "case_started", "index": index})
            try:
                result = calculate(deepcopy(case))
                await journal.append(
                    {"event": "case_returned", "index": index, "result": result}
                )
            except Exception as error:
                # If persistence itself failed the poisoned journal refuses
                # this append too; neither failure becomes a successful batch.
                if journal.persistence_failed:
                    raise
                await journal.append(
                    {
                        "event": "case_failed",
                        "index": index,
                        "error_type": type(error).__name__,
                        "error_message": str(error),
                    }
                )
                raise
        await journal.append(
            {
                "event": "batch_completed",
                "case_count": len(inputs),
                "inputs_sha256": input_hash,
            }
        )
    finally:
        journal.close()
    return len(inputs)


def inspect_cases(path: Path, *, require_complete: bool = True) -> dict[str, Any]:
    """Distinguish a verified prefix from completion of every registered case."""
    records = read_capture(path)
    if not records or records[0].get("event") != "batch_started":
        raise ValueError("Missing evaluation header")
    header = records[0]
    cases = header.get("cases")
    if (
        not isinstance(cases, list)
        or type(header.get("case_count")) is not int
        or header["case_count"] != len(cases)
    ):
        raise ValueError("Registered evaluation inputs changed")
    input_hash = hashlib.sha256(canonical(cases)).hexdigest()
    if input_hash != header.get("inputs_sha256"):
        raise ValueError("Registered evaluation input digest changed")
    results: list[Any] = []
    pending: int | None = None
    failed = False
    complete = False
    for record in records[1:]:
        event = record.get("event")
        if complete or failed:
            raise ValueError("Evaluation continued after its terminal record")
        if event == "case_started":
            if (
                pending is not None
                or type(record.get("index")) is not int
                or record["index"] != len(results)
                or len(results) >= len(cases)
            ):
                raise ValueError("Evaluation case order changed")
            pending = len(results)
        elif event in {"case_returned", "case_failed"}:
            if (
                pending is None
                or type(record.get("index")) is not int
                or record["index"] != pending
            ):
                raise ValueError("Evaluation result lacks its actual started case")
            if event == "case_failed":
                failed = True
            else:
                if "result" not in record:
                    raise ValueError("Evaluation result missing")
                results.append(record["result"])
                pending = None
        elif event == "batch_completed":
            if (
                pending is not None
                or len(results) != len(cases)
                or type(record.get("case_count")) is not int
                or record["case_count"] != len(cases)
                or record.get("inputs_sha256") != input_hash
            ):
                raise ValueError("Evaluation completion is missing registered cases")
            complete = True
        else:
            raise ValueError("Unknown evaluation record")
    if require_complete and not complete:
        raise ValueError(
            "Incomplete evaluation; verified prefix is not a complete batch"
        )
    return {
        "status": "complete" if complete else "failed" if failed else "incomplete",
        "case_count": len(cases),
        "completed_case_count": len(results),
        "pending_case_index": pending if not failed else None,
        "failed_case_index": pending if failed else None,
        "results": results,
        "context": header.get("context"),
        "inputs_sha256": input_hash,
        "last_record_sha256": records[-1]["sha256"],
        "scope": "Locally consistent capture only; no authenticity, source accuracy, model grade or prediction-efficacy certification.",
    }

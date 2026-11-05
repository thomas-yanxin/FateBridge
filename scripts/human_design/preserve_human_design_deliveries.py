"""Preserve same-run evaluation files while the model process is still alive.

This never calculates a chart or grades semantics. Files remain advertised
artifacts; preservation does not certify that the model read their full text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from fatebridge.validation.agent_capture import read_capture
from fatebridge.validation.evaluation_environment import (
    execution_directory,
    load_selection,
    process_environment,
    verify_stage_selection,
)
from scripts.human_design.audit_human_design_semantics import accept_delivery, response


def preserve_delivery(
    folder: Path, packet: dict[str, Any], index: int, *, full_requested: bool
) -> dict[str, Any]:
    declaration = packet["result_delivery"]
    original = Path(declaration["file_path"])
    target = folder / f"delivery-{index}.json"
    raw = target.read_bytes() if target.exists() else original.read_bytes()
    if target.exists() and original.exists() and original.read_bytes() != raw:
        raise ValueError("Original delivery differs from its preserved bytes")
    payload = json.loads(raw)["payload"]
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    binding: dict[str, Any] = {}
    accept_delivery(packet, binding, encoded, full_requested=full_requested)
    if not target.exists():
        descriptor, temporary = tempfile.mkstemp(
            prefix=".delivery-preservation-", dir=folder
        )
        staged = Path(temporary)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(
                staged, target
            )  # Atomic, exclusive: never replace an earlier receipt.
        except FileExistsError:
            if target.read_bytes() != raw:
                raise ValueError("Concurrent preservation has different bytes")
        staged.unlink()
    return {
        "journal_index": index,
        "file": target.name,
        "file_sha256": hashlib.sha256(raw).hexdigest(),
        "full_business_hash_verified": "complete" in binding,
        "full_result_requested": full_requested,
        "model_visibility_certified": False,
    }


def collect(run: Path, *, allow_incomplete_journal: bool) -> list[dict[str, Any]]:
    receipts = []
    for journal in sorted(run.glob("*/mcp-calls.jsonl")):
        try:
            records = read_capture(journal)
        except (ValueError, json.JSONDecodeError):
            if allow_incomplete_journal:
                continue  # Append may still be in flight; terminal collection is strict.
            raise
        case = []
        for index, record in enumerate(records):
            if (
                record.get("event") != "tool_call"
                or record.get("outcome") != "returned"
            ):
                continue
            packet = response(record)
            if not packet.get("result_delivery"):
                continue
            saved = preserve_delivery(
                journal.parent,
                packet,
                index,
                full_requested=record.get("arguments", {}).get("fields") is None,
            )
            case.append(saved)
            receipts.append({"case": journal.parent.name, **saved})
        (journal.parent / "delivery-preservation.json").write_text(
            json.dumps(case, indent=2) + "\n"
        )
    return receipts


def launch(preparation: Path) -> int:
    preparation = preparation.resolve()
    proposal = json.loads((preparation / "proposed-execution.json").read_text())
    command = proposal["command"]
    expected = str(preparation / "source/scripts/evaluate_agent.py")
    if (
        Path(command[0]).resolve() != Path(sys.executable).resolve()
        or command[1] != expected
    ):
        raise ValueError("Unexpected frozen evaluator command")
    if "--model" in command:
        raise ValueError("This cohort uses the CLI default, without a model override")
    if (preparation / "model-run").exists():
        raise FileExistsError(
            "Original model run already exists; never restart in place"
        )
    execution_environment = {**os.environ, **proposal["environment"]}
    prepared_report = json.loads((preparation / "preparation.json").read_text())
    expected_native = prepared_report.get("native_environment_sha256")
    if expected_native is not None:
        required = {
            "--native-environment": str(preparation / "native-environment.json"),
            "--native-environment-sha256": expected_native,
        }
        for flag, value in required.items():
            position = command.index(flag) if command.count(flag) == 1 else -1
            if (
                position < 0
                or position + 1 >= len(command)
                or command[position + 1] != value
            ):
                raise ValueError("Proposal changed the prepared native selection")
        selection, native_raw = load_selection(
            preparation / "native-environment.json", expected_native
        )
        execution_directory(native_raw)
        execution_environment = process_environment(selection, execution_environment)
    run = preparation / "model-run"
    with (preparation / "model-execution.log").open("x") as output:
        process = subprocess.Popen(
            command,
            cwd=proposal["cwd"],
            env=execution_environment,
            stdout=output,
            stderr=output,
        )
        (preparation / "model-process.json").write_text(
            json.dumps(
                {
                    "pid": process.pid,
                    "command": command,
                    "cwd": proposal["cwd"],
                    "prior_lost_runs_replaced": False,
                    "source": "new dated execution",
                },
                indent=2,
            )
            + "\n"
        )
        transient_errors = set()
        while process.poll() is None:
            try:
                collect(run, allow_incomplete_journal=True)
            except (OSError, ValueError) as error:
                transient_errors.add(str(error))
            time.sleep(1)
        code = process.wait()
    # Do not restart a timed-out/failed model or promote an incomplete capture.
    receipts = collect(run, allow_incomplete_journal=False)
    try:
        native_binding = verify_stage_selection(preparation, run)
    except (OSError, ValueError, TypeError) as error:
        native_binding = {
            "status": "rejected",
            "error": str(error),
            "stage_equivalence_verified": False,
        }
    helper_code = code if code else int(native_binding["status"] == "rejected")
    (preparation / "model-terminal.json").write_text(
        json.dumps(
            {
                "exit_code": code,
                "helper_exit_code": helper_code,
                "native_environment_binding": native_binding,
                "preserved_delivery_count": len(receipts),
                "transient_preservation_errors": sorted(transient_errors),
                "model_retried": False,
                "prior_lost_runs_replaced": False,
            },
            indent=2,
        )
        + "\n"
    )
    return helper_code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preparation", type=Path, required=True)
    args = parser.parse_args()
    return launch(args.preparation)


if __name__ == "__main__":
    raise SystemExit(main())

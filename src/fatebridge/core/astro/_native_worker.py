"""Private exec entry; not a CLI, server, arbitrary-code or pickle endpoint."""

from __future__ import annotations

import contextlib
import importlib
import json
import os
import sys
from pathlib import Path
from queue import Queue
from threading import Thread
from typing import Any

# -I ignores the caller's PYTHONPATH. Resolve the package beside this script,
# including in an installed wheel, instead of an unrelated editable checkout.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def main() -> None:
    from fatebridge.core.astro import native_execution as execution
    from fatebridge.core.astro.iers_ut1 import use_ut1_source
    from fatebridge.core.compressed_ephemeris import audit_compressed_endpoints
    from fatebridge.core.execution_context import call_clock
    from fatebridge.core.physical_ephemeris_policy import data_file_policy
    from fatebridge.utils.errors import EphemerisSourceError, JyotishCalculationError

    output = sys.stdout.buffer

    def send(message: dict[str, Any]) -> None:
        output.write(execution.message_bytes(message))
        output.flush()

    line = sys.stdin.buffer.readline(execution._MAX_MESSAGE + 1)
    if len(line) > execution._MAX_MESSAGE or not line.endswith(b"\n"):
        raise execution.NativeExecutionError("Invalid private calculation request")
    request = json.loads(line)
    if request["entry"] not in execution._ENTRIES:
        raise execution.NativeExecutionError("Unsupported private calculation entry")
    acknowledgements: Queue[bytes] = Queue(maxsize=1)

    def watch_parent() -> None:
        while True:
            acknowledgement = sys.stdin.buffer.readline(execution._MAX_MESSAGE + 1)
            if not acknowledgement:
                # The owning process exited (including SIGKILL), or closed its
                # request pipe after receiving the final result. Never carry
                # on a long grid after the sole result recipient disappears.
                os._exit(0)
            if len(acknowledgement) > execution._MAX_MESSAGE:
                os._exit(1)
            acknowledgements.put(acknowledgement)

    owner = Thread(target=watch_parent, name="fatebridge-native-owner", daemon=True)
    owner.start()
    # Process lifetime is exactly one operation. No parent native module, cache,
    # fixed Delta-T override, or fault-injection monkeypatch is inherited.
    execution._WORKER_ACTIVE = True
    selected = request["path"]
    if selected:
        os.environ["SE_EPHE_PATH"] = selected
    else:
        os.environ.pop("SE_EPHE_PATH", None)
    if request["jpl"]:
        os.environ["FATEBRIDGE_JPL_FILE"] = request["jpl"]
    else:
        os.environ.pop("FATEBRIDGE_JPL_FILE", None)
    with contextlib.redirect_stdout(sys.stderr), call_clock(request["clock"]) as clock:
        try:
            auxiliary = execution.AuxiliaryInputs(request["auxiliary_path"])
            if auxiliary.initial != request["auxiliary_fingerprints"]:
                raise EphemerisSourceError("auxiliary_changed_during")
            execution._AUXILIARY_EVIDENCE = {
                **auxiliary.evidence(),
                **execution.context_for_entry(request["entry"]),
            }
            from fatebridge.core.ephemeris_runtime import configure_ephemeris_path

            configure_ephemeris_path(selected or "")
            arguments = execution.decode(request["args"])
            options = execution.decode(request["kwargs"])
            if request["observer"]:

                def observe(*args: Any) -> None:
                    send({"kind": "sample", "args": execution.encode(args)})
                    ack = acknowledgements.get()
                    if json.loads(ack) != {"kind": "continue"}:
                        raise execution.NativeExecutionError(
                            "Invalid sample acknowledgement"
                        )

                options["_sample_observer"] = observe
            module, name = request["entry"].rsplit(".", 1)
            function = getattr(importlib.import_module(module), name)
            send({"kind": "ready"})
            try:
                with (
                    audit_compressed_endpoints(),
                    use_ut1_source(request.get("ut1_source", "swiss_delta_t")),
                    data_file_policy(
                        request.get("physical_ephemeris_policy", "auto")
                    ) as policy,
                ):
                    result = function(*arguments, **options)
            finally:
                auxiliary.check()
            response = {
                "kind": "result",
                "value": execution.encode_result(
                    result, request.get("result_encoding")
                ),
            }
            if policy is not None:
                response["physical_ephemeris_policy"] = policy.receipt()
        except EphemerisSourceError as error:
            response = {
                "kind": "result",
                "error": {"type": "source", "reason": error.reason},
            }
        except JyotishCalculationError as error:
            response = {
                "kind": "result",
                "error": {"type": "jyotish", "reason": error.reason},
            }
        except ValueError as error:
            response = {
                "kind": "result",
                "error": {"type": "value", "message": str(error)},
            }
        except ImportError:
            response = {"kind": "result", "error": {"type": "import"}}
        except Exception:
            response = {"kind": "result", "error": {"type": "internal"}}
        send({**response, "clock_reads": clock.reads})
        # Avoid interpreter shutdown while the pipe reader holds a buffered-I/O
        # lock. The parent closes stdin after accepting the flushed response.
        owner.join()


if __name__ == "__main__":
    main()

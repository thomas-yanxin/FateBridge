"""Isolate each current native sample from other ephemeris contexts."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def sample(case, backend):
    result = subprocess.run(
        [sys.executable, "-m", "scripts.astrodice.astrodice_current_sampling", backend],
        input=json.dumps(case),
        text=True,
        capture_output=True,
        check=True,
        cwd=ROOT,
    )
    return json.loads(result.stdout)


def current(case, backend):
    from scripts.astrodice.astrodice_de441_records import calendar_jd_tdb

    if backend == "jpl_record_window":
        kernel = (
            ROOT / case["source"] / f"diagnostic-kernels/case-{case['window']:02}.eph"
        )
        os.environ["FATEBRIDGE_JPL_FILE"] = kernel.name
        os.environ["SE_EPHE_PATH"] = str(kernel.parent)
    elif backend == "swieph":
        os.environ.pop("FATEBRIDGE_JPL_FILE", None)
        os.environ["SE_EPHE_PATH"] = str(ROOT / "ephe")
    else:
        raise ValueError("Unplanned backend")
    from fatebridge.core import ephemeris_runtime as runtime
    from fatebridge.core.astro import ephemeris
    from fatebridge.core.astro import runtime as domain_runtime
    from fatebridge.core.astro.source_session import source_session

    epoch = float(calendar_jd_tdb(case["label"]))
    calls = []
    original = domain_runtime.ephemeris_call

    def recording(operation, *args, **kwargs):
        result = original(operation, *args, **kwargs)
        if operation == "calc":
            calls.append(
                {"args": args, "returned_flags": result[1], "coordinates": result[0]}
            )
        return result

    domain_runtime.ephemeris_call = recording
    runtime.configure_ephemeris_path()
    rows = []
    try:
        for body in case["bodies"]:
            calls.clear()
            metadata = {}
            with source_session() as session:
                state = ephemeris._swisseph_planet_state(
                    body,
                    julian_day_tt=epoch,
                    source_trace=session.trace,
                    motion_metadata=metadata,
                )
            row = {
                "body": body,
                "native_numeric_jd": epoch,
                "native_calls": list(calls),
                "metadata": metadata,
                "trace": session.trace.snapshot(),
            }
            if state is None:
                row.update(
                    status="unavailable", error="Current native source unavailable"
                )
            else:
                row.update(status="ready", state=state[0], model=state[1])
            rows.append(row)
    finally:
        domain_runtime.ephemeris_call = original
    return {"case": case, "backend_requested": backend, "rows": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backend", choices=("swieph", "jpl_record_window"))
    args = parser.parse_args()
    print(json.dumps(current(json.loads(sys.stdin.read()), args.backend)))


if __name__ == "__main__":
    main()


def sample_lunar(run, split, index, backend, *, jpl_file=None):
    import tempfile

    with tempfile.TemporaryDirectory(prefix="astrodice-current-") as temporary:
        output = Path(temporary) / "sample.json"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.astrodice.astrodice_lunar_pipeline",
                "native",
                "--run",
                str(run),
                "--split",
                split,
                "--index",
                str(index),
                "--backend",
                backend,
                "--output",
                str(output),
                *(
                    ["--jpl-file", str(jpl_file)]
                    if jpl_file is not None and backend == "jpl_record_window"
                    else []
                ),
            ],
            text=True,
            capture_output=True,
            check=True,
            cwd=ROOT,
        )
        return json.loads(output.read_text())

"""Raw native definition controls with explicit cache isolation, not astronomy truth.

The v1 collector reused C state across centuries. Its bytes and failed
arithmetic comparison are retained. This post-candidate control keeps the same
epochs and arithmetic line but resets native state before each body, as the
production state reader does. No FateBridge code is imported.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import swisseph as swe


def collect(protocol: Path) -> dict:
    plan = json.loads(protocol.read_text())
    rows = []
    names = ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn")
    for case in plan["cases"]:
        positions = {}
        for name in names:
            swe.close()
            swe.set_ephe_path(os.environ.get("SE_EPHE_PATH", ""))
            swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
            flags, offset = swe.get_ayanamsa_ex(case["tt"], swe.FLG_SWIEPH)
            if flags < 0:
                raise ValueError("Native ayanamsha failed")
            state, flags = swe.calc(
                case["tt"],
                getattr(swe, name.upper()),
                swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_SIDEREAL,
            )
            if flags < 0:
                raise ValueError("Native position failed")
            positions[name] = {"longitude": state[0], "flags": flags}
        rows.append({**case, "ayanamsha_tt": offset, "positions": positions})
    return {
        "protocol_sha256": hashlib.sha256(protocol.read_bytes()).hexdigest(),
        "native_version": swe.version,
        "production_imports": False,
        "independent_astronomy": False,
        "collected_after_candidate": True,
        "input_cases_or_arithmetic_line_changed": False,
        "native_state_policy": "close and set path before each body",
        "v1_raw_failure_reclassified_as_pass": False,
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = collect(args.protocol)
    # Evidence files must never be silently overwritten by an after runner.
    with args.output.open("x") as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(f"Collected {len(result['rows'])} isolated native definition controls")


if __name__ == "__main__":
    main()

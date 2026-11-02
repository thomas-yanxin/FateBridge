"""Post-opening receipt hardening, separate from the frozen numerical grader.

No thresholds, coordinates, numerical algorithms or first grades are changed.
This checks provenance, source interiors and claim boundaries on all first rows.
"""

import argparse
import json
import math
import struct
import sys
from fractions import Fraction as Q
from pathlib import Path

from scripts.astrodice_lunar_pipeline import BIAS, plan, sha, unit_state, write_new

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.historical_source_identity import HistoricalSources

INPUT_SHA = "a7ec2aa1d470942d205442d429e0335a460baef0f122f7bc7f5f781e9b6cc359"
REFERENCE_SHAS = {
    "development": "4df1711bc494bb86aef4a13211d3271879b9c586b4803ff4723f27c6248a5053",
    "heldout": "3c2c7f269c2ead426e2d9957f094c5beec27b8585eb5fb3a10522265c7728d8d",
}


def require_unpromoted(value):
    for name in (
        "physical_TT_equivalence_certified",
        "original_failure_records_regraded",
    ):
        if value.get(name) is not False:
            raise ValueError("Unproved claim promoted: " + name)
    if (
        "complete_moving_frame_derivative_certified" in value
        and value["complete_moving_frame_derivative_certified"] is not False
    ):
        raise ValueError("Unproved complete moving frame promoted")
    for name, expected in (
        ("original_overall_gate", 1),
        ("original_production_gate", 2),
    ):
        if name in value and value[name] != expected:
            raise ValueError("Original gate changed")


def native_receipt(native, manifest, source_dir):
    if native["status"] != "ready":
        return {"status": native["status"], "qualified": False}
    backend = native["backend_requested"]
    expected_flag = 2 if backend == "swieph" else 1
    if (native["native_version"], native["binding_version"]) != ("2.10.03", 20230604):
        # __version__ is the build stamp; the distribution 2.10.3.2 is separately
        # checked by the actual production motion policy.
        raise ValueError("Unplanned native binding/runtime")
    if native["native_library_sha256"] not in {
        digest for name, digest in manifest.items() if name.endswith((".so", ".pyd"))
    }:
        raise ValueError("Native binary detached from prefrozen identity")
    calls = [c for c in native["native_calls"] if c["args"][1] != -1]
    if not calls or any(c["returned_flags"] & 7 != expected_flag for c in calls):
        raise ValueError("Actual returned physical backend changed")
    if not any(
        c["args"][0] == native["native_numeric_jd"] and c["args"][1] == 1 for c in calls
    ):
        raise ValueError("No native Moon call at the declared numeric reception")
    for file in native["trace"]["files"]:
        path = (
            (Path("ephe") / file["filename"])
            if backend == "swieph"
            else source_dir / "diagnostic-kernels" / file["filename"]
        )
        if file["sha256"] != manifest[str(path)] or file["de_number"] != 441:
            raise ValueError("Observed source identity detached from prefrozen bytes")
    if not native["trace"]["files"] or native["trace"]["has_unidentified_sources"]:
        raise ValueError("Source receipt incomplete")
    policy = native["metadata"]["lunar_light_time"]["fixed_frame_source_derivative"]
    if (
        any(
            policy[k] is not True
            for k in (
                "center_native_states_reproduced_exactly",
                "center_file_context_reproduced_exactly",
                "input_frame_held_fixed",
            )
        )
        or policy["complete_moving_frame_derivative_certified"] is not False
    ):
        raise ValueError("Source restoration or frame scope changed")
    from fatebridge.core.astro.continuous_lahiri import (
        decode_native_fixed_reception_state,
    )

    decoded = decode_native_fixed_reception_state(
        native["native_numeric_jd"],
        policy["full_fixed_frame_apparent_position_au"],
        policy["full_fixed_frame_velocity_au_per_native_argument_day"],
    )
    direction, derivative = unit_state(
        decoded["position"], decoded["velocity_per_native_argument_day"]
    )
    if (
        decoded != native["decoded_state"]
        or direction != native["direction_j2000"]
        or derivative != native["direction_derivative_per_native_argument_day_j2000"]
    ):
        raise ValueError("Derived evidence detached from actual policy vectors")
    control = native["bias_position_control"]
    residual = [
        abs(
            control["j2000"][k]
            - math.fsum(a * b for a, b in zip(BIAS[k], control["icrs"][:3]))
        )
        for k in range(3)
    ]
    if residual != control["absolute_residual_au"]:
        raise ValueError("Bias control detached from native coordinates")
    return {
        "status": "verified",
        "physical_native_calls": len(calls),
        "actual_backend_bit": expected_flag,
        "bias_position_maximum_residual_au": max(residual),
        "atomic_native_read_set_proven": False,
        "independent_absolute_frame_certification": False,
    }


def interiors(source_dir, window, time_bounds):
    raw = (source_dir / f"record-responses/case-{window:02}.bin").read_bytes()
    header = (source_dir / "header.bin").read_bytes()
    low, high = map(Q, time_bounds)
    rows = []
    for group in (2, 9):
        _, _, parts = struct.unpack_from("<3i", header, 2696 + 12 * group)
        source = next(
            (
                r
                for r in (raw[i : i + 8144] for i in range(0, len(raw), 8144))
                if Q(struct.unpack_from("<d", r)[0])
                <= low
                <= high
                < Q(struct.unpack_from("<d", r, 8)[0])
            ),
            None,
        )
        if source is None:
            raise ValueError("Source coordinate outside record support")
        begin, end = map(Q, struct.unpack_from("<2d", source))
        width = (end - begin) / parts
        cell = (low - begin) // width
        margin = min(low - (begin + cell * width), begin + (cell + 1) * width - high)
        if margin <= 0:
            raise ValueError("Unique centre derivative not proved at source boundary")
        rows.append(
            {
                "group": group,
                "record_begin": str(begin),
                "cell": int(cell),
                "strict_interior_margin_source_days": str(margin),
            }
        )
    return rows


def audit(run):
    if sha(run / "inputs-before-evaluation.json") != INPUT_SHA:
        raise ValueError("Prefrozen input manifest changed")
    protocol = plan(run)
    manifest = json.loads((run / "inputs-before-evaluation.json").read_text())
    source = Path(protocol["reference_source"])
    maintenance = json.loads((run / "maintenance-code-before-heldout.json").read_text())
    sources = HistoricalSources(Path(__file__).resolve().parents[1])
    for name, digest in maintenance.items():
        if not sources.matches(Path(name), digest):
            raise ValueError("Numerical code changed after opening heldout")
    rows = []
    cells = []
    for split in ("development", "heldout"):
        reference_path = run / f"{split}-reference-first.json"
        if sha(reference_path) != REFERENCE_SHAS[split]:
            raise ValueError("First reference changed")
        reference = json.loads(reference_path.read_text())
        require_unpromoted(reference)
        grade = json.loads((run / f"{split}-audit-first.json").read_text())
        require_unpromoted(grade)
        for index, ref in enumerate(reference["rows"]):
            for clock in ("reception_epoch", "emission_epoch"):
                cells.append(
                    {
                        "split": split,
                        "label": ref["label"],
                        "clock": clock,
                        "interiors": interiors(
                            source, ref["window"], ref["model"][clock]
                        ),
                    }
                )
            for backend in protocol["backends"]:
                native = json.loads(
                    (run / f"native-{split}-first/{backend}-{index}.json").read_text()
                )
                rows.append(
                    {
                        "split": split,
                        "label": ref["label"],
                        "backend": backend,
                        **native_receipt(native, manifest, source),
                    }
                )
    return {
        "post_opening_provenance_hardening": True,
        "rows": rows,
        "source_interiors": cells,
        "physical_TT_equivalence_certified": False,
        "complete_moving_frame_derivative_certified": False,
        "original_failure_records_regraded": False,
        "original_overall_gate": 1,
        "original_production_gate": 2,
        "new_numerical_rows_or_grades": 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    write_new(args.output, audit(args.run))


if __name__ == "__main__":
    main()

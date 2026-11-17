"""Export independent original-C/SOFA/SciPy controls for the solar horizon.

The external build and its failures/errata remain the reference authority.
No FateBridge import or reference calculation from production outputs.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-directory", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    source, destination = args.reference_directory, args.output_directory
    observer = json.loads(
        (source / "official-observer-reference-contract.json").read_text()
    )
    optics = json.loads((source / "solar-optics-reference-v2.json").read_text())
    reference_hashes = {}
    for name, digest in (
        ("official-observer-reference-contract.npz", observer["reference_sha256"]),
        ("solar-optics-reference-v2.npz", optics["reference_sha256"]),
    ):
        actual = hashlib.sha256((source / name).read_bytes()).hexdigest()
        if actual != digest:
            raise ValueError(f"External reference hash mismatch: {name}")
        reference_hashes[name] = actual
    with np.load(source / "official-observer-reference-contract.npz") as data:
        observers = [
            {
                "input": row.tolist(),
                "physical_pv": values[:6].tolist(),
                "source_site": values[12:15].tolist(),
                "source_flags": int(values[31]),
            }
            for row, values in zip(data["inputs"], data["values"], strict=True)
        ]
    with np.load(source / "solar-optics-reference-v2.npz") as data:
        optical = [
            {
                "row": index,
                "input": data["inputs"][index].tolist(),
                "values": (
                    data["values"][index, :5].tolist()
                    if data["status"][index] == 0
                    else None
                ),
                "status": int(data["status"][index]),
            }
            for index in range(len(data["inputs"]))
            if index % 17 == 0
        ]
    roots = []
    polar_constructions = []
    for label in ("root", "grazing", "edge", "c04-edge", "polar-cluster"):
        summary = json.loads(
            (source / f"solar-event-{label}-reference-summary.json").read_text()
        )
        path = source / f"solar-event-{label}-reference.json.gz"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != summary["reference_sha256"]:
            raise ValueError(f"External root reference hash mismatch: {label}")
        reference_hashes[path.name] = digest
        reference = json.loads(gzip.decompress(path.read_bytes()))
        if label == "polar-cluster":
            polar_constructions = reference["constructions"]
        path = source / f"solar-event-{label}-cases.json"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != reference["cases_sha256"]:
            raise ValueError(f"External root inputs hash mismatch: {label}")
        reference_hashes[path.name] = digest
        cases = json.loads(path.read_text())
        for case, row in zip(cases, reference["rows"], strict=True):
            if label == "root" and not (
                case["longitude"] == 0 and case["latitude"] in {-90, -66.5, 0, 66.5, 90}
            ):
                continue
            roots.append({"family": label, "input": case, "reference": row})
    names = (
        "observer_reference.c",
        "solar_optics_reference_v2.c",
        "generate_observer_reference_contract.py",
        "generate_solar_optics_reference_v2.py",
        "generate_solar_root_reference.py",
        "generate_solar_grazing_reference.py",
        "generate_solar_edge_reference.py",
        "generate_solar_c04_edge_reference.py",
        "generate_guolao_clock_reference.py",
        "generate_solar_polar_cluster_reference.py",
        "generate_solar_polar_cluster_reference.first-attempt.py",
        "solar-polar-cluster-plan.json",
        "generate_polar_adjacent_root_probe.py",
        "polar-adjacent-root-plan.json",
        "diagnose_original_moshier_velocity.py",
        "observer-reference-adjudication.md",
        "solar-optics-reference-erratum.md",
    )
    generators = {name: (source / name).read_text() for name in names}
    reference = {
        "format_version": 2,
        "production_imported": False,
        "selection": "After comparisons: all4428 observers, every17th of17712 optical rows, ordinary windows at longitude0 and the five declared latitudes, all512 central-grazing, all512 window-edge,72 real C04-edge and192 near-polar clustered-extrema windows. Not blind validation.",
        "gates": {
            "observer_position_metres": 0.0001,
            "observer_velocity_mps": 1e-8,
            "optics_arcseconds": 1e-6,
            "event_seconds": 0.001,
        },
        "reference_hashes": reference_hashes,
        "build_receipts": {
            name: json.loads((source / name).read_text())
            for name in (
                "sofa-build.json",
                "author-contract-build.json",
                "observer-reference-build-contract.json",
                "solar-optics-v2-build.json",
            )
        },
        "generator_sources": generators,
        "generator_hashes": {
            name: hashlib.sha256(content.encode()).hexdigest()
            for name, content in generators.items()
        },
        "retained_before_failures": {
            **{
                label: json.loads(
                    (source / f"candidate-solar-{label}-summary.json").read_text()
                )
                for label in ("edge", "c04-edge")
            },
            "first-polar-cluster": json.loads(
                (source / "candidate-polar-cluster-before.json").read_text()
            ),
            "first-spectral-polar-cluster": json.loads(
                (
                    source / "candidate-solar-first-spectral-polar-cluster-summary.json"
                ).read_text()
            ),
            "first-spectral-ordinary": json.loads(
                (
                    source / "candidate-solar-first-spectral-root-summary.json"
                ).read_text()
            ),
        },
        "polar_constructions": polar_constructions,
        "first_polar_construction_summary": json.loads(
            (
                source / "solar-event-polar-cluster-first-attempt-summary.json"
            ).read_text()
        ),
        "polar_adjacent_root_diagnostic": json.loads(
            (source / "polar-adjacent-root-summary.json").read_text()
        ),
        "moshier_velocity_diagnostic": json.loads(
            (source / "original-moshier-velocity-diagnosis.json").read_text()
        ),
        "guolao_clock": json.loads(
            (source / "guolao-clock-frame-reference.json").read_text()
        ),
        "scope": "Finite declared-model observer/optical/root conformance. SOFA and ERFA share ancestry. No measured EOP/geoid/meteorology, independent global dynamical acceptance, exact tangency or prediction certification. Native JPL and installed/protocol checks are separate.",
        "observers": observers,
        "optics": optical,
        "events": roots,
    }
    destination.mkdir(parents=True, exist_ok=True)
    content = json.dumps(
        reference, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode()
    (destination / "reference.json.gz").write_bytes(gzip.compress(content, mtime=0))
    # The new physical-source comparison keeps every original fixed input.
    # It is a separate artifact: native-model expectations above are unchanged.
    de440_path = source / "de440-polar-observation-reference.json.gz"
    de440_bytes = de440_path.read_bytes()
    de440_summary = json.loads(
        (source / "de440-polar-observation-summary.json").read_text()
    )
    de440_digest = hashlib.sha256(de440_bytes).hexdigest()
    if de440_digest != de440_summary["reference_sha256"]:
        raise ValueError("External DE440 horizon reference hash mismatch")
    (destination / "de440-reference.json.gz").write_bytes(de440_bytes)
    de440_provenance = {
        "reference_sha256": de440_digest,
        "production_imported": False,
        "plan": json.loads((source / "de440-polar-observation-plan.json").read_text()),
        "kernel": json.loads((source / "de440-download.json").read_text()),
        "geometry_build": json.loads(
            (source / "de440-solar-reference-geometry-build.json").read_text()
        ),
        "generator_sources": {
            name: (source / name).read_text()
            for name in (
                "generate_de440_polar_reference.py",
                "de440_solar_reference_geometry.c",
                "generate_de440_polar_reference.first-attempt.py",
                "generate_de440_polar_reference.second-attempt.py",
                "diagnose_native_solar_source_cache.py",
            )
        },
        "first_attempt_failure": (
            source / "de440-polar-observation.stderr"
        ).read_text(),
        "second_attempt_failure": (
            source / "de440-polar-observation-attempt2.stderr"
        ).read_text(),
        "native_cache_control": json.loads(
            (source / "native-solar-ecl-nut-cache-diagnosis.json").read_text()
        ),
        "scope": "All96 original polar locations/times and both definitions. Original JPL coefficients, official SOFA, independent jplephem and Skyfield controls. Shared-source model/numerical agreement is not observational or all-domain certification.",
    }
    (destination / "de440-provenance.json").write_text(
        json.dumps(de440_provenance, ensure_ascii=False, indent=2) + "\n"
    )
    jpl_path = source / "solar-all-inputs-jpl-reference.json.gz"
    jpl_bytes = jpl_path.read_bytes()
    jpl_summary = json.loads((source / "solar-all-inputs-jpl-summary.json").read_text())
    jpl_digest = hashlib.sha256(jpl_bytes).hexdigest()
    if jpl_digest != jpl_summary["reference_sha256"]:
        raise ValueError("External all-input original JPL reference hash mismatch")
    (destination / "jpl-reference.json.gz").write_bytes(jpl_bytes)
    jpl_provenance = {
        "reference_sha256": jpl_digest,
        "production_imported": False,
        "summary": jpl_summary,
        "generator_sources": {
            name: (source / name).read_text()
            for name in (
                "generate_all_solar_jpl_reference.py",
                "generate_all_solar_jpl_reference.first-attempt.py",
                "solar_reference_geometry_all_epochs.c",
            )
        },
        "build_receipts": {
            name: json.loads((source / name).read_text())
            for name in (
                "calceph-build.json",
                "calceph-build-first-attempt.json",
                "solar-all-epochs-geometry-build.json",
                "calceph-original-kernel-controls.json",
                "calceph-original-kernel-unit-controls-v2.json",
                "de441-source-lineage-check.json",
            )
        },
        "first_attempt_failure": (source / "solar-all-inputs-jpl.stderr").read_text(),
        "scope": "Every10288 original window, unmodified1ms TT/UT1 gates and ordered counts. Original files through official CALCEPH/SOFA and independent SciPy roots. Not observed EOP, atmospheric, continuous-domain or SOTA certification.",
    }
    (destination / "jpl-provenance.json").write_text(
        json.dumps(jpl_provenance, ensure_ascii=False, indent=2) + "\n"
    )
    file_reference = source / "solar-file-j2000-original-reference-reference.json.gz"
    file_bytes = file_reference.read_bytes()
    file_summary = json.loads(
        (source / "solar-file-j2000-original-reference-summary.json").read_text()
    )
    if hashlib.sha256(file_bytes).hexdigest() != file_summary["reference_sha256"]:
        raise ValueError("External selected-file JPL reference hash mismatch")
    (destination / "jpl-file-reference.json.gz").write_bytes(file_bytes)
    (destination / "jpl-file-provenance.json").write_text(
        json.dumps(
            {
                "summary": file_summary,
                "production_imported": False,
                "generator_source": (
                    source / "generate_file_j2000_solar_reference.py"
                ).read_text(),
                "fixture_lineage": json.loads(
                    (source / "solar-jpl-fixture-lineage.json").read_text()
                ),
                "before_split_epoch_control": json.loads(
                    (
                        source / "solar-jpl-split-epoch-before-integration.json"
                    ).read_text()
                ),
                "scope": "Additional24 maintained J2000 file windows and30 exact split-epoch source controls. Full original192 polar and10288 automatic cohorts remain separate and unchanged.",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    print(
        json.dumps(
            {
                "observers": len(observers),
                "optics": len(optical),
                "event_windows": len(roots),
                "uncompressed_sha256": hashlib.sha256(content).hexdigest(),
                "de440_windows": de440_summary["windows"],
                "de440_roots": de440_summary["roots"],
                "jpl_windows": jpl_summary["rows"],
                "jpl_roots": jpl_summary["events"],
                "selected_file_windows": file_summary["rows"],
            }
        )
    )


if __name__ == "__main__":
    main()

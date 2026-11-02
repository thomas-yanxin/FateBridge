"""Compare the unchanged Swiss date coordinates to JPL directions in IAU2006/00A.

ERFA transforms are frozen independently before importing production. This
reuses the same 113 anchors, does not refit the PMO minutes, and does not
certify physical accuracy or complete calendar conformance.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import math
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/ren_sofa_ecliptic_v1"
PRIOR = ROOT / "tests/fixtures/ren_horizons_inertial_v1"
IMPLEMENTATION = (
    "src/fatebridge/core/almanac.py",
    "src/fatebridge/core/solar_term_runtime.py",
    "src/fatebridge/core/ephemeris_runtime.py",
    "src/fatebridge/core/astro/time_scales.py",
    "src/fatebridge/core/astro/historical_utc.py",
    "src/fatebridge/core/astro/geometry.py",
    "src/fatebridge/utils/timezones.py",
    "scripts/audit_ren_sofa_ecliptic.py",
)
CRITERIA = dict(
    transformed_direction_arcseconds=0.1,
    internal_route_agreement_arcseconds=0.0000001,
    original_pmo_seconds=30,
    original_cross_frame_arcseconds=0.1,
    tdb_tt_proxy_max_seconds=0.002,
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prior_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "sofa_prior", ROOT / "scripts/audit_ren_horizons_inertial.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_contents(corpus: Path) -> dict[str, bytes]:
    """Preserve the original generator bytes inside a single-member archive.

    This is a packaging change after collection, not a new reference freeze.
    The original logical name and all precomparison content hashes remain.
    """
    contents = {
        str(p.relative_to(corpus)): p.read_bytes()
        for p in corpus.rglob("*")
        if p.is_file() and p.name != "freeze.json"
    }
    if "reference-generator.zip" in contents:
        if "build_reference.py" in contents:
            raise ValueError("Duplicate frozen ecliptic generator")
        with zipfile.ZipFile(io.BytesIO(contents.pop("reference-generator.zip"))) as z:
            if z.namelist() != ["build_reference.py"]:
                raise ValueError("Frozen ecliptic generator archive inventory changed")
            contents["build_reference.py"] = z.read("build_reference.py")
    return contents


def reference(corpus: Path = CORPUS) -> dict[str, Any]:
    freeze = json.loads((corpus / "freeze.json").read_text())
    contents = source_contents(corpus)
    names = set(contents)
    if names != set(freeze["files"]):
        raise ValueError("Frozen ecliptic inventory changed")
    for name, digest in freeze["files"].items():
        if hashlib.sha256(contents[name]).hexdigest() != digest:
            raise ValueError("Frozen ecliptic source changed: " + name)
    pre = json.loads((corpus / "precomparison-freeze.json").read_text())
    if pre["production_calculations_performed"] is not False or set(
        pre["files"]
    ) != names - {"precomparison-freeze.json"}:
        raise ValueError("Ecliptic precomparison inventory changed")
    if any(
        hashlib.sha256(contents[n]).hexdigest() != s for n, s in pre["files"].items()
    ):
        raise ValueError("Ecliptic precomparison source changed")
    protocol = json.loads((corpus / "protocol.json").read_text())
    if protocol["criteria"] != CRITERIA:
        raise ValueError("Original ecliptic criteria changed")
    if (
        sha(PRIOR / "freeze.json") != protocol["prior_freeze_sha256"]
        or sha(PRIOR / "protocol.json") != protocol["prior_protocol_sha256"]
    ):
        raise ValueError("Original 113-event reference changed")
    old = prior_module().reference()
    if (
        protocol["cohort"] != old["protocol"]["cohort"]
        or len(protocol["cohort"]) != 113
    ):
        raise ValueError("Complete 113-event ecliptic cohort required")
    data = json.loads((corpus / "reference.json").read_text())
    if any(
        data[k] != v
        for k, v in dict(
            pyerfa="2.0.1.5",
            erfa="2.0.1",
            sofa="20231011",
            numpy="2.5.4",
            production_imported=False,
            production_calculations_performed=False,
        ).items()
    ):
        raise ValueError("Independent ecliptic engine identity changed")
    if len(data["records"]) != 113:
        raise ValueError("All ecliptic reference records required")
    for row, case, original in zip(data["records"], protocol["cohort"], old["rows"]):
        if any(
            row[k] != case[k]
            for k in ("year", "term", "query_label", "label_time_scale")
        ):
            raise ValueError("Ecliptic anchor differs from original cohort")
        if (
            row["ra_icrf_degrees"] != original["RA_(ICRF-a-app)"]
            or row["dec_icrf_degrees"] != original["DEC_(ICRF-a-app)"]
            or row["tdb_minus_ut_seconds"] != original["TDB-UT"]
        ):
            raise ValueError("Ecliptic input differs from raw JPL direction")
        label = datetime.fromisoformat(original["timestamp_label"])
        expected = (
            2451545
            + (label - datetime(2000, 1, 1, 12)).total_seconds() / 86400
            + original["TDB-UT"] / 86400
        )
        if row["jd_tt_proxy"] != expected:
            raise ValueError("Ecliptic time proxy differs")
        validate_matrix_record(row)
    return dict(protocol=protocol, reference=data, original_rows=old["rows"])


def validate_matrix_record(row: dict[str, Any]) -> None:
    if not all(
        math.isfinite(row[key])
        for key in (
            "jd_tt_proxy",
            "ra_icrf_degrees",
            "dec_icrf_degrees",
            "nutation_longitude_radians",
            "true_ecliptic_longitude_degrees",
            "true_ecliptic_latitude_degrees",
            "control_longitude_degrees",
            "control_latitude_degrees",
        )
    ):
        raise ValueError("Nonfinite ecliptic angle/time")
    matrix = row["mean_ecliptic_matrix"]
    vector = row["reference_vector"]
    result = row["transformed_mean_vector"]
    if (
        len(matrix) != 3
        or any(len(r) != 3 for r in matrix)
        or len(vector) != 3
        or len(result) != 3
    ):
        raise ValueError("Invalid ecliptic matrix shape")
    if not all(math.isfinite(v) for r in matrix for v in r) or not all(
        math.isfinite(v) for v in vector + result
    ):
        raise ValueError("Nonfinite ecliptic matrix/vector")
    for i in range(3):
        for j in range(3):
            if (
                abs(sum(matrix[i][k] * matrix[j][k] for k in range(3)) - int(i == j))
                > 1e-14
            ):
                raise ValueError("Ecliptic matrix is not orthogonal")
    determinant = sum(
        matrix[0][i]
        * (
            matrix[1][(i + 1) % 3] * matrix[2][(i + 2) % 3]
            - matrix[1][(i + 2) % 3] * matrix[2][(i + 1) % 3]
        )
        for i in range(3)
    )
    if abs(determinant - 1) > 1e-14:
        raise ValueError("Ecliptic matrix is not a proper rotation")
    ra, dec = map(math.radians, (row["ra_icrf_degrees"], row["dec_icrf_degrees"]))
    literal = [
        math.cos(dec) * math.cos(ra),
        math.cos(dec) * math.sin(ra),
        math.sin(dec),
    ]
    if max(abs(a - b) for a, b in zip(literal, vector)) > 1e-15:
        raise ValueError("Ecliptic reference vector differs")
    q = [sum(a * b for a, b in zip(r, vector)) for r in matrix]
    if max(abs(a - b) for a, b in zip(q, result)) > 1e-15:
        raise ValueError("Ecliptic matrix multiplication differs")
    lon = math.degrees(
        (math.atan2(q[1], q[0]) + row["nutation_longitude_radians"]) % (2 * math.pi)
    )
    lat = math.degrees(math.atan2(q[2], math.hypot(q[0], q[1])))
    if (
        abs((lon - row["true_ecliptic_longitude_degrees"] + 180) % 360 - 180) > 1e-11
        or abs(lat - row["true_ecliptic_latitude_degrees"]) > 1e-11
    ):
        raise ValueError("Ecliptic annotated direction differs from matrix result")
    for prefix in ("true_ecliptic_", "control_"):
        if (
            not 0 <= row[prefix + "longitude_degrees"] < 360
            or not -90 <= row[prefix + "latitude_degrees"] <= 90
        ):
            raise ValueError("Invalid ecliptic coordinate range")


def audit() -> dict[str, Any]:
    ref = reference()
    before = {p: sha(ROOT / p) for p in IMPLEMENTATION}
    from fatebridge.core.ephemeris_runtime import (
        ephemeris_call,
        ephemeris_model_from_retflag,
        swe,
    )
    from fatebridge.core.solar_term_runtime import solar_term_cache_context

    environment = repr(solar_term_cache_context(swe))
    prior = prior_module()
    comparisons = []
    errors = []
    for row, original in zip(ref["reference"]["records"], ref["original_rows"]):
        try:
            if swe is None:
                raise RuntimeError("Swiss Ephemeris is unavailable")
            position, retflag = ephemeris_call(
                "calc", row["jd_tt_proxy"], swe.SUN, swe.FLG_SWIEPH
            )
            model = ephemeris_model_from_retflag(retflag)
            if (
                retflag not in (1, 2, 4)
                or model not in {"swieph", "jpl", "moshier"}
                or not all(math.isfinite(x) for x in position[:2])
                or not 0 <= position[0] < 360
                or not -90 <= position[1] <= 90
            ):
                raise ValueError("Actual default solar geometry/model differs")
            separation = prior.separation_arcseconds(
                position[0],
                position[1],
                row["true_ecliptic_longitude_degrees"],
                row["true_ecliptic_latitude_degrees"],
            )
            route = prior.separation_arcseconds(
                row["control_longitude_degrees"],
                row["control_latitude_degrees"],
                row["true_ecliptic_longitude_degrees"],
                row["true_ecliptic_latitude_degrees"],
            )
            oldlon = ((position[0] - original["ObsEcLon"] + 180) % 360 - 180) * 3600
            oldlat = (position[1] - original["ObsEcLat"]) * 3600
            comparisons.append(
                dict(
                    year=row["year"],
                    term=row["term"],
                    query_label=row["query_label"],
                    label_time_scale=row["label_time_scale"],
                    jd_tt_proxy=row["jd_tt_proxy"],
                    actual_longitude=position[0],
                    actual_latitude=position[1],
                    reference_longitude=row["true_ecliptic_longitude_degrees"],
                    reference_latitude=row["true_ecliptic_latitude_degrees"],
                    longitude_difference_arcseconds=(
                        (position[0] - row["true_ecliptic_longitude_degrees"] + 180)
                        % 360
                        - 180
                    )
                    * 3600,
                    latitude_difference_arcseconds=(
                        position[1] - row["true_ecliptic_latitude_degrees"]
                    )
                    * 3600,
                    separation_arcseconds=separation,
                    within_transformed_direction_criterion=separation
                    <= CRITERIA["transformed_direction_arcseconds"],
                    internal_route_separation_arcseconds=route,
                    within_internal_route_criterion=route
                    <= CRITERIA["internal_route_agreement_arcseconds"],
                    original_cross_frame_longitude_difference_arcseconds=oldlon,
                    original_cross_frame_latitude_difference_arcseconds=oldlat,
                    within_original_cross_frame_criterion=max(abs(oldlon), abs(oldlat))
                    <= CRITERIA["original_cross_frame_arcseconds"],
                    actual_model=model,
                    actual_retflag=retflag,
                )
            )
        except Exception as exc:
            errors.append(
                dict(
                    year=row["year"],
                    term=row["term"],
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
            )
    stable = before == {p: sha(ROOT / p) for p in IMPLEMENTATION}
    envstable = environment == repr(solar_term_cache_context(swe))
    selected = (
        stable
        and envstable
        and len(comparisons) == 113
        and not errors
        and all(
            r["within_transformed_direction_criterion"]
            and r["within_internal_route_criterion"]
            for r in comparisons
        )
    )
    return dict(
        audit_id="ren_sofa_ecliptic_v1",
        reference_sha256=sha(CORPUS / "freeze.json"),
        implementation_sha256=before,
        implementation_unchanged_during_audit=stable,
        ephemeris_environment_unchanged=envstable,
        expected_count=113,
        compared_count=len(comparisons),
        comparisons=comparisons,
        calculation_errors=errors,
        transformed_direction_failures=sum(
            not r["within_transformed_direction_criterion"] for r in comparisons
        ),
        original_cross_frame_failures=sum(
            not r["within_original_cross_frame_criterion"] for r in comparisons
        ),
        max_transformed_separation_arcseconds=max(
            (r["separation_arcseconds"] for r in comparisons), default=None
        ),
        max_internal_route_separation_arcseconds=max(
            (r["internal_route_separation_arcseconds"] for r in comparisons),
            default=None,
        ),
        criteria=CRITERIA,
        reference_runtime={
            k: ref["reference"][k] for k in ("pyerfa", "erfa", "sofa", "numpy")
        },
        selected_alignment_checks_passed=selected,
        all_performed_comparisons_passed=selected
        and all(r["within_original_cross_frame_criterion"] for r in comparisons),
        scope=ref["protocol"]["scope"],
        new_independent_events=0,
        new_horizons_queries=0,
        pmo_model_equivalence_certified=False,
        full_supported_calendar_domain_certified=False,
        classical_acceptance_passed=False,
        free_text_semantic_acceptance_passed=False,
        model_invocations=0,
        goal_complete=False,
    )


def recompute_erfa(ref: dict[str, Any]) -> dict[str, Any]:
    """Optional fresh reference replay; never overwrite the frozen corpus."""
    try:
        import erfa  # type: ignore[import-not-found]  # Optional reference replay.
        import numpy as np  # type: ignore[import-not-found]

        versions = dict(
            pyerfa=erfa.__version__,
            erfa=erfa.version.erfa_version,
            sofa=erfa.version.sofa_version,
            numpy=np.__version__,
        )
        if versions != {k: ref["reference"][k] for k in versions}:
            raise ValueError("ERFA replay runtime differs from the frozen reference")
        comparisons = []
        for row in ref["reference"]["records"]:
            part = row["jd_tt_proxy"] - 2451545
            matrix = erfa.ecm06(2451545.0, part)
            vector = np.array(row["reference_vector"])
            lon, lat = erfa.c2s(matrix @ vector)
            dpsi, deps = erfa.nut06a(2451545.0, part)
            control = (
                erfa.rx(
                    erfa.obl06(2451545.0, part) + deps, erfa.pnm06a(2451545.0, part)
                )
                @ vector
            )
            clon, clat = erfa.c2s(control)
            values = (
                math.degrees(erfa.anp(lon + dpsi)),
                math.degrees(lat),
                math.degrees(erfa.anp(clon)),
                math.degrees(clat),
            )
            keys = (
                "true_ecliptic_longitude_degrees",
                "true_ecliptic_latitude_degrees",
                "control_longitude_degrees",
                "control_latitude_degrees",
            )
            delta = max(abs(a - row[k]) for a, k in zip(values, keys))
            comparisons.append(
                dict(year=row["year"], term=row["term"], max_difference_degrees=delta)
            )
        return dict(
            passed=len(comparisons) == 113
            and all(r["max_difference_degrees"] <= 1e-11 for r in comparisons),
            versions=versions,
            compared_count=len(comparisons),
            comparisons=comparisons,
            frozen_reference_overwritten=False,
        )
    except Exception as exc:
        return dict(passed=False, error_type=type(exc).__name__, error=str(exc))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--recompute-erfa", action="store_true")
    args = parser.parse_args()
    result = audit()
    if args.recompute_erfa:
        native = recompute_erfa(reference())
        result["fresh_erfa_recomputation"] = native
        result["selected_alignment_checks_passed"] &= native["passed"]
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        {
            k: result[k]
            for k in (
                "expected_count",
                "compared_count",
                "transformed_direction_failures",
                "original_cross_frame_failures",
                "max_transformed_separation_arcseconds",
                "selected_alignment_checks_passed",
                "goal_complete",
            )
        }
    )
    return 0 if result["selected_alignment_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

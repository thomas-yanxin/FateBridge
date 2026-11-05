"""Compare actual production TT roots with the unchanged 113-event JPL cohort.

The new reference queries TT directly and transforms apparent ICRF rays into
IAU2006/2000A. It is model comparison, not observation or civil-clock proof.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shlex
import zipfile
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/ren_horizons_tt_v1"
COMPARISON = ROOT / "tests/fixtures/ren_horizons_tt_comparison_v1"
PIN = "4f22aef6865e48d22dcc74450258982e7029c195b71ec45031b1cee82f9e530d"
COMPARISON_PIN = "501caf8e7465ab3a2fbd846486e2d61710ce441f495b457d02de7276e372c57f"
TERMS = "小寒 大寒 立春 雨水 惊蛰 春分 清明 谷雨 立夏 小满 芒种 夏至 小暑 大暑 立秋 处暑 白露 秋分 寒露 霜降 立冬 小雪 大雪 冬至".split()
J2000 = datetime(2000, 1, 1, 12)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen(folder: Path, pin: str) -> dict[str, str]:
    if sha(folder / "freeze.json") != pin:
        raise ValueError("Frozen TT reference identity changed")
    manifest: dict[str, str] = json.loads((folder / "freeze.json").read_text())["files"]
    inventory = {
        str(p.relative_to(folder))
        for p in folder.rglob("*")
        if p.is_file() and p != folder / "freeze.json"
    }
    if inventory != set(manifest):
        raise ValueError("Frozen TT reference inventory changed")
    for name, digest in manifest.items():
        if sha(folder / name) != digest:
            raise ValueError("Frozen TT reference content changed: " + name)
    return manifest


def reference(corpus: Path = CORPUS, comparison: Path = COMPARISON) -> dict[str, Any]:
    manifest = frozen(corpus, PIN)
    frozen(comparison, COMPARISON_PIN)
    pre = json.loads((corpus / "precomparison-freeze.json").read_text())
    if (
        pre["production_imported"] is not False
        or pre["production_calculations_performed"] is not False
        or set(pre["files"]) != set(manifest) - {"precomparison-freeze.json"}
        or any(sha(corpus / n) != h for n, h in pre["files"].items())
    ):
        raise ValueError("TT precomparison reference changed")
    protocol = json.loads((corpus / "protocol.json").read_text())
    specification = json.loads((comparison / "protocol.json").read_text())
    if (
        protocol["criteria"]["original_crossing_absolute_seconds"] != 1
        or specification["criterion_seconds"] != 1
        or specification["pmo_numeric_criterion_seconds"] != 30
        or specification["initial_reference_freeze_sha256"] != PIN
        or specification["production_calculations_performed"] is not False
        or [p["id"] for p in specification["profiles"]]
        != ["native_swiss", "native_moshier", "analytic", "de440", "spk"]
    ):
        raise ValueError("TT cohort or comparison criteria changed")
    prior = ROOT / "tests/fixtures/ren_horizons_crossings_v1"
    if (
        sha(prior / "freeze.json") != protocol["prior_freeze_sha256"]
        or sha(prior / "collection/horizons-protocol.json")
        != protocol["prior_protocol_sha256"]
    ):
        raise ValueError("Original 113-event cohort identity changed")
    prior_manifest = json.loads((prior / "freeze.json").read_text())["files"]
    if any(sha(prior / n) != h for n, h in prior_manifest.items()):
        raise ValueError("Original 113-event source changed")
    old = json.loads((prior / "collection/horizons-protocol.json").read_text())
    cases = protocol["cohort"]
    key = lambda c: (c["year"], c["term"], c["published_moment"])
    if len(cases) != 113 or list(map(key, cases)) != list(map(key, old["cohort"])):
        raise ValueError("All original 113 events are required")
    for case in cases:
        center = (
            datetime.fromisoformat(case["published_moment"])
            .astimezone(timezone.utc)
            .replace(tzinfo=None)
        )
        if case["initial_tt_labels"] != [
            (center + timedelta(seconds=s)).isoformat(sep=" ", timespec="milliseconds")
            for s in (-300, -150, 0, 150, 300)
        ]:
            raise ValueError("Independent TT query window changed")
    import erfa
    import numpy

    from tests.ren_horizons_reference import crossing, parse, transform

    if (
        erfa.__version__,
        erfa.version.erfa_version,
        erfa.version.sofa_version,
        numpy.__version__,
    ) != ("2.0.1.5", "2.0.1", "20231011", "2.5.4"):
        raise ValueError("TT reference transform runtime differs")
    transport = json.loads((corpus / "transport-protocol.json").read_text())
    initial = json.loads((corpus / "initial-reference.json").read_text())
    data = json.loads((corpus / "reference.json").read_text())
    if (
        len(data["events"]) != 113
        or len(initial["events"]) != 113
        or data["production_imported"] is not False
        or data["production_calculations_performed"] is not False
    ):
        raise ValueError("Complete independent TT reference required")
    observed: dict[str, list[dict[str, Any]]] = {}
    for stage, labels in (
        ("initial", [s for c in cases for s in c["initial_tt_labels"]]),
        (
            "refinement",
            [s for c in initial["events"] for s in c["refinement_tt_labels"]],
        ),
    ):
        directory = corpus / "collection" / transport["collection_names"][stage]
        queries = sorted(directory.glob("*.query.json"))
        size = transport["effective_batch_size"]
        if len(queries) != math.ceil(len(labels) / size):
            raise ValueError("Complete TT request batches required")
        rows = []
        for index, path in enumerate(queries):
            base = Path(str(path).removesuffix(".query.json"))
            query = json.loads(path.read_text())
            batch = labels[index * size : (index + 1) * size]
            params = protocol["params"] | {
                "TLIST": " ".join("'" + s + "'" for s in batch)
            }
            if (
                query["params"] != params
                or query["endpoint"] != protocol["endpoint"]
                or query["protocol_sha256"] != sha(corpus / "protocol.json")
                or query["transport_protocol_sha256"]
                != sha(corpus / "transport-protocol.json")
                or params["TIME_TYPE"] != "'TT'"
                or shlex.split(params["TLIST"]) != batch
            ):
                raise ValueError("Remote TT request differs from fixed cohort")
            status = json.loads(base.with_suffix(".status.json").read_text())
            response = base.with_suffix(".response.json")
            if (
                status["curl_exit"] != 0
                or status["http_status"] != "200"
                or status["requested_rows"] != len(batch)
                or status["response_sha256"] != sha(response)
            ):
                raise ValueError("Unsuccessful or replaced remote TT response")
            rows.extend(parse(response, batch))
        observed[stage] = [transform(row) for row in rows]
    if len(observed["initial"]) != 565 or len(observed["refinement"]) != 226:
        raise ValueError("All 791 direct TT probes are required")
    if observed["initial"] != initial["transformed_probes"]:
        raise ValueError("Stored TT transform differs from raw JPL reconstruction")
    for i, (case, seed, result) in enumerate(
        zip(cases, initial["events"], data["events"], strict=True)
    ):
        target = (285 + TERMS.index(case["term"]) * 15) % 360
        root = crossing(observed["initial"][5 * i : 5 * i + 5], target)
        pair = observed["refinement"][2 * i : 2 * i + 2]
        refined = crossing(pair, target)
        expected_seed = case | {
            "target_longitude": target,
            "initial_root_tt": root.isoformat(sep=" ", timespec="microseconds"),
            "refinement_tt_labels": [
                (root + timedelta(seconds=s)).isoformat(
                    sep=" ", timespec="milliseconds"
                )
                for s in (-1, 1)
            ],
        }
        expected_result = expected_seed | {
            "refined_root_tt": refined.isoformat(sep=" ", timespec="microseconds"),
            "refinement_probes": pair,
            "initial_minus_refined_seconds": (root - refined).total_seconds(),
        }
        if seed != expected_seed or result != expected_result:
            raise ValueError("Independent TT interpolation or event binding differs")
    return {"protocol": protocol, "specification": specification, "reference": data}


def tt_days(label: str) -> Fraction:
    moment = datetime.fromisoformat(label)
    if moment.tzinfo is not None:
        raise ValueError("Reference TT label must not masquerade as UTC")
    delta = moment - J2000
    micros = (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds
    return Fraction(2451545) + Fraction(micros, 86400000000)


def compare_cases(
    data: dict[str, Any],
    observe: Callable[[dict[str, Any]], dict[str, Any]],
    profile: dict[str, Any],
) -> dict[str, Any]:
    cases = data["reference"]["events"]
    if len(cases) != 113 or len({(c["year"], c["term"]) for c in cases}) != 113:
        raise ValueError("Complete unique 113-event comparison required")
    rows = []
    for case in cases:
        row: dict[str, Any] = {
            "year": case["year"],
            "term": case["term"],
            "reference_root_tt": case["refined_root_tt"],
        }
        try:
            actual = observe(case)
            parts = actual["selected_tt_parts"]
            if len(parts) != 2 or any(
                type(v) not in (int, float) or not math.isfinite(v) for v in parts
            ):
                raise ValueError("Actual root must have two finite TT parts")
            delta = float(
                (sum(map(Fraction, parts)) - tt_days(case["refined_root_tt"])) * 86400
            )
            civil = datetime.fromisoformat(actual["civil_datetime"])
            if civil.utcoffset() is None:
                raise ValueError("Actual civil label must retain an offset")
            minute_delta = (
                civil - datetime.fromisoformat(case["published_moment"])
            ).total_seconds()
            identity = (
                actual["provider"] == profile["expected_provider"]
                and actual["model"] == profile["expected_model"]
            )
            row.update(
                actual=actual,
                actual_minus_reference_tt_seconds=delta,
                within_original_tt_criterion=abs(delta) <= 1,
                source_identity_matches=identity,
                actual_minus_printed_civil_seconds=minute_delta,
                within_original_pmo_numeric_criterion=abs(minute_delta) <= 30,
                error=None,
            )
        except Exception as error:
            row.update(
                error=f"{type(error).__name__}: {error}",
                within_original_tt_criterion=None,
                source_identity_matches=None,
                within_original_pmo_numeric_criterion=None,
            )
        rows.append(row)
    valid = [r for r in rows if r["error"] is None]
    return {
        "profile": profile["id"],
        "expected_count": 113,
        "compared_count": len(rows),
        "successful_calculations": len(valid),
        "tt_failure_count": sum(
            r["within_original_tt_criterion"] is False for r in rows
        ),
        "source_identity_failures": sum(
            r["source_identity_matches"] is False for r in rows
        ),
        "unavailable_count": len(rows) - len(valid),
        "maximum_tt_difference_seconds": max(
            (abs(r["actual_minus_reference_tt_seconds"]) for r in valid), default=None
        ),
        "pmo_numeric_failure_count_on_same_113_events": sum(
            r["within_original_pmo_numeric_criterion"] is False for r in rows
        ),
        "comparisons": rows,
        "all_declared_tt_comparisons_passed": len(rows) == len(valid) == 113
        and all(
            r["within_original_tt_criterion"] and r["source_identity_matches"]
            for r in valid
        ),
        "original_minute_gate_reclassified": False,
        "new_unique_events": 0,
        "full_supported_calendar_domain_certified": False,
        "classical_acceptance_passed": False,
        "goal_complete": False,
    }


def audit(data: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    # All external references have been rebuilt before importing production.
    from fatebridge.core import almanac

    years: dict[int, dict[str, Any]] = {}
    errors: dict[int, Exception] = {}

    def observe(case: dict[str, Any]) -> dict[str, Any]:
        year = case["year"]
        if year not in years and year not in errors:
            try:
                years[year] = {
                    t.name: t for t in almanac.get_solar_terms_for_year(year, "UTC")
                }
            except Exception as error:
                errors[year] = error
        if year in errors:
            raise errors[year]
        term = years[year][case["term"]]
        detail = term.solar_model_details
        if not isinstance(detail, dict):
            raise ValueError("Actual selected root receipt is missing")
        parts = detail.get("selected_crossing_tt_parts")
        if parts is None:
            parts = [detail["selected_crossing_jd_tt"], 0.0]
        return {
            "selected_tt_parts": parts,
            "provider": term.resolution_provider,
            "model": term.ephemeris_model,
            "retflags": list(term.ephemeris_retflags),
            "library_version": term.ephemeris_library_version,
            "civil_datetime": term.moment.isoformat(),
            "numerical_representation": detail["numerical_epoch_representation"],
        }

    return compare_cases(data, observe, profile)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        choices=["native_swiss", "native_moshier", "analytic", "de440", "spk"],
    )
    parser.add_argument("--ephe-dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = reference()
    result: dict[str, Any]
    if args.profile is None:
        result = {
            "reference_events": 113,
            "direct_tt_raw_probes": 791,
            "raw_reconstruction_matches": True,
            "reference_pin": PIN,
            "comparison_pin": COMPARISON_PIN,
            "production_calculations_performed": False,
            "goal_complete": False,
        }
        status = 0
    else:
        if args.ephe_dir is None:
            parser.error("--profile requires an explicit --ephe-dir")
        profile = next(
            p for p in data["specification"]["profiles"] if p["id"] == args.profile
        )
        os.environ["FATEBRIDGE_SOLAR_TERM_MODEL"] = profile["mode"]
        os.environ["SE_EPHE_PATH"] = str(args.ephe_dir.resolve())
        os.environ.pop("FATEBRIDGE_JPL_FILE", None)
        os.environ.pop("FATEBRIDGE_SOLAR_SPK_FILE", None)
        if args.profile == "spk":
            os.environ["FATEBRIDGE_SOLAR_SPK_FILE"] = str(
                args.ephe_dir.resolve() / "solar-de440.bsp"
            )
        paths = [
            p
            for p in (ROOT / "src").rglob("*")
            if p.is_file() and "__pycache__" not in p.parts
        ] + [Path(__file__), ROOT / "uv.lock", ROOT / "pyproject.toml"]
        before = {str(p.relative_to(ROOT)): sha(p) for p in paths}
        external_paths = [
            p
            for p in args.ephe_dir.glob("*")
            if p.is_file()
            and p.name.startswith(
                ("sepl", "semo", "swe_deltat", "sedeltat", "seleapsec")
            )
        ]
        if args.profile == "spk":
            external_paths.append(args.ephe_dir / "solar-de440.bsp")
        external_before = {
            str(p.resolve()): sha(p) for p in external_paths if p.is_file()
        }
        result = audit(data, profile)
        result.update(reference_pin=PIN, comparison_pin=COMPARISON_PIN)
        stable = before == {str(p.relative_to(ROOT)): sha(p) for p in paths}
        external_stable = external_before == {
            str(p.resolve()): sha(p) for p in external_paths if p.is_file()
        }
        result.update(
            implementation_sha256=before,
            implementation_unchanged=stable,
            external_source_sha256=external_before,
            external_sources_unchanged=external_stable,
        )
        result["all_declared_tt_comparisons_passed"] &= stable and external_stable
        status = 0 if result["all_declared_tt_comparisons_passed"] else 1
    with args.output.open("x") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k
                not in {
                    "comparisons",
                    "implementation_sha256",
                    "external_source_sha256",
                }
            },
            ensure_ascii=False,
        )
    )
    return status


if __name__ == "__main__":
    raise SystemExit(main())

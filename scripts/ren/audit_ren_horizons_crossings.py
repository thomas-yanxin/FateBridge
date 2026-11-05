"""Offline diagnostics against frozen JPL crossings; retain the PMO failures.

The 113 events were selected before fetching JPL. Probes and refinements are
samples of those same events, not additional independent reference cases.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import shlex
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/ren_horizons_crossings_v1"
TERMS = "小寒 大寒 立春 雨水 惊蛰 春分 清明 谷雨 立夏 小满 芒种 夏至 小暑 大暑 立秋 处暑 白露 秋分 寒露 霜降 立冬 小雪 大雪 冬至".split()
IMPLEMENTATION = (
    "src/fatebridge/core/almanac.py",
    "src/fatebridge/core/solar_term_runtime.py",
    "src/fatebridge/core/ephemeris_runtime.py",
    "src/fatebridge/core/ephemeris_installation.py",
    "src/fatebridge/core/astro/runtime.py",
    "src/fatebridge/core/astro/geometry.py",
    "src/fatebridge/core/astro/time_scales.py",
    "src/fatebridge/core/astro/historical_utc.py",
    "src/fatebridge/core/astro_models.py",
    "src/fatebridge/utils/timezones.py",
    "scripts/ren/audit_ren_horizons_crossings.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wrapped_degrees(value: float) -> float:
    return (value + 180) % 360 - 180


def parse_response(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text())
    if data.get("error"):
        raise ValueError(f"JPL returned an error: {data['error']}")
    if data.get("signature") != {
        "source": "NASA/JPL Horizons API",
        "version": "1.0",
    }:
        raise ValueError("Unexpected frozen JPL file API signature")
    before, table = data["result"].split("$$SOE", 1)
    table = table.split("$$EOE", 1)[0]
    for token in (
        "Target body name: Sun (10)",
        "Center body name: Earth (399)",
        "Center-site name: GEOCENTRIC",
        "{source: DE441}",
        "NO (AIRLESS)",
        "Calendar mode   : Gregorian",
    ):
        if token not in before:
            raise ValueError(f"JPL coordinate metadata differs: {token}")
    header = next(line for line in before.splitlines() if "Date__(UT)" in line)
    columns = [value.strip() for value in next(csv.reader([header]))]
    indexes = {
        key: columns.index(key) for key in ("TDB-UT", "ObsEcLon", "ObsEcLat", "UT1-UTC")
    }
    rows = []
    for fields in csv.reader(io.StringIO(table.strip())):
        stamp = datetime.strptime(fields[0].strip(), "%Y-%b-%d %H:%M:%S.%f")
        row: dict[str, Any] = {
            "timestamp_label": stamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        }
        for key, index in indexes.items():
            value = fields[index].strip()
            # Historical EOP is absent; do not fabricate DUT1=0 or drop cases.
            if key == "UT1-UTC" and value == "n.a.":
                if stamp >= datetime(1962, 1, 20):
                    raise ValueError("Unexpected missing modern JPL DUT1")
                row[key] = None
            else:
                row[key] = float(value)
                if not math.isfinite(row[key]):
                    raise ValueError("Non-finite JPL coordinate or time offset")
        if not 0 <= row["ObsEcLon"] < 360 or not -90 <= row["ObsEcLat"] <= 90:
            raise ValueError("Invalid JPL angular units/range")
        rows.append(row)
    if not rows:
        raise ValueError("Empty JPL ephemeris table")
    return rows


def batch_rows(path: Path) -> list[dict[str, Any]]:
    query = json.loads(path.with_suffix("").with_suffix(".query.json").read_text())
    if query["endpoint"] != "https://ssd.jpl.nasa.gov/api/horizons_file.api":
        raise ValueError("Unexpected JPL endpoint")
    params = query["params"]
    for key, value in {
        "COMMAND": "'10'",
        "CENTER": "'500@399'",
        "TIME_TYPE": "'UT'",
        "QUANTITIES": "'30,31,49'",
        "TLIST_TYPE": "'CAL'",
    }.items():
        if params.get(key) != value:
            raise ValueError(f"Unexpected JPL request: {key}")
    source = path.with_suffix("").with_suffix(".input.txt")
    if sha(source) != query["input_sha256"]:
        raise ValueError("JPL submitted input differs from frozen request")
    expected = [datetime.fromisoformat(label) for label in shlex.split(params["TLIST"])]
    rows = parse_response(path)
    if [datetime.fromisoformat(row["timestamp_label"]) for row in rows] != expected:
        raise ValueError("JPL returned timestamps differ from submitted cohort")
    return rows


def interpolate(samples: list[dict[str, Any]], target: float) -> tuple[datetime, float]:
    residuals = [wrapped_degrees(row["ObsEcLon"] - target) for row in samples]
    if not all(a < b for a, b in zip(residuals, residuals[1:])):
        raise ValueError("JPL probes must progress monotonically near the crossing")
    pairs = [
        i for i in range(len(samples) - 1) if residuals[i] <= 0 <= residuals[i + 1]
    ]
    if len(pairs) != 1:
        raise ValueError("JPL probes must bracket exactly one crossing")
    index = pairs[0]
    lo, hi = [
        datetime.fromisoformat(row["timestamp_label"])
        for row in samples[index : index + 2]
    ]
    fraction = -residuals[index] / (residuals[index + 1] - residuals[index])
    return lo + (hi - lo) * fraction, fraction


def reference(corpus: Path = CORPUS) -> dict[str, Any]:
    manifest = json.loads((corpus / "freeze.json").read_text())
    names = {
        str(path.relative_to(corpus))
        for path in corpus.rglob("*")
        if path.is_file() and path != corpus / "freeze.json"
    }
    if names != set(manifest["files"]):
        raise ValueError("Frozen JPL inventory changed")
    for name, expected in manifest["files"].items():
        if sha(corpus / name) != expected:
            raise ValueError(f"Frozen JPL source changed: {name}")
    collection = corpus / "collection"
    precomparison = json.loads((collection / "pre-comparison-freeze.json").read_text())
    if any(
        sha(collection / name) != value
        for name, value in precomparison["files"].items()
    ):
        raise ValueError("External references differ from the pre-comparison freeze")
    protocol = json.loads((collection / "horizons-protocol.json").read_text())
    if protocol["criteria"] != {
        "existing_printed_minute_absolute_seconds": 30,
        "existing_coordinate_absolute_arcseconds": 0.1,
        "independent_refinement_bracket_half_width_seconds": 1,
        "interpolated_root_not_an_observation": True,
    }:
        raise ValueError("Original criteria changed")
    prior = json.loads((corpus / "prior-pmo-comparisons.json").read_text())
    prior_rows = prior["selected_comparisons"]
    expected_keys = {
        (row["year"], row["term"])
        for row in prior_rows
        if not row["within_printed_minute_criterion"]
    } | {(year, term) for year in (1900, 1972, 2011, 2025) for term in TERMS}
    keys = [(row["year"], row["term"]) for row in protocol["cohort"]]
    if len(keys) != 113 or len(set(keys)) != 113 or set(keys) != expected_keys:
        raise ValueError("Complete frozen 113-event diagnostic cohort is required")
    if (
        len(prior_rows) != 113
        or {(r["year"], r["term"]) for r in prior_rows} != set(keys)
        or sum(not r["within_printed_minute_criterion"] for r in prior_rows) != 21
        or prior["original_full_cohort_count"] != 3024
        or prior["original_full_failure_count"] != 21
    ):
        raise ValueError(
            "All 21 prior PMO failures and the fixed denominator must remain"
        )
    initial = []
    for source in json.loads(
        (collection / "initial-combined-sources.json").read_text()
    ):
        initial.extend(batch_rows(collection / source["path"]))
    refinement = []
    for path in sorted((collection / "refinement").glob("*.response.json")):
        refinement.extend(batch_rows(path))
    if len(initial) != 565 or len(refinement) != 226:
        raise ValueError("All original and refinement probes are required")
    if initial != json.loads((collection / "initial-combined-rows.json").read_text()):
        raise ValueError("Annotated initial probes differ from the raw JPL responses")
    ref: dict[str, Any] = json.loads(
        (collection / "independent-reference.json").read_text()
    )
    if [(r["year"], r["term"]) for r in ref["cases"]] != keys:
        raise ValueError("Crossing annotation cohort differs from the protocol")
    for index, (case, annotation) in enumerate(zip(protocol["cohort"], ref["cases"])):
        target = (285 + 15 * TERMS.index(case["term"])) % 360
        samples = initial[index * 5 : index * 5 + 5]
        anchor = (
            datetime.fromisoformat(case["published_moment"])
            .astimezone(timezone.utc)
            .replace(tzinfo=None)
        )
        if [datetime.fromisoformat(s["timestamp_label"]) for s in samples] != [
            anchor + timedelta(seconds=seconds)
            for seconds in protocol["initial_probe_offsets_seconds"]
        ]:
            raise ValueError(
                "Initial probes differ from the preselected published-minute anchors"
            )
        root, _ = interpolate(samples, target)
        pair = refinement[index * 2 : index * 2 + 2]
        for sign, sample in zip((-1, 1), pair):
            expected = (root + timedelta(seconds=sign)).strftime(
                "%Y-%m-%d %H:%M:%S.%f"
            )[:-3]
            if sample["timestamp_label"] != expected:
                raise ValueError(
                    "Refinement is not centered on the independent initial root"
                )
        refined, fraction = interpolate(pair, target)
        offset = pair[0]["TDB-UT"] + fraction * (pair[1]["TDB-UT"] - pair[0]["TDB-UT"])
        latitude = pair[0]["ObsEcLat"] + fraction * (
            pair[1]["ObsEcLat"] - pair[0]["ObsEcLat"]
        )
        dut1 = (
            None
            if pair[0]["UT1-UTC"] is None
            else pair[0]["UT1-UTC"]
            + fraction * (pair[1]["UT1-UTC"] - pair[0]["UT1-UTC"])
        )
        published_label = (
            datetime.fromisoformat(case["published_moment"])
            .astimezone(timezone.utc)
            .replace(tzinfo=None)
        )
        delta = (refined - published_label).total_seconds()
        if (
            annotation["root_label"] != refined.isoformat()
            or annotation["initial_root_label"] != root.isoformat()
            or annotation["refinement_bracket"] != pair
            or annotation["target_longitude"] != target
            or annotation["tt_proxy_label"]
            != (refined + timedelta(seconds=offset)).isoformat()
            or annotation["tt_proxy_max_tdb_tt_seconds"] != 0.002
            or annotation["published_moment"] != case["published_moment"]
            or annotation["root_label_time_scale"]
            != ("UT1" if refined.year < 1962 else "UTC")
            or annotation["tdb_minus_ut_seconds"] != offset
            or annotation["latitude"] != latitude
            or annotation["dut1_seconds"] != dut1
            or annotation["difference_from_pmo_seconds"] != delta
            or annotation["within_original_printed_minute_criterion"]
            != (abs(delta) <= 30)
        ):
            raise ValueError("Crossing annotation differs from independent JPL probes")
    return dict(protocol=protocol, reference=ref, prior=prior)


def audit() -> dict[str, Any]:
    frozen = reference()
    before = {name: sha(ROOT / name) for name in IMPLEMENTATION}
    from fatebridge.core.almanac import get_solar_terms_for_year
    from fatebridge.core.astro.time_scales import ephemeris_time
    from fatebridge.core.ephemeris_runtime import (
        ephemeris_call,
        ephemeris_model_from_retflag,
        swe,
    )
    from fatebridge.core.solar_term_runtime import solar_term_cache_context

    environment_before = repr(solar_term_cache_context(swe))
    rows, errors = [], []
    for case in frozen["reference"]["cases"]:
        try:
            term = next(
                t
                for t in get_solar_terms_for_year(case["year"], "+08:00")
                if t.name == case["term"]
            )
            published = datetime.fromisoformat(case["published_moment"])
            label = datetime.fromisoformat(case["root_label"]).replace(
                tzinfo=timezone.utc
            )
            epoch = ephemeris_time(label)
            term_epoch = ephemeris_time(term.moment)
            if epoch.jd_tt is None or term_epoch.jd_tt is None:
                raise RuntimeError("TT conversion is unavailable")
            proxy = datetime.fromisoformat(case["tt_proxy_label"])
            jd_proxy = (
                2451544.5 + (proxy - datetime(2000, 1, 1)).total_seconds() / 86400
            )
            default, flags = ephemeris_call(
                "calc", epoch.jd_tt, swe.SUN, swe.FLG_SWIEPH
            )
            at_proxy, proxy_flags = ephemeris_call(
                "calc", jd_proxy, swe.SUN, swe.FLG_SWIEPH
            )
            delta = (term.moment - published).total_seconds()
            longitude = wrapped_degrees(default[0] - case["target_longitude"]) * 3600
            latitude = (default[1] - case["latitude"]) * 3600
            jpl_delta = (label - published).total_seconds()
            rows.append(
                dict(
                    year=case["year"],
                    term=case["term"],
                    actual=term.moment.isoformat(),
                    provider=term.resolution_provider,
                    actual_model=term.ephemeris_model,
                    ephemeris_retflags=list(term.ephemeris_retflags),
                    library_version=term.ephemeris_library_version,
                    difference_from_pmo_seconds=delta,
                    within_original_printed_minute_criterion=abs(delta) <= 30
                    and term.resolution_provider == "swisseph",
                    jpl_root_label=case["root_label"],
                    jpl_label_scale=case["root_label_time_scale"],
                    jpl_difference_from_pmo_seconds=jpl_delta,
                    jpl_within_original_printed_minute_criterion=abs(jpl_delta) <= 30,
                    actual_minus_jpl_label_seconds=(
                        term.moment - label
                    ).total_seconds(),
                    clock_method=epoch.method,
                    longitude_error_same_label_arcseconds=longitude,
                    latitude_error_same_label_arcseconds=latitude,
                    within_original_coordinate_criterion=max(
                        abs(longitude), abs(latitude)
                    )
                    <= 0.1,
                    longitude_error_same_tt_proxy_arcseconds=wrapped_degrees(
                        at_proxy[0] - case["target_longitude"]
                    )
                    * 3600,
                    latitude_error_same_tt_proxy_arcseconds=(
                        at_proxy[1] - case["latitude"]
                    )
                    * 3600,
                    swiss_minus_jpl_offset_at_jpl_label_seconds=(epoch.jd_tt - jd_proxy)
                    * 86400,
                    actual_tt_minus_jpl_tt_proxy_seconds=(term_epoch.jd_tt - jd_proxy)
                    * 86400,
                    label_model=ephemeris_model_from_retflag(flags),
                    proxy_model=ephemeris_model_from_retflag(proxy_flags),
                )
            )
        except Exception as exc:
            errors.append(
                dict(
                    year=case["year"],
                    term=case["term"],
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
            )
    changed = [
        name for name, expected in before.items() if sha(ROOT / name) != expected
    ]
    environment_unchanged = environment_before == repr(solar_term_cache_context(swe))
    native_file = swe.get_current_file_data(0) if swe is not None else None
    planet_file = None
    native_file_error = None
    if native_file and native_file[0]:
        planet_file = dict(
            path=native_file[0],
            first_jd=native_file[1],
            last_jd=native_file[2],
            jpl_de_number=native_file[3],
            scope="Last file reported by native Swiss; not the packaged DE440 coefficient source",
        )
        try:
            planet_file["sha256"] = sha(Path(native_file[0]))
        except OSError as exc:
            # The native library can retain an attempted/stale file path.
            # Keep every comparison/error and the failed source receipt.
            native_file_error = dict(error_type=type(exc).__name__, error=str(exc))
            planet_file["sha256"] = None
    return dict(
        audit_id="ren_horizons_crossings_v1",
        expected_count=113,
        compared_count=len(rows),
        criteria=frozen["protocol"]["criteria"],
        comparisons=rows,
        calculation_errors=errors,
        pmo_minute_failure_count=sum(
            not r["within_original_printed_minute_criterion"] for r in rows
        ),
        jpl_pmo_minute_failure_count=sum(
            not r["jpl_within_original_printed_minute_criterion"] for r in rows
        ),
        cross_frame_coordinate_failure_count=sum(
            not r["within_original_coordinate_criterion"] for r in rows
        ),
        implementation_sha256=before,
        implementation_changed_during_audit=changed,
        ephemeris_environment_before=environment_before,
        ephemeris_environment_unchanged_during_audit=environment_unchanged,
        planet_file=planet_file,
        native_file_receipt_error=native_file_error,
        source_sha256={
            str(path.relative_to(ROOT)): sha(path)
            for path in (
                CORPUS / "freeze.json",
                CORPUS / "collection/pre-comparison-freeze.json",
            )
        },
        all_performed_comparisons_passed=not changed
        and environment_unchanged
        and native_file_error is None
        and not errors
        and len(rows) == 113
        and all(
            r["within_original_printed_minute_criterion"]
            and r["within_original_coordinate_criterion"]
            and r["jpl_within_original_printed_minute_criterion"]
            for r in rows
        ),
        full_supported_calendar_domain_certified=False,
        classical_acceptance_passed=False,
        goal_complete=False,
        limits=frozen["protocol"]["limits"]
        + [
            frozen["reference"]["scope"],
            frozen["reference"]["tt_proxy_note"],
            "Cross-frame residuals do not establish an error under either frame's own definition.",
        ],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit()
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
    raise SystemExit(0 if report["all_performed_comparisons_passed"] else 1)

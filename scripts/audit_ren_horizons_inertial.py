"""Match apparent ICRF solar directions without changing old of-date criteria."""

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

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/ren_horizons_inertial_v1"
PRIOR = ROOT / "tests/fixtures/ren_horizons_crossings_v1"
IMPLEMENTATION = (
    "src/fatebridge/core/almanac.py",
    "src/fatebridge/core/ephemeris_runtime.py",
    "src/fatebridge/core/solar_term_runtime.py",
    "src/fatebridge/core/astro/time_scales.py",
    "src/fatebridge/core/astro/historical_utc.py",
    "src/fatebridge/core/astro/geometry.py",
    "scripts/audit_ren_horizons_inertial.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_response(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text())
    if data.get("error") or data.get("signature") != {
        "source": "NASA/JPL Horizons API",
        "version": "1.0",
    }:
        raise ValueError("JPL error or unexpected file API signature")
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
            raise ValueError(f"Unexpected JPL geometry/source: {token}")
    header = next(line for line in before.splitlines() if "Date__(UT)" in line)
    names = [n.strip() for n in next(csv.reader([header]))]
    keys = (
        "TDB-UT",
        "ObsEcLon",
        "ObsEcLat",
        "RA_(ICRF-a-app)",
        "DEC_(ICRF-a-app)",
        "UT1-UTC",
    )
    indexes = {k: names.index(k) for k in keys}
    rows = []
    for fields in csv.reader(io.StringIO(table.strip())):
        stamp = datetime.strptime(fields[0].strip(), "%Y-%b-%d %H:%M:%S.%f")
        row: dict[str, Any] = {
            "timestamp_label": stamp.isoformat(sep=" ", timespec="milliseconds")
        }
        for key, index in indexes.items():
            token = fields[index].strip()
            if token == "n.a." and key == "UT1-UTC" and stamp < datetime(1962, 1, 20):
                row[key] = None
            else:
                row[key] = float(token)
                if not math.isfinite(row[key]):
                    raise ValueError("Nonfinite independent coordinate")
        if (
            not 0 <= row["RA_(ICRF-a-app)"] < 360
            or not -90 <= row["DEC_(ICRF-a-app)"] <= 90
        ):
            raise ValueError("JPL RA/DEC range differs")
        rows.append(row)
    return rows


def reference(corpus: Path = CORPUS) -> dict[str, Any]:
    manifest = json.loads((corpus / "freeze.json").read_text())
    inventory = {
        str(p.relative_to(corpus))
        for p in corpus.rglob("*")
        if p.is_file() and p.name != "freeze.json"
    }
    if inventory != set(manifest["files"]):
        raise ValueError("Frozen inertial source inventory changed")
    for name, digest in manifest["files"].items():
        if sha(corpus / name) != digest:
            raise ValueError(f"Frozen inertial source changed: {name}")
    pre = json.loads((corpus / "precomparison-freeze.json").read_text())
    if pre["production_calculations_performed"] is not False or any(
        sha(corpus / n) != s for n, s in pre["files"].items()
    ):
        raise ValueError("Precomparison reference changed")
    protocol = json.loads((corpus / "protocol.json").read_text())
    if protocol["criteria"] != {
        "inertial_angular_separation_arcseconds": 0.1,
        "original_cross_frame_component_arcseconds": 0.1,
        "original_pmo_absolute_seconds": 30,
        "tdb_tt_proxy_max_seconds": 0.002,
    }:
        raise ValueError("Precommitted criteria changed")
    old = json.loads((PRIOR / "collection/horizons-protocol.json").read_text())
    if (
        sha(PRIOR / "freeze.json") != protocol["prior_cohort_freeze_sha256"]
        or sha(PRIOR / "collection/horizons-protocol.json")
        != protocol["prior_protocol_sha256"]
    ):
        raise ValueError("Prior diagnostic cohort changed")
    prior_manifest = json.loads((PRIOR / "freeze.json").read_text())
    if any(sha(PRIOR / n) != s for n, s in prior_manifest["files"].items()):
        raise ValueError("Prior independent responses changed")
    if [(r["year"], r["term"], r["published_moment"]) for r in protocol["cohort"]] != [
        (r["year"], r["term"], r["published_moment"]) for r in old["cohort"]
    ] or len(protocol["cohort"]) != 113:
        raise ValueError("Complete prior 113-event cohort required")
    for case in protocol["cohort"]:
        anchor = (
            datetime.fromisoformat(case["published_moment"])
            .astimezone(timezone.utc)
            .replace(tzinfo=None)
        )
        if case["query_label"] != anchor.isoformat(
            sep=" ", timespec="milliseconds"
        ) or case["label_time_scale"] != ("UT1" if anchor.year < 1962 else "UTC"):
            raise ValueError("Position anchor differs from original printed minute")
    prefiles = set(pre["files"])
    if prefiles != set(manifest["files"]) - {"precomparison-freeze.json"}:
        raise ValueError("Incomplete precomparison inventory")
    statuses = json.loads((corpus / "collection/status.json").read_text())
    rows = []
    for i, status in enumerate(statuses):
        base = corpus / "collection" / status["batch"]
        query = json.loads(base.with_suffix(".query.json").read_text())
        if (
            query["endpoint"] != "https://ssd.jpl.nasa.gov/api/horizons_file.api"
            or sha(base.with_suffix(".input.txt")) != query["input_sha256"]
            or query["protocol_sha256"] != sha(corpus / "protocol.json")
        ):
            raise ValueError("Submitted request differs from frozen protocol")
        if (
            base.with_suffix(".input.txt").read_text()
            != "!$$SOF\n"
            + "\n".join(k + "=" + v for k, v in query["params"].items())
            + "\n"
        ):
            raise ValueError("Submitted text differs from parameter record")
        for key, expected in {
            "COMMAND": "'10'",
            "CENTER": "'500@399'",
            "TIME_TYPE": "'UT'",
            "QUANTITIES": "'30,31,45,49'",
            "TLIST_TYPE": "'CAL'",
            "REF_SYSTEM": "'ICRF'",
            "APPARENT": "'AIRLESS'",
            "ANG_FORMAT": "'DEG'",
        }.items():
            if query["params"].get(key) != expected:
                raise ValueError(f"Wrong independent query: {key}")
        planned = [r["query_label"] for r in protocol["cohort"][i * 20 : (i + 1) * 20]]
        if shlex.split(query["params"]["TLIST"]) != planned:
            raise ValueError("Query labels differ from fixed cohort")
        batch = parse_response(corpus / "collection" / status["selected_response"])
        if [r["timestamp_label"] for r in batch] != planned or len(batch) != status[
            "count"
        ]:
            raise ValueError("Returned timestamps or count differ")
        rows.extend(batch)
    if len(statuses) != 6 or len(rows) != 113:
        raise ValueError("All 113 positions and six batches required")
    prior_rows = json.loads(
        (PRIOR / "collection/initial-combined-rows.json").read_text()
    )
    repeated = []
    for i, row in enumerate(rows):
        previous = prior_rows[i * 5 + 2]
        keys = ("timestamp_label", "TDB-UT", "ObsEcLon", "ObsEcLat", "UT1-UTC")
        repeated.append(
            dict(
                year=protocol["cohort"][i]["year"],
                term=protocol["cohort"][i]["term"],
                matched=all(row[k] == previous[k] for k in keys),
                previous={k: previous[k] for k in keys},
                current={k: row[k] for k in keys},
            )
        )
    return dict(protocol=protocol, rows=rows, repeated_of_date_controls=repeated)


def unit_vector(ra: float, dec: float) -> tuple[float, float, float]:
    r, d = math.radians(ra), math.radians(dec)
    return math.cos(d) * math.cos(r), math.cos(d) * math.sin(r), math.sin(d)


def separation_arcseconds(
    ra: float, dec: float, expected_ra: float, expected_dec: float
) -> float:
    a, b = unit_vector(ra, dec), unit_vector(expected_ra, expected_dec)
    cross = (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )
    return (
        math.degrees(
            math.atan2(
                math.sqrt(sum(x * x for x in cross)), sum(x * y for x, y in zip(a, b))
            )
        )
        * 3600
    )


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
    flags = (
        0
        if swe is None
        else (
            swe.FLG_SWIEPH
            | swe.FLG_EQUATORIAL
            | swe.FLG_J2000
            | swe.FLG_NONUT
            | swe.FLG_ICRS
        )
    )
    comparisons, errors = [], []
    for case, row in zip(ref["protocol"]["cohort"], ref["rows"]):
        try:
            if swe is None:
                raise RuntimeError("Swiss Ephemeris is unavailable")
            label = datetime.fromisoformat(row["timestamp_label"])
            tt_proxy = label + timedelta(seconds=row["TDB-UT"])
            jd = 2451544.5 + (tt_proxy - datetime(2000, 1, 1)).total_seconds() / 86400
            position, retflag = ephemeris_call("calc", jd, swe.SUN, flags)
            if (
                not all(math.isfinite(v) for v in position[:2])
                or not 0 <= position[0] < 360
                or not -90 <= position[1] <= 90
            ):
                raise ValueError("Nonfinite or out-of-range computed RA/DEC")
            if retflag & ~7 != flags & ~7 or ephemeris_model_from_retflag(
                retflag
            ) not in {"swieph", "moshier", "jpl"}:
                raise ValueError(
                    "Actual inertial flags/model differ from requested geometry"
                )
            error = separation_arcseconds(
                position[0],
                position[1],
                row["RA_(ICRF-a-app)"],
                row["DEC_(ICRF-a-app)"],
            )
            default, default_flag = ephemeris_call("calc", jd, swe.SUN, swe.FLG_SWIEPH)
            if default_flag not in {
                swe.FLG_SWIEPH,
                swe.FLG_MOSEPH,
                swe.FLG_JPLEPH,
            } or ephemeris_model_from_retflag(
                default_flag
            ) != ephemeris_model_from_retflag(
                retflag
            ):
                raise ValueError("Default/inertial model or geometry differs")
            longitude_error = ((default[0] - row["ObsEcLon"] + 180) % 360 - 180) * 3600
            latitude_error = (default[1] - row["ObsEcLat"]) * 3600
            if not all(math.isfinite(v) for v in (longitude_error, latitude_error)):
                raise ValueError("Nonfinite default of-date coordinates")
            comparisons.append(
                dict(
                    year=case["year"],
                    term=case["term"],
                    query_label=row["timestamp_label"],
                    query_label_scale=case["label_time_scale"],
                    tt_proxy_label=tt_proxy.isoformat(),
                    tdb_tt_proxy_max_seconds=0.002,
                    expected_ra=row["RA_(ICRF-a-app)"],
                    expected_dec=row["DEC_(ICRF-a-app)"],
                    actual_ra=position[0],
                    actual_dec=position[1],
                    angular_separation_arcseconds=error,
                    of_date_longitude_difference_arcseconds=longitude_error,
                    of_date_latitude_difference_arcseconds=latitude_error,
                    within_cross_frame_component_criterion=max(
                        abs(longitude_error), abs(latitude_error)
                    )
                    <= 0.1,
                    default_of_date_retflag=default_flag,
                    within_inertial_criterion=error <= 0.1,
                    actual_retflag=retflag,
                    actual_model=ephemeris_model_from_retflag(retflag),
                )
            )
        except Exception as exc:
            errors.append(dict(year=case["year"], term=case["term"], error=str(exc)))
    stable = before == {p: sha(ROOT / p) for p in IMPLEMENTATION}
    unchanged = environment == repr(solar_term_cache_context(swe))
    return dict(
        audit_id="ren_horizons_inertial_v1",
        expected_count=113,
        compared_count=len(comparisons),
        comparisons=comparisons,
        repeated_of_date_controls=ref["repeated_of_date_controls"],
        repeated_of_date_equal_count=sum(
            r["matched"] for r in ref["repeated_of_date_controls"]
        ),
        calculation_errors=errors,
        inertial_failure_count=sum(
            not r["within_inertial_criterion"] for r in comparisons
        ),
        cross_frame_component_failure_count=sum(
            not r["within_cross_frame_component_criterion"] for r in comparisons
        ),
        date_frame_equivalence_certified=False,
        max_inertial_separation_arcseconds=max(
            (r["angular_separation_arcseconds"] for r in comparisons), default=None
        ),
        criteria=ref["protocol"]["criteria"],
        source_sha256=sha(CORPUS / "freeze.json"),
        implementation_sha256=before,
        implementation_unchanged_during_audit=stable,
        ephemeris_environment_before=environment,
        ephemeris_environment_unchanged_during_audit=unchanged,
        selected_inertial_comparison_passed=stable
        and unchanged
        and len(comparisons) == 113
        and not errors
        and all(r["within_inertial_criterion"] for r in comparisons),
        original_pmo_criterion_changed=False,
        original_cross_frame_criterion_changed=False,
        full_supported_calendar_domain_certified=False,
        classical_acceptance_passed=False,
        free_text_semantic_acceptance_passed=False,
        goal_complete=False,
        model_invocations=0,
        scope=ref["protocol"]["scope"],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "compared_count",
                    "inertial_failure_count",
                    "max_inertial_separation_arcseconds",
                    "selected_inertial_comparison_passed",
                    "goal_complete",
                )
            },
            ensure_ascii=False,
        )
    )
    return 0 if result["selected_inertial_comparison_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

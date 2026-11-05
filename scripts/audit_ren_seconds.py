"""Run the complete frozen second-boundary cohort through Ren domain services."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/data/ren/second_boundary_inputs"
FREEZE_SHA = "9593cb737bca892c8884ff5901c3a774449cdd0a6fed08fc742f7df6cc16bc35"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def reference(corpus: Path = CORPUS) -> dict[str, Any]:
    if sha(corpus / "freeze.json") != FREEZE_SHA:
        raise ValueError("Frozen second-reference manifest changed")
    freeze = json.loads((corpus / "freeze.json").read_text())
    if {p.name for p in corpus.iterdir()} != {
        "freeze.json",
        "protocol.json",
        "probes.json.gz",
    }:
        raise ValueError("Frozen second-reference inventory changed")
    if any(sha(corpus / n) != h for n, h in freeze["files"].items()):
        raise ValueError("Frozen second-reference payload changed")
    protocol = json.loads((corpus / "protocol.json").read_text())
    for n, h in protocol["reference_pins"].items():
        if sha(ROOT / n) != h:
            raise ValueError("Pinned independent source changed: " + n)
    data = json.loads(gzip.decompress((corpus / "probes.json.gz").read_bytes()))
    rows = data["rows"]
    if (
        data["protocol_sha256"] != sha(corpus / "protocol.json")
        or len(rows) != 19248
        or len({r["id"] for r in rows}) != 19248
    ):
        raise ValueError("The entire19248-input cohort is required")
    if any(sum(r["year"] == y for r in rows) != 48 for y in range(1800, 2201)):
        raise ValueError("Every input year needs all48 second labels")
    return dict(protocol=protocol, data=data)


def source_map() -> dict[str, str]:
    paths = [
        p
        for p in (ROOT / "src/fatebridge").rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    ]
    paths += [
        ROOT / n
        for n in [
            "scripts/audit_ren_seconds.py",
            "scripts/ren_second_reference.py",
            "scripts/collect_ren_second_probes.py",
            "pyproject.toml",
            "uv.lock",
        ]
    ]
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(paths)}


def evaluate_probe(probe: dict[str, Any], protocol: dict[str, Any]) -> dict[str, Any]:
    from fatebridge.core.astro.time_scales import ephemeris_time
    from fatebridge.core.metaphysics.jinkou import build_jinkou_board
    from fatebridge.core.metaphysics.liureng import build_liureng_board
    from fatebridge.core.metaphysics.ren_calendar import require_ren_calendar
    from fatebridge.services.metaphysics import _build_analysis_seed

    moment = datetime.fromisoformat(probe["civil_utc"])
    epoch = ephemeris_time(moment)
    seed = _build_analysis_seed(
        analysis_year=moment.year,
        analysis_month=moment.month,
        analysis_day=moment.day,
        analysis_hour=moment.hour,
        analysis_minute=moment.minute,
        analysis_second=moment.second,
        analysis_timezone="UTC",
        use_true_solar_time=False,
    )
    policy = require_ren_calendar(seed)
    seed.calendar_context["ren_calendar_policy"] = policy
    liuren = build_liureng_board(seed, is_diurnal_override=protocol["is_diurnal"])
    jinkou = build_jinkou_board(
        seed,
        liuren,
        di_fen=protocol["di_fen"],
        is_diurnal_override=protocol["is_diurnal"],
    )
    actual = dict(
        current_term=seed.calendar_context["current_solar_term"]["name"],
        next_term=seed.calendar_context["next_solar_term"]["name"],
        **{k: "".join(seed.pillars[k]) for k in ["year", "month", "day", "hour"]},
        month_general=liuren["month_general"]["branch"],
        positions=[v["content"] for v in jinkou["rows"]],
        seasonal_powers=[v["seasonal_power"] for v in jinkou["rows"]],
        polarity_use=jinkou["overview"]["use_position"],
    )
    deps = policy["solar_term_dependencies"]
    selected = protocol["profiles"][os.environ["FATEBRIDGE_REN_SECOND_AUDIT_PROFILE"]]
    clock_delta = (
        (epoch.jd_tt - probe["input_jd_tt"]) * 86400
        if epoch.jd_tt is not None
        else None
    )
    return dict(
        id=probe["id"],
        civil_utc=probe["civil_utc"],
        actual=actual,
        expected=probe["expected"],
        matches={k: actual[k] == v for k, v in probe["expected"].items()},
        actual_input_jd_tt=epoch.jd_tt,
        reference_input_jd_tt=probe["input_jd_tt"],
        clock_difference_seconds=clock_delta,
        clock_within_frozen_criterion=clock_delta is not None
        and abs(clock_delta) <= protocol["criteria"]["input_clock_seconds"],
        input_time_method=epoch.method,
        future_leap_seconds_assumed_unchanged=epoch.future_leap_seconds_assumed_unchanged,
        dependency_models=[
            dict(
                role=d["role"],
                name=d["name"],
                provider=d["provider"],
                model=d["ephemeris_model"],
            )
            for d in deps
        ],
        dependency_identity_matches=len(deps) == 5
        and all(
            d["provider"] == selected["provider"]
            and d["ephemeris_model"] == selected["model"]
            for d in deps
        ),
        reference_inside_root_bracket=probe["inside_root_bracket"],
    )


def audit(profile: str, ephe: Path, details: Path) -> dict[str, Any]:
    ref = reference()
    protocol, data = ref["protocol"], ref["data"]
    selected = protocol["profiles"][profile]
    if not ephe.is_dir() or (selected["directory"] == "empty" and any(ephe.iterdir())):
        raise ValueError("Profile needs its frozen directory class")
    if details.exists():
        raise FileExistsError("Refusing to overwrite earlier details")
    os.environ["FATEBRIDGE_SOLAR_TERM_MODEL"] = selected["mode"]
    os.environ["FATEBRIDGE_REN_SECOND_AUDIT_PROFILE"] = profile
    os.environ["SE_EPHE_PATH"] = str(ephe.resolve())
    for n in ["FATEBRIDGE_JPL_FILE", "FATEBRIDGE_SOLAR_SPK_FILE"]:
        os.environ.pop(n, None)
    before = source_map()
    from fatebridge.core import almanac
    from fatebridge.core.astro.time_scales import ephemeris_time

    assert Path(almanac.__file__).resolve() == ROOT / "src/fatebridge/core/almanac.py"
    roots = json.loads(
        (ROOT / "tests/data/solar/liuyao_de440_tt1800_2200.json").read_text()
    )["rows"]
    by_year = {y: [r for r in roots if r["year"] == y] for y in range(1800, 2201)}
    probes = {y: [r for r in data["rows"] if r["year"] == y] for y in range(1800, 2201)}
    counts: dict[str, Counter[str]] = {
        k: Counter() for k in data["rows"][0]["expected"]
    }
    bad_ids = []
    clock_bad = []
    identity_bad = []
    root_bad = []
    errors = []
    max_tt = 0.0
    max_clock = 0.0
    root_count = 0
    probe_count = 0
    providers: Counter[str] = Counter()
    future: Counter[str] = Counter()
    details.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(details, "xt", encoding="utf-8") as stream:
        for year in range(1800, 2201):
            try:
                terms = almanac.get_solar_terms_for_year(year, "UTC")
                for r in by_year[year]:
                    t = terms[r["index"]]
                    clock = ephemeris_time(t.moment)
                    tt = (t.solar_model_details or {}).get(
                        "selected_crossing_jd_tt", clock.jd_tt
                    )
                    if tt is None:
                        raise ValueError("No TT root")
                    delta = (tt - r["jd_tt"]) * 86400
                    max_tt = max(max_tt, abs(delta))
                    ok = abs(delta) <= protocol["criteria"]["tt_seconds"]
                    identity = (
                        t.resolution_provider == selected["provider"]
                        and t.ephemeris_model == selected["model"]
                    )
                    root_count += 1
                    if not ok or not identity:
                        root_bad.append(
                            dict(
                                year=year,
                                index=r["index"],
                                term=t.name,
                                delta_seconds=delta,
                                identity=identity,
                            )
                        )
                    stream.write(
                        json.dumps(
                            dict(
                                kind="root",
                                year=year,
                                index=r["index"],
                                term=t.name,
                                reference_jd_tt=r["jd_tt"],
                                actual_jd_tt=tt,
                                delta_seconds=delta,
                                within_one_second=ok,
                                provider=t.resolution_provider,
                                model=t.ephemeris_model,
                                identity_matches=identity,
                            ),
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                        + "\n"
                    )
            except Exception as e:
                errors.append(
                    dict(
                        kind="root",
                        year=year,
                        error_type=type(e).__name__,
                        error=str(e),
                    )
                )
            for p in probes[year]:
                try:
                    row = evaluate_probe(p, protocol)
                    probe_count += 1
                    for k, v in row["matches"].items():
                        counts[k]["matched" if v else "mismatched"] += 1
                    if not all(row["matches"].values()):
                        bad_ids.append(p["id"])
                    if not row["clock_within_frozen_criterion"]:
                        clock_bad.append(p["id"])
                    if row["clock_difference_seconds"] is not None:
                        max_clock = max(max_clock, abs(row["clock_difference_seconds"]))
                    if not row["dependency_identity_matches"]:
                        identity_bad.append(p["id"])
                    providers.update(
                        x["provider"] + "/" + x["model"]
                        for x in row["dependency_models"]
                    )
                    future[str(row["future_leap_seconds_assumed_unchanged"])] += 1
                    stream.write(
                        json.dumps(
                            dict(kind="probe", **row),
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                        + "\n"
                    )
                except Exception as e:
                    error = dict(
                        kind="probe",
                        id=p["id"],
                        error_type=type(e).__name__,
                        error=str(e),
                    )
                    errors.append(error)
                    stream.write(json.dumps(error, ensure_ascii=False) + "\n")
            stream.flush()
            if year % 10 == 0 or year == 2200:
                print(
                    f"{profile} {year} roots={root_count} probes={probe_count} bad={len(bad_ids)} clock={len(clock_bad)} errors={len(errors)}",
                    flush=True,
                )
    after = source_map()
    unchanged = before == after
    passed = (
        root_count == 9624
        and probe_count == 19248
        and not any([root_bad, bad_ids, clock_bad, identity_bad, errors])
        and unchanged
    )
    return dict(
        profile=profile,
        protocol_sha256=sha(CORPUS / "protocol.json"),
        reference_freeze_sha256=FREEZE_SHA,
        details_file=details.name,
        details_sha256=sha(details),
        root_count=root_count,
        probe_count=probe_count,
        counts={k: dict(v) for k, v in counts.items()},
        bad_probe_ids=bad_ids,
        clock_mismatch_ids=clock_bad,
        identity_mismatch_ids=identity_bad,
        root_failures=root_bad,
        errors=errors,
        max_abs_tt_difference_seconds=max_tt,
        max_abs_input_clock_difference_seconds=max_clock,
        providers=dict(providers),
        future_flags=dict(future),
        source_sha256=before,
        implementation_unchanged=unchanged,
        changed_source_paths=sorted(
            n for n in before.keys() | after.keys() if before.get(n) != after.get(n)
        ),
        reference_inside_root_bracket_ids=data["inside_root_bracket_ids"],
        selected_second_checks_passed=passed,
        full_calendar_acceptance=False,
        complete_classical_conformance=False,
        free_text_model_review="not_run",
        real_world_prediction="deferred",
        new_physical_observations=0,
        full_goal_complete=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile", choices=reference()["protocol"]["profiles"], required=True
    )
    parser.add_argument("--ephe-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--details", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Refusing to overwrite an earlier audit")
    result = audit(args.profile, args.ephe_dir, args.details)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return 0 if result["selected_second_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

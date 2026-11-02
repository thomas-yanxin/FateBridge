"""Propagate all frozen TT/minute boundaries through actual Ren boards.

Original HKO dates and both frozen/current clock expectations remain distinct.
This does not turn numerical root tolerance into an exact decision guarantee.
"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import importlib.util
import json
import os
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/ren_boundary_decisions_v1"
FREEZE_SHA = "35e00eefca1f0f0007ce1f55843b411cf9cbd1c43a5052020787d62bfbe96f88"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
STEMS = "甲乙丙丁戊己庚辛壬癸"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def reference(fixture: Path = FIXTURE) -> dict[str, Any]:
    if sha(fixture / "freeze.json") != FREEZE_SHA:
        raise ValueError("Frozen Ren boundary protocol manifest changed")
    manifest = json.loads((fixture / "freeze.json").read_text())
    if set(manifest["files"]) != {"protocol.json"} or {
        p.name for p in fixture.iterdir()
    } != {"protocol.json", "freeze.json"}:
        raise ValueError("Frozen Ren boundary protocol inventory changed")
    if sha(fixture / "protocol.json") != manifest["files"]["protocol.json"]:
        raise ValueError("Frozen Ren boundary protocol changed")
    protocol: dict[str, Any] = json.loads((fixture / "protocol.json").read_text())
    for name, checksum in protocol["reference_checksums"].items():
        if sha(ROOT / name) != checksum:
            raise ValueError(f"Frozen Ren boundary source changed: {name}")
    roots = json.loads(
        (ROOT / "tests/fixtures/bazi_all_terms_v1/reference.json").read_text()
    )["rows"]
    probes = json.loads(
        (ROOT / "tests/fixtures/bazi_boundary_decisions_v1/probes.json").read_text()
    )["rows"]
    if len(roots) != 4872 or len(probes) != 9744:
        raise ValueError("Full Ren boundary denominators required")
    if (
        len({(v["year"], v["name"]) for v in roots}) != 4872
        or len({v["id"] for v in probes}) != 9744
    ):
        raise ValueError("Duplicated Ren boundary rows")
    if [v["jd_tt"] for v in roots] != sorted(v["jd_tt"] for v in roots):
        raise ValueError("Independent roots must remain ordered")
    for year in range(1899, 2102):
        terms = [v for v in roots if v["year"] == year]
        points = [v for v in probes if v["year"] == year]
        if len(terms) != 24 or len(points) != 48:
            raise ValueError("All terms and both minute sides required per year")
    return dict(protocol=protocol, roots=roots, probes=probes)


def source_map() -> dict[str, str]:
    paths = [
        p
        for p in (ROOT / "src/fatebridge").rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    ]
    paths += [
        ROOT / n
        for n in (
            "scripts/audit_ren_boundary_decisions.py",
            "scripts/audit_ren_calendar.py",
            "pyproject.toml",
            "uv.lock",
        )
    ]
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(paths)}


def expected_state(
    roots: list[dict[str, Any]], jd_tt: float, jie: dict[str, str]
) -> dict[str, Any]:
    def last(values: list[dict[str, Any]]) -> dict[str, Any] | None:
        index = bisect.bisect_right([v["jd_tt"] for v in values], jd_tt) - 1
        return values[index] if index >= 0 else None

    term = last(roots)
    spring = last([v for v in roots if v["name"] == "立春"])
    month = last([v for v in roots if v["name"] in jie])
    return dict(
        last_term=term["name"] if term else None,
        bazi_year=spring["year"] if spring else None,
        month_branch=jie[month["name"]] if month else None,
    )


def expectations(
    state: dict[str, Any],
    moment: datetime,
    protocol: dict[str, Any],
    calendar: dict[str, Any],
    rules: dict[str, Any],
) -> dict[str, Any]:
    maps = protocol["reference_maps"]
    month = state["month_branch"]
    year = state["bazi_year"]
    year_pair = (
        STEMS[(year - 1984) % 10] + BRANCHES[(year - 1984) % 12]
        if year is not None
        else None
    )
    month_pair = None
    if month is not None and year_pair is not None:
        sequence = next(
            v for k, v in calendar["month_stems"].items() if year_pair[0] in k
        )
        month_pair = sequence["寅卯辰巳午未申酉戌亥子丑".index(month)] + month
    general = maps["general_by_last_term"].get(state["last_term"])
    # HKO/NAOJ JDN anchor and the already declared 23h software day rule.
    cycle = (
        calendar["day_cycle"]["jdn_anchor"]
        + (moment.date() - date(2000, 1, 1)).days
        + int(moment.hour >= 23)
        + calendar["day_cycle"]["cycle_offset"]
    ) % 60
    day_stem = STEMS[cycle % 10]
    hour = BRANCHES[((moment.hour + 1) // 2) % 12]
    ground = protocol["criteria"]["di_fen"]
    human = next(v for k, v in calendar["hour_stems"].items() if day_stem in k)[
        BRANCHES.index(ground)
    ]
    start = next(v["day"] for v in rules["guiren"] if v["stem"] == day_stem)
    distance = (BRANCHES.index(ground) - BRANCHES.index(start)) % 12
    god = maps["gui_sequence"][
        (-distance if start in "巳午未申酉戌" else distance) % 12
    ]
    god_branch = rules["inherent"][god][1]
    general_branch = (
        BRANCHES[
            (BRANCHES.index(general) + BRANCHES.index(ground) - BRANCHES.index(hour))
            % 12
        ]
        if general
        else None
    )
    positions = [human, god_branch, general_branch, ground] if general_branch else None
    powers, use = None, None
    if positions is not None:
        elements = [maps["stem_elements"][human]] + [
            maps["branch_elements"][v] for v in positions[1:]
        ]
        if month is not None:
            power = rules["power"][maps["branch_elements"][month]]
            powers = [power[v] for v in elements]
        mask = ("阳" if STEMS.index(human) % 2 == 0 else "阴") + "".join(
            "阳" if BRANCHES.index(v) % 2 == 0 else "阴" for v in positions[1:]
        )
        use = next(v["use"] for v in rules["polarity_use"] if v["mask"] == mask)
    return dict(
        current_term=state["last_term"],
        year=year_pair,
        month=month_pair,
        month_general=general,
        positions=positions,
        seasonal_powers=powers,
        polarity_use=use,
    )


def audit(profile: str, ephe_dir: Path, kernel: Path | None) -> dict[str, Any]:
    ref = reference()
    protocol, roots, probes = ref["protocol"], ref["roots"], ref["probes"]
    selected = protocol["arms"][profile]
    if not ephe_dir.is_dir() or (
        selected["directory"] == "explicit_empty" and any(ephe_dir.iterdir())
    ):
        raise ValueError(
            "Profile needs its declared existing or empty ephemeris directory"
        )
    if profile == "explicit_de440_spk" and (
        kernel is None or sha(kernel) != protocol["kernel_sha256"]
    ):
        raise ValueError("SPK profile requires the frozen official kernel bytes")
    os.environ["SE_EPHE_PATH"] = str(ephe_dir.resolve())
    os.environ["FATEBRIDGE_SOLAR_TERM_MODEL"] = selected["mode"]
    os.environ.pop("FATEBRIDGE_JPL_FILE", None)
    if kernel is not None:
        os.environ["FATEBRIDGE_SOLAR_SPK_FILE"] = str(kernel.resolve())
    else:
        os.environ.pop("FATEBRIDGE_SOLAR_SPK_FILE", None)
    before = source_map()
    from fatebridge.core.almanac import get_solar_terms_for_year
    from fatebridge.core.astro.time_scales import ephemeris_time
    from fatebridge.core.metaphysics.jinkou import build_jinkou_board
    from fatebridge.core.metaphysics.liureng import build_liureng_board
    from fatebridge.core.metaphysics.ren_calendar import require_ren_calendar
    from fatebridge.services.metaphysics import _build_analysis_seed

    cal = json.loads(
        (ROOT / "tests/fixtures/ren_calendar_v1/reference.json").read_text()
    )
    rules = json.loads(
        (ROOT / "tests/fixtures/ren_classical_v1/rules.json").read_text()
    )
    spec = importlib.util.spec_from_file_location(
        "hko_original_parser", ROOT / "scripts/audit_ren_calendar.py"
    )
    assert spec and spec.loader
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    manifest = json.loads(
        (ROOT / "tests/fixtures/ziwei_independent/calendar_manifest.json").read_text()
    )
    hko = {}
    lunar_state = (1900, 11, False)
    for src in manifest["sources"]:
        path = ROOT / "tests/fixtures/ziwei_independent" / src["path"]
        if sha(path) != src["sha256"]:
            raise ValueError("Original HKO annual source changed")
        rows, lunar_state = old.annual_rows(
            path.read_text(encoding="utf-8-sig"), src["year"], lunar_state
        )
        hko.update(
            {(src["year"], v["term"]): v["date"].isoformat() for v in rows if v["term"]}
        )
    if len(hko) != 4800:
        raise ValueError("All 4800 HKO term labels required")
    by_year = defaultdict(list)
    for probe in probes:
        by_year[probe["year"]].append(probe)
    root_rows, date_rows, comparisons, errors = [], [], [], []
    for year in range(1899, 2102):
        terms = {v.name: v for v in get_solar_terms_for_year(year, "+08:00")}
        for expected in [v for v in roots if v["year"] == year]:
            term = terms[expected["name"]]
            epoch = ephemeris_time(term.moment)
            assert epoch.jd_tt is not None
            difference = (epoch.jd_tt - expected["jd_tt"]) * 86400
            identity = (
                term.resolution_provider == selected["provider"]
                and term.ephemeris_model == selected["model"]
            )
            root_rows.append(
                dict(
                    year=year,
                    term=term.name,
                    actual=term.moment.isoformat(),
                    provider=term.resolution_provider,
                    model=term.ephemeris_model,
                    jd_tt=epoch.jd_tt,
                    expected_jd_tt=expected["jd_tt"],
                    difference_seconds=difference,
                    within_original_one_second=abs(difference) <= 1,
                    identity_matches=identity,
                )
            )
            label = hko.get((year, term.name))
            if label is not None:
                date_rows.append(
                    dict(
                        year=year,
                        term=term.name,
                        expected_date=label,
                        actual=term.moment.isoformat(),
                        literal_date_matches=term.moment.date().isoformat() == label,
                        future_leap_seconds_assumed_unchanged=epoch.future_leap_seconds_assumed_unchanged,
                    )
                )
        for probe in by_year[year]:
            try:
                moment = datetime.fromisoformat(probe["civil_utc"])
                epoch = ephemeris_time(moment)
                assert epoch.jd_tt is not None
                current_state = expected_state(roots, epoch.jd_tt, cal["month_starts"])
                expected = expectations(current_state, moment, protocol, cal, rules)
                frozen_expected = expectations(
                    probe["reference_state_under_frozen_policy"],
                    moment,
                    protocol,
                    cal,
                    rules,
                )
                seed = _build_analysis_seed(
                    analysis_year=moment.year,
                    analysis_month=moment.month,
                    analysis_day=moment.day,
                    analysis_hour=moment.hour,
                    analysis_minute=moment.minute,
                    analysis_timezone="UTC",
                    use_true_solar_time=False,
                )
                seed.calendar_context["ren_calendar_policy"] = require_ren_calendar(
                    seed
                )
                liuren = build_liureng_board(seed, is_diurnal_override=True)
                jinkou = build_jinkou_board(
                    seed, liuren, di_fen="酉", is_diurnal_override=True
                )
                actual = dict(
                    current_term=seed.calendar_context["current_solar_term"]["name"],
                    year="".join(seed.pillars["year"]),
                    month="".join(seed.pillars["month"]),
                    month_general=liuren["month_general"]["branch"],
                    positions=[v["content"] for v in jinkou["rows"]],
                    seasonal_powers=[v["seasonal_power"] for v in jinkou["rows"]],
                    polarity_use=jinkou["overview"]["use_position"],
                )
                matches = lambda exp: {
                    k: actual[k] == v if v is not None else None for k, v in exp.items()
                }
                comparisons.append(
                    dict(
                        id=probe["id"],
                        civil_utc=probe["civil_utc"],
                        actual_input_jd_tt=epoch.jd_tt,
                        frozen_input_jd_tt=probe["input_jd_tt_under_frozen_policy"],
                        input_clock_difference_seconds=(
                            epoch.jd_tt - probe["input_jd_tt_under_frozen_policy"]
                        )
                        * 86400,
                        input_time_method=epoch.method,
                        future_leap_seconds_assumed_unchanged=epoch.future_leap_seconds_assumed_unchanged,
                        actual=actual,
                        expected_under_actual_clock=expected,
                        expected_under_frozen_clock=frozen_expected,
                        matches=matches(expected),
                        frozen_clock_matches=matches(frozen_expected),
                    )
                )
            except Exception as error:
                errors.append(
                    dict(id=probe["id"], type=type(error).__name__, error=str(error))
                )
        if year % 25 == 0 or year == 2101:
            print(
                f"{profile} {year}: roots={len(root_rows)} probes={len(comparisons)} errors={len(errors)}",
                flush=True,
            )
    reference()
    after = source_map()
    fields = list(comparisons[0]["matches"]) if comparisons else []
    counts = {
        scope: {
            k: dict(
                matched=sum(v[scope][k] is True for v in comparisons),
                mismatched=sum(v[scope][k] is False for v in comparisons),
                not_applicable=sum(v[scope][k] is None for v in comparisons),
            )
            for k in fields
        }
        for scope in ("matches", "frozen_clock_matches")
    }
    return dict(
        profile=profile,
        selected=selected,
        protocol_sha256=sha(FIXTURE / "protocol.json"),
        root_count=len(root_rows),
        root_failures=[v for v in root_rows if not v["within_original_one_second"]],
        identity_failures=[v for v in root_rows if not v["identity_matches"]],
        root_comparisons=root_rows,
        hko_date_count=len(date_rows),
        hko_date_mismatches=[v for v in date_rows if not v["literal_date_matches"]],
        hko_date_comparisons=date_rows,
        probe_count=len(comparisons),
        counts=counts,
        comparisons=comparisons,
        calculation_errors=errors,
        implementation_sha256=before,
        implementation_unchanged=before == after,
        implementation_changed_paths=[n for n in before if before[n] != after.get(n)],
        new_unique_astronomical_events=0,
        new_real_world_samples=0,
        model_processes=0,
        full_goal_complete=False,
        maximum_tt_difference_seconds=max(
            abs(v["difference_seconds"]) for v in root_rows
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile", choices=reference()["protocol"]["arms"], required=True
    )
    parser.add_argument("--ephe-dir", type=Path, required=True)
    parser.add_argument("--kernel", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Refuse to overwrite original boundary evidence")
    result = audit(args.profile, args.ephe_dir, args.kernel)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    failed = (
        result["root_failures"]
        or result["identity_failures"]
        or result["hko_date_mismatches"]
        or result["calculation_errors"]
        or any(v["mismatched"] for v in result["counts"]["matches"].values())
        or not result["implementation_unchanged"]
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

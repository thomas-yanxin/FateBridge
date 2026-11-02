"""Audit independent Qimen excerpts and finite invariants without an authority score."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fatebridge.core.almanac import (
    get_day_ganzhi,
    get_solar_terms_for_year,
    localize_datetime,
)
from fatebridge.core.local_techniques.chart import _build_metaphysics_seed
from fatebridge.core.local_techniques.qimen import build_qimen_with_options
from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.core.metaphysics.qimen import (
    _qimen_build_ju_text,
    _qimen_build_palaces,
    _qimen_build_yinyangdun_map,
    _qimen_resolve_zhirun_meta,
    _qimen_zhifu_zhishi,
)
from fatebridge.core.qimen_evidence import RULESET_ID, enrich_qimen_evidence
from fatebridge.services.divination import calculate_sanshiunited_analysis
from fatebridge.services.metaphysics import calculate_qimen_analysis
from fatebridge.utils.timezones import parse_timezone_name, validate_local_clock
from fatebridge.validation.qimen import (
    audit_chapter_profiles,
    audit_day_stem_collation,
    audit_head_dependent_examples,
    audit_numeric_tables,
    audit_scan_examples,
)
from fatebridge.validation.qimen_calendar_stems import audit_calendar_stems
from fatebridge.validation.qimen_clock import audit_clock_fold
from fatebridge.validation.qimen_five_jia import audit_five_jia
from fatebridge.validation.qimen_gate_relations import audit_gate_relations
from fatebridge.validation.qimen_punishment import audit_punishment
from fatebridge.validation.qimen_solar import audit_solar_clocks
from fatebridge.validation.qimen_table_integrity import (
    audit_printed_table_integrity,
    audit_table_source_context,
    unrepresented_walk_anomalies,
)
from fatebridge.validation.qimen_three_deceptions import audit_three_deceptions
from fatebridge.validation.qimen_time_conditions import audit_hour_branch_tombs
from fatebridge.validation.qimen_tombs import audit_wonder_tomb_clauses

ROOT = Path(__file__).resolve().parents[1]


def audit() -> dict[str, Any]:
    implementation_files = [
        "scripts/audit_qimen.py",
        "src/fatebridge/core/metaphysics/qimen.py",
        "src/fatebridge/core/metaphysics/common.py",
        "src/fatebridge/core/qimen_evidence.py",
        "src/fatebridge/core/qimen_profiles.py",
        "src/fatebridge/core/qimen_tombs.py",
        "src/fatebridge/core/qimen_punishment.py",
        "src/fatebridge/validation/qimen_punishment.py",
        "src/fatebridge/core/qimen_gate_relations.py",
        "src/fatebridge/validation/qimen_gate_relations.py",
        "src/fatebridge/validation/qimen_tombs.py",
        "src/fatebridge/core/qimen_combinations.py",
        "src/fatebridge/core/qimen_stem_context.py",
        "src/fatebridge/core/qimen_calendar_stems.py",
        "src/fatebridge/core/qimen_time_conditions.py",
        "src/fatebridge/core/qimen_three_deceptions.py",
        "src/fatebridge/validation/qimen_three_deceptions.py",
        "tests/test_qimen_three_deceptions.py",
        "src/fatebridge/core/qimen_five_jia.py",
        "src/fatebridge/validation/qimen_five_jia.py",
        "tests/test_qimen_five_jia.py",
        "src/fatebridge/validation/qimen_time_conditions.py",
        "src/fatebridge/validation/qimen_calendar_stems.py",
        "src/fatebridge/core/almanac.py",
        "src/fatebridge/core/calendar.py",
        "src/fatebridge/core/local_techniques/qimen.py",
        "src/fatebridge/core/local_techniques/sanshi.py",
        "src/fatebridge/core/local_techniques/chart.py",
        "src/fatebridge/services/metaphysics.py",
        "src/fatebridge/services/divination.py",
        "src/fatebridge/utils/solar_time.py",
        "src/fatebridge/utils/solar_time_provenance.py",
        "src/fatebridge/validation/qimen_solar.py",
        "tests/test_qimen_solar_provenance.py",
        "src/fatebridge/utils/timezones.py",
        "src/fatebridge/utils/civil_clock.py",
        "src/fatebridge/validation/qimen_clock.py",
        "src/fatebridge/core/output_qimen.py",
        "src/fatebridge/core/output_chinese.py",
        "src/fatebridge/core/requests/metaphysics.py",
        "src/fatebridge/core/requests/divination.py",
        "src/fatebridge/data/agent_examples.json",
        "src/fatebridge/validation/qimen.py",
        "src/fatebridge/validation/qimen_table_integrity.py",
        "tests/test_qimen_table_integrity.py",
        "src/fatebridge/validation/qimen_study.py",
        "src/fatebridge/validation/predictions.py",
        "scripts/audit_qimen_study.py",
        "scripts/demo_qimen_study.py",
        "tests/test_qimen_study.py",
        "tests/test_qimen_registration_binding.py",
        "tests/test_prediction_baselines.py",
        "tests/test_qimen_clock_fold.py",
        "tests/test_prediction_fold_order.py",
        "src/fatebridge/validation/claims.py",
        "uv.lock",
    ]
    implementation = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in implementation_files
    }
    classical_path = ROOT / "tests/fixtures/qimen-classical-excerpts.json"
    calendar_path = ROOT / "tests/fixtures/qimen-calendar-hko-2026.json"
    hko_directory = ROOT / "tests/fixtures/calendar_hko_v1"
    hko_path = hko_directory / "reference.json"
    timezone_directory = ROOT / "tests/fixtures/qimen_timezone_iana_v1"
    timezone_path = timezone_directory / "reference.json"
    boundary_path = ROOT / "tests/fixtures/qimen-zhirun-boundary-2018.json"
    scan_directory = ROOT / "tests/fixtures/qimen_classical_v2"
    table_directory = ROOT / "tests/fixtures/qimen_classical_v3"
    profile_directory = ROOT / "tests/fixtures/qimen_classical_v4"
    head_directory = ROOT / "tests/fixtures/qimen_classical_v5"
    day_stem_directory = ROOT / "tests/fixtures/qimen_classical_v6"
    calendar_stem_directory = ROOT / "tests/fixtures/qimen_classical_v7"
    time_condition_directory = ROOT / "tests/fixtures/qimen_classical_v8"
    tomb_clause_directory = ROOT / "tests/fixtures/qimen_classical_v9"
    punishment_directory = ROOT / "tests/fixtures/qimen_classical_v10"
    gate_relations_directory = ROOT / "tests/fixtures/qimen_classical_v11"
    clock_fold_directory = ROOT / "tests/fixtures/qimen_clock_fold_v1"
    table_diagnostics_directory = ROOT / "tests/fixtures/qimen_classical_v12"
    three_deceptions_directory = ROOT / "tests/fixtures/qimen_classical_v13"
    five_jia_directory = ROOT / "tests/fixtures/qimen_classical_v14"
    solar_clock_directory = ROOT / "tests/fixtures/qimen_solar_jpl_v1"
    fixture_fingerprints: dict[str, str] = {}

    def read_fixture(path: Path) -> Any:
        raw = path.read_bytes()
        fixture_fingerprints[str(path.relative_to(ROOT))] = hashlib.sha256(
            raw
        ).hexdigest()
        return json.loads(raw)

    classical = read_fixture(classical_path)
    calendar = read_fixture(calendar_path)
    hko = read_fixture(hko_path)
    clock_fold = read_fixture(clock_fold_directory / "reference.json")
    timezone_reference = read_fixture(timezone_path)
    boundary = read_fixture(boundary_path)
    clock_representations = read_fixture(
        ROOT / "tests/fixtures/qimen-clock-representations-v1.json"
    )
    for path in [
        *[clock_fold_directory / s["file"] for s in clock_fold["source_files"]],
        *[hko_directory / source["file"] for source in hko["sources"]],
        *[
            timezone_directory / source["excerpt_file"]
            for source in timezone_reference["sources"]
        ],
        scan_directory / "sources-and-cases.json",
        scan_directory / "siku-pages-16-20.pdf",
        table_directory / "sources-and-tables.json",
        table_directory / "siku-pages-62-71.pdf",
        table_directory / "cadal-06056497-p118.jpg",
        table_directory / "cadal-06056497-p128.jpg",
        table_directory / "cadal-06056497-imageinfo.json",
        profile_directory / "sources-and-profiles.json",
        profile_directory / "siku-chapter-variants.pdf",
        head_directory / "sources-and-cases.json",
        head_directory / "siku-pages-29-31-32.pdf",
        day_stem_directory / "sources-and-stems.json",
        day_stem_directory / "tushu705-p127.jpg",
        day_stem_directory / "tushu705-p128.jpg",
        day_stem_directory / "commons-imageinfo.json",
        calendar_stem_directory / "sources-and-anchors.json",
        *[
            calendar_stem_directory / f"hko-lunar-{year}.pdf"
            for year in (2024, 2025, 2026)
        ],
        time_condition_directory / "sources-and-hours.json",
        time_condition_directory / "siku-page33.pdf",
        tomb_clause_directory / "sources-and-tomb-clauses.json",
        tomb_clause_directory / "siku-pages32-33.pdf",
        punishment_directory / "sources-and-punishment.json",
        punishment_directory / "siku-pages33-34.pdf",
        gate_relations_directory / "siku-page34.pdf",
        gate_relations_directory / "sources-and-gate-relations.json",
        table_diagnostics_directory / "source-diagnostics.json",
        table_diagnostics_directory / "siku-pages07-08.pdf",
        three_deceptions_directory / "source-and-three-deceptions.json",
        three_deceptions_directory / "siku-pages25-26.pdf",
        five_jia_directory / "source-and-five-jia.json",
        five_jia_directory / "siku-pages26-35.pdf",
        *[
            solar_clock_directory / name
            for name in (
                "reference.json",
                "request.json",
                "protocol.json",
                "horizons-response.json",
            )
        ],
    ]:
        fixture_fingerprints[str(path.relative_to(ROOT))] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
    failures: list[dict[str, Any]] = []
    counts = {
        "calendar_references": 0,
        "calendar_pdf_cross_checks": 0,
        "chaibu_term_boundary_probes": 0,
        "invalid_civil_clock_cases": 0,
        "iana_offset_references": 0,
        "iana_future_gap_fold_references": 0,
        "classical_excerpt_examples": 0,
        "structural_boards": 0,
        "year_seam_dates": 0,
        "zhirun_profile_boundary_cases": 0,
    }

    def check(condition: bool, category: str, case: Any) -> None:
        if not condition:
            failures.append({"category": category, "case": case})

    terms = {
        t.name: t.moment for t in get_solar_terms_for_year(2026, calendar["timezone"])
    }
    for case in calendar["cases"]:
        counts["calendar_pdf_cross_checks"] += 1
        check(
            abs(
                (
                    terms[case["term"]] - datetime.fromisoformat(case["at"])
                ).total_seconds()
            )
            <= calendar["tolerance_seconds"],
            "solar_term",
            case,
        )
    for source in hko["sources"]:
        check(
            hashlib.sha256((hko_directory / source["file"]).read_bytes()).hexdigest()
            == source["sha256"],
            "calendar_source_hash",
            source["file"],
        )
    for index, case in enumerate(hko["cases"]):
        published = datetime.fromisoformat(case["at"])
        term = next(
            t
            for t in get_solar_terms_for_year(case["year"], hko["timezone"])
            if t.name == case["term"]
        )
        counts["calendar_references"] += 1
        check(
            abs((term.moment - published).total_seconds()) <= hko["tolerance_seconds"],
            "solar_term",
            case,
        )
        previous_term = hko["cases"][index - 1]["term"]
        for zone, longitude in [
            ("Asia/Hong_Kong", 114.17),
            ("America/New_York", -74.006),
        ]:
            for solar in [False, True]:
                for offset, expected in [(-2, previous_term), (2, case["term"])]:
                    at = localize_datetime(published + timedelta(minutes=offset), zone)
                    result = calculate_qimen_analysis(
                        analysis_year=at.year,
                        analysis_month=at.month,
                        analysis_day=at.day,
                        analysis_hour=at.hour,
                        analysis_minute=at.minute,
                        analysis_timezone=zone,
                        analysis_longitude=longitude,
                        use_true_solar_time=solar,
                        qimen_options={"ju_method": "chaibu"},
                    )
                    counts["chaibu_term_boundary_probes"] += 1
                    check(
                        result.get("qimen", {}).get("ju_term") == expected
                        and result.get("calendar_context", {})
                        .get("current_solar_term", {})
                        .get("name")
                        == expected,
                        "chaibu_term_boundary",
                        {
                            "reference": case,
                            "zone": zone,
                            "solar": solar,
                            "offset": offset,
                        },
                    )

    for month, day, invalid_hour, message in [
        (3, 8, 2, "nonexistent local time"),
        (11, 1, 1, "ambiguous local time"),
    ]:
        for solar in [False, True]:
            for entry in ["qimen", "sanshi"]:
                if entry == "qimen":
                    result = calculate_qimen_analysis(
                        analysis_year=2026,
                        analysis_month=month,
                        analysis_day=day,
                        analysis_hour=invalid_hour,
                        analysis_minute=30,
                        analysis_timezone="America/New_York",
                        analysis_longitude=-74.006,
                        use_true_solar_time=solar,
                    )
                else:
                    result = calculate_sanshiunited_analysis(
                        date=f"2026-{month:02d}-{day:02d}",
                        time=f"{invalid_hour:02d}:30",
                        zone="America/New_York",
                        gps_lat=40.7,
                        gps_lon=-74.006,
                        use_true_solar_time=solar,
                    )
                counts["invalid_civil_clock_cases"] += 1
                check(
                    result.get("error_code") == "validation_error"
                    and message in result.get("error", "")
                    and "qimen" not in result,
                    "civil_clock_validation",
                    {
                        "month": month,
                        "day": day,
                        "hour": invalid_hour,
                        "solar": solar,
                        "entry": entry,
                    },
                )
    # Representation invariance is a regression gate, separately counted from
    # independent astronomical references and source-derived timezone anchors.
    counts["equivalent_clock_regression_pairs"] = 0
    for case in clock_representations["cases"]:
        for solar in (False, True):
            for method in ("chaibu", "zhirun"):
                seeds = [
                    _build_metaphysics_seed(
                        date_text=case[f"{prefix}_date"],
                        time_text=case[f"{prefix}_time"],
                        timezone_name=case["zone"],
                        gps_lon=case["longitude"],
                        use_true_solar_time=solar,
                    )
                    for prefix in ("civil", "utc")
                ]
                a, b = seeds
                counts["equivalent_clock_regression_pairs"] += 1
                check(
                    a.input_datetime.isoformat() == b.input_datetime.isoformat()
                    and a.corrected_datetime.isoformat()
                    == b.corrected_datetime.isoformat()
                    and a.total_correction_minutes == b.total_correction_minutes
                    and a.pillars == b.pillars
                    and a.calendar_context == b.calendar_context
                    and build_qimen_with_options(a, {"ju_method": method})
                    == build_qimen_with_options(b, {"ju_method": method}),
                    "equivalent_clock_regression",
                    {**case, "solar": solar, "ju_method": method},
                )

    for source in timezone_reference["sources"]:
        check(
            hashlib.sha256(
                (timezone_directory / source["excerpt_file"]).read_bytes()
            ).hexdigest()
            == source["excerpt_sha256"],
            "timezone_source_hash",
            source["excerpt_file"],
        )
    for case in timezone_reference["cases"]:
        clock = datetime.fromisoformat(case["at"]).replace(
            tzinfo=parse_timezone_name(case["zone"])
        )
        counts["iana_offset_references"] += 1
        utc_offset, dst = clock.utcoffset(), clock.dst()
        check(
            utc_offset is not None
            and utc_offset.total_seconds() == case["offset_seconds"]
            and dst is not None
            and dst.total_seconds() == case["dst_seconds"],
            "iana_offset",
            case,
        )
    for case in timezone_reference["invalid_clocks"]:
        clock = datetime.fromisoformat(case["at"]).replace(
            tzinfo=parse_timezone_name(case["zone"])
        )
        rejected = False
        try:
            validate_local_clock(clock)
        except ValueError as exc:
            rejected = case["kind"] in str(exc)
        counts["iana_future_gap_fold_references"] += 1
        check(rejected, "iana_future_gap_fold", case)

    for case in calendar["day_anchors"]:
        at = datetime.fromisoformat(case["date"])
        counts["calendar_references"] += 1
        check(
            get_day_ganzhi(at.year, at.month, at.day) == case["ganzhi"],
            "civil_day",
            case,
        )

    for group in ["leader_examples", "moving_examples", "pattern_examples"]:
        for case in classical[group]:
            counts["classical_excerpt_examples"] += 1
            ju = f'{case["dun"]}{"一二三四五六七八九"[case["ju"]-1]}局上元'
            leader = _qimen_zhifu_zhishi(case["hour"], ju, dun_type=case["dun"])
            palaces = _qimen_build_palaces(
                time_ganzhi=case["hour"],
                ju_text=ju,
                dun_type=case["dun"],
                current_term="冬至",
            )
            by_gua = {p["trigram"]: p for p in palaces}
            if group == "leader_examples":
                from fatebridge.core.metaphysics.qimen import (
                    QIMEN_DOOR_DISPLAY,
                    QIMEN_STAR_DISPLAY,
                )

                ok = (
                    QIMEN_STAR_DISPLAY[leader["star"]] == case["star"]
                    and QIMEN_DOOR_DISPLAY[leader["door"]] == case["door"]
                    and leader["source_gong"] == case["source"]
                )
            elif group == "moving_examples":
                ok = (
                    leader["star_gong"] == case["star_at"]
                    and leader["door_gong"] == case["door_at"]
                    and all(
                        stem in by_gua[gua]["heaven_stems"]
                        for gua, stem in case["sky_stems"].items()
                    )
                )
            else:
                at = datetime(2026, 1, 1, 12)
                seed = MetaphysicsSeed(
                    at,
                    at,
                    "Asia/Shanghai",
                    None,
                    False,
                    0.0,
                    {"month": ("丙", "寅")},
                    {"current_solar_term": {"name": "冬至"}},
                )
                board = enrich_qimen_evidence(
                    {
                        "ju_text": ju,
                        "palaces": palaces,
                        "ju_method": "zhirun",
                        "ju_term": "冬至",
                        "day_ganzhi": "甲子",
                        "time_ganzhi": case["hour"],
                        "kongwang": "戌亥空",
                    },
                    seed=seed,
                    leader=leader,
                )
                ok = any(
                    p["name"] == case["name"]
                    and p["palace"] == case["palace"]
                    and p["facts"]
                    == {"heaven_stem": case["sky"], "earth_stem": case["earth"]}
                    for p in board["patterns"]
                )
            check(ok, group, case)

    stems, branches = "甲乙丙丁戊己庚辛壬癸", "子丑寅卯辰巳午未申酉戌亥"
    for dun in ["阳遁", "阴遁"]:
        for ju_number in range(1, 10):
            ju = f'{dun}{"一二三四五六七八九"[ju_number-1]}局上元'
            for i in range(60):
                hour = stems[i % 10] + branches[i % 12]
                palaces = _qimen_build_palaces(
                    time_ganzhi=hour, ju_text=ju, dun_type=dun, current_term="冬至"
                )
                outer = [p for p in palaces if p["trigram"] != "中"]
                counts["structural_boards"] += 1
                ok = (
                    len({p["door"] for p in outer}) == 8
                    and len({p["god"] for p in outer}) == 8
                    and sorted(s for p in outer for s in p["heaven_stems"])
                    == sorted("戊己庚辛壬癸丁丙乙")
                    and len([s for p in outer for s in [p["star"], *p["hosted_stars"]]])
                    == 9
                )
                if i % 10 == 0:
                    ok = ok and all(p["heaven_stem"] == p["earth_stem"] for p in outer)
                check(ok, "conservation", {"ju": ju, "hour": hour})
    for year in range(1901, 2100):
        current = _qimen_build_yinyangdun_map(year, "Asia/Shanghai")
        following = _qimen_build_yinyangdun_map(year + 1, "Asia/Shanghai")
        for key in sorted(current.keys() & following.keys()):
            if key.startswith(str(year + 1)):
                counts["year_seam_dates"] += 1
                check(current[key] == following[key], "year_seam", key)

    for case in boundary["cases"]:
        at = datetime.fromisoformat(case["at"])
        seed = MetaphysicsSeed(
            at,
            at,
            "Asia/Hong_Kong",
            None,
            False,
            0.0,
            {"day": tuple(case["day"]), "hour": ("甲", "子")},
            {},
        )
        meta = _qimen_resolve_zhirun_meta(seed=seed)
        counts["zhirun_profile_boundary_cases"] += 1
        check(
            meta["current_term"] == case["ju_term"]
            and _qimen_build_ju_text(meta["dun_type"], meta["ju_number"], meta["yuan"])
            == case["ju_text"],
            "zhirun_profile_boundary",
            case,
        )

    scan_report = audit_scan_examples(scan_directory)
    counts["facsimile_cases"] = scan_report["case_count"]
    counts["facsimile_matched_cases"] = scan_report["matched_case_count"]
    failures.extend(
        {"category": "facsimile_disagreement", **d}
        for d in scan_report["disagreements"]
    )
    table_report = audit_numeric_tables(table_directory)
    table_integrity = audit_printed_table_integrity(table_directory)
    table_source_context = audit_table_source_context(table_diagnostics_directory)
    # One printed cell can have both an engine disagreement and a diagnostic
    # witness. Count it once; do not erase it if the engine is forced to agree.
    unrepresented_source_cells = unrepresented_walk_anomalies(
        table_integrity, table_report["disagreements"]
    )
    failures.extend(
        {"category": "printed_numeric_walk_inconsistency", **d}
        for d in unrepresented_source_cells
    )
    counts["printed_walk_anomalous_cells"] = len(table_integrity["anomalous_cells"])
    counts["printed_walk_adjacent_transition_defects"] = len(
        table_integrity["adjacent_transition_defects"]
    )
    counts["printed_walk_nine_step_closure_defects"] = len(
        table_integrity["nine_step_closure_defects"]
    )
    counts["printed_numeric_table_cases"] = table_report["case_count"]
    counts["printed_numeric_table_matched_cases"] = table_report["matched_case_count"]
    failures.extend(
        {"category": "printed_numeric_table_disagreement", **d}
        for d in table_report["disagreements"]
    )
    profile_report = audit_chapter_profiles(profile_directory)
    failures.extend(
        {"category": "chapter_profile_disagreement", **d}
        for d in profile_report["disagreements"]
    )
    head_report = audit_head_dependent_examples(head_directory)
    counts["head_dependent_source_examples"] = head_report["case_count"]
    counts["head_dependent_matched_examples"] = head_report["matched_case_count"]
    counts["head_dependent_deferred_unpassed"] = head_report["deferred_unpassed_count"]
    failures.extend(
        {"category": "head_dependent_source_disagreement", **d}
        for d in head_report["disagreements"]
    )
    day_stem_report = audit_day_stem_collation(day_stem_directory)
    failures.extend(
        {"category": "day_stem_preferred_source_disagreement", **d}
        for d in day_stem_report["preferred_source_disagreements"]
    )
    counts["day_stem_collation_records"] = day_stem_report["case_count"]
    counts["day_stem_supporting_disagreements"] = len(
        day_stem_report["supporting_source_disagreements"]
    )
    calendar_stem_report = audit_calendar_stems(calendar_stem_directory)
    time_condition_report = audit_hour_branch_tombs(time_condition_directory)
    tomb_clause_report = audit_wonder_tomb_clauses(tomb_clause_directory)
    punishment_report = audit_punishment(punishment_directory)
    gate_report = audit_gate_relations(gate_relations_directory)
    three_deceptions_report = audit_three_deceptions(three_deceptions_directory)
    five_jia_report = audit_five_jia(five_jia_directory)
    counts["five_jia_computable_naming_definitions"] = five_jia_report[
        "printed_computable_naming_definitions"
    ]
    counts["five_jia_unresolved_naming_definitions"] = five_jia_report[
        "printed_unresolved_naming_definitions"
    ]
    counts["five_jia_finite_context_probes"] = five_jia_report[
        "finite_single_stem_context_probes"
    ]
    failures.extend(
        {"category": "five_jia_implementation_disagreement", **d}
        for d in five_jia_report["implementation_disagreements"]
    )
    failures.extend(
        {"category": "five_jia_unresolved_human_identity", **d}
        for d in five_jia_report["unresolved_source_priorities"]
    )
    counts["three_deceptions_printed_naming_definitions"] = three_deceptions_report[
        "printed_naming_definitions"
    ]
    counts["three_deceptions_retained_partial_clauses"] = three_deceptions_report[
        "retained_partial_clauses"
    ]
    counts["three_deceptions_finite_context_probes"] = three_deceptions_report[
        "finite_single_stem_context_probes"
    ]
    failures.extend(
        {"category": "three_deceptions_implementation_disagreement", **d}
        for d in three_deceptions_report["implementation_disagreements"]
    )
    failures.extend(
        {"category": "three_deceptions_unresolved_partial_priority", **d}
        for d in three_deceptions_report["unresolved_source_priorities"]
    )
    clock_fold_report = audit_clock_fold(clock_fold_directory)
    solar_clock_report = audit_solar_clocks(solar_clock_directory)
    counts["jpl_solar_clock_reference_instants"] = solar_clock_report[
        "reference_instants"
    ]
    counts["solar_boundary_classifications_unverified_at_reference_tolerance"] = len(
        solar_clock_report["boundary_cases_not_certified_at_reference_tolerance"]
    )
    failures.extend(
        {"category": "solar_clock_reference", **d}
        for d in solar_clock_report["implementation_disagreements"]
    )
    counts["calendar_references"] += clock_fold_report[
        "independent_calendar_reference_count"
    ]
    counts["havana_fold_iana_clock_probes"] = clock_fold_report[
        "iana_derived_clock_probes"
    ]
    failures.extend(
        {"category": "clock_fold_reference", "detail": d}
        for d in clock_fold_report["disagreements"]
    )
    counts["gate_relation_wording_definitions"] = gate_report[
        "source_relation_definition_count"
    ]
    counts["gate_literal_pair_observations"] = gate_report[
        "literal_pair_observation_count"
    ]
    counts["gate_matched_pair_observations"] = gate_report[
        "matched_pair_observation_count"
    ]
    counts["gate_finite_evidence_scope_probes"] = gate_report[
        "finite_evidence_scope_probes"
    ]
    failures.extend(
        {"category": "gate_relation_source_disagreement", **d}
        for d in gate_report["disagreements"]
    )
    counts["printed_punishment_identity_definitions"] = punishment_report[
        "definition_count"
    ]
    counts["printed_punishment_hour_examples"] = punishment_report["example_count"]
    counts["matched_punishment_hour_examples"] = punishment_report[
        "matched_example_count"
    ]
    counts["punishment_unresolved_scope_priorities"] = len(
        punishment_report["unresolved_source_scope_priorities"]
    )
    failures.extend(
        {"category": "punishment_definition_disagreement", **d}
        for d in punishment_report["definition_disagreements"]
    )
    failures.extend(
        {"category": "punishment_printed_example_disagreement", **d}
        for d in punishment_report["example_disagreements"]
    )
    failures.extend(
        {"category": "punishment_unresolved_source_scope", **d}
        for d in punishment_report["unresolved_source_scope_priorities"]
    )
    counts["wonder_tomb_selected_rule_cells"] = tomb_clause_report[
        "selected_explicit_rule_cells"
    ]
    counts["wonder_tomb_unadopted_literal_cells"] = tomb_clause_report[
        "unadopted_literal_candidate_cells"
    ]
    counts["wonder_tomb_unresolved_priorities"] = len(
        tomb_clause_report["unresolved_source_priorities"]
    )
    failures.extend(
        {"category": "wonder_tomb_implementation_disagreement", **d}
        for d in tomb_clause_report["implementation_disagreements"]
    )
    failures.extend(
        {"category": "wonder_tomb_unresolved_source_priority", **d}
        for d in tomb_clause_report["unresolved_source_priorities"]
    )
    counts["printed_hour_branch_tomb_definitions"] = time_condition_report[
        "printed_literal_pair_definitions"
    ]
    counts["finite_literal_hour_values_checked"] = time_condition_report[
        "finite_hour_values_checked"
    ]
    failures.extend(
        {"category": "hour_branch_tomb_definition", **d}
        for d in time_condition_report["disagreements"]
    )
    counts["calendar_stem_printed_examples"] = calendar_stem_report[
        "printed_literal_stem_examples"
    ]
    counts["modern_lunar_month_start_references"] = calendar_stem_report[
        "calendar_reference_count"
    ]
    failures.extend(
        {
            "category": (
                "modern_lunar_month_anchor"
                if d["scope"] == "modern_hko_date_with_derived_ganzhi"
                else "calendar_stem_printed_source_disagreement"
            ),
            **d,
        }
        for d in calendar_stem_report["disagreements"]
    )
    if any(
        hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected
        for name, expected in {**implementation, **fixture_fingerprints}.items()
    ):
        raise RuntimeError(
            "奇门审计期间依赖源码或参考资料发生变化；本次结果不写入，请固定输入后重跑"
        )

    return {
        "ruleset_id": RULESET_ID,
        "implementation_sha256": implementation,
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "pyswisseph": importlib.metadata.version("pyswisseph"),
            "lunardate": importlib.metadata.version("lunardate"),
            "pytz": importlib.metadata.version("pytz"),
        },
        "fixture_sha256": fixture_fingerprints,
        "counts": counts,
        "failures": failures,
        "calendar": {
            "status": (
                "failed"
                if any(
                    f["category"]
                    in {
                        "solar_term",
                        "civil_day",
                        "calendar_source_hash",
                        "chaibu_term_boundary",
                        "civil_clock_validation",
                        "equivalent_clock_regression",
                        "iana_offset",
                        "iana_future_gap_fold",
                        "timezone_source_hash",
                        "modern_lunar_month_anchor",
                        "clock_fold_reference",
                        "solar_clock_reference",
                    }
                    for f in failures
                )
                else (
                    "reference_values_passed_boundary_classification_partial"
                    if solar_clock_report[
                        "boundary_cases_not_certified_at_reference_tolerance"
                    ]
                    else "reference_cases_passed"
                )
            ),
            "scope": "73 HKO terms (72 in 2026-2028 and 2021 Winter Commences) and 4 civil day anchors; 12 additional 2026 PDF cross-checks; 576 term-boundary probes in Hong Kong/New York with civil/apparent-solar clocks; 4 IANA-derived Havana repeated-midnight probes; 8 ambiguous/unavailable civil clocks rejected when no disambiguating offset is supplied; 15 IANA text-derived offsets and 6 future gap/fold cases outside the 32-bit interval; 32 equivalent-clock regression pairs across eight date/zone cases, separately counted from independent references",
            "repeated_midnight_boundary": clock_fold_report,
            "solar_clock_references": solar_clock_report,
        },
        "classical": {
            "status": (
                "incomplete_with_disagreements"
                if scan_report["disagreements"]
                or table_report["disagreements"]
                or table_integrity["anomalous_cells"]
                or profile_report["disagreements"]
                or head_report["disagreements"]
                or day_stem_report["preferred_source_disagreements"]
                or any(
                    d["scope"] == "printed_literal_stem_palace_only"
                    for d in calendar_stem_report["disagreements"]
                )
                or time_condition_report["disagreements"]
                or tomb_clause_report["implementation_disagreements"]
                or tomb_clause_report["unresolved_source_priorities"]
                or punishment_report["definition_disagreements"]
                or punishment_report["example_disagreements"]
                or punishment_report["unresolved_source_scope_priorities"]
                or gate_report["disagreements"]
                or three_deceptions_report["implementation_disagreements"]
                or three_deceptions_report["unresolved_source_priorities"]
                or five_jia_report["implementation_disagreements"]
                or five_jia_report["unresolved_source_priorities"]
                else "partial_excerpt"
            ),
            "source": classical["source_url"],
            "whole_book_conformance_established": False,
            "scan_collation_complete": False,
            "selected_scan_comparison": scan_report,
            "all_eighteen_numeric_tables": table_report,
            "printed_table_internal_diagnostics": table_integrity,
            "table_context_and_catalogue_observations": table_source_context,
            "chapter_profiles": profile_report,
            "head_dependent_examples": head_report,
            "day_stem_collation": day_stem_report,
            "calendar_stem_examples": calendar_stem_report,
            "hour_branch_tomb_definitions": time_condition_report,
            "wonder_tomb_textual_clauses": tomb_clause_report,
            "current_zhifu_punishment": punishment_report,
            "gate_palace_relation_names": gate_report,
            "three_deceptions_full_names_and_partial_scope": three_deceptions_report,
            "five_jia_four_names_and_unresolved_human_identity": five_jia_report,
        },
        "interpretation": {
            "status": "structured_rule_evidence",
            "live_model_behavior_validated": False,
            "same_run_whole_pattern_quote_validator": "fatebridge.validation.qimen.verify_qimen_pattern_quotes",
            "same_run_whole_time_condition_quote_validator": "fatebridge.validation.qimen_time_conditions.verify_qimen_time_condition_quotes",
            "same_run_whole_solar_time_quote_validator": "fatebridge.validation.qimen_solar.verify_qimen_solar_time_quotes",
            "free_text_semantics_validated": False,
        },
        "real_world_prediction": {
            "status": "not_tested",
            "independent_cases": 0,
            "prospective_registration_completed": False,
            "evidence_binding_protocol": {
                "status": "implemented_replay_protocol_not_empirical_validation",
                "commitment_format": "qimen_forecast_commitment_v3",
                "cli": "scripts/audit_qimen_study.py",
                "scope": "Complete study plan, full cohort, policy and castings fingerprint in every case receipt; actual charts and decisions recomputed before scoring. Real submissions require a separately retained expected canonical whole-packet digest.",
                "expected_digest_provenance_authenticated": False,
                "external_registration_and_adjudication_verified": False,
            },
        },
        "authority_certified": False,
        "four_dimensions_perfect": False,
        "limitations": [
            "Structural checks are finite invariants, not independent classical predictions.",
            "The 9-day civil-date intercalation convention is internally continuous; historical variants and all-year astronomical accuracy are not certified.",
            "Only externally verified prospective outcomes could establish predictive performance for a registered target. No such data was supplied.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    print(
        json.dumps(
            {
                "counts": report["counts"],
                "failure_count": len(report["failures"]),
                "four_dimensions_perfect": False,
            },
            ensure_ascii=False,
        )
    )
    return int(bool(report["failures"]))


if __name__ == "__main__":
    raise SystemExit(main())

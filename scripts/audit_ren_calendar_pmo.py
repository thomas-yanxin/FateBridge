"""Compare all 3024 printed PMO term minutes, retaining every discrepancy."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/ren_calendar_pmo_v1"
TERMS = "小寒 大寒 立春 雨水 惊蛰 春分 清明 谷雨 立夏 小满 芒种 夏至 小暑 大暑 立秋 处暑 白露 秋分 寒露 霜降 立冬 小雪 大雪 冬至".split()
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
IMPLEMENTATION = (
    "src/fatebridge/core/almanac.py",
    "src/fatebridge/core/solar_term_runtime.py",
    "src/fatebridge/core/ephemeris_runtime.py",
    "src/fatebridge/core/astro_models.py",
    "src/fatebridge/core/ephemeris_installation.py",
    "src/fatebridge/core/astro/time_scales.py",
    "src/fatebridge/core/astro/historical_utc.py",
    "src/fatebridge/core/calendar.py",
    "src/fatebridge/services/metaphysics.py",
    "src/fatebridge/core/metaphysics/ren_calendar.py",
    "src/fatebridge/core/metaphysics/liureng.py",
    "src/fatebridge/core/metaphysics/jinkou.py",
    "scripts/audit_ren_calendar_pmo.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extracted_tables(text: str) -> list[dict[str, Any]]:
    pattern = re.compile(
        "(" + "|".join(TERMS) + r")(?:\s*\d\s*\)?)?\s+"
        r"(\d{1,2})\s+(\d{1,2})\s+(\d{1,2})\s+(\d{2})"
    )
    rows = []
    pages_per_year: dict[int, int] = {}
    for index, page in enumerate(text.split("\f"), start=1):
        heading = re.search(r"公元\s*(\d{4})\s*年", page)
        if heading is None:
            continue
        year = int(heading[1])
        pages_per_year[year] = pages_per_year.get(year, 0) + 1
        section = re.split(r"节\s*气", page)[-1]
        matches = list(pattern.finditer(section))
        if len(matches) != 8:
            raise ValueError(f"PMO page {index} must retain eight terms")
        for match in matches:
            month, day, hour, minute = map(int, match.group(2, 3, 4, 5))
            moment = datetime(year, month, day, hour, minute).isoformat() + "+08:00"
            rows.append(
                dict(
                    year=year,
                    term=match[1],
                    published_moment=moment,
                    pdf_page=index,
                    extracted_table_token=match[0],
                )
            )
    if pages_per_year != {year: 3 for year in range(1900, 2026)}:
        raise ValueError("PMO must retain all three pages of all 126 years")
    rows.sort(key=lambda row: (row["year"], row["published_moment"]))
    for year in range(1900, 2026):
        if [row["term"] for row in rows if row["year"] == year] != TERMS:
            raise ValueError(f"PMO year {year} must retain all 24 ordered terms")
    return rows


def reference(corpus: Path = CORPUS) -> dict[str, Any]:
    manifest = json.loads((corpus / "freeze.json").read_text())
    files = {"reference.json", "source.pdf", "source.txt"}
    if set(manifest["files"]) != files or {
        path.name for path in corpus.iterdir()
    } != files | {"freeze.json"}:
        raise ValueError("Frozen PMO inventory changed")
    for name, checksum in manifest["files"].items():
        if sha(corpus / name) != checksum:
            raise ValueError(f"Frozen PMO source changed: {name}")
    ref: dict[str, Any] = json.loads((corpus / "reference.json").read_text())
    if extracted_tables((corpus / "source.txt").read_text()) != ref["cases"]:
        raise ValueError("PMO annotation differs from the complete extracted tables")
    return ref


def audit() -> dict[str, Any]:
    ref = reference()
    # Reuse only the separately frozen primary calendar tables; this module
    # imports no production code until audit() itself is called.
    spec = importlib.util.spec_from_file_location(
        "ren_calendar_reference", ROOT / "scripts/audit_ren_calendar.py"
    )
    assert spec and spec.loader
    calendar_audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(calendar_audit)
    calendar_ref = calendar_audit.reference()
    implementation = {name: sha(ROOT / name) for name in IMPLEMENTATION}
    from fatebridge.core.almanac import get_solar_terms_for_year, localize_datetime
    from fatebridge.core.metaphysics.jinkou import build_jinkou_board
    from fatebridge.core.metaphysics.liureng import build_liureng_board
    from fatebridge.core.metaphysics.ren_calendar import require_ren_calendar
    from fatebridge.services.metaphysics import _build_analysis_seed

    comparisons = []
    errors = []
    boundary_failures = []
    boundary_pairs = 0
    generals = calendar_ref["general_starts"]
    middle_terms = list(generals)
    for case in ref["cases"]:
        published = datetime.fromisoformat(case["published_moment"])
        try:
            actual = next(
                term
                for term in get_solar_terms_for_year(case["year"], "+08:00")
                if term.name == case["term"]
            )
            delta = (actual.moment - published).total_seconds()
            comparisons.append(
                dict(
                    **case,
                    actual=actual.moment.isoformat(),
                    provider=actual.resolution_provider,
                    ephemeris_model=actual.ephemeris_model,
                    ephemeris_retflags=list(actual.ephemeris_retflags),
                    ephemeris_library_version=actual.ephemeris_library_version,
                    difference_seconds=delta,
                    within_printed_minute_criterion=(
                        abs(delta)
                        <= ref["minute_precision_policy"][
                            "max_absolute_difference_seconds"
                        ]
                        and actual.resolution_provider == "swisseph"
                    ),
                    literal_date_matches=actual.moment.date() == published.date(),
                )
            )
            if case["term"] not in generals:
                continue
            before = generals[middle_terms[(middle_terms.index(case["term"]) - 1) % 12]]
            after = generals[case["term"]]
            for zone in ("+08:00", "UTC", "+09:00"):
                observed = []
                for seconds in (-90, 90):
                    civil = localize_datetime(
                        published + timedelta(seconds=seconds), zone
                    )
                    seed = _build_analysis_seed(
                        analysis_year=civil.year,
                        analysis_month=civil.month,
                        analysis_day=civil.day,
                        analysis_hour=civil.hour,
                        analysis_minute=civil.minute,
                        analysis_second=civil.second,
                        analysis_timezone=zone,
                        use_true_solar_time=False,
                    )
                    seed.calendar_context["ren_calendar_policy"] = require_ren_calendar(
                        seed
                    )
                    board = build_liureng_board(seed)
                    jinkou = build_jinkou_board(seed, board, di_fen="子")
                    observed.append(
                        [
                            board["month_general"]["branch"],
                            jinkou["overview"]["month_general"]["branch"],
                        ]
                    )
                boundary_pairs += 1
                if observed != [[before, before], [after, after]]:
                    boundary_failures.append(
                        dict(
                            year=case["year"],
                            term=case["term"],
                            timezone=zone,
                            expected=[before, after],
                            actual=observed,
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
    failures = [
        row for row in comparisons if not row["within_printed_minute_criterion"]
    ]
    unchanged = implementation == {name: sha(ROOT / name) for name in IMPLEMENTATION}
    return dict(
        audit_id="ren_calendar_pmo_v1",
        expected_count=len(ref["cases"]),
        compared_count=len(comparisons),
        minute_criterion=ref["minute_precision_policy"],
        minute_failure_count=len(failures),
        minute_failures=failures,
        max_absolute_difference_seconds=max(
            (abs(row["difference_seconds"]) for row in comparisons), default=None
        ),
        literal_date_differences=[
            row for row in comparisons if not row["literal_date_matches"]
        ],
        boundary_pair_count=boundary_pairs,
        boundary_pair_failures=boundary_failures,
        boundary_clock_scope="fixed offsets +08:00, UTC and +09:00; independent printed minute +/-90 seconds",
        calculation_errors=errors,
        comparisons=comparisons,
        historical_term_notes=ref["historical_term_notes"],
        implementation_sha256=implementation,
        implementation_unchanged_during_audit=unchanged,
        all_performed_comparisons_passed=(
            not failures and not errors and not boundary_failures and unchanged
        ),
        full_supported_calendar_domain_certified=False,
        goal_complete=False,
        source_sha256=sha(CORPUS / "reference.json"),
        limits=ref["limits"],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "compared_count",
                    "minute_failure_count",
                    "max_absolute_difference_seconds",
                    "boundary_pair_count",
                    "all_performed_comparisons_passed",
                )
            }
        )
    )
    return 0 if report["all_performed_comparisons_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

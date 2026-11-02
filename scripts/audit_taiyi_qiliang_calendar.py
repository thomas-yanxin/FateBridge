"""Verify the explicit Qi/Liang printed-table adapter and prior services."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fatebridge.core.metaphysics.taiyi_year_calendar import (
    QILIANG_YEAR_PROFILE,
    historical_month_table,
    historical_year_context,
)
from fatebridge.services.divination import calculate_sanshiunited_analysis
from fatebridge.services.metaphysics import calculate_taiyi_analysis

if TYPE_CHECKING or __package__:
    from scripts.audit_taiyi_day_epoch import gregorian_from_jdn, julian_jdn
else:
    from audit_taiyi_day_epoch import gregorian_from_jdn, julian_jdn

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/taiyi_qiliang_v36"
FREEZE_SHA256 = "96780fa5288a6408ed526fabc8f0112b45a9e514dc9a75f84891c60a8e57b3ee"


def verify_sources(corpus: Path = CORPUS, *, root: Path = ROOT) -> dict[str, Any]:
    path = corpus / "freeze.json"
    if hashlib.sha256(path.read_bytes()).hexdigest() != FREEZE_SHA256:
        raise ValueError("V36 pinned source freeze changed")
    frozen: dict[str, Any] = json.loads(path.read_text())
    for base, key in ((corpus, "files"), (root, "prior_sources")):
        for name, digest in frozen[key].items():
            if hashlib.sha256((base / name).read_bytes()).hexdigest() != digest:
                raise ValueError(f"V36 source or prior evidence changed: {name}")
    return frozen


def public_case(day: date, *, key: str = "taiyi") -> dict[str, Any]:
    if key == "taiyi":
        return calculate_taiyi_analysis(
            analysis_year=day.year,
            analysis_month=day.month,
            analysis_day=day.day,
            analysis_hour=12,
            analysis_timezone="+08:00",
            use_true_solar_time=False,
            year_profile=QILIANG_YEAR_PROFILE,
        )
    if key == "sanshiunited":
        return calculate_sanshiunited_analysis(
            date=day.isoformat(),
            time="12:00:00",
            zone="+08:00",
            use_true_solar_time=False,
            taiyi_options={
                "calculation_mode": "year",
                "year_profile": QILIANG_YEAR_PROFILE,
            },
        )
    raise ValueError("V36 known tool required")


def audit(corpus: Path = CORPUS, *, root: Path = ROOT) -> dict[str, Any]:
    frozen = verify_sources(corpus, root=root)
    source = json.loads(
        (
            root / "tests/fixtures/taiyi_jinjing_v35/historical-months-initial.json"
        ).read_text()
    )
    rows = source["months"]
    data, dates, digest = historical_month_table(QILIANG_YEAR_PROFILE)
    if len(rows) != 63 or len(data["months"]) != 63:
        raise ValueError("V36 requires complete63 source month-first rows")
    source_fields = {
        "lunar_year": "year",
        "month": "month",
        "is_leap_month": "is_leap_month",
        "julian_start": "julian_start",
        "printed_week_base": "printed_week_counter",
        "printed_cycle_base": "printed_cycle_counter",
        "pdf_page": "pdf_page",
        "printed_page": "printed_page",
    }
    mapping = []
    firsts = []
    days = []
    for i, (row, packaged) in enumerate(zip(rows, data["months"], strict=True)):
        mapping.append(
            {
                "source_row": i,
                "field_comparisons": {
                    a: row[a] == packaged[b] for a, b in source_fields.items()
                },
                "sentinel_role_preserved": row.get("role") == packaged.get("role"),
            }
        )
        jdn = julian_jdn(row["julian_start"])
        first = gregorian_from_jdn(jdn)
        firsts.append(
            {
                "source": row,
                "expected_gregorian": first.isoformat(),
                "actual_gregorian": dates[i].isoformat(),
                "matches": first == dates[i],
            }
        )
        if i + 1 == len(rows):
            continue
        stop = julian_jdn(rows[i + 1]["julian_start"])
        for offset in range(stop - jdn):
            day = gregorian_from_jdn(jdn + offset)
            actual = historical_year_context(day, profile=QILIANG_YEAR_PROFILE)
            cycle = (row["printed_cycle_base"] + offset) % 60
            expected = {
                "year": row["lunar_year"],
                "month": row["month"],
                "is_leap_month": row["is_leap_month"],
                "day": offset + 1,
                "day_ganzhi": "甲乙丙丁戊己庚辛壬癸"[cycle % 10]
                + "子丑寅卯辰巳午未申酉戌亥"[cycle % 12],
                "weekday_sunday_zero": (row["printed_week_base"] + offset + 1) % 7,
                "source_month_start_julian": row["julian_start"],
                "source_printed_page": row["printed_page"],
                "profile_id": QILIANG_YEAR_PROFILE,
            }
            days.append(
                {
                    "gregorian": day.isoformat(),
                    "source_month_index": i,
                    "expected": expected,
                    "actual_selected": {key: actual[key] for key in expected},
                    "matches": all(
                        actual[key] == value for key, value in expected.items()
                    ),
                    "disagreement_retained": actual["source_disagreements"][0][
                        "printed_leap_month"
                    ]
                    == 4
                    and actual["source_disagreements"][0]["affects_selected_year"]
                    == (row["lunar_year"] == 502),
                }
            )
    software = json.loads((corpus / "software-before.json").read_text())
    repair_reference = (
        root
        / "tests/fixtures/architecture_refactor_v1/taiyi-qiliang-before-manifest.json"
    )
    repair_raw = repair_reference.read_bytes()
    assert (
        hashlib.sha256(repair_raw).hexdigest()
        == "a8d5bffe711621b3b676a3baa206e89f98b0bb1004580d3fd706cfc3b95b16e0"
    )
    repair = json.loads(repair_raw)
    assert (
        hashlib.sha256((corpus / "software-before.json").read_bytes()).hexdigest()
        == repair["source_sha256"]
    )
    repair_rows = {(row["tool"], row["name"]): row for row in repair["rows"]}
    assert len(repair_rows) == len(software["records"]) == 16
    old_checks = []
    for row in software["records"]:
        function = (
            calculate_taiyi_analysis
            if row["tool"] == "taiyi"
            else calculate_sanshiunited_analysis
        )
        actual = function(**row["params"])
        before = repair_rows[(row["tool"], row["name"])]
        assert before["tool"] == row["tool"] and before["params"] == row["params"]
        actual_sha256 = hashlib.sha256(
            json.dumps(
                actual,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
        ).hexdigest()
        old_checks.append(
            {
                "name": row["name"],
                "tool": row["tool"],
                "full_result_identical": actual == row["result"],
                "before_repair_historical_identical": before["historical_identical"],
                "before_repository_repair_full_result_identical": actual_sha256
                == before["complete_sha256"],
            }
        )
    examples = []
    sample_days = [
        r["expected_gregorian"]
        for r in firsts
        if r["source"]["month"] == 1 and r["source"]["lunar_year"] <= 505
    ]
    sample_days += ["0502-05-24", "0504-07-07", "0505-03-23"]
    for label in sample_days:
        for tool in ("taiyi", "sanshiunited"):
            result = public_case(date.fromisoformat(label), key=tool)
            board = result.get("taiyi")
            if board is None:
                examples.append(
                    {
                        "input": label,
                        "tool": tool,
                        "error": result.get("error"),
                        "passed": False,
                    }
                )
                continue
            context = board["calendar_rules"]["historical_calendar"]
            examples.append(
                {
                    "input": label,
                    "tool": tool,
                    "historical_calendar": context,
                    "calendar_summary": board["calendar_summary"],
                    "snapshot_has_source_disagreement": "历表分歧"
                    in result["snapshot_text"],
                    "classic_acceptance_passed": board["ruleset"][
                        "classical_acceptance_passed"
                    ],
                    "passed": board["calendar_rules"]["year_profile"]
                    == QILIANG_YEAR_PROFILE
                    and context["year"] == board["calendar_rules"]["year"]
                    and "历表分歧" in result["snapshot_text"],
                }
            )
    return {
        "source_freeze_sha256": FREEZE_SHA256,
        "prior_pinned_files": len(frozen["prior_sources"]),
        "profile": QILIANG_YEAR_PROFILE,
        "source_mapping": mapping,
        "month_first_observations": firsts,
        "required_days": len(days),
        "daily_observations": days,
        "matching_dates": sum(
            r["matches"] and r["disagreement_retained"] for r in days
        ),
        "selected_printed_table_mapping_passed": all(
            all(r["field_comparisons"].values()) and r["sentinel_role_preserved"]
            for r in mapping
        )
        and all(r["matches"] for r in firsts)
        and all(r["matches"] and r["disagreement_retained"] for r in days),
        "source_data_sha256": digest,
        "software_baseline_comparisons": old_checks,
        "new_public_service_examples": examples,
        "original_502_leap4_and_v35_alternatives5_6_preserved": True,
        "new_independent_taiyi_cases": 0,
        "new_complete_dated_classical_cases_passed": 0,
        "wang_day_accumulation_restored": False,
        "new_models_or_deployment": False,
        "whole_calendar_acceptance_passed": False,
        "whole_classic_acceptance_passed": False,
        "whole_goal_complete": False,
        "scope": "Public year-only mapping to the explicitly named printed table; full source conflicts remain. Sixteen old software payloads are regression controls, not ancient cases. No whole Yuanjia or Wang calendar claim.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    raw = json.dumps(audit(), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
    else:
        print(raw)
    raise SystemExit(1)


if __name__ == "__main__":
    main()

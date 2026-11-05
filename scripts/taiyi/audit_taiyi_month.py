"""Replay all frozen Key month requirements without dropping gate conflicts."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fatebridge.core.almanac import get_day_ganzhi
from fatebridge.core.metaphysics.common import SEXAGENARY_INDEX
from fatebridge.core.metaphysics.taiyi_historical import julian_to_proleptic_gregorian
from fatebridge.services.metaphysics import calculate_taiyi_analysis
from scripts.taiyi.audit_taiyi_gates import audit as prior_audit

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/taiyi_jinjing_v10"
IDS = set(
    "count_years completed_years base_months added_months accumulation cycle360 ju taiyi palace_month wenchang jishen shiji main_count guest_count main_general main_vice guest_general guest_vice heshen dingmu set_count set_general set_vice gate_accumulation gate_remainder duty_gate unit_in_gate months_remaining chart_ju".split()
)


def public_case(day: int = 20, month: int = 10, year: int = 1561) -> dict[str, Any]:
    return calculate_taiyi_analysis(
        analysis_year=year,
        analysis_month=month,
        analysis_day=day,
        analysis_hour=12,
        analysis_timezone="+08:00",
        calculation_mode="month",
        month_profile="key_month_tianzheng_jie_v1",
        use_true_solar_time=False,
    )


def audit(corpus: Path = CORPUS) -> dict[str, Any]:
    manifest_path = corpus / "manifest.json"
    m = json.loads(manifest_path.read_text())
    if {r["file"] for r in m["source_files"]} != {
        "key-page36.jpg",
        "key-page37.jpg",
        "key-page38.jpg",
        "sino-western-printed313.jpg",
        "month-worked.json",
    }:
        raise ValueError("完整月段及矛盾门段、历表不得删除")
    if {r["file"] for r in m["prior_source_references"]} != {
        "../taiyi_jinjing_v5/worked-cases.json",
        "../taiyi_jinjing_v5/manifest.json",
        "../taiyi_jinjing_v9/annual-ten-essences.json",
        "../taiyi_jinjing_v9/manifest.json",
    }:
        raise ValueError("原V5四课例与V9祖数来源必须保留")
    for item in (
        m["source_files"] + m["prior_source_references"] + [m["source_reference"]]
    ):
        if (
            hashlib.sha256((corpus / item["file"]).read_bytes()).hexdigest()
            != item["sha256"]
        ):
            raise ValueError("月计冻结指纹不符：" + item["file"])
    case = json.loads((corpus / "month-worked.json").read_text())
    observations = case["observations"]
    if (
        len(observations) != 29
        or {r["id"] for r in observations} != IDS
        or m["observation_count"] != 29
        or case["input"] != {"year": 1561, "nominal_month": 9}
    ):
        raise ValueError("29要求含5处门段差异和缺局数，不得改输入或择优删除")
    result = public_case()
    b = result["taiyi"]
    matches, differences, unknown = [], [], []
    for row in observations:
        actual: Any = b
        for part in row["result_path"].split("."):
            actual = actual[part]
        record = {**row, "computed_value": actual}
        if actual is None or row["expected"] is None:
            unknown.append(record)
        elif actual == row["expected"]:
            matches.append(record)
        else:
            differences.append(record)
    data = json.loads((corpus / m["source_reference"]["file"]).read_text())
    dates = []
    for key in ("month_start", "next_month_start"):
        row = data["calendar"][key]
        y, month, day = map(int, row["julian"].split("-"))
        greg = julian_to_proleptic_gregorian(y, month, day)
        gz = get_day_ganzhi(greg.year, greg.month, greg.day)
        dates.append(
            {
                "id": key,
                **row,
                "computed_gregorian": greg.isoformat(),
                "computed_ganzhi": gz,
                "matches": greg.isoformat() == row["gregorian"]
                and gz == row["day_ganzhi"]
                and SEXAGENARY_INDEX[gz] == row["cycle_index"]
                and greg.weekday() == row["weekday_monday_zero"],
            }
        )
    later = public_case(day=10, month=11)["taiyi"]["calendar_rules"]["month_origin"][
        "calendar_reference"
    ]
    arithmetic = case["source_gate_arithmetic"]
    prior = prior_audit(corpus.parent / "taiyi_jinjing_v5")
    return {
        "completion_claim": False,
        "corpus_manifest_sha256": hashlib.sha256(
            manifest_path.read_bytes()
        ).hexdigest(),
        "required_observations": 29,
        "evaluated_observations": 29 - len(unknown),
        "matching_observations": len(matches),
        "disagreements": differences,
        "unadjudicated": unknown,
        "source_example_acceptance_passed": not differences and not unknown,
        "full_accumulation": b["core_board"]["accumulation"],
        "source_shortcut_count": b["calendar_rules"]["month_origin"]["shortcut_count"],
        "calendar_month_start_observations": dates,
        "selected_calendar_facts_passed": all(r["matches"] for r in dates),
        "modern_jie_is_not_original_lunar_month": later,
        "source_gate_arithmetic_diagnostic": {
            "printed_input": arithmetic["printed_input"],
            "printed_subtracted": arithmetic["printed_subtracted"],
            "computed_remainder": arithmetic["printed_input"]
            - arithmetic["printed_subtracted"],
            "printed_remainder": arithmetic["printed_remainder"],
            "equal": arithmetic["printed_input"] - arithmetic["printed_subtracted"]
            == arithmetic["printed_remainder"],
        },
        "prior_gate_audit": prior,
        "count_policy": "V5四课例32字段与本月段29要求、两个月首事实分别报告，不合并抬高匹配率；年月日界现代适配不冒认全古历，重复课式不作新案例。",
        "whole_book_conformance": "not_established",
        "full_ancient_calendar_reconstructed": False,
        "real_world_efficacy": "not_tested",
    }

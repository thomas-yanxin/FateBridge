"""Original external layout fields; symbolic inputs do not certify civil dates."""

import gzip
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.core.metaphysics.liureng import build_liureng_board, twelve_god_layout
from fatebridge.core.metaphysics.liureng_auxiliary_stars import build_auxiliary_stars
from fatebridge.core.metaphysics.liureng_course_layout import BASIS
from fatebridge.core.metaphysics.ren_evidence import xun_dun_stems
from fatebridge.core.metaphysics.ren_sources import JINGWEI_SCAN_SHA256, JINGWEI_SOURCE
from fatebridge.utils.civil_time import NominalClockLabel

REFERENCE = json.loads(
    gzip.decompress(
        (
            Path(__file__).parents[1] / "fixtures/liureng-layout-reference-v1.json.gz"
        ).read_bytes()
    )
)


def test_original_provider_identity_and_distinct_input_denominators() -> None:
    rows = REFERENCE["layouts"]
    assert len(rows) == 4320
    assert (
        len(
            {
                (r["day"], r["general"], r["hour"], r["is_diurnal"], r["profile"])
                for r in rows
            }
        )
        == 4320
    )
    assert sum(r["provider"] == "daliuren" for r in rows) == 2880
    assert sum(r["provider"] == "kinliuren" for r in rows) == 1440
    assert len(REFERENCE["xun_days"]) == 60
    assert sum(len(row["stems"]) for row in REFERENCE["xun_days"]) == 720
    assert len(REFERENCE["day_horses"]) == 12
    assert REFERENCE["sources"]["daliuren_commit"] == (
        "2afe9194e3644d2ead5652ed8b366ae6c70d7087"
    )
    assert REFERENCE["sources"]["kinliuren_commit"] == (
        "557a9ad3ced7b0551b4e623a63dc74536a190a7e"
    )


def test_complete_layout_matches_the_selected_original_external_program() -> None:
    for case in REFERENCE["layouts"]:
        assert (
            twelve_god_layout(
                hour_branch=case["hour"],
                month_general_branch=case["general"],
                day_stem=case["day"][0],
                is_diurnal=case["is_diurnal"],
                guiren_profile=case["profile"],
            )
            == case["expected"]
        ), case


def test_all_day_identities_keep_original_actual_and_empty_xun_stems() -> None:
    for case in REFERENCE["xun_days"]:
        actual = xun_dun_stems(case["day"])
        assert len(actual) == 10, case["day"]
        assert {branch: actual.get(branch) for branch in case["stems"]} == case[
            "stems"
        ], case["day"]


def test_auxiliary_day_horse_uses_the_original_day_branch_anchor() -> None:
    for case in REFERENCE["day_horses"]:
        layout = twelve_god_layout(
            hour_branch="子",
            month_general_branch="子",
            day_stem=case["day"][0],
            is_diurnal=False,
        )
        result = build_auxiliary_stars(
            day_ganzhi=case["day"],
            month_branch="寅",
            sky_by_earth=layout["sky_by_earth"],
            god_by_sky=layout["god_by_sky"],
            lessons=[
                {"index": i, "upper_branch": branch}
                for i, branch in enumerate("子丑寅卯", 1)
            ],
            transmissions=list("子辰申"),
        )
        assert (
            next(row for row in result["stars"] if row["id"] == "day_horse")["branch"]
            == case["branch"]
        ), case


@pytest.mark.parametrize("profile", ["liuren_common_v1", "tanyuan_xieji_v1"])
def test_actual_noble_trace_identifies_the_selected_source_without_changing_profile(
    profile: str,
) -> None:
    instant = datetime(2026, 1, 1, 12, tzinfo=timezone(timedelta(hours=8)))
    seed = MetaphysicsSeed(
        input_datetime=instant,
        clock=NominalClockLabel.from_local_datetime(instant),
        timezone="Asia/Shanghai",
        longitude=None,
        applied_true_solar=False,
        total_correction_minutes=0,
        pillars={
            "year": ("丙", "午"),
            "month": ("庚", "寅"),
            "day": ("甲", "子"),
            "hour": ("庚", "午"),
        },
        calendar_context={"current_solar_term": {"name": "冬至"}},
        input_offset_visible=False,
    )
    board = build_liureng_board(
        seed,
        month_general_override="子",
        is_diurnal_override=True,
        guiren_profile=profile,
    )
    trace = next(
        t for t in board["rule_trace"] if t["rule_id"] == "liuren.guiren_start"
    )
    assert trace["result"]["profile"] == profile
    assert trace["result"]["is_diurnal"] is True
    assert board["ruleset"]["version"] == "1.16.1"
    if profile == "liuren_common_v1":
        assert trace["source_url"] == REFERENCE["common_primary"]["source_url"]
        assert "PDF10–11" in trace["source_section"]
        assert trace["result"]["start_branch"] == "丑"
        assert JINGWEI_SOURCE in board["ruleset"]["source_urls"]
    else:
        assert trace["source_url"] != JINGWEI_SOURCE
        assert trace["result"]["start_branch"] == "未"
        assert JINGWEI_SOURCE not in board["ruleset"]["source_urls"]


def test_primary_source_identity_matches_the_retained_existing_witness() -> None:
    primary = REFERENCE["common_primary"]
    assert JINGWEI_SOURCE == primary["source_url"]
    assert JINGWEI_SCAN_SHA256 == primary["source_sha256"]
    witness = next(w for w in BASIS["witnesses"] if w["id"] == "gugong_gugong-419")
    assert witness["source_url"] == primary["source_url"]
    assert witness["source_sha256"] == primary["source_sha256"]

"""Liuyao oracle tests: 伏神 (base-only), 卦身, 暗动/日破, 神煞, 进退神, 多爻取用, and payload budget."""

from __future__ import annotations

import json
import time

import pytest

from fatebridge.core.liuyao.najia import compute_shensha
from fatebridge.core.liuyao.strength import (
    ADVANCES,
    branch_facts,
    classify_day_clash,
    month_strength,
)
from fatebridge.services.divination import calculate_sixyao_analysis
from tests.support.transports import SPECS, business


@pytest.mark.parametrize(
    ("base_code", "changed_code", "expected_hidden"),
    [
        # 100000 地雷复(坤宫缺父母) -> 100100 震为雷(4爻动变午火父母): 父母巳火伏神不被变爻掩盖
        ("100000", "100100", [("父母", "巳", True, [4])]),
        # 000001 山地剥(乾宫缺兄弟) -> 000101 火地晋(4爻动变酉金兄弟): 兄弟申金伏神不被变爻掩盖
        ("000001", "000101", [("兄弟", "申", True, [4])]),
        # 111011 风天小畜(巽宫缺官鬼) -> 101011 风火家人
        ("111011", "101011", [("官鬼", "酉", False, [])]),
        # 111111 乾为天(五亲俱全) -> 111011 风天小畜
        ("111111", "111011", []),
    ],
)
def test_hidden_spirits_depend_strictly_on_base_hexagram(
    base_code: str,
    changed_code: str,
    expected_hidden: list[tuple[str, str, bool, list[int]]],
) -> None:
    res = calculate_sixyao_analysis(
        date="2024-05-20",
        time="14:30",
        timezone="Asia/Shanghai",
        gua_code=base_code,
        changed_code=changed_code,
    )
    assert "conditional_analysis" not in res["liuyao_evidence"]
    actual = [
        (
            h["liuqin"],
            h["branch"],
            h["present_in_changed"],
            h["changed_positions"],
        )
        for h in res["liuyao_evidence"]["hidden_spirits"]
    ]
    assert actual == expected_hidden


@pytest.mark.parametrize(
    ("gua_code", "expected_branch", "expected_yin_yang", "expected_positions"),
    [
        ("111111", "巳", "阳", []),  # 乾为天 世6阳 -> 子起数至6=巳
        ("000000", "亥", "阴", [5]),  # 坤为地 世6阴 -> 午起数至6=亥
        ("010000", "申", "阴", []),  # 地水师 世3阴 -> 午起数至3=申
        ("111011", "子", "阳", [1]),  # 风天小畜 世1阳 -> 子起数至1=子(临初爻)
    ],
)
def test_gua_shen_calculation(
    gua_code: str,
    expected_branch: str,
    expected_yin_yang: str,
    expected_positions: list[int],
) -> None:
    res = calculate_sixyao_analysis(
        date="2024-05-20",
        time="14:30",
        timezone="Asia/Shanghai",
        gua_code=gua_code,
        changed_code=gua_code,
    )
    gs = res["hexagram_info"]["gua_shen"]
    assert gs["branch"] == expected_branch
    assert gs["shi_yin_yang"] == expected_yin_yang
    assert gs["present_positions"] == expected_positions


def test_dark_moving_vs_day_broken_flags() -> None:
    # 卯木 static line in 卯月, 酉日冲: 临月建旺相 -> 暗动
    facts = branch_facts("卯", "卯", "酉", ["戌", "亥"])
    monthly = month_strength("卯", "卯")
    dark = classify_day_clash(
        branch="卯", is_moving=False, month="卯", day="酉", facts=facts, monthly=monthly
    )
    assert dark["is_dark_moving"] is True
    assert dark["is_day_broken"] is False
    assert dark["day_clash_status"] == "dark_moving"

    # 卯木 static line in 申月(休囚), 酉日冲: 休囚无气 -> 日破
    monthly_weak = month_strength("卯", "申")
    broken = classify_day_clash(
        branch="卯",
        is_moving=False,
        month="申",
        day="酉",
        facts=facts,
        monthly=monthly_weak,
    )
    assert broken["is_dark_moving"] is False
    assert broken["is_day_broken"] is True
    assert broken["day_clash_status"] == "day_broken"

    # Moving line with day clash -> moving_line_clashed
    moving = classify_day_clash(
        branch="卯",
        is_moving=True,
        month="申",
        day="酉",
        facts=facts,
        monthly=monthly_weak,
    )
    assert moving["day_clash_status"] == "moving_line_clashed"
    assert moving["is_dark_moving"] is False
    assert moving["is_day_broken"] is False


def test_shensha_table_all_nine_stars() -> None:
    lines = [
        {"position": 1, "branch": "子"},
        {"position": 2, "branch": "寅"},
        {"position": 3, "branch": "辰"},
        {"position": 4, "branch": "巳"},
        {"position": 5, "branch": "未"},
        {"position": 6, "branch": "酉"},
    ]
    table, per_line = compute_shensha(day_gan="甲", day_branch="子", lines=lines)
    assert table["天乙贵人"] == {"branches": ["丑", "未"], "positions": [5]}
    assert table["驿马"] == {"branches": ["寅"], "positions": [2]}
    assert table["桃花"] == {"branches": ["酉"], "positions": [6]}
    assert table["禄神"] == {"branches": ["寅"], "positions": [2]}
    assert table["羊刃"] == {"branches": ["卯"], "positions": []}
    assert table["将星"] == {"branches": ["子"], "positions": [1]}
    assert table["劫煞"] == {"branches": ["巳"], "positions": [4]}
    assert table["谋星"] == {"branches": ["戌"], "positions": []}
    assert table["华盖"] == {"branches": ["辰"], "positions": [3]}
    assert set(per_line[2]) == {"驿马", "禄神"}


def test_advance_and_retreat_pairs() -> None:
    assert ADVANCES == {
        "亥": "子",
        "寅": "卯",
        "巳": "午",
        "申": "酉",
        "丑": "辰",
        "辰": "未",
        "未": "戌",
    }
    # 000000 坤 -> 100000 地雷复: line 1 坤下未 -> 震下子 (not advance),
    # 111011 风天小畜 (line 4 未) -> 111001? Let's test 110110 兑 (line 2 卯) -> 100110 震 (line 2 寅) = 退神!
    res = calculate_sixyao_analysis(
        date="2024-05-20",
        time="14:30",
        timezone="Asia/Shanghai",
        gua_code="110110",
        changed_code="100110",
    )
    trans = res["liuyao_evidence"]["lines"][1]["transformation"]
    assert trans["branch"] == "寅"
    assert trans["retreat"] is True
    assert trans["advance"] is False


@pytest.mark.parametrize(
    ("base", "changed", "expected_mode"),
    [
        ("111111", "111111", "static"),
        ("111111", "011111", "single_moving"),
        ("111111", "001111", "two_moving"),
        ("111111", "000111", "three_moving"),
        ("111111", "000011", "four_moving"),
        ("111111", "000001", "five_moving"),
        ("111111", "000000", "all_moving"),
    ],
)
def test_moving_focus_guidance_modes(
    base: str, changed: str, expected_mode: str
) -> None:
    res = calculate_sixyao_analysis(
        date="2024-05-20",
        time="14:30",
        timezone="Asia/Shanghai",
        gua_code=base,
        changed_code=changed,
    )
    assert res["liuyao_evidence"]["moving_focus_guidance"]["mode"] == expected_mode


def test_liuyao_audit_payload_budget_and_transports(surface_calls) -> None:
    payload = {
        "date": "2024-05-20",
        "time": "14:30:00",
        "timezone": "Asia/Shanghai",
        "gua_code": "100000",
        "changed_code": "100100",
    }
    # Warm call budget
    calculate_sixyao_analysis(**payload)
    t0 = time.perf_counter()
    res = calculate_sixyao_analysis(**payload)
    dt_ms = (time.perf_counter() - t0) * 1000
    size_bytes = len(json.dumps(res, ensure_ascii=False).encode("utf-8"))
    assert size_bytes < 25_000
    assert dt_ms < 15.0

    fields = [
        "hexagram_info.gua_shen",
        "liuyao_evidence.hidden_spirits",
        "liuyao_evidence.shensha",
        "liuyao_evidence.moving_focus_guidance",
    ]
    controls = {"fields": fields}
    http, mcp, code, cli = surface_calls(
        SPECS["liuyao"],
        payload,
        params=controls,
        options=controls,
        flags=("--fields", *fields),
    )
    assert http.status_code == 200 and code == 0 and not mcp.is_error
    assert business(http.json()) == business(cli) == business(mcp.structured_content)


def test_liuyao_retires_conditional_analysis_and_event_horizon() -> None:
    from pydantic import ValidationError

    from fatebridge.core.contracts.output_divination import LiuyaoEvidence
    from fatebridge.core.requests.divination import SixYaoRequest

    retired_evidence_fields = {
        "conditional_analysis",
        "source_kind",
        "conformance_scope",
        "source_revisions",
        "textual_corrections",
        "pattern_detection_scope",
        "pending_judgments",
    }
    assert retired_evidence_fields.isdisjoint(LiuyaoEvidence.model_fields)
    assert "event_horizon" not in SixYaoRequest.model_fields

    with pytest.raises(ValidationError):
        SixYaoRequest(
            date="2024-05-20",
            time="14:30:00",
            event_horizon="near",
        )

    res = calculate_sixyao_analysis(
        date="2024-05-20",
        time="14:30:00",
        timezone="Asia/Shanghai",
        gua_code="100000",
        changed_code="100100",
    )
    assert "event_horizon" not in res["analysis_context"]
    assert retired_evidence_fields.isdisjoint(res["liuyao_evidence"])


def test_liuyao_focus_errors_expose_exact_paths_and_constraints() -> None:
    from pydantic import ValidationError

    from fatebridge.core.liuyao.evidence import resolve_focus
    from fatebridge.core.requests.divination import SixYaoRequest
    from fatebridge.utils.errors import ParameterError, validation_error_result

    base = {"date": "2024-05-20", "time": "14:30:00", "timezone": "Asia/Shanghai"}
    cases = [
        ({**base, "lines": [{"value": 1}]}, "lines", "invalid_lines_count"),
        (
            {**base, "focus_kind": "day", "focus_line": 2},
            "focus_line",
            "conflicting_focus_line",
        ),
        ({**base, "focus_kind": "visible"}, "focus_kind", "missing_focus_target"),
        ({**base, "timing_days": 5}, "timing_days", "missing_focus_for_timing"),
    ]
    for payload, expected_path, expected_code in cases:
        with pytest.raises(ValidationError) as exc_info:
            SixYaoRequest.model_validate(payload)
        envelope = validation_error_result(exc_info.value)
        assert envelope["issues"][0]["path"] == expected_path
        assert envelope["issues"][0]["code"] == expected_code

    # calculate_sixyao_analysis returns the ParameterError envelope from resolve_focus
    static_changed = calculate_sixyao_analysis(
        date="2024-05-20",
        time="14:30",
        timezone="Asia/Shanghai",
        gua_code="100000",
        changed_code="100100",
        focus_kind="changed",
        focus_line=1,
    )
    assert static_changed["error_code"] == "validation_error"
    assert static_changed["issues"] == [
        {
            "path": "focus_line",
            "code": "focus_line_not_available",
            "constraints": {"available": [4]},
        }
    ]

    mismatch = calculate_sixyao_analysis(
        date="2024-05-20",
        time="14:30",
        timezone="Asia/Shanghai",
        gua_code="100000",
        changed_code="100100",
        focus_line=1,
        focus_kinship="官鬼",
    )
    assert mismatch["error_code"] == "validation_error"
    assert mismatch["issues"] == [
        {
            "path": "focus_kinship",
            "code": "focus_kinship_mismatch",
            "constraints": {"expected": "妻财"},
        }
    ]

    with pytest.raises(ParameterError) as bad_kind:
        resolve_focus(
            focus_line=None,
            focus_kinship=None,
            lines=[],
            hidden=[],
            palace="坤",
            month="巳",
            day="甲子",
            focus_kind="bogus",
        )
    assert bad_kind.value.issues[0]["path"] == "focus_kind"
    assert "visible" in bad_kind.value.issues[0]["constraints"]["allowed"]

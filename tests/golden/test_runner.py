"""runner 的覆盖与确定性测试。"""

import json
from datetime import timedelta

import pytest

from fatebridge.core.export_contracts import get_technique_info
from tests.fixtures.surface_payloads import REST_POST_CASES
from tests.golden.runner import (
    _MCP_ONLY_CASES,
    FROZEN_NOW,
    SNAPSHOT_DIR,
    compute_outputs,
    golden_diff_active,
    golden_diff_skip_reason,
)


def test_runner_covers_every_rest_tool():
    outputs = compute_outputs()
    # REST 工具 + MCP-only 工具都要产出一份规范化文本。
    expected_count = len(REST_POST_CASES) + len(_MCP_ONLY_CASES)
    assert len(outputs) == expected_count
    assert all(isinstance(text, str) and text for text in outputs.values())


def test_outputs_are_deterministic():
    # 进程内连跑两次必须逐字节相同——抓「同一进程内的可变状态泄漏」。
    # 跨机器 / 跨次运行的可复现性，由 canonical 层剔除易变字段保证，并最终由
    # test_golden_master 对committed 基线的 diff 来兜底。
    assert compute_outputs() == compute_outputs()


@pytest.mark.skipif(not golden_diff_active(), reason=golden_diff_skip_reason())
def test_outputs_stable_across_simulated_clock_change():
    """时钟冻结有效性回归测试：拨动冻结时刻，时钟敏感工具的 FROZEN_NOW 输出必须与快照吻合。

    验证步骤：
    1. compute_outputs(frozen=FROZEN_NOW) 与快照文件逐字节一致。
       → 确认快照是在当前 FROZEN_NOW 下生成的，且 freeze_clock 在生成时有效。
    2. compute_outputs(frozen=FROZEN_NOW + 400d) 与快照不同。
       → 证明冻结时刻确实驱动了日历字段（如「当下节气」「分析日期」），
         换言之 freeze_clock 真的控制了工具行为，而非工具忽视了时钟。

    不受此测试约束的工具（如 mcp_analyze_destiny）：仅依赖出生日期，本就不消费
    now() 回退路径，输出与冻结时刻无关，无需列入时钟敏感工具集合。
    时钟敏感工具若有新增，在 CLOCK_SENSITIVE_SLUGS 补充对应 slug 即可。
    """
    # 真正调用 now() 回退路径的工具（payload 不含 analysis_*）
    CLOCK_SENSITIVE_SLUGS = {"api_cn_bazi_birth"}

    missing = sorted(
        slug
        for slug in CLOCK_SENSITIVE_SLUGS
        if not (SNAPSHOT_DIR / f"{slug}.json").exists()
    )
    assert not missing, f"缺少时钟敏感工具的必需快照：{missing}"

    baseline = compute_outputs(frozen=FROZEN_NOW)
    advanced = compute_outputs(frozen=FROZEN_NOW + timedelta(days=400))

    for slug in CLOCK_SENSITIVE_SLUGS:
        snapshot_text = (
            (SNAPSHOT_DIR / f"{slug}.json").read_text(encoding="utf-8").rstrip("\n")
        )

        # 1. 基线（FROZEN_NOW）必须与快照吻合。
        assert baseline[slug] == snapshot_text, (
            f"{slug}（FROZEN_NOW）输出与快照不符；"
            "freeze_clock() 可能未覆盖该工具的 now() 路径，或快照未在 FROZEN_NOW 下生成。"
            "请检查 freeze_clock 的实际时钟入口，并用 python -m tests.golden.runner 重新冻结基线。"
        )

        # 2. 拨 400 天后输出必须与快照不同，证明冻结时刻有效驱动了日历字段。
        assert advanced[slug] != snapshot_text, (
            f"{slug}（FROZEN_NOW+400d）输出与 FROZEN_NOW 快照相同；"
            "该工具可能并不消费 now() 回退路径，无需列入时钟敏感工具列表，"
            "或 freeze_clock 完全隔离了时钟以致两种冻结值产出相同内容（不应发生）。"
        )


def _embedded_export_techniques(value, path="$"):
    if isinstance(value, dict):
        if {"key", "preset_sections", "settings_template"} <= value.keys():
            yield path, value
        for key, child in value.items():
            yield from _embedded_export_techniques(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _embedded_export_techniques(child, f"{path}[{index}]")


@pytest.mark.parametrize(
    "snapshot", sorted(SNAPSHOT_DIR.glob("*.json")), ids=lambda path: path.stem
)
def test_frozen_export_registry_metadata_matches_current_contract(snapshot):
    """Shared export metadata must migrate in every nested frozen payload.

    This check is independent of astronomy, operating system and Python version;
    it prevents stale copies from surviving where numerical golden checks skip.
    """
    payload = json.loads(snapshot.read_text(encoding="utf-8"))
    for path, technique in _embedded_export_techniques(payload):
        current = get_technique_info(technique["key"])
        assert current is not None, f"{snapshot.name}:{path}: unregistered technique"
        assert technique == current, f"{snapshot.name}:{path}: stale export contract"

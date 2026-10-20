"""Golden-master runner：用固定输入驱动每个工具，产出 ``{slug: canonical_json}``。

只走 REST 一个面即可覆盖全部工具——三端共享同一 catalog 与 service 层，REST
响应是最完整的结构化输出。健康端点（/health、/ready、/metrics）含非确定计数，
不在冻结范围。冻结基线时强制 Moshier 星历模式，与 CI 对齐。

还包含 MCP-only 工具（无 rest_path）的黄金覆盖，目前仅 analyze_destiny
通过其 MCP 面驱动，slug 为 ``mcp_analyze_destiny``。
"""

from __future__ import annotations

import json
import os
import platform
import sys
from contextlib import contextmanager
from datetime import datetime as _RealDatetime
from datetime import timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, Generator
from unittest.mock import patch

from fastapi.testclient import TestClient

import fatebridge.api as api_module
from tests.fixtures.surface_payloads import MCP_CASES, REST_POST_CASES
from tests.golden.canonical import canonical_json

#: 冻结基线的存放目录。
SNAPSHOT_DIR = Path(__file__).resolve().parent / "snapshots"

# ---------------------------------------------------------------------------
# 参考环境锚定（平台 + Python 版本）
# ---------------------------------------------------------------------------
# 字节级基线对「环境」敏感，两层原因：
# 1. 平台：星历（pyswisseph / kerykeion 的 Moshier 模型）走 C/libm，浮点结果随
#    CPU 架构与 libm 实现而微变（实测 macOS arm64 与 Linux x86_64 月亮经度差
#    约 0.01°，且渲染进 snapshot_text 字符串，浮点 round 够不着）。
# 2. Python 版本和依赖版本：其数值实现与序列化差异仍可能影响字节级输出。
#    五行百分比的残差补偿已使用量化规则，另有跨版本确定性回归。
# 故基线统一在「参考环境」冻结，字节比对也只在该环境生效；其它环境（本地 macOS、
# 非参考 py 版本）跳过比对，改用「同环境 regen 前后 diff」验证重构零漂移。
BASELINE_PLATFORM = "Linux-x86_64"
BASELINE_PYTHON = "3.12"


def current_platform() -> str:
    """当前平台标识，如 ``Linux-x86_64`` / ``Darwin-arm64``。"""
    return f"{platform.system()}-{platform.machine()}"


def current_python() -> str:
    """当前 Python 版本，如 ``3.12``。"""
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def is_baseline_platform() -> bool:
    """当前是否为基线冻结平台。"""
    return current_platform() == BASELINE_PLATFORM


def is_baseline_environment() -> bool:
    """当前是否为基线参考环境（平台 + Python 版本都吻合）。"""
    return is_baseline_platform() and current_python() == BASELINE_PYTHON


#: floor 作业用最低依赖版本（见 ci.yml），星历输出与「最新版」基线不同口径，
#: 故由它设此环境变量显式关闭字节比对——floor 只为守 API 下限，不做数值锁。
_SKIP_DIFF_ENV = "FATEBRIDGE_SKIP_GOLDEN_DIFF"


def golden_diff_active() -> bool:
    """golden 字节比对是否生效：须在基线参考环境、且未被显式关闭（如 floor 作业）。"""
    if os.getenv(_SKIP_DIFF_ENV):
        return False
    return is_baseline_environment()


def golden_diff_skip_reason() -> str:
    """字节比对被跳过的原因（供 skipif 展示）。"""
    if os.getenv(_SKIP_DIFF_ENV):
        return f"{_SKIP_DIFF_ENV} 已设：当前依赖非基线口径（如 floor 最低版本），跳过字节比对"
    return (
        f"golden 基线锁定参考环境 {BASELINE_PLATFORM} / Python {BASELINE_PYTHON}；"
        f"当前 {current_platform()} / Python {current_python()}，"
        "星历浮点与派生量跨环境微差，字节比对仅在参考环境进行"
    )


# ---------------------------------------------------------------------------
# 时钟冻结
# ---------------------------------------------------------------------------
# 凡是不提供 analysis_* 日期的 payload（如 /api/cn/bazi/birth）
# 都会在服务层落到 datetime.now() 回退路径，导致基线随日历漂移。
# 在 compute_outputs() 期间把所有工具模块里的 datetime 替换成此固定子类，
# 使 now()/today() 永远返回同一瞬间，无需任何三方库。
#
# 日期选 2026-01-01T12:00:00：处于历法「平稳期」，远离节气边界，方便人工核查。
FROZEN_NOW = _RealDatetime(2026, 1, 1, 12, 0, 0)

# 所有通过 ``from datetime import datetime`` 引入、且在输出路径上调用
# now()/today() 的模块。新增工具若在输出路径用了 datetime.now()，须在此补记。
_DATETIME_PATCH_TARGETS = [
    # 默认"当前时刻"现集中在 almanac.current_local_datetime()，其内部的
    # datetime.now(tz) 是真正落地的 now() 调用点，必须冻结。
    "fatebridge.core.almanac.datetime",
    "fatebridge.services.bazi.datetime",
    "fatebridge.services.timing.datetime",
    "fatebridge.analysis.timing_effects.datetime",
    "fatebridge.utils.birth_input.datetime",
    "fatebridge.core.timing.datetime",
    "fatebridge.core.predictive._common.datetime",
]

# analyze_destiny 是唯一没有 rest_path 的独立工具，通过 MCP 面覆盖。
# key → slug 前缀，value → MCP_CASES 里对应的 key。
_MCP_ONLY_CASES: Dict[str, str] = {
    "mcp_analyze_destiny": "analyze_destiny",
}


def _make_frozen_datetime(frozen: _RealDatetime) -> type:
    """返回一个 datetime 子类，其 now()/today() 固定返回 ``frozen``。"""

    class FrozenDatetime(_RealDatetime):
        # now() 可带 tz 参数；忽略时区仅返回裸 naive datetime，与 bazi.py 保持一致。
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            if tz is not None:
                # 服务层偶尔传 tz（astrology_predictive）；返回 aware 固定值。
                return _RealDatetime(
                    frozen.year,
                    frozen.month,
                    frozen.day,
                    frozen.hour,
                    frozen.minute,
                    frozen.second,
                    tzinfo=tz,
                )
            return frozen

        @classmethod
        def today(cls):  # type: ignore[override]
            return frozen

    FrozenDatetime.__name__ = "FrozenDatetime"
    FrozenDatetime.__qualname__ = "FrozenDatetime"
    return FrozenDatetime


@contextmanager
def freeze_clock(frozen: _RealDatetime = FROZEN_NOW) -> Generator[None, None, None]:
    """上下文管理器：在所有工具模块里把 datetime 冻结到 ``frozen``。

    只替换模块属性，不影响其他 stdlib 使用者；退出时自动恢复。
    """
    frozen_cls = _make_frozen_datetime(frozen)
    patches = [patch(target, frozen_cls) for target in _DATETIME_PATCH_TARGETS]

    # Preserve this historical fixture's fixed local wall clock in every zone.
    # Production instead uses one UTC instant per execution; replay/isolation
    # tests validate that contract independently. Golden metadata is stripped.
    def frozen_current_datetime(zone, timezone_name=None, **kwargs):
        return frozen_cls.now(zone)

    patches.extend(
        [
            patch("fatebridge.core.almanac.current_datetime", frozen_current_datetime),
            patch(
                "fatebridge.core.predictive._common.current_datetime",
                frozen_current_datetime,
            ),
        ]
    )
    # The shared registrar now creates a per-call UTC clock. The fixture epoch
    # is Shanghai civil noon, so freeze that clock to the same *instant*, rather
    # than letting receipt timestamps drive current-time business calculations.
    from fatebridge.utils.timezones import parse_timezone_name

    utc_frozen = frozen.replace(tzinfo=parse_timezone_name("Asia/Shanghai")).astimezone(
        timezone.utc
    )
    patches.append(
        patch(
            "fatebridge.core.execution_context.datetime",
            _make_frozen_datetime(utc_frozen.replace(tzinfo=None)),
        )
    )
    for p in patches:
        p.start()
    try:
        yield
    finally:
        for p in patches:
            p.stop()


def _slug(path: str) -> str:
    """把 REST 路径压成稳定文件名，如 /api/cn/bazi/birth → api_cn_bazi_birth。"""
    return path.strip("/").replace("/", "_")


def _clear_ephemeris_dependent_caches() -> None:
    """Discard solar-term facts and derived caches when switching test models."""
    from fatebridge.core.almanac import get_solar_terms_for_year
    from fatebridge.core.calendar import BaZiCalendar
    from fatebridge.core.metaphysics.qimen import (
        _qimen_build_year_term_seed,
        _qimen_build_yinyangdun_map,
    )
    from fatebridge.core.timing import _calculate_liuyue_cached

    for cached in (
        get_solar_terms_for_year,
        BaZiCalendar._get_four_pillars_cached,
        _calculate_liuyue_cached,
        _qimen_build_year_term_seed,
        _qimen_build_yinyangdun_map,
    ):
        cached.cache_clear()


@contextmanager
def golden_ephemeris() -> Generator[None, None, None]:
    """Force Moshier despite repo-local data, restoring shared state on exit."""
    from fatebridge.core import ephemeris_runtime as runtime

    with TemporaryDirectory(prefix="fatebridge-golden-") as empty_directory:
        with runtime._EPHEMERIS_LOCK:
            previous_env = os.environ.get("SE_EPHE_PATH")
            previous_path = runtime.configured_ephemeris_path()
        try:
            with runtime._EPHEMERIS_LOCK:
                os.environ["SE_EPHE_PATH"] = empty_directory
                runtime.configure_ephemeris_path(empty_directory)
                _clear_ephemeris_dependent_caches()
            # REST workers also acquire this lock; never hold it across requests.
            yield
        finally:
            with runtime._EPHEMERIS_LOCK:
                if previous_env is None:
                    os.environ.pop("SE_EPHE_PATH", None)
                else:
                    os.environ["SE_EPHE_PATH"] = previous_env
                try:
                    if runtime.swe is not None:
                        runtime.swe.set_ephe_path(previous_path or "")
                finally:
                    runtime._configured_path = previous_path
                    _clear_ephemeris_dependent_caches()


def compute_outputs(frozen: _RealDatetime = FROZEN_NOW) -> Dict[str, str]:
    """跑遍全部 REST 工具 case 及 MCP-only case，返回 {slug: 规范化 JSON}。

    时钟冻结到 ``frozen``，使所有 now() 回退路径产出确定性输出。
    """
    outputs: Dict[str, str] = {}

    with golden_ephemeris(), freeze_clock(frozen):
        # --- REST 面 ---
        client = TestClient(api_module.app)
        for path, build_payload in REST_POST_CASES.items():
            response = client.post(path, json=build_payload())
            # 非 200 会把错误体当成「黄金真相」冻进基线，掩盖真正的回归——当场拦下。
            assert (
                response.status_code == 200
            ), f"{path} 返回 {response.status_code}：{response.text}"
            outputs[_slug(path)] = canonical_json(response.json())

        # --- MCP-only 面 ---
        from tests.fixtures.transports import mcp_text

        for slug, mcp_key in _MCP_ONLY_CASES.items():
            tool_name, payload_fn = MCP_CASES[mcp_key]
            raw_text = mcp_text(tool_name, **payload_fn())
            outputs[slug] = canonical_json(json.loads(raw_text))

    return outputs


def freeze_baseline() -> int:
    """把当前输出写进 snapshots/。仅在「经确认的输出变更」时调用。返回写入文件数。"""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    outputs = compute_outputs()
    for slug, text in outputs.items():
        (SNAPSHOT_DIR / f"{slug}.json").write_text(text + "\n", encoding="utf-8")
    return len(outputs)


if __name__ == "__main__":  # `python -m tests.golden.runner` 重新生成基线
    count = freeze_baseline()
    print(f"冻结 {count} 份基线到 {SNAPSHOT_DIR}")

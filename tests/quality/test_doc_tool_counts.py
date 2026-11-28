"""核对维护中指南的计数、能力清单与验证命令，防止文档随接口变化漂移。

期望值来自实时中央目录和 CLI 支持策略。
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest

from fatebridge.api import app
from fatebridge.services.tool_catalog import CATALOG, mcp_specs, rest_specs

REPO_ROOT = Path(__file__).resolve().parents[1].parent

LIVE_REST = len(rest_specs())
LIVE_MCP = len(mcp_specs())
LIVE_FAMILIES = len({spec.family for spec in mcp_specs()})
LIVE_CATALOG = len(CATALOG)
LIVE_CLI = len(CATALOG)

# (相对路径, 人类可读标签, 抽取数字的正则, 期望的实时计数)
# 正则用 (\d+) 捕获文档当前声称的数字；期望值取自实时目录。
CHECKS = [
    ("README.md", "README REST 业务路由", r"(\d+)\s*个业务\s*REST\s*路由", LIVE_REST),
    (
        "README.en.md",
        "README.en REST routes",
        r"(\d+)\s+business\s+REST\s+routes",
        LIVE_REST,
    ),
    (
        "README.en.md",
        "README.en MCP capabilities",
        r"provide\s+access\s+to\s+\*{0,2}(\d+)\s+capabilities",
        LIVE_MCP,
    ),
    (
        "README.en.md",
        "README.en families",
        r"across\s+\*{0,2}(\d+)\s+families",
        LIVE_FAMILIES,
    ),
    (
        "README.en.md",
        "README.en catalog entries",
        r"catalog\s+contains\s+(\d+)\s+entries",
        LIVE_CATALOG,
    ),
    (
        "README.en.md",
        "README.en CLI entries",
        r"with\s+(\d+)\s+available\s+through\s+the\s+CLI",
        LIVE_CLI,
    ),
    (
        "docs/api-reference.md",
        "api-reference.md REST 业务路由",
        r"(\d+)\s*个业务\s*REST\s*路由",
        LIVE_REST,
    ),
    (
        "docs/architecture.md",
        "architecture REST 业务路由",
        r"(\d+)\s*个业务\s*REST\s*路由",
        LIVE_REST,
    ),
    (
        "README.md",
        "README family 数",
        r"(\d+)\s*个\s*family",
        LIVE_FAMILIES,
    ),
    (
        "docs/algorithm-coverage.md",
        "algorithm-coverage family 数",
        r"(\d+)\s*个\s*family",
        LIVE_FAMILIES,
    ),
]

for _path in (
    "README.md",
    "docs/api-reference.md",
    "docs/architecture.md",
    "docs/algorithm-coverage.md",
):
    CHECKS.extend(
        [
            (
                _path,
                f"{_path} catalog 数",
                r"目录(?:共有|有|含|包含)\s*(\d+)\s*条记录",
                LIVE_CATALOG,
            ),
            (
                _path,
                f"{_path} CLI 数",
                r"CLI\s*可执行(?:其中)?\s*(\d+)\s*条",
                LIVE_CLI,
            ),
            (
                _path,
                f"{_path} MCP 业务能力",
                r"MCP\s*通过(?:两个|三个)入口(?:（[^）]+）)?提供\s*\*{0,2}(\d+)\s*项业务能力",
                LIVE_MCP,
            ),
        ]
    )

CHECKS.extend(
    [
        (
            "docs/algorithm-coverage.md",
            "docs/algorithm-coverage.md REST 数",
            r"REST\s*(?:公开|暴露)\s*\*{0,2}(\d+)\s*个工具",
            LIVE_REST,
        ),
        (
            "docs/README.md",
            "docs/README.md REST 路由数",
            r"(\d+)\s*个\s*REST\s*路由",
            LIVE_REST,
        ),
        (
            "docs/README.md",
            "docs/README.md family 数",
            r"(\d+)\s*个\s*family\s*/\s*\d+\s*项计算能力清单",
            LIVE_FAMILIES,
        ),
        (
            "docs/README.md",
            "docs/README.md 能力清单数",
            r"\d+\s*个\s*family\s*/\s*(\d+)\s*项计算能力清单",
            LIVE_CATALOG,
        ),
        (
            "docs/configuration.md",
            "docs/configuration.md 全量能力数",
            r"全量\s*(\d+)\s*项能力",
            LIVE_CATALOG,
        ),
    ]
)


@pytest.mark.parametrize(
    "rel_path,label,pattern,expected", CHECKS, ids=[c[1] for c in CHECKS]
)
def test_documented_count_matches_catalog(
    rel_path: str, label: str, pattern: str, expected: int
) -> None:
    text = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
    found = re.findall(pattern, text)
    assert found, (
        f"{label}: 在 {rel_path} 未找到匹配 /{pattern}/ 的计数语句——"
        f"文档措辞可能被改动，请同步更新本测试的正则。"
    )
    documented = {int(n) for n in found}
    assert documented == {expected}, (
        f"{label}: {rel_path} 声称 {sorted(documented)}，但中央目录实时计数为 {expected}。"
        f"请把文档数字改为 {expected}（计数唯一信源是 tool_catalog 的 rest_specs()/mcp_specs()）。"
    )


def test_rest_and_mcp_counts_are_plausible() -> None:
    """守一道下限，防止目录被意外清空时上面的相等断言变得无意义。"""
    assert LIVE_REST > 0 and LIVE_MCP > 0


def test_algorithm_matrix_covers_each_published_tool_once() -> None:
    """Catch missing/repeated tool rows even when prose totals were updated."""
    text = (REPO_ROOT / "docs/algorithm-coverage.md").read_text(encoding="utf-8")
    matrix = text.split("## 2. 逐 family 工具清单", 1)[1].split(
        "## 3. 精度与依赖说明", 1
    )[0]
    documented = Counter(
        re.findall(r"^\| `([a-z][a-z0-9_]+)` \|", matrix, re.MULTILINE)
    )
    expected = Counter(spec.name for spec in mcp_specs())
    assert documented == expected, (
        f"算法矩阵缺失 {dict(expected - documented)}；"
        f"额外或重复 {dict(documented - expected)}"
    )


def test_algorithm_family_counts_match_published_tools() -> None:
    text = (REPO_ROOT / "docs/algorithm-coverage.md").read_text(encoding="utf-8")
    documented = Counter(
        {
            name: int(count)
            for name, count in re.findall(
                r"^\| `([a-z][a-z0-9_]+)` \| (\d+) \|", text, re.MULTILINE
            )
        }
    )
    assert documented == Counter(spec.family for spec in mcp_specs())


def test_api_mcp_group_list_covers_each_published_tool_once() -> None:
    text = (REPO_ROOT / "docs/api-reference.md").read_text(encoding="utf-8")
    groups = text.split("### 6.2 MCP 工具分组", 1)[1].split(
        "### 6.3 MCP 与 REST 的差异", 1
    )[0]
    names = [
        name
        for line in groups.splitlines()
        if line.startswith("- ")
        for name in re.findall(r"`([a-z][a-z0-9_]+)`", line)
    ]
    assert Counter(names) == Counter(spec.name for spec in mcp_specs())


@pytest.mark.parametrize("rel_path", ["README.md", "docs/development-guide.md"])
def test_documented_test_commands_reference_existing_files(rel_path: str) -> None:
    """Keep copyable validation commands usable after test-module removals."""
    text = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
    paths = set(re.findall(r"tests/[A-Za-z0-9_./-]+\.py", text))
    assert paths, f"{rel_path} 未列出验证测试"
    missing = sorted(path for path in paths if not (REPO_ROOT / path).is_file())
    assert not missing, f"{rel_path} 引用了不存在的测试：{missing}"


def test_api_md_documents_every_live_rest_route() -> None:
    """API 参考必须列出每一个已发布的业务与发现路由。"""
    live_routes = {
        r.path
        for r in app.routes
        if getattr(r, "include_in_schema", False)
        and getattr(r, "path", "").startswith("/api")
    }
    api_md = (REPO_ROOT / "docs/api-reference.md").read_text(encoding="utf-8")
    documented = set(re.findall(r"/api/[A-Za-z0-9_/{}-]+", api_md))
    missing = sorted(p for p in live_routes if p not in documented)
    assert (
        not missing
    ), (
        "docs/api-reference.md 漏列以下真实 REST 路由，请补到对应 §4 端点表：\n  "
        + "\n  ".join(missing)
    )


def test_maintained_docs_reflect_three_mcp_tools_and_cli_dotenv() -> None:
    """Ensure docs/README.md, configuration, getting-started, troubleshooting & CHANGELOG stay in sync."""
    readme_text = (REPO_ROOT / "docs/README.md").read_text(encoding="utf-8")
    assert "MCP 三工具面" in readme_text
    for name in ("discover_tools", "run_calculation", "run_batch"):
        assert name in readme_text, f"docs/README.md missing {name}"

    config_text = (REPO_ROOT / "docs/configuration.md").read_text(encoding="utf-8")
    assert "REST、MCP 与 CLI 启动时会读取源码仓库根目录的 `.env`" in config_text

    getting_started = (REPO_ROOT / "docs/getting-started.md").read_text(
        encoding="utf-8"
    )
    assert "CLI 不自动读取 .env" not in getting_started

    troubleshooting = (REPO_ROOT / "docs/troubleshooting.md").read_text(
        encoding="utf-8"
    )
    assert "CLI 未读取 .env" not in troubleshooting
    for name in ("discover_tools", "run_calculation", "run_batch"):
        assert name in troubleshooting, f"docs/troubleshooting.md missing {name}"

    for rel in (
        "README.md",
        "README.en.md",
        "CHANGELOG.md",
        "docs/README.md",
        "docs/architecture.md",
        "docs/configuration.md",
        "docs/troubleshooting.md",
        "docs/getting-started.md",
        "docs/agent-guide.md",
        "docs/api-reference.md",
        "docs/algorithm-coverage.md",
        "docs/development-guide.md",
    ):
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        for stale in ("两工具", "两个入口", "detail=compact", "detail=audit"):
            assert stale not in text, f"{rel} still contains stale term {stale!r}"
        stale_90 = re.findall(r"\b90\s*(?:个|项)", text)
        assert not stale_90, f"{rel} still contains stale 90 count: {stale_90}"

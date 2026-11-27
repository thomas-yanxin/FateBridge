# Changelog

版本唯一来源为 `src/fatebridge/__init__.py::__version__`。本页记录维护中的变更；具体计算范围与接口依赖见[算法覆盖矩阵](docs/algorithm-coverage.md)。已发布代码的历史由 Git 标签保存。

## [Unreleased]

- **MCP 两入口与渐进发现**：MCP 收口为 `discover_tools` 与 `run_calculation` 两个工具（无 MCP 资源），与 REST `/api/tools`、CLI `fatebridge discover` 共用渐进发现策略——默认 `detail=summary`，指定 `tool`、`family` 或 `q` 过滤时可选 `detail=full`，完整 `output_schema` 仅在显式传 `include_output_schema=True`（REST `?include_output_schema=true`、CLI `--include-output-schema`）时返回。
- **三端统一输出控制**：REST、MCP 与 CLI 统一采用默认 `detail=compact`（精简核心业务字段与回执）、按需 `detail=audit`（完整业务载荷、时间线与方法证据）、严格点号路径 `fields` 投影（无效路径返回 `unknown_projection_path` 并附 `constraints.available`）以及 `as_of` 时钟冻结；移除旧四工具协议、分段读取与结果持久化。
- **风水领域重构**：重构为 8 个结构化确定性工具（`fengshui_directions`、`fengshui_minggua`、`fengshui_bazhai`、`fengshui_jinsuo`、`fengshui_annual_stars`、`fengshui_monthly_stars`、`fengshui_xuankong_house_chart`、`fengshui_assess`），新增 WMM2025/IGRF-14 地磁参考、阳宅三要（门/主/灶）、金锁 24 山砂水、年/月/日/时四层紫白与十二节月界、中州玄空条件解读（正/副城门、零正、时令与主客）及四层叠加评估，不生成化煞处方或吉凶评分。
- **错误与契约强化**：统一三端错误包络，补全 `unknown_tool`、`unknown_projection_path`、`de441_archive_missing`、`ephemeris_source_inconsistent`、`fengshui_calculation_inconsistent`、`jyotish_calculation_inconsistent` 等诊断码，并新增 `FATEBRIDGE_STRICT_OUTPUT_VALIDATION`、`FATEBRIDGE_JPL_FILE`、`FATEBRIDGE_VSOP2013_MANIFEST`、`FATEBRIDGE_AA1996_MANIFEST` 等运行时控制。
- **文档体系重构**：按 Diátaxis 架构与单一信源原则重组根目录与 `docs/` 文档，同步删除过时咨询/交付文档与无效示例，补全可运行的 CLI/REST 示例与链接/计数自动校验。

## [0.1.1] - 2026-10-20

发布版本 `0.1.1`，提供共享领域计算的 REST、MCP 与 CLI 入口。

## [0.1.0] - 2026-10-19

首次正式发布，分发计算规则、知识数据、类型标记及 LICENSE／NOTICE。

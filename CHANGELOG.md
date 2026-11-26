# Changelog

版本唯一来源为 `src/fatebridge/__init__.py::__version__`。本页记录维护中的变更；具体计算范围与接口依赖见[算法覆盖矩阵](docs/algorithm-coverage.md)。已发布代码的历史由 Git 标签保存。

## [Unreleased]

- 八字九专题、双人八字、流时、西占关系盘和择日改用结构化证据，移除泛用评分和建议模板，经典条目改为按需检索。
- 西占与奇门知识卡改从现行规则表取值；占星卜问 `perfection` 交付七曜事件与条件，果老与印占专题统一由各自领域字段交付依据。
- 统一 REST、MCP 与 CLI 的现行工具命名；MCP 通过 `discover_capabilities`、`describe_capability`、`run_calculation` 和 `read_result` 四个入口暴露全部能力，默认使用 `detail=compact`（REST/CLI 默认 `standard`），完整证据使用 `detail=audit`。
- CLI 的 JSON 目录统一使用 `discover`，`list` 保留文本输出；MCP 成功结果只在 `structuredContent` 中交付。
- 公开结果与交付回执统一移除散列与指纹字段，使用 `run_id` 与同次结果交付接口核验载荷；调用指南与解读参考整理至 `AGENTS.md` 与 `docs/interpretation/`。
- 精简文档、示例与维护入口：移除内部审计日志、逐轮过程记录与研究夹具，保留开发者接入文档与独立参考数据。

## [0.1.1] - 2026-10-20

发布版本 `0.1.1`，提供共享领域计算的 REST、MCP 与 CLI 入口。

## [0.1.0] - 2026-10-19

首次正式发布，分发计算规则、知识数据、类型标记及 LICENSE／NOTICE。

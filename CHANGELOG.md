# Changelog

All notable changes to FateBridge are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
The version is single-sourced from `src/fatebridge/__init__.py::__version__`.
A version bump updates package metadata; PyPI publication is triggered separately
by a published GitHub Release through `.github/workflows/publish.yml`.

## [Unreleased]

### Changed

- 按首次使用、任务指南、接口参考和原理说明重组项目文档，新增核心概念与结果阅读指南，
  统一锁定环境命令、导航及可运行示例。
- Onda 扩展为九个生活主题、三个服务入口与一个多主题组合入口，共 13 个技能包；
  场景发现同步主题、任务、时间范围和共享咨询策略。
- 公共请求模型与共享执行层拒绝已知明确的生死、临床判断和医疗择时请求；
  卜卦与择时移除相关类别，健康与子女输出限定为命主盘内的传统文化解释。
  文本检测不能替代调用方对完整上下文的判断。
- 结果交付仅接受当前带元数据的临时记录，不再自动升级旧格式记录。
- 包管理统一使用 uv：提交 `uv.lock` 与默认 Python 3.12 配置，源码安装使用
  `uv sync --locked`，开发环境追加 `--extra dev`；发布构建使用 `uv build`，
  CI 增加锁定环境检查并保留最新版与最低依赖版本回归。

## [0.1.0] - 2026-10-19

首次正式发布到 PyPI，包版本统一为 `0.1.0`，Git 标签为 `v0.1.0`。
此前 `0.2.0` 为未发布的开发版本；下方保留其开发记录。

- 提供 `pip install fatebridge==0.1.0` 安装方式，以及
  `fatebridge`、`fatebridge-api`、`fatebridge-mcp` 三个命令入口。
- 随安装包分发计算规则、知识与场景 JSON、`py.typed`、LICENSE 和 NOTICE；
  场景技能随 Git 仓库提供，外部星历文件另行获取。

### Added

- 新增文档离线校验命令 `scripts/check_docs.py` 与 CI 检查，覆盖本地链接、标题锚点、围栏及 JSON 语法；新增迁移指南和按用途组织的请求示例索引。

- 补齐九类八字专题、宿曜双向关系、知识目录/来源/查询及导出模板/动态设置/分段的嵌套输出合同，并复用到各工具 snapshot_export；严格校验保持可空事实、扩展字段、部分投影及既有整数/浮点数原样输出。

- 专业输出补齐主限坐标与命中、递归时主、寿限、古典/关系盘及中国术数的嵌套合同；三端共用校验和发现 schema，保留动态键、扩展字段、可空事实、部分投影及既有数值。嵌套类型违规在投影前按内部失败处理。
- 场景 manifest 从 9 个技能 YAML 与住宅路由生成，共 10 个发现入口，REST `/api/scenarios`、CLI `scenarios`、MCP resources 共用；工具发现支持 scenario 筛选，可选 MCP scenario profile 与 family 取交集。
- 共享调用上下文支持 as_of / trace_id / parent_run_id；固定默认时间，保留显式日期、时区和手动起卦优先级，随机六爻记录本次 seed。
- 成功元数据增加格式/包版本、输入/合同/业务输出摘要、环境及数据指纹、耗时、口径和 replay 参数。新增字段可选，旧基础字段和 CLI --no-metadata 保留；有效标识传播到领域与校验失败，CLI profile 建立根/子关联。

- 玄空宅盘 `fengshui_xuankong_natal`（中州派 v1）：历史事件定运、24山／三元龙、五黄同元龙借运、下卦与兼向替星，分界和测量误差返回候选；REST/MCP/CLI 共用合同，合参与年度飞星分层。登记规则出处、网页版本和笔误范围，新增独立公开盘例及固定第三方比对差异记录。
- Six residential Feng Shui tools across REST, MCP and CLI: fixed directions,
  personal Ming Gua, sitting-trigram Eight Mansions, basic Jin Suo sand/water,
  annual Zi Bai stars and layered assessment. Versioned source registry,
  per-person results, explicit partial coverage and scoped differences are
  preserved; Xuan Kong natal charts are recorded in the separate entry above.
- Opt-in JSON `--request-file` and nested JSON flags for residential tools,
  shared layered output schemas, factual snapshots, offline independent
  reference fixtures and three-transport contract tests.

### API compatibility notes
- MCP results use FastMCP's native `ToolResult` with FastMCP >= 3.4.2;
  the custom SDK constructor adapter has been removed. Linux x86_64 / Python 3.12
  reference validation completes all golden comparisons without skips.
- Feng Shui `Ruleset` output fields now permit omission in dotted projections;
  native MCP clients can validate single-rule-field results. Full results and
  rule versions are preserved; catalog-wide projection regression checks cover
  nested objects, arrays and the REST/MCP/CLI schemas.
- Invalid projection paths now return additive `projection_warnings` while
  retaining the existing selected data and success status by default. Opt in to
  `strict_fields=true` (CLI `--strict-fields`) for shared 422 validation failures.
- Progressive discovery adds summary/filter/single-tool views to `/api/tools`,
  JSON `discover` / `list --json` CLI commands, and MCP catalog resources. REST
  defaults to full records; existing CLI text listings and `describe` remain.
  `FATEBRIDGE_MCP_FAMILIES` optionally narrows the registered MCP tools.
- MCP execution annotations derive from the same catalog hints exposed by REST
  and CLI. These describe environmental effects, not deterministic output.
- Requests now reject unknown fields and invalid civil dates with safe field-level
  `issues`. Explicit invalid election topics and horary categories are rejected;
  omitted selectors retain their defaults. Remove previously ignored fields from
  ordinary tool requests; CLI subject profiles still select fields for each tool.
- MCP errors now set native `isError=true`. FastMCP Client callers that inspect
  error payloads must use `raise_on_error=False`; successful text JSON remains
  available alongside structuredContent.
- All catalog tools publish projection-compatible output schemas. REST documents
  API Key authentication and error statuses, and uses stable catalog operationIds.
  Successful JSON shapes are preserved; schema-validation errors use 422 across
  REST/MCP/CLI. CLI command syntax errors retain exit 2 / usage_error.

### Changed

- 重整 README 与文档中心，集中安装配置、接口约定和迁移说明；风水路由归入 API 端点家族，统一已知契约直接调用、完整结果交付及文档信源维护流程。
- Synchronize maintained guides with nine Onda skills and ten discovery scenarios;
  complete Feng Shui topic navigation and the seven-tool entry table, and correct
  Xuan Kong examples to port 8010. Document same-run full export, post-projection
  retention, SHA-256 verification and explicit Western analysis clock inputs.
- Build compact call contracts without materializing full output schemas; copy
  timing-cache containers directly while preserving caller isolation. Benchmark
  reports separate initial calls, warm samples and the execution environment.
- Normalize hourly timing inputs before truncation and measure solar-term
  intervals in UTC across daylight-saving transitions. Metadata attachment and
  final output validation now share correlated internal errors across transports.
- Synchronize nine reviewed BaZi golden fixtures with the explicit timing-pillar
  provenance already added by the preceding implementation; existing numerical
  values and sections remain identical.
- Isolate golden output generation from locally discovered ephemeris files and
  restore the shared ephemeris configuration and derived caches on exit.
- Align maintained guides with the retired helper modules and transport-specific
  capability counts; check the complete algorithm tool matrix and per-family
  counts against the live catalog. Clarify bundled reference JSON, external
  ephemeris files, Git-only skills, and the scope of accuracy/performance evidence.
- Cache default model schemas and contract fingerprints with bounded, model-identity
  and rebuild-aware entries; public schemas remain independent copies and business
  executions are never cached. Remove the redundant third REST output validation.
- Build native MCP structured results directly from response dictionaries;
  move internal imports and transport tests to canonical modules and native
  registration paths while preserving retained transport contracts and numbers.
- Remove the obsolete `iztro-verify` extra, unused imports and private parameters,
  unreachable compatibility error forwarding and repeated export-section mapping.
  Bind documented CLI example tests to their test interpreter and refresh document
  navigation and maintenance guidance.
- Align integration, architecture, security, and Onda documentation with the
  current catalog and request models: distinguish transport bindings, document
  REST projections and 422 errors, and clarify installation, solar-time defaults
  and actual ephemeris precision. Simplify contribution steps and add a
  documentation maintenance and verification workflow.

- **Adopt the PyPA-recommended `src/` layout** (`fatebridge/` → `src/fatebridge/`).
  The package is no longer importable from the repo root without installing it,
  so a bare `pytest`/`import` runs against the *installed* package — packaging
  gaps (like the missing data files fixed in 0.2.0) now fail locally instead of
  only after `pip install`. Import name, wheel contents, and the three console
  scripts are unchanged. Repo-root-relative lookups (`.env`, `ephe/`) had their
  parent-index depth bumped so they still resolve to the repo root.

### Added
- `[project.urls]` (Homepage / Repository / Issues / Changelog) so the PyPI
  project page links back to the repository.
- `Typing :: Typed` and `Topic ::` classifiers.

### Removed
- Remove the remaining Python compatibility facades and aliases. Requests now
  use canonical Python field names on REST, MCP and CLI. Relative charts use
  `relative_mode`, directional snake_case fields and the primary `chart` layer;
  duplicate camelCase fields and `composite_chart` are removed. Export sections
  match current titles without legacy remapping. Primary directions use
  `equatorial` in place of the two historical method names.
- Remove the custom MCP result adapter; require FastMCP >=3.4.2 and use its
  native success/error results.
- Retired Python compatibility modules, package re-exports and REST/MCP wrapper
  aliases; remove `POST /api/calculate` and CLI `calculate_legacy`. Use
  `/api/cn/bazi/birth` / `bazi_birth` for a standalone chart and MCP / CLI
  `analyze_destiny` for composite analysis; see
  [migration guide](docs/architecture.md#旧入口迁移).
- `requirements.txt`, which duplicated `[project.dependencies]` with no check
  against drift. Docs now point at `pip install -e .` / `pip install fatebridge`.

### Fixed
- Preserve the actual selected Liu Ren lesson through transmission selection,
  so duplicate upper gods cannot mislabel 发用 or change Jin Kou 用神.
- Correct lunar month lengths in 1933, 1954 and 1978 without mutating the
  dependency's global tables; all 73,058 supported solar dates now agree with
  sxtwl. Cache immutable lunar-date values for repeated calendar requests.
- Resolve Zi Wei ages and flowing palaces using lunar boundaries and natal
  month/hour rotation, including childhood and leap-month handling. Expose
  calendar conventions and distinguish palace stems from transformation stems.
- Replace simplified Liu Ren transmission selection with the nine-method
  rules, use the day stem's element in the first lesson, and place generals
  using the nobleman's earthly position (including the 戌 reverse boundary).
- Include the equation of time in shared apparent-solar analysis inputs,
  bringing Qi Men / Liu Ren / Tai Yi / Jin Kou into agreement with birth inputs.
- Replace the Zi Wei oracle's calendar-branch comparison with actual active
  palaces; add pinned independent calendar and Liu Ren regression fixtures.
- README status badge and "项目状态" section said Alpha `0.1.0`; corrected to
  Beta `0.2.0` to match the `Development Status` classifier.

## 0.2.0 development notes - 2026-07-01 (unpublished)

First packaging-hardening release: the distribution is now installable and
usable from a wheel (previously the reference-data JSON was omitted, so several
engines crashed at runtime after `pip install`).

### Fixed
- **Ship reference data in the wheel/sdist.** Declared
  `[tool.setuptools.package-data]` so `fatebridge/data/**/*.json`
  (canping / heluo / knowledge stores) is packaged. Without it an installed
  wheel raised `FileNotFoundError` because the engines load these files via
  `Path(__file__).parents[1] / "data" / ...` at runtime.

### Added
- **PEP 561 typed marker** (`fatebridge/py.typed`) so downstream mypy / IDEs
  consume the package's inline type hints.
- `SECURITY.md` disclosure policy and a `publish.yml` GitHub Actions workflow
  that publishes to PyPI via Trusted Publishing (OIDC, no API tokens).
- `__all__` and a "Public API" note in the top-level package docstring.

### Changed
- Version `0.1.0` → `0.2.0`; `Development Status` classifier `3 - Alpha`
  → `4 - Beta` to reflect the stabilized, CI-locked API.
- Migrated license metadata to the PEP 639 form: SPDX `license = "Apache-2.0"`
  + `license-files = ["LICENSE", "NOTICE"]`, dropping the deprecated
  `License :: OSI Approved ::` classifier. `build-system` now requires
  `setuptools>=77.0.0` (first version to support the SPDX expression).

## Initial development (unpublished)

- Initial FateBridge engine: 80 tools across 13 families exposed over three
  transports (FastAPI REST, FastMCP, `fatebridge` CLI) from a single central
  tool catalog. Golden-master numeric locks and a 4-version CI matrix.

[Unreleased]: https://github.com/Yonder-Lab/FateBridge/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Yonder-Lab/FateBridge/releases/tag/v0.1.0

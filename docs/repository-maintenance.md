# 仓库维护

仓库保留当前实现、可运行测试、必要夹具和有来源的验证证据。可再生成的构建与缓存按固定范围清理；删除旧代码前先核对调用方、公开合同和回归用途。

`docs/` 保留安装、使用、接入、开发维护和各体系的主要计算说明。完成的逐轮审计、实验复盘和单次修复记录不再各占一篇当前指南；仍需引用的历史依据使用固定 Git 提交链接，避免把旧验收结果当作当前状态。

| 内容 | 维护位置与规则 |
| --- | --- |
| 领域算法 | `src/fatebridge/core/`；不导入服务或协议层 |
| 请求编排与三端接入 | `application/`、`services/`、`transports/` 各自负责执行、领域服务和协议适配 |
| JSON 指纹 | `utils/json_digest.py` 统一编码；领域事实、合同和运行回执共用同一实现 |
| 当前测试及冻结夹具 | 测试代码由 Git 维护；`tests/fixtures/` 的原始数据与历史程序副本由配套冻结数据提供，当前 Python 辅助模块继续提交 |
| 一次性研究程序和测试 | 只复放旧实验、不调用当前实现的研究测试与无当前调用方的过程脚本一并移出仓库；原字节和依赖保留在外部归档，需要复放时恢复对应 Git 版本及配套数据 |
| 当前说明与合同 | `docs/`、`docs/contracts/`；生成合同由生成器维护 |
| 回归证据与来源指纹 | `docs/validation/` 的历史报告、原始数据、日志、来源指纹与历史副本在 Git 之外保存，保留原字节、失败记录与适用版本 |
| 数值黄金快照 | `tests/golden/snapshots/`；由配套冻结数据提供，按原有逐字段与数值标准验收 |
| 构建、缓存与临时实验 | `build/`、`dist/`、各工具缓存及根目录 `tmp/`；不作为当前源码或发布依据 |

## 清理可再生成的产物

先预览，再执行：

```bash
uv run --locked --extra dev python scripts/clean_repository.py
uv run --locked --extra dev python scripts/clean_repository.py --apply
```

脚本只处理根目录构建、测试与类型检查缓存、根目录 CI 产物、覆盖率数据（`.coverage`、`.coverage.*`、`htmlcov/`），`dist/` 直属 wheel／sdist，以及当前源码、脚本、测试中的 Python 缓存和 Finder 元数据。覆盖率配置 `.coveragerc` 保留。Git 索引不可读或候选范围包含受版本控制的文件时，整个清理停止。符号链接不进入清理范围。

脚本保留虚拟环境、星历、资料书籍、`tmp/`、`dist/validation/`、`docs/validation/` 与 `tests/fixtures/`。这些目录可能保存独有证据，需核对引用后另行归档。不要使用全仓库 `git clean -fdx`，也不要按 `.log`、`.sha256` 或 JSON 扩展名删除文件。

历史审查目录和退役输出先在仓库外归档并校验，再移出工作区；梅花现场应事测试的当前来源清单继续校验原始资料，不携带旧算法输出哈希。

一次性整理报告、命令日志、Git 状态清单和旧构建回执放在仓库外，不加入当前文档索引。归档前核对代码、测试和清单引用，并保留原字节、相对路径与校验摘要；需要复放时恢复对应相对路径，不用当前重跑替代历史原件。移出工作仓库不会释放归档占用的磁盘空间。

过程代码是否退役按用途判断：生成生产数据、当前测试依赖的独立参考和来源校验器继续维护；仅核对历史研究文件的脚本与测试共同归档。删除后比较 pytest 收集清单，确保其他测试身份完整保留，并检查导入、CI 和文档引用。专题文档保留现行行为、来源、固定门槛与未决结论，逐轮进度合并到对应专题，原报告留在归档。

核对旧报告中的轮次、源码哈希、wheel 和命令回执属于历史复放；没有当前实现、测试、文档或 CI 调用方的专用脚本随原实验退役。原实验需要的脚本、专用测试和固定环境一起保存，复放时使用对应提交。不能仅凭文件名含 `audit`、`reference`、版本号或哈希就判断它过时。

架构测试共用一次源码依赖图，集中检查领域与协议分层、内部循环依赖、目录装配及退役入口；已被全图检查覆盖的局部断言不重复维护。模块整理前后，保留其他测试的节点身份与原有验收阈值。

`.gitignore` 排除历史验证与回归数据；已有跟踪数据使用 `git rm --cached` 取消跟踪，本地原件保留。执行本地全量测试前恢复与测试版本匹配的数据，保留原有缺失检查、来源哈希、反例及数值阈值。维护文档以本地数据路径标明这些原件的位置。

云端清理通过普通 Git 提交同步当前文件树。CI 回归产物保留14天；需长期保存的验收材料应另行下载归档。手动移除旧 Actions 产物或日志前，保存运行元数据、原始压缩包和校验摘要；最近运行及发布依据继续保留，历史失败不因清理改判。

## 本地恢复冻结数据

测试数据只在本地保存。`tests/fixture-data.json` 固定来源提交、归档名称、大小和 SHA-256；清单不包含云端仓库或资产 ID。`scripts/restore_test_data.py` 只读取显式提供的本地归档目录，核验后恢复夹具、黄金快照和历史验证目录。已有文件字节不同会停止，不覆盖现有参考，也不重算样本。

```bash
uv run --locked --extra dev python scripts/restore_test_data.py --archive-directory /path/to/frozen-archives
uv run --locked --extra dev python scripts/restore_test_data.py --archive-directory /path/to/frozen-archives --core-only
uv run --locked --extra dev python -m pytest -q
```

归档名称必须与清单一致。缺少归档、来源哈希不符或本地参考不同仍然报错；数据缺失不算验收通过。外部星历、独立参考与专用锁环境按[开发指南](development-guide.md#测试)在本地准备。

## 云端自包含检查

云端不上传、下载或恢复外部测试数据。`scripts/run_ci_checks.py` 集中维护云端检查文件：覆盖架构、请求与响应合同、REST／MCP／CLI、私有存储、临时夹具和文档。Windows 使用跨平台集合，其他平台另检查文档、技能与 CI 配置。六种既有版本／依赖／平台环境各分三片；汇总同时核对每个节点恰好执行一次。混合文件中需本地参考的用例用 `local_data` 标记，保留原断言并从云端集合中排除。

```bash
uv run --locked --extra dev python scripts/run_ci_checks.py
```

普通 README 与 `docs/` Markdown 改动只运行路径筛选和成功的汇总状态；场景路由生成源、JSON、技能及代码变更仍触发完整检查。PR 更新取消旧运行，main／master 的每次 push 不互相取消。格式、类型、文档和生成合同在 Ubuntu 独立并行执行。

新增云端检查须在没有 `docs/validation/`、外部夹具、黄金快照与星历目录的干净 checkout 验证。默认 `pytest` 仍收集本地全部测试；历史原件、独立来源和数值门槛继续由本地全量与专题验证负责。云端检查通过不代表这些验证已执行或通过。

## 文档和依赖检查

```bash
uv run --locked --extra dev python scripts/check_docs.py
uv run --locked --extra dev python scripts/check_docs.py --include-archives
uv run --locked --extra dev python -m pytest -q \
  tests/test_architecture_boundaries.py tests/test_runtime_contracts.py \
  tests/test_repository_cleanup.py tests/test_documentation_integrity.py
```

第一个命令检查当前维护文档，也核对其中指向历史材料的文件和标题。第二个命令额外检查历史材料内部的链接与代码块；历史源码副本可能含有已经失效的路径，结果单独报告，不能改写冻结内容来使检查通过。

默认 pytest 收集排除 `tests/fixtures/` 内的历史测试程序；当前 `tests/test_*.py` 仍通过夹具、来源哈希与独立复放核对这些材料。原程序保留，可在对应冻结环境显式复放。

结构整理保留业务输出与公开合同；源码变化会自然改变实现指纹。算法、数据来源、数值阈值和黄金样本的修改应作为独立工程变更验证。完整开发与发布要求见[开发指南](development-guide.md)。

Git 跟踪的文本统一以 LF 检出，避免 Windows 的 `core.autocrlf` 改变来源文件字节、触发哈希校验失败。需保留原始换行的文件在 `.gitattributes` 中用 `-text` 明确标注；冻结数据包继续保留原字节，不重算其哈希。

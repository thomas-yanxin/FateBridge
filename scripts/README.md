# 维护脚本

通用开发、契约生成、CI 与发布工具位于 `scripts/` 顶层，星历数据工具位于 `scripts/astronomy/`。生产计算均由 `src/fatebridge/` 提供。

从仓库根目录使用开发环境运行：

```bash
uv sync --extra dev
uv run --extra dev python scripts/check_docs.py
uv run --extra dev python scripts/run_ci_checks.py
```

## 脚本清单

| 任务 | 脚本入口 |
| --- | --- |
| 文档链接、锚点、代码块与示例 JSON 校验 | [check_docs.py](check_docs.py) |
| 生成并核对按需调用合同（`docs/contracts/`） | [build_codex_call_contracts.py](build_codex_call_contracts.py)（支持 `--check`） |
| 运行自包含 CI 测试集 | [run_ci_checks.py](run_ci_checks.py)（分片配置：[ci_sharding.py](ci_sharding.py)） |
| 清理可再生的本地构建、缓存与临时文件 | [clean_repository.py](clean_repository.py)（默认预览，`--apply` 执行） |
| PyPI 发布包与 GitHub Release 同步校验 | [check_pypi_release.py](check_pypi_release.py) · [sync_github_release.py](sync_github_release.py) |
| 准备独立 DE440 太阳参考内核 | [astronomy/prepare_reference_kernel.py](astronomy/prepare_reference_kernel.py) |
| 构建并校验星历系数共享档案 | [astronomy/build_coefficient_archives.py](astronomy/build_coefficient_archives.py)（见[星历说明](../docs/ephemeris.md)） |
| 维护 Swiss Ephemeris 清单配置 | [astronomy/build_ephemeris_manifest.py](astronomy/build_ephemeris_manifest.py) |

维护规则、文档同步与发布流程见[开发指南](../docs/development-guide.md)。

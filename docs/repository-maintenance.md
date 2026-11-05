# 仓库维护

仓库维护现行算法、公开盘式、当前测试和独立参考资料。退役实现、旧兼容适配、旧算法整包快照、源码回放、迁移哈希链、单次日志和过程报告不属于当前框架。

## 当前源码与资料

- 领域计算在 `src/fatebridge/core/`，服务和 REST／MCP／CLI 共享同一计算入口。
- `tests/data/` 保存当前检查需要的原始输入、独立数值和原典转录；保留来源、坐标系、时标、适用范围、容差、未知和实际分歧。当前测试不以旧算法输出作为正确答案。
- `tests/fixtures/` 中的 Python 模块提供当前代表请求和协议辅助。外部星历、原始文献和大型物理参考按实际读取关系维护，不随版本后缀或文件扩展名批删。
- 当前规则数据的完整性校验、执行回执、同次结果交付和真实来源身份继续使用哈希；不保留仅用于接受旧源码或旧输出的白名单。
- 公开传统盘式仍可选择，历史历法和历史 UTC 仍按其现行范围计算。它们不属于旧软件兼容层。

## 清理构建与缓存

```bash
uv run --locked --extra dev python scripts/clean_repository.py
uv run --locked --extra dev python scripts/clean_repository.py --apply
```

脚本只清理已确认可再生成的构建、缓存、覆盖率、根目录 CI 产物和 Finder 产物。保留虚拟环境、星历和当前参考资料；不使用全仓库 `git clean -fdx`。

历史审查目录和退役输出先在仓库外归档并校验，再移出工作区；当前来源清单继续校验原始资料，不携带旧算法输出哈希。

退役代码前核对实际调用者与公开合同，提取仍有独立价值的当前验证，再一起删除旧实现、专用测试、脚本及说明。不得用重算期望值、删反例或放宽容差取得通过。

## 验证

```bash
uv run --locked --extra dev python -m pytest -q
uv run --locked --extra dev python scripts/run_ci_checks.py
uv run --locked --extra dev python scripts/check_docs.py
uv run --locked --extra dev python scripts/build_scenario_manifest.py --check
uv run --locked --extra dev python scripts/build_codex_call_contracts.py --check
```

数据缺失仍应报错；不把缺失检查变成通过。原典符合、物理误差、三端一致性、真实模型解释和部署验收分别报告。数值与原典未决项见[当前算法状态](algorithm-status.md)，开发要求见[开发指南](development-guide.md)。

CI 使用自包含集合；需要本地外部星历或参考的用例单独执行。CI 的绿色状态不能代替本地数值与来源验收。构建应清除旧 `build/lib` 残留，并核对 wheel 与当前源码一致。

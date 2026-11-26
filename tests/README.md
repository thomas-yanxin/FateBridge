# 测试目录

测试按计算领域与公共接口边界组织，通用辅助夹具位于 [support/](support/) 与 [fixtures/](fixtures/)。[conftest.py](conftest.py) 配置 `importlib` 模式并排除原始资料目录，[native_engine_test_worker.py](native_engine_test_worker.py) 为原生故障注入提供隔离进程入口。测试直接从已安装的 `src/fatebridge` 包导入。

## 运行测试

在仓库根目录使用锁定开发环境执行：

```bash
uv sync --locked --extra dev
uv run --locked --extra dev python -m pytest -q tests/bazi
uv run --locked --extra dev python -m pytest -q tests/integration/test_full_surface_validation.py
uv run --locked --extra dev python scripts/run_ci_checks.py
```

完整本地收集与执行：

```bash
uv run --locked --extra dev python -m pytest --collect-only -q
uv run --locked --extra dev python -m pytest -q
```

`scripts/run_ci_checks.py` 仅运行自包含 CI 集合；完整本地运行会额外执行标记为 `local_data` 的用例，需按[星历安装说明](../docs/ephemeris.md)提前准备对应外部数据。

## 目录结构

| 范围 | 目录 |
| --- | --- |
| 请求校验、执行回执、输出投影、结果交付与 REST/MCP/CLI 合同 | [integration/](integration/) |
| 架构依赖边界、文档完整性、工具计数、生成合同、CI 与发布校验 | [quality/](quality/) |
| 八字、时运与双人关系 | [bazi/](bazi/) · [compatibility/](compatibility/) |
| 星历、节气、时间尺度与太阳模型 | [astronomy/](astronomy/) |
| 西方占星、推运与占星骰 | [western/](western/) · [astrodice/](astrodice/) |
| 人类图、印度占星 | [human_design/](human_design/) · [jyotish/](jyotish/) |
| 果老、紫微、宿曜 | [guolao/](guolao/) · [ziwei/](ziwei/) · [sukuyo/](sukuyo/) |
| 梅花、六爻、河洛与参评 | [meihua/](meihua/) · [liuyao/](liuyao/) · [numerology/](numerology/) |
| 六壬、金口诀、奇门与太乙 | [qimen/](qimen/) · [taiyi/](taiyi/) |
| 家居风水、地磁、玄空与布局 | [fengshui/](fengshui/) |
| 心理测量量表 | [psychometrics/](psychometrics/) |
| 共享协议调用、时间冻结、星历上下文与夹具 | [support/](support/) · [fixtures/](fixtures/) |

## 测试约定

- 跨领域共享辅助统一放入 `tests/support/`（如三端调用封装 `support/transports.py`、风水传输封装 `support/fengshui_transports.py`、交付存储夹具 `support/result_delivery.py` 与空星历隔离 `support/ephemeris_context.py`）。
- 独立测试夹具放在 `tests/fixtures/`；不得通过运行当前生产计算重新生成测试期望值或放宽断言门槛。
- 严格嵌套输出模型检查由 `FATEBRIDGE_STRICT_OUTPUT_VALIDATION=1` 控制，详见[开发指南](../docs/development-guide.md#设计与测试约束)。

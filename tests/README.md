# 测试目录

测试按计算领域和公共边界分组，通用辅助代码位于 [support/](support/)。[conftest.py](conftest.py) 与 [native_engine_test_worker.py](native_engine_test_worker.py) 保留原生故障注入的独立进程入口；领域测试从同一套安装后的源码导入。

## 选择测试范围

在仓库根目录运行：

```bash
uv sync --locked --extra dev
uv run --locked --extra dev python -m pytest -q tests/bazi
uv run --locked --extra dev python -m pytest -q tests/integration/test_full_surface_validation.py
uv run --locked --extra dev python scripts/run_ci_checks.py
```

最后一个命令执行明确列出的自包含 CI 集合，不代表全仓库测试。完整收集与完整本地执行分别使用：

```bash
uv run --locked --extra dev python -m pytest --collect-only -q
uv run --locked --extra dev python -m pytest -q
```

全量本地执行需要具体测试所要求的外部星历和独立参考；准备方式与当前 CI 范围见[开发指南](../docs/development-guide.md#测试策略)。`local_data` 标记识别这些用例，默认本地 pytest 不排除它们。收集成功不代表所有测试已执行。

## 目录职责

| 范围 | 目录 |
| --- | --- |
| 请求、执行、输出、交付、CLI／REST／MCP 和其他公共合同 | [integration/](integration/) |
| 架构、文档、技能、CI、仓库与发布检查 | [quality/](quality/) |
| 真实模型运行器、解释引用、外部评估和预测研究协议 | [evaluation/](evaluation/) |
| 八字与时运、双人评分 | [bazi/](bazi/) · [compatibility/](compatibility/) |
| 物理星历、历法、时间尺度与太阳模型 | [astronomy/](astronomy/) |
| 西方占星与推运、占星骰 | [western/](western/) · [astrodice/](astrodice/) |
| 人类图、印度占星 | [human_design/](human_design/) · [jyotish/](jyotish/) |
| 果老、紫微、宿曜 | [guolao/](guolao/) · [ziwei/](ziwei/) · [sukuyo/](sukuyo/) |
| 梅花、六爻、河洛与参评 | [meihua/](meihua/) · [liuyao/](liuyao/) · [numerology/](numerology/) |
| 六壬与金口诀、奇门、太乙与三式 | [ren/](ren/) · [qimen/](qimen/) · [taiyi/](taiyi/) |
| 风水、地磁、玄空与布局几何 | [fengshui/](fengshui/) |
| 公共手算、来源读取、时间冻结和协议辅助 | [support/](support/)；实际协议夹具继续在 [fixtures/](fixtures/) |
| 固定来源、独立期望值与反例 | [data/](data/) · [fixtures/](fixtures/) 中对应资料集 |

测试模块可以复用其他模块中的已命名辅助，但导入测试函数作为辅助时应使用不以 `test_` 开头的别名，避免额外收集同一测试。合并场景文件时保留全部参数、断言、标记及故障方式，并比较完整测试节点清单。

pytest 使用 `importlib` 导入模式，允许不同领域的同名模块一起收集。三端夹具与调用在 [support/transports.py](support/transports.py)维护；同主题的相同协议控制优先参数化，保留各请求、投影、分页、故障注入与业务断言。

测试精简以完整独立参考为准：参评逐格转录与复读对照覆盖的同值抽查无需另留；紫微亮度用完整独立转录同时核对20颗星、空缺分支和无亮度星。退役脚本的参数解析／JSON打印测试随入口移除，领域计算、来源校验和错误注入继续维护。

八字来源状态、集合约束和错误事实共用 `bazi/test_bazi_source_comparison_transports.py` 的三端参数队列。风水来源测试直接执行各自完整审计，避免多个文件反复启动同一总审计进程；正文213／216、下卦图5831／5832、替卦图5829／5832等分歧仍由对应领域断言保留。

原典字面冲突、数值超差和未裁定结果本身也需要回归：测试通过可能只证明这些失败被诚实保留。不得从当前计算输出重新生成期望值、删反例或把固定来源检查改成跳过。当前算法限制见[算法状态](../docs/algorithm-status.md)，验证方法见[计算与预测验收](../docs/prediction-validation.md)。

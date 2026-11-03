# FateBridge 文档中心

想先完成一次计算，还是准备把它接入自己的应用？想了解一种方法的规则，还是核对结果究竟经过了哪些验证？从下面的任务出发，找到对应文档。

FateBridge 提供术数与占星计算，Onda 技能指导咨询，接入应用提供模型对话与界面。这些部分各有职责：[核心概念](concepts.md)解释它们如何配合，以及如何区分计算结果、传统解释和现实建议。

文档对应当前开发分支。使用已发布包时，查阅对应 Git 标签的文档；尚未发布的变化见 [CHANGELOG](../CHANGELOG.md#unreleased)。

## 从这里开始

| 目标 | 阅读顺序 |
| --- | --- |
| 在终端完成第一次计算 | [快速入门](getting-started.md) |
| 在 Codex 中使用 | 快速入门 → [Codex 使用指南](codex-guide.md) |
| 接入应用或其他 Agent | 快速入门 → [Agent 接入指南](agent-guide.md) |
| 贡献代码或文档 | [贡献指南](../CONTRIBUTING.md) → [开发指南](development-guide.md) |

CLI 可直接运行；REST 默认端口为 `8010`；MCP 默认通过 stdio 由客户端启动。各端名称与可用范围见[三端能力边界](api-reference.md#24-三端能力边界)。

## 安装、接入与交付

| 任务 | 指南 |
| --- | --- |
| 安装、环境变量与外部星历 | [快速入门](getting-started.md) |
| 本地 stdio、远程 HTTP、Onda 插件与停用 | [MCP 部署](mcp-deployment.md) |
| 工具发现、错误恢复与字段投影 | [Agent 接入](agent-guide.md) |
| 读取和保存同次完整结果 | [完整结果交付](agent-guide.md#完整结果交付与同次导出) |
| 按问题选择咨询场景 | [场景路由](scenario-routing.md) · [Onda 技能](../skills/README.md) |
| 运行请求示例 | [示例索引](examples/README.md) |
| 升级旧接口或解决故障 | [迁移指南](migration.md) · [故障排除](troubleshooting.md) |
| 报告安全问题 | [安全策略](../SECURITY.md) |

## 计算原理与专题

同一种方法可能有不同规则与适用条件。专题页介绍项目采用的规则、依据与适用范围。字段定义以实际 Schema 为准；局部软件回归、原典对照、模型解释与现实效度分别报告。

| 主题 | 指南 |
| --- | --- |
| 八字 | [旺衰、喜用与原典查询](bazi-assessment.md) · [时运与历法边界](bazi-timing.md) |
| 紫微斗数 | [规则选择、时间与原典](ziwei.md) |
| 双人配合 | [评分与解释范围](compatibility-scoring.md) |
| 易占 | [梅花](meihua.md) · [六爻与周易](liuyao-depth-audit.md) |
| 河洛与参评 | [取数、配运与来源](numerology-audit.md) |
| 三式与金口诀 | [奇门](qimen-depth-audit.md) · [太乙与三式](taiyi-sanshi-audit.md) · [六壬与金口诀](liuren-jinkou-audit.md) |
| 人类图 | [计算、专业结构与原典](human-design.md) |
| 印度占星 | [本命、分盘与 Vimshottari](jyotish.md) |
| 果老与宿曜 | [果老星宗](guolao.md) · [宿曜与宿占](sukuyo.md) |
| 西方占星 | [天文、宫位与技法](western-astrology.md) · [法达日期口径](firdaria-compatibility.md) · [其他流派](other-chart-schools.md) |
| 占星骰 | [骰面、原典与解释](astrodice.md) |
| 风水 | [家居与布局](fengshui.md) · [玄空宅盘](fengshui-xuankong.md) |
| 计算基础 | [可选太阳后端](solar-backends.md) · [地点与坐标](place-catalog.md) |

风水咨询从 [onda-fengshui](../skills/onda-fengshui/SKILL.md)进入；规则作者、版本、现场条件与动作许可在该技能及其参考资料中维护。

## 开发与验证

| 需要查什么 | 入口 |
| --- | --- |
| 工具、参数、端点和错误 | [API 参考](api-reference.md) · [按需调用合同](contracts/README.md) |
| 实现覆盖、依赖与近似路径 | [算法覆盖矩阵](algorithm-coverage.md) · [当前算法状态](algorithm-status.md) |
| 模块职责、数据流与依赖边界 | [架构说明](architecture.md) |
| 扩展、测试、CI、打包与发布 | [开发指南](development-guide.md) |
| 本地清理与冻结数据恢复 | [仓库维护](repository-maintenance.md) |
| 真实模型的调用与解释质量 | [Agent 行为验收](agent-evaluation.md) |
| 外部命例评估 | [MingLi-Bench](mingli-bench-evaluation.md) |
| 计算引用、现实预测与奇门研究绑定 | [验证方法](prediction-validation.md) |

当前指南保留行为、依据和限制；逐轮进度、首次失败与旧验收记录按页内固定提交链接查阅。冻结资料在 Git 之外保留原字节，历史成绩不代表当前版本或完整验收。生成合同与场景清单由脚本维护。

修改文档后按[文档维护与验证](development-guide.md#文档维护与验证)检查内容、示例、链接与生成物：

```bash
uv run --locked --extra dev python scripts/check_docs.py
```

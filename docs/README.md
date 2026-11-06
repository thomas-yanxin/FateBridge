# FateBridge 文档中心

按任务选择入口：第一次运行看快速入门，接入应用看协议指南，核对计算看领域专题，贡献修改看开发与验证。

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
| 安装与首次计算 | [快速入门](getting-started.md) |
| 环境变量、加载顺序与 REST 密钥 | [运行配置](configuration.md) |
| 下载星历、校验文件与核对实际模型 | [星历数据安装](ephemeris.md) |
| 本地 stdio、远程 HTTP、Onda 插件与停用 | [MCP 部署](mcp-deployment.md) |
| 工具发现、错误恢复与字段投影 | [Agent 接入](agent-guide.md) |
| 读取和保存同次完整结果 | [完整结果交付](agent-guide.md#完整结果交付与同次导出) |
| 按问题选择咨询场景 | [场景路由](scenario-routing.md) · [Onda 技能](../skills/README.md) |
| 运行请求示例 | [示例索引](examples/README.md) |
| 升级旧接口或解决故障 | [故障排除](troubleshooting.md) |
| 报告安全问题 | [安全策略](../SECURITY.md) |

## 计算原理与专题

同一种方法可能有不同规则与适用条件。专题页介绍项目采用的规则、依据与适用范围。字段定义以实际 Schema 为准；局部软件回归、原典对照、模型解释与现实效度分别报告。

| 主题 | 指南 |
| --- | --- |
| 八字 | [旺衰、喜用与原典查询](bazi-assessment.md) · [时运与历法边界](bazi-timing.md) |
| 紫微斗数 | [规则选择、时间与原典](ziwei.md) |
| 双人配合 | [评分与解释范围](compatibility-scoring.md) |
| 易占 | [梅花](meihua.md) · [六爻与周易](liuyao-depth-audit.md) · [梅花天气研究](meihua-weather-study.md) |
| 河洛与参评 | [取数、配运与来源](numerology-audit.md) |
| 三式与金口诀 | [奇门](qimen-depth-audit.md) · [太乙与三式](taiyi-sanshi-audit.md) · [六壬与金口诀](liuren-jinkou-audit.md) |
| 人类图 | [计算、专业结构与原典](human-design.md) |
| 印度占星 | [本命、分盘与 Vimshottari](jyotish.md) |
| 果老与宿曜 | [果老星宗](guolao.md) · [宿曜与宿占](sukuyo.md) |
| 西方占星 | [天文、宫位与技法](western-astrology.md) · [法达日期口径](firdaria-compatibility.md) · [其他流派](other-chart-schools.md) |
| 占星骰 | [骰面、原典与解释](astrodice.md) |
| 风水 | [家居与布局](fengshui.md) · [玄空宅盘](fengshui-xuankong.md) · [实测工位与有限搜索](fengshui-workstation-layout.md) |
| 计算基础 | [可选太阳后端](solar-backends.md) · [地点与坐标](place-catalog.md) |

风水咨询从 [onda-fengshui](../skills/onda-fengshui/SKILL.md)进入；规则作者、版本、现场条件与动作许可在该技能及其参考资料中维护。

## 开发与验证

| 需要查什么 | 入口 |
| --- | --- |
| 工具、参数、端点和错误 | [API 参考](api-reference.md) · [按需调用合同](contracts/README.md) |
| 实现覆盖、依赖与近似路径 | [算法覆盖矩阵](algorithm-coverage.md) · [当前算法状态](algorithm-status.md) |
| 模块职责、数据流与共享历法依赖 | [架构说明](architecture.md) |
| 太阳、近太阳位置及月球日速的固定队列 | [分项精度验收](precision-acceptance.md) |
| 方法登记、误差预算、证据图与固定总体验收 | [计算证据合同](computation-evidence.md) |
| 扩展、测试、CI、打包与发布 | [开发指南](development-guide.md) · [脚本索引](../scripts/README.md) · [测试索引](../tests/README.md) |
| 文档分工、写作与来源维护 | [文档写作与维护](documentation-guide.md) |
| 仓库维护与本地清理 | [仓库维护](repository-maintenance.md) |
| 真实模型的调用与解释质量 | [Agent 行为验收](agent-evaluation.md) |
| 外部命例评估 | [MingLi-Bench](mingli-bench-evaluation.md) |
| 计算引用、现实预测与奇门研究绑定 | [验证方法](prediction-validation.md) |

## 文档维护

文档按入门、操作、参考和解释分工，写作与信源规则见[文档写作与维护](documentation-guide.md)。修改后按[开发指南](development-guide.md#文档维护与验证)检查链接、示例和生成物。文档检查不验证外部数值、原典读法或模型解释。

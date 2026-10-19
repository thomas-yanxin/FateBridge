# FateBridge 文档中心

FateBridge 提供可在本地运行的传统术数与占星计算，通过 CLI、REST 和 MCP 接入。本中心按阅读目的组织文档：先完成一次调用，再学习所需操作，遇到字段或精度问题时查参考。

首次了解项目，先读[项目首页](../README.md)；已安装的用户可直接进入下面的任务指南。

本文档描述当前开发分支；使用已发布包时，以对应 Git 标签下的文档为准。最新功能的源码安装见[快速入门](getting-started.md)，尚未发布的变化见 [CHANGELOG](../CHANGELOG.md#unreleased)。

## 第一次使用

| 你的目标 | 建议路径 | 完成标志 |
| --- | --- | --- |
| 在终端完成计算 | [快速入门](getting-started.md) → CLI 虚构示例 | 命令成功，能找到业务字段与计算回执 |
| 在 Codex 中咨询 | [快速入门](getting-started.md) → [Codex 使用指南](codex-guide.md) | MCP 诊断通过，新聊天可见所选场景工具 |
| 集成到应用或其他 Agent | [快速入门](getting-started.md) → [接入指南](agent-guide.md) | 能发现工具、发送请求并处理结果与错误 |
| 贡献代码或文档 | [贡献指南](../CONTRIBUTING.md) → [开发指南](development-guide.md) | 锁定环境可用，按修改范围完成检查 |

CLI 可直接执行，无需启动 REST。REST 默认端口为 `8010`，MCP 默认使用 stdio，由 host 启动子进程。三个入口共享领域计算，实际名称、输入与公开范围见[三端能力边界](api-reference.md#24-三端能力边界)。

## 完成具体任务

| 任务 | 阅读入口 |
| --- | --- |
| 安装、配置环境变量或获取星历 | [快速入门](getting-started.md) |
| 注册 Codex 并完成第一次对话 | [Codex 使用指南](codex-guide.md) |
| 发现工具、接入客户端或恢复错误 | [Agent 与应用接入指南](agent-guide.md) |
| 保存完整 JSON 或全部时间线 | [完整结果交付与同次导出](agent-guide.md#完整结果交付与同次导出) |
| 根据生活问题选择场景 | [场景路由矩阵](scenario-routing.md) · [Onda 技能索引](../skills/README.md) |
| 提交住宅、工位或布局候选 | [家居风水](fengshui.md) · [可运行示例索引](examples/README.md) |
| 升级旧接口 | [迁移指南](migration.md) · [变更记录](../CHANGELOG.md) |
| 定位安装、MCP、参数或结果交付错误 | [故障排除](troubleshooting.md) |
| 报告安全问题 | [安全策略](../SECURITY.md) |

## 理解计算与结果

[核心概念](concepts.md)解释工具、family、场景与技能的关系，以及业务字段、快照、交付物和回执的区别。初次接入时读这一页，可以避免把摘要当全文，或把计算完成当成现实效果已验证。

| 原理与专题 | 说明范围 |
| --- | --- |
| [架构说明](architecture.md) | 工具目录、请求、领域服务与三种传输入口如何协作 |
| [八字判定说明](bazi-assessment.md) | 旺衰、喜用分层、原典与工程参数、回归及未覆盖范围 |
| [双人配合评分](compatibility-scoring.md) | 分项权重、舍入、方向性和可解释范围 |
| [法达兼容性](firdaria-compatibility.md) | 法达模式、时间口径、版本差异与对照方法 |
| [玄空宅盘](fengshui-xuankong.md) | 历史定运、角区、来源版本与独立验证 |

## 查询接口与覆盖

| 参考 | 适合查什么 |
| --- | --- |
| [API 参考](api-reference.md) | 请求族、端点、公共选项、错误、快照与跨端差异 |
| [算法覆盖矩阵](algorithm-coverage.md) | 逐工具实现范围、依赖、精度、近似路径与快照覆盖 |
| [场景路由矩阵](scenario-routing.md) | 各任务的候选依据，以及全部工具的归属 |
| [Onda 技能索引](../skills/README.md) | 各主题的取证与交付规则、共享参考、发现与维护 |
| [开发指南](development-guide.md) | 目录职责、扩展步骤、CI、发布与文档验证 |

接口默认值与参数约束以当前代码和 Schema 为准。规则资料记录其作者、版本与适用范围；软件回归、Linux 黄金快照、独立规则比较、真实模型对话与现实效力分别提供不同层次的证据。

## 风水专题

普通咨询从 [onda-fengshui](../skills/onda-fengshui/SKILL.md)进入，工程接入从[家居风水](fengshui.md)进入。[示例索引](examples/README.md)区分原始盘、布局、候选方案与执行条件。

| 需要核对的内容 | 规则资料 |
| --- | --- |
| 事实采集、选法、家庭楼层与闭环 | [咨询闭环](../skills/onda-fengshui/references/consultation.md) · [场景与候选](../skills/onda-fengshui/references/scene-planning.md) |
| 作者、版本、方位与基础判据 | [规则来源](../skills/onda-fengshui/references/rule-sources.md) · [布局规则](../skills/onda-fengshui/references/layout-rules.md) |
| 厨卫、镜、梁管、尖角、材质器形 | [室内关系与材质](../skills/onda-fengshui/references/sourced-interior-rules.md) |
| 历史宅运、山水条件与有限解释 | [宅盘来源](../skills/onda-fengshui/references/xuankong.md) · [有限解释](../skills/onda-fengshui/references/xuankong-interpretation.md) |
| 工位活动、隔挡与材料条件 | [工位作者规则](../skills/onda-fengshui/references/workstation-authored.md) |
| 用户明确另选的 BTB 桌面规则 | [桌面作者规则](../skills/onda-fengshui/references/surface-rules.md) |
| 结果表达、逐物件与候选对照 | [结果交付](../skills/onda-fengshui/references/delivery.md) |

普通解释使用已有依据；动作可执行状态与规则审查是否完整分别核对。详细输入和来源限制以对应规则资料为准。

## 维护文档

文档修改应同时检查读者任务、代码事实、可复制示例和链接。信源与同步范围见[文档维护与验证](development-guide.md#文档维护与验证)，检查命令在锁定开发环境中运行：

```bash
uv run --locked --extra dev python scripts/check_docs.py
```

场景清单与调用合同由脚本生成，不手改生成区。仓库维护当前指南、规则资料、示例及回归测试；历史变更保留在 CHANGELOG 与 Git。一次性评审、运行回执和实现快照放在仓库外，`docs/reviews/` 只供本地临时使用，不入库。

# FateBridge 文档中心

按目标选择入口。各页集中维护自己的主题，接口默认值、能力边界和来源以当前代码、Schema 与规则数据为依据。

## 按目标找文档

| 你的目标 | 阅读入口 | 本页负责什么 |
| --- | --- | --- |
| 首次安装、配置和运行 | [快速入门](getting-started.md) | 依赖、环境变量、REST / MCP / CLI 首次调用、星历数据 |
| 用 Codex 直接体验 | [Codex 使用指南](codex-guide.md) | doctor、注册、新聊天加载、虚构体验和错误恢复 |
| 集成应用或 Agent | [接入指南](agent-guide.md) | 发现能力、消费结果、错误恢复、Python / JS 与 host 配置 |
| 查路由、参数和三端差异 | [API 参考](api-reference.md) | 全部接口、公共选项、请求族与响应字段 |
| 保存完整 JSON 或全部时间线 | [完整结果交付](agent-guide.md#完整结果交付与同次导出) | 首次保留完整范围、同次分页、本地保存与 SHA-256 |
| 确认实现范围与精度 | [算法覆盖矩阵](algorithm-coverage.md) | 工具覆盖、依赖、近似路径、快照和未覆盖范围 |
| 按用户问题选择工具 | [场景路由](scenario-routing.md) · [Onda 技能](../skills/README.md) | 主证 / 旁证 / 深调、资料采集与解读 |
| 理解或修改实现 | [架构说明](architecture.md) · [开发指南](development-guide.md) | 调用链、模块职责、扩展步骤与验证 |
| 贡献或报告问题 | [贡献指南](../CONTRIBUTING.md) · [安全策略](../SECURITY.md) | 协作流程、问题材料与安全报告 |
| 升级已有集成 | [迁移指南](migration.md) · [变更记录](../CHANGELOG.md) | 已删除入口、字段变化和替换步骤 |
| 排查调用故障 | [故障排除](troubleshooting.md) | 按错误层检查安装、连接、输入、星历与交付 |

## 风水专题

咨询从 [onda-fengshui](../skills/onda-fengshui/SKILL.md) 进入；工程接入阅读[家居风水](fengshui.md)，历史定运和独立验证阅读[玄空宅盘](fengshui-xuankong.md)。[示例索引](examples/README.md) 按用途列出可运行请求，以及如何区分原始盘、布局、候选和执行状态。

| 本次问题 | 按需选读的技能参考 |
| --- | --- |
| 事实核对、选法、家庭与楼层、候选布局 | [咨询闭环](../skills/onda-fengshui/references/consultation.md) · [场景与候选](../skills/onda-fengshui/references/scene-planning.md) |
| 来源、方位与基础规则 | [规则来源](../skills/onda-fengshui/references/rule-sources.md) |
| 床、桌、灶的形态与元素参考 | [布局规则](../skills/onda-fengshui/references/layout-rules.md) |
| 厨卫、镜、梁管、尖角、材质器形 | [室内关系与材质](../skills/onda-fengshui/references/sourced-interior-rules.md) |
| 玄空历史宅运、山水条件与有限解释 | [宅盘来源](../skills/onda-fengshui/references/xuankong.md) · [有限解释](../skills/onda-fengshui/references/xuankong-interpretation.md) |
| 书桌用途、入口隔挡、材料施用条件 | [工位作者规则](../skills/onda-fengshui/references/workstation-authored.md) |
| 用户明确另选的 BTB 桌面规则 | [桌面作者规则](../skills/onda-fengshui/references/surface-rules.md) |

规则来源、计算一致性与现实预测效力分别说明；动作可执行状态不代表所有方法审查完成。

## 阅读时区分这些范围

- 当前仓库提供后端、CLI 与场景技能；默认 REST 端口为 `8010`，MCP 默认使用 stdio。
- 中央目录与各端公开数量见 [三端能力边界](api-reference.md#24-三端能力边界)；MCP 连接可按 family / scenario 缩小实际范围。
- 并非每个工具都提供双层快照，见 [快照覆盖](algorithm-coverage.md#4-快照协议覆盖)。`result_delivery` 保存的是首轮选项处理后的结果。
- 本地测试、Linux 黄金快照、独立规则比较与真实模型对话是不同验收项，不能互相替代。

## 维护文档

先查 [文档维护与验证](development-guide.md#文档维护与验证) 中的信源与同步表，再运行 `python scripts/check_docs.py` 和相关合同检查。生成区与场景 manifest 由脚本更新；来源资料保留版本和范围。

仓库保留当前指南、规则资料、示例及回归测试。一次性评审对话、运行回执和实现快照放在仓库外；`docs/reviews/` 仅供本地临时使用，不入库，历史过程可查 Git。

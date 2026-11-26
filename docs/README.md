# FateBridge 文档中心

按任务选择入口：第一次运行看快速入门，接入应用看协议指南，核对计算看领域与方法参考，贡献修改看开发与验证。

FateBridge 提供术数、占星与心理测量计算，接入应用提供模型对话、解释与界面。[核心概念](concepts.md)说明各模块如何配合，以及如何区分计算事实、传统解释与现实建议。文档对应当前开发分支；已发布包请查阅对应 Git 标签文档，未发布变更见 [CHANGELOG](../CHANGELOG.md#unreleased)。

## 从这里开始

| 目标 | 阅读顺序 |
| --- | --- |
| 在终端完成第一次计算 | [快速入门](getting-started.md) |
| 接入应用或 AI Agent | [快速入门](getting-started.md) → [Agent 接入指南](agent-guide.md) |
| 贡献代码或文档 | [贡献指南](../CONTRIBUTING.md) → [开发指南](development-guide.md) |

CLI 可直接运行；REST 默认端口为 `8010`；MCP 默认通过 stdio 由客户端启动。各端名称与可用范围见[三端能力边界](api-reference.md#24-三端能力边界)。

## 安装、接入与交付

| 任务 | 指南 |
| --- | --- |
| 安装与首次计算 | [快速入门](getting-started.md) |
| 环境变量、加载顺序与 REST 密钥 | [运行配置](configuration.md) |
| 下载星历与核对实际模型 | [星历数据安装](ephemeris.md) |
| 本地 stdio、远程 HTTP 与停用 | [MCP 部署](mcp-deployment.md) |
| 工具发现、错误恢复与字段投影 | [Agent 接入](agent-guide.md) |
| 读取和保存同次完整结果 | [完整结果交付](agent-guide.md#完整结果交付与同次导出) |
| 按能力选择计算方法 | [工具覆盖](algorithm-coverage.md) · [方法参考](interpretation/README.md) |
| 运行请求示例 | [示例索引](examples/README.md) |
| 升级旧接口或解决故障 | [故障排除](troubleshooting.md) |
| 报告安全问题 | [安全策略](../SECURITY.md) |

## 领域与方法参考

| 主题 | 指南 |
| --- | --- |
| 方法读取与结果解读参考 | [结果解读参考](interpretation/README.md) |
| 紫微斗数 | [紫微斗数参考](ziwei.md) |
| 人类图 | [人类图参考](human-design.md) |
| 宿曜与宿占 | [宿曜参考](sukuyo.md) |
| 占星骰 | [占星骰参考](astrodice.md) |
| 家居风水 | [家居风水参考](fengshui.md) · [现场资料与来源](interpretation/fengshui/consultation.md) |
| 地点与坐标 | [离线城市与行政区坐标](place-catalog.md) |

## 开发与验证

| 需要查什么 | 入口 |
| --- | --- |
| 工具、参数、端点和错误 | [API 参考](api-reference.md) · [按需调用合同](contracts/README.md) |
| 实现覆盖、依赖与近似路径 | [算法覆盖矩阵](algorithm-coverage.md) |
| 模块职责、数据流与依赖边界 | [架构说明](architecture.md) |
| 扩展、测试、CI、打包与发布 | [开发指南](development-guide.md) · [脚本索引](../scripts/README.md) · [测试索引](../tests/README.md) |
| 文档分工、写作与验证命令 | [文档写作与维护](development-guide.md#文档写作) |

文档按入门、操作、参考和解读分工，修改后请按[开发指南](development-guide.md#文档维护与验证)检查链接、示例与生成物。

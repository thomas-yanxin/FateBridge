# FateBridge 文档中心

FateBridge 提供确定性的术数、占星与心理测量结构化计算；接入应用或 AI Agent 负责对话交互、传统解释组织与界面呈现。本页采用 **Diátaxis 四象限结构** 与 **按角色入口** 组织全部维护文档，避免重复维护同一约定。

文档对应当前开发分支（`0.1.1` 开发期）；已发布版本请查阅对应 [Git 标签](https://github.com/thomas-yanxin/FateBridge/tags)，未发布变更见 [CHANGELOG](../CHANGELOG.md#unreleased)。

## 按角色快速进入

| 你的角色或目标 | 推荐阅读路径 |
| --- | --- |
| 首次体验（本地命令行运行） | [快速入门](getting-started.md) → [可运行请求示例](examples/README.md) → [核心概念与结果阅读](concepts.md) |
| 应用与 AI Agent 接入（REST / MCP / CLI） | [开发者 / Agent 接入指南](agent-guide.md) → [API 参考](api-reference.md) → [MCP 部署指南](mcp-deployment.md) → [按需调用合同](contracts/README.md) |
| 贡献者与维护者 | [贡献指南](../CONTRIBUTING.md) → [开发指南](development-guide.md) → [架构说明](architecture.md) → [安全策略](../SECURITY.md) |

## Diátaxis 文档导航

### 1. Tutorials（快速入门）

面向首次上手的端到端最短路径，不要求预先启动服务或理解全部协议细节。

| 文档 | 内容说明 |
| --- | --- |
| [快速入门](getting-started.md) | 5 分钟完成安装、`doctor` 自检、CLI 首次计算、REST 启动及 MCP 入口验证 |
| [可运行请求示例](examples/README.md) | 可直接通过 `--request-file` 或 REST/MCP 运行的最小虚构 JSON 示例 |

### 2. How-to Guides（操作指南）

面向特定工程与运维任务的操作步骤，覆盖协议接入、环境配置、外部星历与问题排查。

| 文档 | 内容说明 |
| --- | --- |
| [开发者 / Agent 接入指南](agent-guide.md) | **发现 → 调用 → 读取 → 恢复**集成闭环、[输出控制与结果读取](agent-guide.md#输出控制与结果读取)、[错误恢复与复现](agent-guide.md#错误恢复与复现) |
| [运行配置](configuration.md) | 全部环境变量分组表、`.env` 加载顺序与 REST API Key 鉴权配置 |
| [MCP 部署指南](mcp-deployment.md) | [本地 stdio 注册](mcp-deployment.md#注册本地-stdio)、[Windows PowerShell](mcp-deployment.md#windows-powershell)、[工具筛选](mcp-deployment.md#工具筛选与运行环境)与 [HTTP 远程部署](mcp-deployment.md#http-与远程部署) |
| [星历数据安装与运行模型](ephemeris.md) | Swiss `.se1`、JPL DE441、DE440/VSOP2013/AA1996/SPK 配置与精度核对 |
| [故障排除](troubleshooting.md) | 按现象定位安装导入、MCP/REST 连通、错误码、字段投影与星历回退问题 |

### 3. Reference（技术参考）

与源码、中央 `ToolSpec` 目录和自动生成契约保持 1:1 同步的权威规格说明。

| 文档 | 内容说明 |
| --- | --- |
| [API 参考](api-reference.md) | 90 个 REST 路由、MCP 两工具面（`discover_tools` / `run_calculation`）、[三端能力边界](api-reference.md#22-三端能力边界)与请求族 |
| [算法与能力覆盖矩阵](algorithm-coverage.md) | 12 个 family / 90 项计算能力清单、实现状态与依赖矩阵 |
| [按需 MCP 调用合同](contracts/README.md) | 由代码生成的离线工具输入 Schema 与 `evidence_views` 索引 |
| [家居风水参考](fengshui.md) | 8 个风水工具速查表、统一响应层、`WMM2025/IGRF-14` 地磁与四层紫白/玄空规则 |
| [紫微斗数参考](ziwei.md) | 命盘、运限与规则库参数及返回结构 |
| [人类图参考](human-design.md) | 太阳 88° 双时刻、门线、通道、类型与权威参考 |
| [宿曜参考](sukuyo.md) | 二十七宿宿占与三九之秘法相性参考 |
| [占星骰参考](astrodice.md) | `interpret_astrology_dice` 行星/星座/宫位参数规范 |
| [离线城市与行政区坐标](place-catalog.md) | 内置静态地名目录覆盖范围与时区解析说明 |
| [开发指南](development-guide.md) | [常用开发命令](development-guide.md#常用开发命令)、[设计与测试约束](development-guide.md#设计与测试约束)、[文档维护与验证](development-guide.md#文档维护与验证)与[发布流程](development-guide.md#构建与发布) |
| [脚本索引](../scripts/README.md) · [测试索引](../tests/README.md) | 仓库维护、校验脚本与按领域分组的测试目录索引 |

### 4. Explanation（原理与方法解读）

解释系统分层设计、结果阅读语义、咨询安全红线以及各传统体系的证据与来源边界。

| 文档 | 内容说明 |
| --- | --- |
| [核心概念与结果阅读](concepts.md) | 计算/解读/对话职责分工、三端同源载体差异、时间口径与分层状态覆盖 |
| [架构说明](architecture.md) | 中央目录、`application/` 共享执行与投影管线、模块依赖边界与合同缓存 |
| [结果解读与方法参考](interpretation/README.md) | 按当前问题与已连接工具按需查阅各体系证据与来源的总目录 |
| 共用约束与时间 | [咨询核心](interpretation/shared/consultation-core.md) · [硬边界](interpretation/shared/safety-boundaries.md) · [共享时间选择](interpretation/shared/timing-selection.md) · [引擎调用参考](interpretation/shared/fatebridge-engine.md) · [传统解释与现实建议](interpretation/shared/interpretation.md) |
| 八字 / 占星 / 宿曜 / 时运证据 | [八字专题](interpretation/shared/bazi-topic-evidence.md) · [紫微专题](interpretation/shared/ziwei-topic-evidence.md) · [西占专题](interpretation/shared/western-topic-evidence.md) · [西占深层](interpretation/shared/western-deep-evidence.md) · [印占](interpretation/shared/vedic-evidence.md) · [宿曜](interpretation/shared/sukuyo-evidence.md) · [时运技法](interpretation/shiyun/techniques.md) |
| 风水规则与现场参考 | [现场咨询闭环](interpretation/fengshui/consultation.md) · [基础规则与来源](interpretation/fengshui/rule-sources.md) · [玄空历史宅盘](interpretation/fengshui/xuankong.md) |
| 盘式 / 数术 / 占式 / 关系示例 | [河洛与参评](interpretation/xingpan/numerology.md) · [果老](interpretation/xingpan/guolao-evidence.md) · [汉堡中点](interpretation/xingpan/hamburg-evidence.md) · [人类图](interpretation/xingpan/human-design.md) · [关系盘](interpretation/xingpan/relationship-reading.md) · [数术示例](interpretation/xingpan/examples.md) · [六爻](interpretation/zhanbu/liuyao-source-target.md) · [奇门](interpretation/zhanbu/qimen-evidence.md) · [六壬与金口](interpretation/zhanbu/ren-evidence.md) · [太乙与三式](interpretation/zhanbu/taiyi-sanshi.md) · [占式示例](interpretation/zhanbu/examples.md) · [关系示例](interpretation/yuanfen/examples.md) |
